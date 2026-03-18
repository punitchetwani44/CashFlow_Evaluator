"""AuthMiddleware — validates JWT and injects auth state into every request.

Exempt paths bypass JWT validation entirely (login, OTP, docs, health).
All other paths require a valid, non-revoked access token.
"""
from datetime import datetime, timezone
from typing import Optional, Set

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..database import SessionLocal
from ..models import User, Company, UserSession


# Paths that never require a JWT ─────────────────────────────────────────────
EXEMPT_PATHS: Set[str] = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/auth/login",
    "/api/auth/verify-otp",
    "/api/auth/refresh",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/resend-otp",
}

EXEMPT_PREFIXES = ("/docs/", "/redoc/", "/openapi")


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pass OPTIONS (CORS preflight) through without any auth processing
        if request.method == "OPTIONS":
            return await call_next(request)

        # Always attach defaults so downstream code never gets AttributeError
        request.state.user_id = None
        request.state.user_role = None
        request.state.company_id = None
        request.state.active_business_id = None
        request.state.session_id = None
        request.state.is_shadow = False
        request.state.shadow_actor_id = None

        if _is_exempt(request.url.path):
            return await call_next(request)

        # ── Extract token ─────────────────────────────────────────────────────
        auth_header: Optional[str] = request.headers.get("Authorization")
        token: Optional[str] = None

        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            # Also accept from cookie (for browser clients)
            token = request.cookies.get("access_token")

        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        # ── Decode JWT ────────────────────────────────────────────────────────
        from ..auth.jwt_handler import decode_token
        payload = decode_token(token)
        if payload is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        # Must be a full access token, not an OTP session token
        if payload.get("purpose") == "awaiting_otp":
            return JSONResponse(
                status_code=401,
                content={"detail": "OTP not yet verified"},
            )

        user_id = int(payload["sub"])
        jti: str = payload.get("jti", "")

        db = SessionLocal()
        try:
            # ── Validate session row ──────────────────────────────────────────
            now = datetime.now(timezone.utc)

            session = (
                db.query(UserSession)
                .filter(
                    UserSession.user_id == user_id,
                    UserSession.access_jti == jti,
                    UserSession.is_revoked == False,
                )
                .first()
            )
            if session is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Session not found or revoked"},
                )

            # Inactivity timeout: 30 minutes
            last_used = session.last_used_at
            if last_used.tzinfo is None:
                last_used = last_used.replace(tzinfo=timezone.utc)
            if (now - last_used).total_seconds() > 30 * 60:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Session expired due to inactivity"},
                )

            # ── Validate user ─────────────────────────────────────────────────
            user = db.query(User).filter(User.id == user_id).first()
            if user is None or not user.is_active:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "User account inactive"},
                )

            # ── Validate company ──────────────────────────────────────────────
            company = db.query(Company).filter(Company.id == user.company_id).first()
            if company is None or not company.is_active:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Company account inactive"},
                )

            # ── Touch session last_used_at ─────────────────────────────────────
            session.last_used_at = now
            db.commit()

            # ── Inject into request.state ─────────────────────────────────────
            request.state.user_id = user_id
            request.state.user_role = payload.get("role", user.role)
            request.state.company_id = user.company_id
            request.state.active_business_id = payload.get("active_business_id") or \
                session.active_business_account_id
            request.state.session_id = session.id
            request.state.is_shadow = payload.get("is_shadow", False)
            request.state.shadow_actor_id = payload.get("shadow_actor_id")

        except Exception as exc:
            db.rollback()
            return JSONResponse(
                status_code=500,
                content={"detail": f"Auth middleware error: {str(exc)}"},
            )
        finally:
            db.close()

        return await call_next(request)
