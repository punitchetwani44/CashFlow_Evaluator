from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import MonthlyMetric, User, BusinessAccount, UserBusinessAccess
from ..schemas import MonthlyMetricResponse, AggregatedMetricsResponse
from ..services.metrics_calculator import (
    calculate_monthly_metrics, recalculate_all_months, calculate_aggregate_metrics,
)
from ..services.audit_service import create_audit_log, AuditAction
from ..auth.dependencies import get_current_user, get_active_business_id

router = APIRouter()


@router.get("/aggregate", response_model=AggregatedMetricsResponse)
def get_aggregate_metrics(
    business_ids: List[int] = Query(..., description="One or more business account IDs"),
    date_from: str = Query(..., description="Start month YYYY-MM"),
    date_to: str = Query(..., description="End month YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate cashflow metrics across multiple business accounts and a date range."""
    from datetime import datetime

    # ── Date range validation ────────────────────────────────────────────────
    try:
        dfrom = datetime.strptime(date_from, "%Y-%m")
        dto   = datetime.strptime(date_to,   "%Y-%m")
    except ValueError:
        raise HTTPException(400, "date_from and date_to must be YYYY-MM format")

    if dfrom > dto:
        raise HTTPException(400, "date_from must be <= date_to")

    months_diff = (dto.year - dfrom.year) * 12 + (dto.month - dfrom.month)
    if months_diff > 24:
        raise HTTPException(400, "Date range cannot exceed 24 months")

    if not business_ids:
        raise HTTPException(400, "business_ids cannot be empty")

    # ── Access verification (skip for super_admin) ───────────────────────────
    if current_user.role != "super_admin":
        accesses = db.query(UserBusinessAccess).filter(
            UserBusinessAccess.user_id == current_user.id,
            UserBusinessAccess.business_account_id.in_(business_ids),
        ).all()
        accessible_ids = {a.business_account_id for a in accesses}
        denied = set(business_ids) - accessible_ids
        if denied:
            raise HTTPException(403, f"Access denied to business accounts: {sorted(denied)}")

    # ── Cross-company guard ──────────────────────────────────────────────────
    bas = db.query(BusinessAccount).filter(
        BusinessAccount.id.in_(business_ids)
    ).all()
    found_ids = {ba.id for ba in bas}
    missing = set(business_ids) - found_ids
    if missing:
        raise HTTPException(404, f"Business accounts not found: {sorted(missing)}")

    # super_admin may view any company's data; cross-company check only for others
    if current_user.role != "super_admin":
        if any(ba.company_id != current_user.company_id for ba in bas):
            raise HTTPException(403, "Cross-company aggregation is not permitted")

    business_names = [ba.name for ba in bas]

    # ── Audit log ────────────────────────────────────────────────────────────
    if len(business_ids) > 1:
        create_audit_log(
            db,
            action=AuditAction.MULTI_BA_VIEW,
            actor_user_id=current_user.id,
            extra={
                "business_ids": business_ids,
                "date_from": date_from,
                "date_to": date_to,
            },
        )

    # ── Compute ──────────────────────────────────────────────────────────────
    result = calculate_aggregate_metrics(db, business_ids, date_from, date_to)

    is_multi_month = date_from != date_to
    period_label = date_from if date_from == date_to else f"{date_from} – {date_to}"

    return AggregatedMetricsResponse(
        period_label=period_label,
        date_from=date_from,
        date_to=date_to,
        business_names=business_names,
        is_multi_month=is_multi_month,
        **result,
    )


@router.get("", response_model=List[MonthlyMetricResponse])
def get_all_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    return (
        db.query(MonthlyMetric)
        .filter(MonthlyMetric.business_account_id == business_id)
        .order_by(MonthlyMetric.month.asc())
        .all()
    )


@router.get("/{month}", response_model=MonthlyMetricResponse)
def get_month_metrics(
    month: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    metric = db.query(MonthlyMetric).filter(
        MonthlyMetric.month == month,
        MonthlyMetric.business_account_id == business_id,
    ).first()
    if not metric:
        raise HTTPException(404, f"No metrics found for month {month}")
    return metric


@router.post("/recalculate/{month}", response_model=MonthlyMetricResponse)
def recalculate_month(
    month: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    return calculate_monthly_metrics(db, month, business_id)


@router.post("/recalculate-all")
def recalculate_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    recalculate_all_months(db, business_id)
    return {"message": "All months recalculated"}
