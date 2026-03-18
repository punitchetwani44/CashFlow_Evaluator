"""Immutable audit log writer.

Never UPDATE or DELETE rows in audit_logs.
"""
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import AuditLog


def create_audit_log(
    db: Session,
    *,
    action: str,
    actor_user_id: Optional[int] = None,
    impersonated_by: Optional[int] = None,
    target_user_id: Optional[int] = None,
    target_company_id: Optional[int] = None,
    target_business_account_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> AuditLog:
    """Append an immutable audit record and return it."""
    log = AuditLog(
        actor_user_id=actor_user_id,
        impersonated_by=impersonated_by,
        action=action,
        target_user_id=target_user_id,
        target_company_id=target_company_id,
        target_business_account_id=target_business_account_id,
        ip_address=ip_address,
        user_agent=user_agent,
        extra_data=json.dumps(extra) if extra else None,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


# ── Known action constants ───────────────────────────────────────────────────
class AuditAction:
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    OTP_SENT = "otp_sent"
    OTP_VERIFIED = "otp_verified"
    OTP_FAILED = "otp_failed"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET_DONE = "password_reset_done"
    ROLE_CHANGED = "role_changed"
    USER_CREATED = "user_created"
    USER_INACTIVATED = "user_inactivated"
    USER_REACTIVATED = "user_reactivated"
    COMPANY_INACTIVATED = "company_inactivated"
    COMPANY_REACTIVATED = "company_reactivated"
    BUSINESS_SWITCH = "business_switch"
    SHADOW_LOGIN_START = "shadow_login_start"
    SHADOW_LOGIN_END = "shadow_login_end"
    BA_CREATED = "ba_created"
    BA_INACTIVATED = "ba_inactivated"
    PASSWORD_CHANGED = "password_changed"
    # Dashboard multi-BA / date-range actions
    MULTI_BA_VIEW               = "multi_ba_view"
    DATE_RANGE_CHANGED          = "date_range_changed"
    BUSINESS_SELECTION_CHANGED  = "business_selection_changed"
