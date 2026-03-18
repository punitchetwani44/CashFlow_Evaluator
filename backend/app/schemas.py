from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class UploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    status: str
    error_message: Optional[str]
    row_count: int
    mapped_count: int
    unmapped_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: int
    upload_id: int
    date: str
    description: str
    amount: float
    type: Optional[str]
    head: Optional[str]
    month: Optional[str]
    comments: Optional[str]
    status: str
    is_user_modified: bool
    classification_confidence: Optional[float]
    raw_debit: Optional[float]
    raw_credit: Optional[float]
    raw_balance: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionUpdate(BaseModel):
    head: Optional[str] = None
    type: Optional[str] = None
    comments: Optional[str] = None
    create_rule: bool = True  # if False, skip saving a classification rule


class BulkUpdateRequest(BaseModel):
    ids: List[int]
    head: str
    type: Optional[str] = None
    comments: Optional[str] = None
    create_rule: bool = True  # if False, skip saving a classification rule


class MonthlyMetricResponse(BaseModel):
    id: int
    month: str
    total_inflow: float
    total_outflow: float
    net_cashflow: float
    indicator_cashflow: float
    capital_infused: float
    capital_withdrawn: float
    fixed_cost_ratio: float
    payroll_ratio: float
    cash_runway: Optional[float]
    vendor_dependency: Optional[float]
    transaction_count: int
    mapped_count: int
    category_breakdown: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class AIInsightItem(BaseModel):
    insight: str
    category: str  # warning | positive | alert | info
    metric: str


class AIInsightResponse(BaseModel):
    id: int
    month: str
    insights: str  # JSON string
    generated_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Classification Rule schemas
# ---------------------------------------------------------------------------

class RuleCreate(BaseModel):
    key_phrase: str
    head: str
    type: str  # inflow | outflow
    rule_type: str = "user_learned"  # user_learned | vendor_exact | regex_keyword
    pattern: Optional[str] = None
    normalized_vendor: Optional[str] = None
    is_enabled: bool = True
    confidence: float = 0.95
    scope: str = "user"  # user | system


class RuleUpdate(BaseModel):
    key_phrase: Optional[str] = None
    head: Optional[str] = None
    type: Optional[str] = None
    rule_type: Optional[str] = None
    pattern: Optional[str] = None
    normalized_vendor: Optional[str] = None
    is_enabled: Optional[bool] = None
    confidence: Optional[float] = None
    scope: Optional[str] = None


class RuleResponse(BaseModel):
    id: int
    key_phrase: str
    head: str
    type: str
    rule_type: str
    pattern: Optional[str]
    normalized_vendor: Optional[str]
    is_enabled: bool
    confidence: float
    use_count: int
    confirmation_count: int
    scope: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RulesStatsResponse(BaseModel):
    total: int
    active: int
    user_learned: int
    vendor_exact: int
    regex_keyword: int
    system_rules: int


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyOTPRequest(BaseModel):
    otp_session_token: str
    otp_code: str


class ResendOTPRequest(BaseModel):
    otp_session_token: str


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None   # also accepted from HttpOnly cookie


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    otp_session_token: str   # the password-reset OTP session token
    otp_code: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class SwitchBusinessRequest(BaseModel):
    business_account_id: int


# ── Response models ──────────────────────────────────────────────────────────

class BusinessAccountBrief(BaseModel):
    id: int
    name: str
    is_active: bool

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    company_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    active_business_id: Optional[int]


class OTPSessionResponse(BaseModel):
    otp_session_token: str
    message: str


# ---------------------------------------------------------------------------
# User management schemas (Phase 5)
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str  # company_admin | manager | end_user
    company_id: Optional[int] = None          # super_admin only — target company
    business_account_ids: Optional[List[int]] = []


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class InactivateRequest(BaseModel):
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Company schemas (Phase 5)
# ---------------------------------------------------------------------------

class CompanyCreate(BaseModel):
    name: str
    plan: str = "starter"
    max_business_accounts: int = 3


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    max_business_accounts: Optional[int] = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    slug: str
    plan: str
    max_business_accounts: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class BusinessAccountCreate(BaseModel):
    name: str
    description: Optional[str] = None


class BusinessAccountUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class BusinessAccountResponse(BaseModel):
    id: int
    company_id: int
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Aggregate metrics schemas (multi-business + date-range dashboard)
# ---------------------------------------------------------------------------

class MonthlyBreakdown(BaseModel):
    month: str
    total_inflow: float
    total_outflow: float
    net_cashflow: float
    indicator_cashflow: float
    transaction_count: int
    sma_3: Optional[float] = None  # 3-month simple moving average of outflow (null for first 2 months)


class AggregatedMetricsResponse(BaseModel):
    # Period metadata
    period_label: str           # e.g. "2024-01 – 2024-12" or "2024-03"
    date_from: str
    date_to: str
    business_names: List[str]
    is_multi_month: bool
    # Aggregated totals
    total_inflow: float
    total_outflow: float
    net_cashflow: float
    indicator_cashflow: float
    fixed_cost_ratio: float
    payroll_ratio: float
    cash_runway: Optional[float]
    vendor_dependency: Optional[float]
    transaction_count: int
    mapped_count: int
    category_breakdown: Optional[str]   # JSON string — same format as MonthlyMetric
    # Monthly breakdown for trend charts
    monthly_breakdown: List[MonthlyBreakdown]
    # Auto-computed previous same-length period
    prev_period_label: Optional[str]
    prev_total_inflow: Optional[float]
    prev_total_outflow: Optional[float]
    prev_net_cashflow: Optional[float]


class AggregateInsightsRequest(BaseModel):
    business_ids: List[int]
    date_from: str   # YYYY-MM
    date_to: str     # YYYY-MM


class AggregateInsightsResponse(BaseModel):
    period_label: str
    business_names: List[str]
    insights: str    # JSON array — same format as AIInsightResponse.insights
    generated_at: datetime
