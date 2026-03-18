import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import AIInsight, MonthlyMetric, User, BusinessAccount, UserBusinessAccess
from ..schemas import AIInsightResponse, AggregateInsightsRequest, AggregateInsightsResponse
from ..services.insights_generator import InsightsGenerator
from ..services.metrics_calculator import calculate_aggregate_metrics
from ..auth.dependencies import get_current_user, get_active_business_id

router = APIRouter()
generator = InsightsGenerator()


@router.post("/generate-aggregate", response_model=AggregateInsightsResponse)
def generate_aggregate_insights(
    body: AggregateInsightsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate AI insights for a multi-business or multi-month date range."""
    # ── Date validation ──────────────────────────────────────────────────────
    try:
        dfrom = datetime.strptime(body.date_from, "%Y-%m")
        dto   = datetime.strptime(body.date_to,   "%Y-%m")
    except ValueError:
        raise HTTPException(400, "date_from and date_to must be YYYY-MM format")

    if dfrom > dto:
        raise HTTPException(400, "date_from must be <= date_to")

    months_diff = (dto.year - dfrom.year) * 12 + (dto.month - dfrom.month)
    if months_diff > 24:
        raise HTTPException(400, "Date range cannot exceed 24 months")

    if not body.business_ids:
        raise HTTPException(400, "business_ids cannot be empty")

    # ── Access verification ──────────────────────────────────────────────────
    if current_user.role != "super_admin":
        accesses = db.query(UserBusinessAccess).filter(
            UserBusinessAccess.user_id == current_user.id,
            UserBusinessAccess.business_account_id.in_(body.business_ids),
        ).all()
        accessible_ids = {a.business_account_id for a in accesses}
        denied = set(body.business_ids) - accessible_ids
        if denied:
            raise HTTPException(403, f"Access denied to business accounts: {sorted(denied)}")

    # ── Cross-company guard ──────────────────────────────────────────────────
    bas = db.query(BusinessAccount).filter(
        BusinessAccount.id.in_(body.business_ids)
    ).all()
    if current_user.role != "super_admin":
        if any(ba.company_id != current_user.company_id for ba in bas):
            raise HTTPException(403, "Cross-company aggregation is not permitted")

    business_names = [ba.name for ba in bas]
    period_label = (
        body.date_from
        if body.date_from == body.date_to
        else f"{body.date_from} – {body.date_to}"
    )

    # ── Compute aggregated metrics ───────────────────────────────────────────
    result = calculate_aggregate_metrics(db, body.business_ids, body.date_from, body.date_to)

    insights_list = generator.generate(
        month=body.date_from,
        current=result,
        previous=None,
        period_label=period_label,
        business_names=business_names,
    )

    return AggregateInsightsResponse(
        period_label=period_label,
        business_names=business_names,
        insights=json.dumps(insights_list),
        generated_at=datetime.utcnow(),
    )


@router.get("/{month}", response_model=AIInsightResponse)
def get_insights(
    month: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    insight = db.query(AIInsight).filter(
        AIInsight.month == month,
        AIInsight.business_account_id == business_id,
    ).first()
    if not insight:
        raise HTTPException(404, f"No insights found for {month}. Generate them first.")
    return insight


@router.post("/generate/{month}", response_model=AIInsightResponse)
def generate_insights(
    month: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    current = db.query(MonthlyMetric).filter(
        MonthlyMetric.month == month,
        MonthlyMetric.business_account_id == business_id,
    ).first()
    if not current:
        raise HTTPException(404, f"No metrics found for {month}. Upload transactions first.")

    # Get previous month for comparison
    from datetime import datetime, timedelta
    dt = datetime.strptime(month, "%Y-%m")
    prev_month = (dt.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    previous = db.query(MonthlyMetric).filter(
        MonthlyMetric.month == prev_month,
        MonthlyMetric.business_account_id == business_id,
    ).first()

    current_dict = {
        "total_inflow": current.total_inflow,
        "total_outflow": current.total_outflow,
        "net_cashflow": current.net_cashflow,
        "indicator_cashflow": current.indicator_cashflow,
        "fixed_cost_ratio": current.fixed_cost_ratio,
        "payroll_ratio": current.payroll_ratio,
        "cash_runway": current.cash_runway,
        "category_breakdown": current.category_breakdown,
    }
    prev_dict = None
    if previous:
        prev_dict = {
            "total_inflow": previous.total_inflow,
            "total_outflow": previous.total_outflow,
        }

    insights_list = generator.generate(month, current_dict, prev_dict)

    # Upsert insight record (scoped to BA)
    existing = db.query(AIInsight).filter(
        AIInsight.month == month,
        AIInsight.business_account_id == business_id,
    ).first()
    if existing:
        existing.insights = json.dumps(insights_list)
        existing.generated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        new_insight = AIInsight(
            month=month,
            business_account_id=business_id,
            insights=json.dumps(insights_list),
        )
        db.add(new_insight)
        db.commit()
        db.refresh(new_insight)
        return new_insight


@router.get("")
def list_insights(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    return (
        db.query(AIInsight)
        .filter(AIInsight.business_account_id == business_id)
        .order_by(AIInsight.month.desc())
        .all()
    )
