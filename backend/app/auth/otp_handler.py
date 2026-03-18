"""OTP generation, hashing, and verification."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from ..models import OTPCode


# ─────────────────────────────────────────────────────────────────────────────
# Core helpers
# ─────────────────────────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """Return a cryptographically random numeric OTP string."""
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def _hash_otp(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def verify_otp(code: str, hashed: str) -> bool:
    return _hash_otp(code) == hashed


# ─────────────────────────────────────────────────────────────────────────────
# DB operations
# ─────────────────────────────────────────────────────────────────────────────

OTP_TTL_MINUTES = 5
RESET_OTP_TTL_MINUTES = 15
OTP_MAX_ATTEMPTS = 3
OTP_RESEND_COOLDOWN_SECONDS = 60


def create_otp(db: Session, user_id: int, purpose: str) -> str:
    """Create and persist a new OTP; returns the plaintext code."""
    # Invalidate any previous unused OTP for the same purpose
    db.query(OTPCode).filter(
        OTPCode.user_id == user_id,
        OTPCode.purpose == purpose,
        OTPCode.is_used == False,
    ).delete(synchronize_session=False)

    code = generate_otp()
    ttl = RESET_OTP_TTL_MINUTES if purpose == "password_reset" else OTP_TTL_MINUTES
    now = datetime.now(timezone.utc)

    otp = OTPCode(
        user_id=user_id,
        code_hash=_hash_otp(code),
        purpose=purpose,
        attempts=0,
        is_used=False,
        resend_after=now + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS),
        expires_at=now + timedelta(minutes=ttl),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return code


def get_latest_otp(
    db: Session, user_id: int, purpose: str
) -> Optional[OTPCode]:
    """Fetch the most recent unused, unexpired OTP row."""
    now = datetime.now(timezone.utc)
    return (
        db.query(OTPCode)
        .filter(
            OTPCode.user_id == user_id,
            OTPCode.purpose == purpose,
            OTPCode.is_used == False,
            OTPCode.expires_at > now,
        )
        .order_by(OTPCode.created_at.desc())
        .first()
    )


def consume_otp(db: Session, otp_row: OTPCode, code: str) -> bool:
    """Verify the code, increment attempts, mark used if correct.

    Returns True on success, False if wrong / too many attempts.
    Raises ValueError on expired or already-used codes.
    """
    now = datetime.now(timezone.utc)

    expires_at = otp_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        raise ValueError("otp_expired")
    if otp_row.is_used:
        raise ValueError("otp_already_used")
    if otp_row.attempts >= OTP_MAX_ATTEMPTS:
        raise ValueError("otp_max_attempts")

    otp_row.attempts += 1

    if not verify_otp(code, otp_row.code_hash):
        db.commit()
        return False

    otp_row.is_used = True
    db.commit()
    return True


def check_resend_cooldown(db: Session, user_id: int, purpose: str) -> Optional[int]:
    """Return seconds remaining on cooldown, or None if resend is allowed."""
    from sqlalchemy import desc
    row = (
        db.query(OTPCode)
        .filter(OTPCode.user_id == user_id, OTPCode.purpose == purpose)
        .order_by(desc(OTPCode.created_at))
        .first()
    )
    if row is None:
        return None

    resend_after = row.resend_after
    if resend_after is None:
        return None

    now = datetime.now(timezone.utc)
    if resend_after.tzinfo is None:
        resend_after = resend_after.replace(tzinfo=timezone.utc)

    if resend_after > now:
        return int((resend_after - now).total_seconds())
    return None
