"""TenantMiddleware — verifies that the active business account is accessible.

Runs AFTER AuthMiddleware (inner middleware). Assumes request.state already
has user_id, user_role, and active_business_id populated by AuthMiddleware.
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..database import SessionLocal
from ..models import BusinessAccount, UserBusinessAccess


# Paths that don't need a valid business account context ──────────────────────
EXEMPT_PATHS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    # All auth endpoints (also exempt from AuthMiddleware)
    "/api/auth/login",
    "/api/auth/verify-otp",
    "/api/auth/refresh",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/resend-otp",
    # These auth-authenticated endpoints don't need a BA context
    "/api/auth/logout",
    "/api/auth/logout-all",
    "/api/auth/switch-business",
    "/api/users/me",
    "/api/users/me/business-accounts",
    # Multi-BA aggregate endpoints handle their own access verification
    "/api/metrics/aggregate",
    "/api/insights/generate-aggregate",
}

EXEMPT_PREFIXES = (
    "/docs/",
    "/redoc/",
    "/openapi",
    "/api/auth/switch-business/",
    "/api/users/",
    "/api/companies/",
)


def _is_exempt(path: str) -> bool:
    if path in EXEMPT_PATHS:
        return True
    return any(path.startswith(p) for p in EXEMPT_PREFIXES)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Pass OPTIONS (CORS preflight) through without any tenant processing
        if request.method == "OPTIONS":
            return await call_next(request)

        # If AuthMiddleware didn't authenticate (exempt path or no user), pass through
        user_id = getattr(request.state, "user_id", None)
        if user_id is None or _is_exempt(request.url.path):
            return await call_next(request)

        role = getattr(request.state, "user_role", None)
        active_business_id = getattr(request.state, "active_business_id", None)

        # super_admin bypasses BA access checks
        if role == "super_admin":
            return await call_next(request)

        if active_business_id is None:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "No active business account selected. "
                              "Call /api/auth/switch-business first."
                },
            )

        db = SessionLocal()
        try:
            # Verify the BA is active
            ba = db.query(BusinessAccount).filter(
                BusinessAccount.id == active_business_id
            ).first()
            if ba is None or not ba.is_active:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Business account not found or inactive"},
                )

            # Verify user has access to this BA
            access = db.query(UserBusinessAccess).filter(
                UserBusinessAccess.user_id == user_id,
                UserBusinessAccess.business_account_id == active_business_id,
            ).first()
            if access is None:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Access denied to this business account"},
                )

        except Exception as exc:
            db.rollback()
            return JSONResponse(
                status_code=500,
                content={"detail": f"Tenant middleware error: {str(exc)}"},
            )
        finally:
            db.close()

        return await call_next(request)
