"""Users router — /api/users/*

Role hierarchy enforcement:
  - company_admin can manage users within their own company
  - super_admin can manage all users
  - end_user / manager can only view/update their own profile
"""
import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Company, BusinessAccount, UserBusinessAccess, UserSession
from ..schemas import (
    UserCreate, UserUpdate, UserResponse, InactivateRequest,
    BusinessAccountResponse,
)
from ..auth.dependencies import get_current_user, ROLE_ORDER
from ..auth.password_handler import hash_password
from ..services.audit_service import create_audit_log, AuditAction

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _can_manage_user(actor: User, target: User) -> bool:
    """Return True if actor can perform management actions on target."""
    if actor.role == "super_admin":
        return True
    if actor.role == "company_admin" and actor.company_id == target.company_id:
        # company_admin cannot manage users with equal or higher role
        return ROLE_ORDER.get(actor.role, 0) > ROLE_ORDER.get(target.role, 0)
    return False


# ─────────────────────────────────────────────────────────────────────────────
# GET /me
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# PUT /me
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/me", response_model=UserResponse)
def update_my_profile(
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    # Users cannot change their own role or is_active
    db.commit()
    db.refresh(current_user)
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
# GET /me/business-accounts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/me/business-accounts", response_model=List[BusinessAccountResponse])
def get_my_business_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == "super_admin":
        # Super admin can see all BAs across all companies
        return db.query(BusinessAccount).filter(BusinessAccount.is_active == True).all()

    accesses = (
        db.query(UserBusinessAccess)
        .filter(UserBusinessAccess.user_id == current_user.id)
        .all()
    )
    ba_ids = [a.business_account_id for a in accesses]
    return (
        db.query(BusinessAccount)
        .filter(BusinessAccount.id.in_(ba_ids))
        .all()
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /  — list users (company_admin+ only)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("super_admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    query = db.query(User)
    if current_user.role == "company_admin":
        query = query.filter(User.company_id == current_user.company_id)
    return query.all()


# ─────────────────────────────────────────────────────────────────────────────
# POST /  — create user (company_admin+)
# ─────────────────────────────────────────────────────────────────────────────

MIN_PASSWORD_LENGTH = 8


@router.post("/", response_model=UserResponse, status_code=201)
def create_user(
    body: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("super_admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Role hierarchy: cannot create a user with equal or higher role
    if ROLE_ORDER.get(body.role, -1) >= ROLE_ORDER.get(current_user.role, -1):
        raise HTTPException(
            status_code=403,
            detail=f"Cannot create a user with role '{body.role}'",
        )

    allowed_roles = {"end_user", "manager", "company_admin"}
    if current_user.role == "super_admin":
        allowed_roles.add("super_admin")
    if body.role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")

    if len(body.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {MIN_PASSWORD_LENGTH} characters",
        )

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Company assignment — super_admin can target any company via body.company_id
    if current_user.role == "super_admin" and body.company_id:
        target_company = db.query(Company).filter(
            Company.id == body.company_id,
            Company.is_active.is_(True),
        ).first()
        if not target_company:
            raise HTTPException(status_code=404, detail="Company not found or inactive")
        company_id = body.company_id
    else:
        company_id = current_user.company_id

    new_user = User(
        company_id=company_id,
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        is_active=True,
        created_by=current_user.id,
        password_changed_at=datetime.now(timezone.utc),
    )
    db.add(new_user)
    db.flush()

    # Assign business account access — only BAs that belong to the target company
    for ba_id in (body.business_account_ids or []):
        ba = db.query(BusinessAccount).filter(
            BusinessAccount.id == ba_id,
            BusinessAccount.company_id == company_id,
        ).first()
        if ba is None:
            continue  # silently skip BAs from wrong company or missing BAs
        can_switch = body.role in ("company_admin", "manager")
        db.add(UserBusinessAccess(
            user_id=new_user.id,
            business_account_id=ba_id,
            can_switch=can_switch,
        ))

    db.commit()
    db.refresh(new_user)

    create_audit_log(
        db,
        action=AuditAction.USER_CREATED,
        actor_user_id=current_user.id,
        target_user_id=new_user.id,
        target_company_id=company_id,
        ip_address=_get_client_ip(request),
    )
    return new_user


# ─────────────────────────────────────────────────────────────────────────────
# GET /{id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not _can_manage_user(current_user, target) and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return target


# ─────────────────────────────────────────────────────────────────────────────
# PUT /{id}
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not _can_manage_user(current_user, target):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if body.full_name is not None:
        target.full_name = body.full_name

    if body.role is not None:
        if ROLE_ORDER.get(body.role, -1) >= ROLE_ORDER.get(current_user.role, -1):
            raise HTTPException(status_code=403, detail="Cannot assign this role")
        old_role = target.role
        target.role = body.role
        create_audit_log(
            db, action=AuditAction.ROLE_CHANGED,
            actor_user_id=current_user.id,
            target_user_id=target.id,
            ip_address=_get_client_ip(request),
            extra={"old_role": old_role, "new_role": body.role},
        )

    db.commit()
    db.refresh(target)
    return target


# ─────────────────────────────────────────────────────────────────────────────
# POST /{id}/inactivate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/inactivate")
def inactivate_user(
    user_id: int,
    body: InactivateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not _can_manage_user(current_user, target):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if target.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot inactivate yourself")

    target.is_active = False
    target.inactive_reason = body.reason
    target.inactive_at = datetime.now(timezone.utc)

    # Revoke all sessions
    db.query(UserSession).filter(
        UserSession.user_id == target.id,
        UserSession.is_revoked == False,
    ).update({"is_revoked": True})
    db.commit()

    create_audit_log(
        db, action=AuditAction.USER_INACTIVATED,
        actor_user_id=current_user.id,
        target_user_id=target.id,
        ip_address=_get_client_ip(request),
        extra={"reason": body.reason},
    )
    return {"message": f"User {target.email} inactivated"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /{id}/reactivate  (super_admin only)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/reactivate")
def reactivate_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    target.is_active = True
    target.inactive_reason = None
    target.inactive_at = None
    db.commit()

    create_audit_log(
        db, action=AuditAction.USER_REACTIVATED,
        actor_user_id=current_user.id,
        target_user_id=target.id,
        ip_address=_get_client_ip(request),
    )
    return {"message": f"User {target.email} reactivated"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /{id}/assign-business
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{user_id}/assign-business")
def assign_business(
    user_id: int,
    business_account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("super_admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    ba = db.query(BusinessAccount).filter(BusinessAccount.id == business_account_id).first()
    if ba is None:
        raise HTTPException(status_code=404, detail="Business account not found")

    existing = db.query(UserBusinessAccess).filter(
        UserBusinessAccess.user_id == user_id,
        UserBusinessAccess.business_account_id == business_account_id,
    ).first()
    if existing:
        return {"message": "Access already granted"}

    can_switch = target.role in ("company_admin", "manager")
    db.add(UserBusinessAccess(
        user_id=user_id,
        business_account_id=business_account_id,
        can_switch=can_switch,
    ))
    db.commit()
    return {"message": "Business account access granted"}
