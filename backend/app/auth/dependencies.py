"""FastAPI dependency functions for auth, tenant, and role enforcement."""
from typing import Optional
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, BusinessAccount, UserBusinessAccess


# ─────────────────────────────────────────────────────────────────────────────
# Core user dependency — reads from request.state set by AuthMiddleware
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Fetch the authenticated User object from DB using request.state.user_id.

    AuthMiddleware sets request.state.user_id on every authenticated request.
    If missing (shouldn't happen on protected routes), raises 401.
    """
    user_id: Optional[int] = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


def get_active_business_id(request: Request) -> int:
    """Return the active_business_id from request.state (set by AuthMiddleware)."""
    bid: Optional[int] = getattr(request.state, "active_business_id", None)
    if bid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active business account. Call /api/auth/switch-business first.",
        )
    return bid


# ─────────────────────────────────────────────────────────────────────────────
# Role enforcement
# ─────────────────────────────────────────────────────────────────────────────

ROLE_ORDER = {
    "end_user": 0,
    "manager": 1,
    "company_admin": 2,
    "super_admin": 3,
}


def require_roles(*roles: str):
    """Return a Depends()-compatible checker that enforces allowed roles.

    Usage:
        @router.post("/admin-only")
        def admin_only(user: User = Depends(require_roles("super_admin"))):
            ...
    """
    def checker(request: Request, db: Session = Depends(get_db)) -> User:
        user = get_current_user(request, db)
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(roles)}",
            )
        return user
    return Depends(checker)


def require_min_role(min_role: str):
    """Return a checker that enforces a minimum role level (inclusive)."""
    min_level = ROLE_ORDER.get(min_role, 99)

    def checker(request: Request, db: Session = Depends(get_db)) -> User:
        user = get_current_user(request, db)
        if ROLE_ORDER.get(user.role, -1) < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires at least role: {min_role}",
            )
        return user
    return Depends(checker)
