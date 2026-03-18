import secrets
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Existing ──────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    database_url: str = "sqlite:///./cashflow.db"
    classification_confidence_threshold: float = 0.7

    # ── JWT ───────────────────────────────────────────────────────────────
    jwt_secret: str = secrets.token_hex(32)   # overridden by env var in production
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── CORS / Frontend ───────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"   # comma-separated list
    frontend_url: str = "http://localhost:3000"

    # ── Email / OTP ───────────────────────────────────────────────────────
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "CashFlow Evaluator <noreply@example.com>"
    otp_dev_mode: bool = True   # True → print OTP to console instead of sending email

    # ── Bootstrap Super Admin (used on first startup only) ────────────────
    super_admin_email: str = "admin@cashflow.local"
    super_admin_password: str = "Admin@123456"    # change in production via .env

    # ── Default Company / Business Account ────────────────────────────────
    default_company_name: str = "Default Company"
    default_business_account_name: str = "Default Account"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]


settings = Settings()
