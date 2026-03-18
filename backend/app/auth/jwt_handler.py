"""JWT creation and decoding utilities."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt

from ..config import settings

# ─────────────────────────────────────────────────────────────────────────────
# Token factories
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: int,
    role: str,
    company_id: int,
    active_business_id: Optional[int] = None,
    is_shadow: bool = False,
    shadow_actor_id: Optional[int] = None,
) -> tuple[str, str]:
    """Return (access_token, jti)."""
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "role": role,
        "company_id": company_id,
        "active_business_id": active_business_id,
        "is_shadow": is_shadow,
        "shadow_actor_id": shadow_actor_id,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, jti


def create_otp_session_token(user_id: int, email: str) -> str:
    """Short-lived (10 min) token issued after password check, before OTP verification."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=10)
    payload = {
        "sub": str(user_id),
        "email": email,
        "purpose": "awaiting_otp",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ─────────────────────────────────────────────────────────────────────────────
# Decoding
# ─────────────────────────────────────────────────────────────────────────────

def decode_token(token: str) -> Optional[dict[str, Any]]:
    """Decode and validate a JWT. Returns None on any error."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None
