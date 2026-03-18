from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Auth / RBAC / Multi-Tenant Models
# ─────────────────────────────────────────────────────────────────────────────

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    plan = Column(String(30), default="starter")          # starter | growth | enterprise
    max_business_accounts = Column(Integer, default=3)
    is_active = Column(Boolean, default=True, nullable=False)
    inactive_reason = Column(Text)
    inactive_at = Column(DateTime)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="company", foreign_keys="User.company_id")
    business_accounts = relationship("BusinessAccount", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    role = Column(String(30), nullable=False)             # super_admin|company_admin|manager|end_user
    is_active = Column(Boolean, default=True, nullable=False)
    inactive_reason = Column(Text)
    inactive_at = Column(DateTime)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)
    password_changed_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="users", foreign_keys=[company_id])
    business_accesses = relationship("UserBusinessAccess", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    otp_codes = relationship("OTPCode", back_populates="user")


class BusinessAccount(Base):
    __tablename__ = "business_accounts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company", back_populates="business_accounts")
    user_accesses = relationship("UserBusinessAccess", back_populates="business_account")


class UserBusinessAccess(Base):
    __tablename__ = "user_business_access"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=False, index=True)
    can_switch = Column(Boolean, default=False)   # True for manager/company_admin
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "business_account_id"),)

    user = relationship("User", back_populates="business_accesses")
    business_account = relationship("BusinessAccount", back_populates="user_accesses")


class UserSession(Base):
    """DB-backed session row (replaces Redis)."""
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    refresh_token_hash = Column(String(255), nullable=False, unique=True, index=True)
    access_jti = Column(String(255), index=True)          # jti of the last issued access token
    active_business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=True)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    is_revoked = Column(Boolean, default=False, nullable=False)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    purpose = Column(String(30), nullable=False)          # login_2fa | password_reset
    attempts = Column(Integer, default=0)
    is_used = Column(Boolean, default=False)
    resend_after = Column(DateTime)                       # 60-second cooldown
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="otp_codes")


class AuditLog(Base):
    """Immutable audit trail — never UPDATE or DELETE rows here."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    impersonated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    target_company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    target_business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=True)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    extra_data = Column(Text)                             # JSON blob for extra context
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ShadowSession(Base):
    __tablename__ = "shadow_sessions"

    id = Column(Integer, primary_key=True, index=True)
    super_admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    shadow_token = Column(String(255), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)


# ─────────────────────────────────────────────────────────────────────────────
# Existing cashflow models (business_account_id added for tenant isolation)
# ─────────────────────────────────────────────────────────────────────────────

class Upload(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(10), nullable=False)
    status = Column(String(20), default="pending")       # pending, processing, completed, failed
    error_message = Column(Text)
    row_count = Column(Integer, default=0)
    mapped_count = Column(Integer, default=0)
    unmapped_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transactions = relationship("Transaction", back_populates="upload", cascade="all, delete-orphan")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=True, index=True)
    upload_id = Column(Integer, ForeignKey("uploads.id"), nullable=False)
    date = Column(String(10), nullable=False)            # YYYY-MM-DD
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String(10))                            # inflow | outflow
    head = Column(String(100))
    month = Column(String(7))                            # YYYY-MM
    comments = Column(Text)
    status = Column(String(20), default="unmapped")      # mapped | unmapped
    is_user_modified = Column(Boolean, default=False)
    classification_confidence = Column(Float)
    raw_debit = Column(Float)
    raw_credit = Column(Float)
    raw_balance = Column(Float)
    matched_rule_id = Column(Integer, nullable=True)
    matched_rule_source = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    upload = relationship("Upload", back_populates="transactions")


class MonthlyMetric(Base):
    __tablename__ = "monthly_metrics"

    id = Column(Integer, primary_key=True, index=True)
    business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=True, index=True)
    month = Column(String(7), nullable=False)            # YYYY-MM  (unique per BA now)
    total_inflow = Column(Float, default=0)
    total_outflow = Column(Float, default=0)
    net_cashflow = Column(Float, default=0)
    indicator_cashflow = Column(Float, default=0)
    capital_infused = Column(Float, default=0)
    capital_withdrawn = Column(Float, default=0)
    fixed_cost_ratio = Column(Float, default=0)
    payroll_ratio = Column(Float, default=0)
    cash_runway = Column(Float)
    vendor_dependency = Column(Float)
    transaction_count = Column(Integer, default=0)
    mapped_count = Column(Integer, default=0)
    category_breakdown = Column(Text)                    # JSON string
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=True, index=True)
    month = Column(String(7), nullable=False)            # YYYY-MM  (unique per BA now)
    insights = Column(Text, nullable=False)              # JSON array
    generated_at = Column(DateTime, default=datetime.utcnow)


class ClassificationRule(Base):
    """Learned rules built from user corrections: key_phrase → (head, type)."""
    __tablename__ = "classification_rules"

    id = Column(Integer, primary_key=True, index=True)
    business_account_id = Column(Integer, ForeignKey("business_accounts.id"), nullable=True, index=True)
    key_phrase = Column(String(300), nullable=False, unique=True, index=True)
    head = Column(String(100), nullable=False)
    type = Column(String(10), nullable=False)            # inflow | outflow
    use_count = Column(Integer, default=1)
    # ── Extended rule engine fields ─────────────────────────────────────────
    rule_type = Column(String(20), default="user_learned")
    pattern = Column(Text, nullable=True)
    normalized_vendor = Column(String(200), nullable=True)
    is_enabled = Column(Boolean, default=True)
    confidence = Column(Float, default=0.95)
    confirmation_count = Column(Integer, default=0)
    scope = Column(String(20), default="user")           # user | system
    # ───────────────────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
