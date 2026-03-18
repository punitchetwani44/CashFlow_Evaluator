"""Auth router — all /api/auth/* endpoints.

Login flow:
  1. POST /login        → verify password → send OTP → return otp_session_token
  2. POST /verify-otp   → verify OTP     → issue access + refresh tokens

Other:
  POST /resend-otp
  POST /refresh
  POST /logout
  POST /logout-all
  POST /forgot-password
  POST /reset-password
  POST /switch-business/{id}
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db, SessionLocal
from ..models import User, UserSession, UserBusinessAccess, BusinessAccount
from ..schemas import (
    LoginRequest, VerifyOTPRequest, ResendOTPRequest, RefreshRequest,
    ForgotPasswordRequest, ResetPasswordRequest,
    TokenResponse, OTPSessionResponse, UserResponse,
)
from ..auth.jwt_handler import (
    create_access_token, create_otp_session_token, decode_token,
)
from ..auth.password_handler import verify_password, hash_password, needs_rehash
from ..auth.otp_handler import (
    create_otp, consume_otp, get_latest_otp, check_resend_cooldown,
)
from ..auth.dependencies import get_current_user, get_active_business_id
from ..services.email_service import send_otp_email
from ..services.audit_service import create_audit_log, AuditAction
from ..config import settings

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_TTL_DAYS = settings.refresh_token_expire_days

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _create_session(
    db: Session,
    user: User,
    jti: str,
    active_business_id: Optional[int],
    ip: str,
    user_agent: str,
) -> str:
    """Create a DB session row and return the raw refresh token."""
    raw_refresh = secrets.token_hex(32)
    refresh_hash = _hash_refresh(raw_refresh)
    now = datetime.now(timezone.utc)

    session = UserSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        access_jti=jti,
        active_business_account_id=active_business_id,
        ip_address=ip,
        user_agent=user_agent,
        is_revoked=False,
        last_used_at=now,
        expires_at=now + timedelta(days=REFRESH_TTL_DAYS),
    )
    db.add(session)
    db.commit()
    return raw_refresh


def _pick_default_business(db: Session, user: User) -> Optional[int]:
    """Auto-select BA if user has exactly one accessible BA."""
    accesses = db.query(UserBusinessAccess).filter(
        UserBusinessAccess.user_id == user.id
    ).all()
    if len(accesses) == 1:
        return accesses[0].business_account_id
    return None


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh,
        httponly=True,
        secure=False,          # set True in production (HTTPS)
        samesite="lax",
        max_age=REFRESH_TTL_DAYS * 86400,
        path="/api/auth",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: POST /login
# ─────────────────────────────────────────────────────────────────────────────

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


@router.post("/login", response_model=OTPSessionResponse)
async def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")

    user = db.query(User).filter(User.email == body.email).first()

    # Always audit failure, even for unknown email (don't reveal existence)
    if user is None:
        create_audit_log(db, action=AuditAction.LOGIN_FAILURE,
                         ip_address=ip, user_agent=ua,
                         extra={"email": body.email, "reason": "user_not_found"})
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Account lock check
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            remaining = int((locked_until - datetime.now(timezone.utc)).total_seconds() // 60)
            raise HTTPException(
                status_code=429,
                detail=f"Account locked. Try again in {remaining} minute(s).",
            )
        else:
            # Lock expired — reset
            user.failed_login_attempts = 0
            user.locked_until = None
            db.commit()

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")

    # Verify password
    if not verify_password(body.password, user.hashed_password):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
            db.commit()
            create_audit_log(db, action=AuditAction.LOGIN_FAILURE,
                             actor_user_id=user.id, ip_address=ip, user_agent=ua,
                             extra={"reason": "account_locked"})
            raise HTTPException(status_code=429, detail="Account locked after too many failed attempts.")
        db.commit()
        create_audit_log(db, action=AuditAction.LOGIN_FAILURE,
                         actor_user_id=user.id, ip_address=ip, user_agent=ua,
                         extra={"reason": "wrong_password",
                                "attempts": user.failed_login_attempts})
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Rehash if needed (transparent upgrade)
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(body.password)
        db.commit()

    # Reset failed attempts on success
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()

    # Generate and send OTP
    otp_code = create_otp(db, user.id, "login_2fa")
    await send_otp_email(user.email, otp_code, "login_2fa")
    create_audit_log(db, action=AuditAction.OTP_SENT,
                     actor_user_id=user.id, ip_address=ip, user_agent=ua)

    otp_session_token = create_otp_session_token(user.id, user.email)
    return OTPSessionResponse(
        otp_session_token=otp_session_token,
        message="OTP sent to your email. It expires in 5 minutes.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: POST /verify-otp
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/verify-otp")
async def verify_otp_endpoint(
    body: VerifyOTPRequest, request: Request,
    db: Session = Depends(get_db),
):
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")

    payload = decode_token(body.otp_session_token)
    if not payload or payload.get("purpose") != "awaiting_otp":
        raise HTTPException(status_code=401, detail="Invalid or expired OTP session token")

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    otp_row = get_latest_otp(db, user_id, "login_2fa")
    if otp_row is None:
        raise HTTPException(status_code=400, detail="No active OTP found. Please log in again.")

    try:
        success = consume_otp(db, otp_row, body.otp_code)
    except ValueError as e:
        reason = str(e)
        create_audit_log(db, action=AuditAction.OTP_FAILED,
                         actor_user_id=user_id, ip_address=ip, user_agent=ua,
                         extra={"reason": reason})
        raise HTTPException(status_code=400, detail=f"OTP error: {reason}")

    if not success:
        create_audit_log(db, action=AuditAction.OTP_FAILED,
                         actor_user_id=user_id, ip_address=ip, user_agent=ua,
                         extra={"reason": "wrong_code"})
        remaining = max(0, 3 - otp_row.attempts)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid OTP. {remaining} attempt(s) remaining.",
        )

    # OTP verified ✓ — issue tokens
    active_bid = _pick_default_business(db, user)
    access_token, jti = create_access_token(
        user_id=user.id,
        role=user.role,
        company_id=user.company_id,
        active_business_id=active_bid,
    )
    raw_refresh = _create_session(db, user, jti, active_bid, ip, ua)

    create_audit_log(db, action=AuditAction.LOGIN_SUCCESS,
                     actor_user_id=user.id, ip_address=ip, user_agent=ua,
                     extra={"active_business_id": active_bid})
    create_audit_log(db, action=AuditAction.OTP_VERIFIED,
                     actor_user_id=user.id, ip_address=ip, user_agent=ua)

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "company_id": user.company_id,
            "created_at": user.created_at.isoformat(),
        },
        "active_business_id": active_bid,
    })
    _set_refresh_cookie(response, raw_refresh)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# POST /resend-otp
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/resend-otp", response_model=OTPSessionResponse)
async def resend_otp(
    body: ResendOTPRequest, request: Request,
    db: Session = Depends(get_db),
):
    payload = decode_token(body.otp_session_token)
    if not payload or payload.get("purpose") != "awaiting_otp":
        raise HTTPException(status_code=401, detail="Invalid OTP session token")

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    cooldown = check_resend_cooldown(db, user_id, "login_2fa")
    if cooldown is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {cooldown} second(s) before resending OTP.",
        )

    otp_code = create_otp(db, user_id, "login_2fa")
    await send_otp_email(user.email, otp_code, "login_2fa")
    create_audit_log(db, action=AuditAction.OTP_SENT,
                     actor_user_id=user_id,
                     ip_address=_get_client_ip(request),
                     extra={"type": "resend"})

    new_session_token = create_otp_session_token(user_id, user.email)
    return OTPSessionResponse(
        otp_session_token=new_session_token,
        message="New OTP sent.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /refresh
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh_token(request: Request, db: Session = Depends(get_db)):
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")

    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        body = await request.json() if request.headers.get("content-type") else {}
        raw_refresh = body.get("refresh_token") if isinstance(body, dict) else None

    if not raw_refresh:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    refresh_hash = _hash_refresh(raw_refresh)
    now = datetime.now(timezone.utc)

    session = db.query(UserSession).filter(
        UserSession.refresh_token_hash == refresh_hash,
        UserSession.is_revoked == False,
    ).first()
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid or revoked refresh token")

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        session.is_revoked = True
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token expired")

    user = db.query(User).filter(User.id == session.user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Rotate: revoke old session, create new one
    session.is_revoked = True
    db.commit()

    access_token, jti = create_access_token(
        user_id=user.id,
        role=user.role,
        company_id=user.company_id,
        active_business_id=session.active_business_account_id,
    )
    new_raw_refresh = _create_session(
        db, user, jti, session.active_business_account_id, ip, ua
    )

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "active_business_id": session.active_business_account_id,
    })
    _set_refresh_cookie(response, new_raw_refresh)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# POST /logout
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            session.is_revoked = True
            db.commit()

    create_audit_log(db, action=AuditAction.LOGOUT,
                     actor_user_id=current_user.id,
                     ip_address=_get_client_ip(request))

    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/auth")
    return response


# ─────────────────────────────────────────────────────────────────────────────
# POST /logout-all
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/logout-all")
async def logout_all(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_revoked == False,
    ).update({"is_revoked": True})
    db.commit()

    create_audit_log(db, action=AuditAction.LOGOUT_ALL,
                     actor_user_id=current_user.id,
                     ip_address=_get_client_ip(request))

    response = JSONResponse(content={"message": "All sessions revoked"})
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/auth")
    return response


# ─────────────────────────────────────────────────────────────────────────────
# POST /forgot-password
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/forgot-password", response_model=OTPSessionResponse)
async def forgot_password(
    body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == body.email, User.is_active == True).first()
    # Always return success (don't reveal whether email exists)
    if user is None:
        return OTPSessionResponse(
            otp_session_token="",
            message="If that email exists, a reset code has been sent.",
        )

    cooldown = check_resend_cooldown(db, user.id, "password_reset")
    if cooldown is not None:
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {cooldown} second(s) before requesting another reset.",
        )

    otp_code = create_otp(db, user.id, "password_reset")
    await send_otp_email(user.email, otp_code, "password_reset")
    create_audit_log(db, action=AuditAction.PASSWORD_RESET_REQUESTED,
                     actor_user_id=user.id,
                     ip_address=_get_client_ip(request))

    otp_session_token = create_otp_session_token(user.id, user.email)
    return OTPSessionResponse(
        otp_session_token=otp_session_token,
        message="If that email exists, a reset code has been sent.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /reset-password
# ─────────────────────────────────────────────────────────────────────────────

MIN_PASSWORD_LENGTH = 8


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db),
):
    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )

    payload = decode_token(body.otp_session_token)
    if not payload or payload.get("purpose") != "awaiting_otp":
        raise HTTPException(status_code=401, detail="Invalid or expired reset token")

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    otp_row = get_latest_otp(db, user_id, "password_reset")
    if otp_row is None:
        raise HTTPException(status_code=400, detail="No active reset OTP. Request a new one.")

    try:
        success = consume_otp(db, otp_row, body.otp_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"OTP error: {str(e)}")

    if not success:
        raise HTTPException(status_code=400, detail="Invalid OTP code")

    # Update password + revoke all sessions
    user.hashed_password = hash_password(body.new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    db.query(UserSession).filter(UserSession.user_id == user_id).update(
        {"is_revoked": True}
    )
    db.commit()

    create_audit_log(db, action=AuditAction.PASSWORD_RESET_DONE,
                     actor_user_id=user_id,
                     ip_address=_get_client_ip(request))

    return {"message": "Password reset successfully. Please log in with your new password."}


# ─────────────────────────────────────────────────────────────────────────────
# POST /switch-business/{business_account_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/switch-business/{business_account_id}")
async def switch_business(
    business_account_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip = _get_client_ip(request)

    # Only company_admin and manager can switch (super_admin can always)
    if current_user.role not in ("super_admin", "company_admin", "manager"):
        raise HTTPException(status_code=403, detail="Business switching not allowed for your role")

    # Verify BA exists and is active
    ba = db.query(BusinessAccount).filter(
        BusinessAccount.id == business_account_id,
        BusinessAccount.is_active == True,
    ).first()
    if ba is None:
        raise HTTPException(status_code=404, detail="Business account not found or inactive")

    # Verify access (super_admin bypasses)
    if current_user.role != "super_admin":
        access = db.query(UserBusinessAccess).filter(
            UserBusinessAccess.user_id == current_user.id,
            UserBusinessAccess.business_account_id == business_account_id,
        ).first()
        if access is None:
            raise HTTPException(status_code=403, detail="No access to this business account")

    # Revoke current session and create new one with updated BA
    session_id = getattr(request.state, "session_id", None)
    if session_id:
        old_session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if old_session:
            old_session.is_revoked = True
            db.commit()

    access_token, jti = create_access_token(
        user_id=current_user.id,
        role=current_user.role,
        company_id=current_user.company_id,
        active_business_id=business_account_id,
    )
    raw_refresh = _create_session(
        db, current_user, jti, business_account_id, ip,
        request.headers.get("User-Agent", ""),
    )

    create_audit_log(db, action=AuditAction.BUSINESS_SWITCH,
                     actor_user_id=current_user.id,
                     target_business_account_id=business_account_id,
                     ip_address=ip)

    response = JSONResponse(content={
        "access_token": access_token,
        "token_type": "bearer",
        "active_business_id": business_account_id,
        "business_name": ba.name,
    })
    _set_refresh_cookie(response, raw_refresh)
    return response
