"""CSRF double-submit cookie protection using itsdangerous HMAC."""
import secrets
from typing import Optional

from itsdangerous import BadSignature, TimestampSigner

from ..config import settings

_signer = TimestampSigner(settings.jwt_secret, salt="csrf")

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_MAX_AGE_SECONDS = 3600  # 1 hour


def generate_csrf_token() -> str:
    """Return a signed, time-stamped CSRF token."""
    raw = secrets.token_hex(16)
    return _signer.sign(raw).decode()


def validate_csrf_token(token: str) -> bool:
    """Return True if the token has a valid signature and is not expired."""
    if not token:
        return False
    try:
        _signer.unsign(token, max_age=CSRF_MAX_AGE_SECONDS)
        return True
    except BadSignature:
        return False


# Safe HTTP methods that do NOT require CSRF validation
CSRF_SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}

# Paths exempt from CSRF (login/OTP are already protected by rate-limit + OTP)
CSRF_EXEMPT_PATHS = {
    "/api/auth/login",
    "/api/auth/verify-otp",
    "/api/auth/refresh",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
}
