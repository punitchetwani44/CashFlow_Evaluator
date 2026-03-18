import json
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from ..models import Transaction, MonthlyMetric

logger = logging.getLogger(__name__)

FIXED_COST_HEADS = {"Salaries", "Rentals", "EMI", "Utilities", "Loan Repayment", "Labor Charges"}
PAYROLL_HEADS = {"Salaries", "Labor Charges", "Staff Welfare", "Bonus Paid"}
CAPITAL_INFUSE_HEADS = {"Capital Infused"}
CAPITAL_WITHDRAW_HEADS = {"Capital Withdrawn", "Drawings"}
SUPPLIER_HEADS = {"Suppliers' Payment"}


def calculate_monthly_metrics(
    db: Session,
    month: str,
    business_account_id: Optional[int] = None,
) -> MonthlyMetric:
    """Calculate and upsert monthly metrics for the given month + business account."""
    q = db.query(Transaction).filter(Transaction.month == month)
    if business_account_id is not None:
        q = q.filter(Transaction.business_account_id == business_account_id)
    transactions = q.all()

    inflow_txns = [t for t in transactions if t.type == "inflow"]
    outflow_txns = [t for t in transactions if t.type == "outflow"]

    total_inflow = sum(t.amount for t in inflow_txns)
    total_outflow = sum(t.amount for t in outflow_txns)
    net_cashflow = total_inflow - total_outflow

    capital_infused = sum(t.amount for t in inflow_txns if t.head in CAPITAL_INFUSE_HEADS)
    capital_withdrawn = sum(t.amount for t in outflow_txns if t.head in CAPITAL_WITHDRAW_HEADS)

    # Indicator Cashflow = Inflow - Outflow - Capital Infused + Capital Withdrawn
    indicator_cashflow = total_inflow - total_outflow - capital_infused + capital_withdrawn

    # Fixed Cost Ratio
    fixed_costs = sum(t.amount for t in outflow_txns if t.head in FIXED_COST_HEADS)
    fixed_cost_ratio = (fixed_costs / total_inflow * 100) if total_inflow > 0 else 0.0

    # Payroll Ratio
    payroll = sum(t.amount for t in outflow_txns if t.head in PAYROLL_HEADS)
    payroll_ratio = (payroll / total_inflow * 100) if total_inflow > 0 else 0.0

    # Cash Runway: last known balance / average monthly outflow
    balance_txns = [t for t in transactions if t.raw_balance is not None]
    cash_runway = None
    if balance_txns and total_outflow > 0:
        last_balance = balance_txns[-1].raw_balance
        cash_runway = last_balance / total_outflow if last_balance and last_balance > 0 else None

    # Vendor Dependency: top supplier / total supplier payments
    supplier_txns = [t for t in outflow_txns if t.head in SUPPLIER_HEADS]
    vendor_dependency = None
    if supplier_txns:
        total_supplier = sum(t.amount for t in supplier_txns)
        vendor_groups: Dict[str, float] = {}
        for t in supplier_txns:
            key = t.description[:30].strip()
            vendor_groups[key] = vendor_groups.get(key, 0) + t.amount
        if vendor_groups and total_supplier > 0:
            top_vendor_amount = max(vendor_groups.values())
            vendor_dependency = (top_vendor_amount / total_supplier * 100)

    # Category breakdown
    category_breakdown: Dict[str, float] = {}
    for t in transactions:
        head = t.head or "Unknown / Unmapped"
        key = f"{t.type}:{head}"
        category_breakdown[key] = category_breakdown.get(key, 0.0) + t.amount

    mapped = sum(1 for t in transactions if t.status == "mapped")

    # Upsert MonthlyMetric — unique by (month, business_account_id)
    existing_q = db.query(MonthlyMetric).filter(MonthlyMetric.month == month)
    if business_account_id is not None:
        existing_q = existing_q.filter(
            MonthlyMetric.business_account_id == business_account_id
        )
    existing = existing_q.first()

    if existing:
        existing.total_inflow = total_inflow
        existing.total_outflow = total_outflow
        existing.net_cashflow = net_cashflow
        existing.indicator_cashflow = indicator_cashflow
        existing.capital_infused = capital_infused
        existing.capital_withdrawn = capital_withdrawn
        existing.fixed_cost_ratio = fixed_cost_ratio
        existing.payroll_ratio = payroll_ratio
        existing.cash_runway = cash_runway
        existing.vendor_dependency = vendor_dependency
        existing.transaction_count = len(transactions)
        existing.mapped_count = mapped
        existing.category_breakdown = json.dumps(category_breakdown)
        db.commit()
        db.refresh(existing)
        return existing
    else:
        metric = MonthlyMetric(
            month=month,
            business_account_id=business_account_id,
            total_inflow=total_inflow,
            total_outflow=total_outflow,
            net_cashflow=net_cashflow,
            indicator_cashflow=indicator_cashflow,
            capital_infused=capital_infused,
            capital_withdrawn=capital_withdrawn,
            fixed_cost_ratio=fixed_cost_ratio,
            payroll_ratio=payroll_ratio,
            cash_runway=cash_runway,
            vendor_dependency=vendor_dependency,
            transaction_count=len(transactions),
            mapped_count=mapped,
            category_breakdown=json.dumps(category_breakdown),
        )
        db.add(metric)
        db.commit()
        db.refresh(metric)
        return metric


def recalculate_all_months(db: Session, business_account_id: Optional[int] = None):
    """Recalculate metrics for all months, optionally scoped to a business account."""
    q = db.query(Transaction.month, Transaction.business_account_id).distinct()
    if business_account_id is not None:
        q = q.filter(Transaction.business_account_id == business_account_id)
    pairs = q.all()
    for (month, ba_id) in pairs:
        if month:
            calculate_monthly_metrics(db, month, ba_id)


def calculate_aggregate_metrics(
    db: Session,
    business_ids: List[int],
    date_from: str,   # YYYY-MM
    date_to: str,     # YYYY-MM
) -> Dict:
    """Aggregate from raw Transaction rows via SQL GROUP BY.

    Uses a single DB round-trip (GROUP BY month, type, head, status) to compute
    totals + monthly breakdown + previous-period comparison. Safe for large ranges.
    """
    from sqlalchemy import func

    rows = db.query(
        Transaction.month,
        Transaction.type,
        Transaction.head,
        Transaction.status,
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("cnt"),
    ).filter(
        Transaction.business_account_id.in_(business_ids),
        Transaction.month >= date_from,
        Transaction.month <= date_to,
        Transaction.month.isnot(None),
    ).group_by(
        Transaction.month, Transaction.type, Transaction.head, Transaction.status
    ).all()

    # ── Aggregate in Python ──────────────────────────────────────────────────
    monthly: Dict[str, Dict] = {}
    total_inflow = total_outflow = 0.0
    fixed_costs = payroll = capital_infused = capital_withdrawn = 0.0
    category_breakdown: Dict[str, float] = {}
    supplier_amounts: Dict[str, float] = {}
    transaction_count = mapped_count = 0

    for row in rows:
        m = monthly.setdefault(row.month, {
            "total_inflow": 0.0, "total_outflow": 0.0,
            "net_cashflow": 0.0, "indicator_cashflow": 0.0,
            "transaction_count": 0, "mapped_count": 0,
        })
        m["transaction_count"] += row.cnt
        transaction_count += row.cnt
        if row.status == "mapped":
            m["mapped_count"] += row.cnt
            mapped_count += row.cnt

        cat_key = f"{row.type}:{row.head or 'Unknown / Unmapped'}"
        category_breakdown[cat_key] = category_breakdown.get(cat_key, 0.0) + row.total

        if row.type == "inflow":
            total_inflow += row.total
            m["total_inflow"] += row.total
            if row.head in CAPITAL_INFUSE_HEADS:
                capital_infused += row.total
        elif row.type == "outflow":
            total_outflow += row.total
            m["total_outflow"] += row.total
            if row.head in FIXED_COST_HEADS:
                fixed_costs += row.total
            if row.head in PAYROLL_HEADS:
                payroll += row.total
            if row.head in CAPITAL_WITHDRAW_HEADS:
                capital_withdrawn += row.total
            if row.head in SUPPLIER_HEADS:
                supplier_amounts[row.head] = supplier_amounts.get(row.head, 0.0) + row.total

    net_cashflow = total_inflow - total_outflow
    indicator_cashflow = net_cashflow - capital_infused + capital_withdrawn
    fixed_cost_ratio = (fixed_costs / total_inflow * 100) if total_inflow > 0 else 0.0
    payroll_ratio = (payroll / total_inflow * 100) if total_inflow > 0 else 0.0

    vendor_dependency = None
    if supplier_amounts:
        ts = sum(supplier_amounts.values())
        if ts > 0:
            vendor_dependency = max(supplier_amounts.values()) / ts * 100

    # Fill per-month net/indicator cashflow (simplified — no per-month capital split)
    for d in monthly.values():
        infl, outfl = d["total_inflow"], d["total_outflow"]
        d["net_cashflow"] = infl - outfl
        d["indicator_cashflow"] = infl - outfl

    # ── 3-Month SMA via SQL window functions ────────────────────────────────────
    # Step 1: subquery — monthly outflow totals for the requested period
    from sqlalchemy import case as sa_case
    _inner = (
        db.query(
            Transaction.month.label("month"),
            func.sum(
                sa_case((Transaction.type == "outflow", Transaction.amount), else_=0.0)
            ).label("expense"),
        )
        .filter(
            Transaction.business_account_id.in_(business_ids),
            Transaction.month >= date_from,
            Transaction.month <= date_to,
            Transaction.month.isnot(None),
        )
        .group_by(Transaction.month)
        .subquery()
    )

    # Step 2: apply ROW_NUMBER + AVG window function, then NULL-out partial windows
    _rn_col      = func.row_number().over(order_by=_inner.c.month).label("rn")
    _sma_raw_col = func.avg(_inner.c.expense).over(
        order_by=_inner.c.month, rows=(-2, 0)
    ).label("sma_raw")
    _sub2 = db.query(
        _inner.c.month, _inner.c.expense, _rn_col, _sma_raw_col
    ).subquery()

    _sma_col = sa_case(
        (_sub2.c.rn >= 3, _sub2.c.sma_raw), else_=None
    ).label("sma_3")

    _sma_rows = (
        db.query(_sub2.c.month, _sma_col)
        .order_by(_sub2.c.month)
        .all()
    )
    sma_map: Dict[str, float] = {r.month: r.sma_3 for r in _sma_rows}

    monthly_breakdown = [
        {
            "month": mo,
            "total_inflow":       monthly[mo]["total_inflow"],
            "total_outflow":      monthly[mo]["total_outflow"],
            "net_cashflow":       monthly[mo]["net_cashflow"],
            "indicator_cashflow": monthly[mo]["indicator_cashflow"],
            "transaction_count":  monthly[mo]["transaction_count"],
            "sma_3":              sma_map.get(mo),   # None for first 2 months
        }
        for mo in sorted(monthly.keys())
    ]

    # ── Previous-period computation (same duration, shifted back) ────────────
    from datetime import datetime as _dt
    dfrom = _dt.strptime(date_from, "%Y-%m")
    dto   = _dt.strptime(date_to,   "%Y-%m")
    duration = (dto.year - dfrom.year) * 12 + (dto.month - dfrom.month) + 1

    # prev_date_to = one month before date_from
    prev_dto_m = dfrom.month - 1 or 12
    prev_dto_y = dfrom.year if dfrom.month > 1 else dfrom.year - 1
    prev_date_to = f"{prev_dto_y}-{prev_dto_m:02d}"

    # prev_date_from = duration-1 months before prev_date_to
    prev_dfrom_m = prev_dto_m - (duration - 1)
    prev_dfrom_y = prev_dto_y
    while prev_dfrom_m < 1:
        prev_dfrom_m += 12
        prev_dfrom_y -= 1
    prev_date_from = f"{prev_dfrom_y}-{prev_dfrom_m:02d}"

    prev_rows = db.query(
        Transaction.type,
        func.sum(Transaction.amount).label("total"),
    ).filter(
        Transaction.business_account_id.in_(business_ids),
        Transaction.month >= prev_date_from,
        Transaction.month <= prev_date_to,
        Transaction.month.isnot(None),
    ).group_by(Transaction.type).all()

    prev_inflow = prev_outflow = 0.0
    for r in prev_rows:
        if r.type == "inflow":
            prev_inflow = r.total
        elif r.type == "outflow":
            prev_outflow = r.total

    return dict(
        total_inflow=total_inflow,
        total_outflow=total_outflow,
        net_cashflow=net_cashflow,
        indicator_cashflow=indicator_cashflow,
        fixed_cost_ratio=fixed_cost_ratio,
        payroll_ratio=payroll_ratio,
        cash_runway=None,       # balance not available from GROUP BY
        vendor_dependency=vendor_dependency,
        transaction_count=transaction_count,
        mapped_count=mapped_count,
        category_breakdown=json.dumps(category_breakdown),
        monthly_breakdown=monthly_breakdown,
        prev_period_label=f"{prev_date_from} – {prev_date_to}",
        prev_total_inflow=prev_inflow,
        prev_total_outflow=prev_outflow,
        prev_net_cashflow=prev_inflow - prev_outflow,
    )
