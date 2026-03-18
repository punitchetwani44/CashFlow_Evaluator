import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime
from ..database import get_db
from ..models import Transaction, ClassificationRule, User
from ..schemas import TransactionResponse, TransactionUpdate, BulkUpdateRequest
from ..services.classifier import Classifier, extract_key_phrase
from ..services.metrics_calculator import calculate_monthly_metrics
from ..auth.dependencies import get_current_user, get_active_business_id

logger = logging.getLogger(__name__)
router = APIRouter()
classifier = Classifier()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _save_rule(
    db: Session,
    description: str,
    head: str,
    txn_type: str,
    business_account_id: Optional[int] = None,
) -> None:
    """Persist a learned classification rule from a user correction."""
    if not head or head == "Unknown / Unmapped":
        return

    key_phrase = extract_key_phrase(description)
    if not key_phrase or len(key_phrase.strip()) < 3:
        return

    # Look for an existing user rule with the same key_phrase + same BA
    existing_q = (
        db.query(ClassificationRule)
        .filter(
            ClassificationRule.key_phrase == key_phrase,
            ClassificationRule.scope != "system",
        )
    )
    if business_account_id is not None:
        existing_q = existing_q.filter(
            ClassificationRule.business_account_id == business_account_id
        )
    existing = existing_q.first()

    if existing:
        existing.head = head
        existing.type = txn_type
        existing.use_count = (getattr(existing, "use_count", 0) or 0) + 1
        existing.confirmation_count = (getattr(existing, "confirmation_count", 0) or 0) + 1
        existing.updated_at = datetime.utcnow()
    else:
        db.add(ClassificationRule(
            key_phrase=key_phrase,
            head=head,
            type=txn_type,
            rule_type="user_learned",
            is_enabled=True,
            confidence=0.99,
            scope="user",
            business_account_id=business_account_id,
            use_count=1,
            confirmation_count=1,
        ))


def _load_rules(db: Session, business_account_id: Optional[int] = None) -> List[dict]:
    """Fetch rules scoped to this BA + system rules."""
    q = db.query(ClassificationRule)
    if business_account_id is not None:
        q = q.filter(
            or_(
                ClassificationRule.business_account_id == business_account_id,
                ClassificationRule.scope == "system",
            )
        )
    return [
        {
            "id":                getattr(r, "id", None),
            "key_phrase":        r.key_phrase,
            "head":              r.head,
            "type":              r.type,
            "rule_type":         getattr(r, "rule_type", "user_learned") or "user_learned",
            "pattern":           getattr(r, "pattern", None),
            "normalized_vendor": getattr(r, "normalized_vendor", None),
            "is_enabled":        getattr(r, "is_enabled", True),
            "confidence":        getattr(r, "confidence", 0.99) or 0.99,
            "scope":             getattr(r, "scope", "user") or "user",
        }
        for r in q.all()
    ]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[TransactionResponse])
def get_transactions(
    month: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    head: Optional[str] = Query(None),
    upload_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    q = db.query(Transaction).filter(Transaction.business_account_id == business_id)
    if month:
        q = q.filter(Transaction.month == month)
    if status:
        q = q.filter(Transaction.status == status)
    if head:
        q = q.filter(Transaction.head == head)
    if upload_id:
        q = q.filter(Transaction.upload_id == upload_id)
    q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    return q.offset(skip).limit(limit).all()


@router.get("/count")
def count_transactions(
    month: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    q = db.query(Transaction).filter(Transaction.business_account_id == business_id)
    if month:
        q = q.filter(Transaction.month == month)
    if status:
        q = q.filter(Transaction.status == status)
    return {"count": q.count()}


@router.get("/months")
def get_months(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    months = (
        db.query(Transaction.month)
        .filter(
            Transaction.month.isnot(None),
            Transaction.business_account_id == business_id,
        )
        .distinct()
        .order_by(Transaction.month.desc())
        .all()
    )
    return [m[0] for m in months]


@router.get("/{txn_id}", response_model=TransactionResponse)
def get_transaction(
    txn_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    txn = db.query(Transaction).filter(
        Transaction.id == txn_id,
        Transaction.business_account_id == business_id,
    ).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")
    return txn


@router.put("/{txn_id}", response_model=TransactionResponse)
def update_transaction(
    txn_id: int,
    data: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    txn = db.query(Transaction).filter(
        Transaction.id == txn_id,
        Transaction.business_account_id == business_id,
    ).first()
    if not txn:
        raise HTTPException(404, "Transaction not found")

    if data.head is not None:
        txn.head = data.head
        txn.status = "mapped" if data.head and data.head != "Unknown / Unmapped" else "unmapped"
        if data.create_rule:
            effective_type = data.type or txn.type or "outflow"
            _save_rule(db, txn.description, data.head, effective_type, business_id)

    if data.type is not None:
        txn.type = data.type
    if data.comments is not None:
        txn.comments = data.comments

    txn.is_user_modified = True
    txn.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(txn)

    if txn.month:
        calculate_monthly_metrics(db, txn.month, business_id)

    return txn


@router.post("/bulk-update")
def bulk_update_transactions(
    data: BulkUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    if not data.ids:
        raise HTTPException(400, "No transaction IDs provided")

    months_affected = set()
    updated = 0
    for txn_id in data.ids:
        txn = db.query(Transaction).filter(
            Transaction.id == txn_id,
            Transaction.business_account_id == business_id,
        ).first()
        if not txn:
            continue
        txn.head = data.head
        txn.status = "mapped" if data.head and data.head != "Unknown / Unmapped" else "unmapped"
        if data.type:
            txn.type = data.type
        if data.comments:
            txn.comments = data.comments
        txn.is_user_modified = True
        txn.updated_at = datetime.utcnow()
        if txn.month:
            months_affected.add(txn.month)
        if data.create_rule:
            effective_type = data.type or txn.type or "outflow"
            _save_rule(db, txn.description, data.head, effective_type, business_id)
        updated += 1

    db.commit()

    for month in months_affected:
        calculate_monthly_metrics(db, month, business_id)

    return {"updated": updated, "months_recalculated": list(months_affected)}


@router.post("/reprocess/{month}")
def reprocess_month(
    month: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    """Re-classify non-user-modified transactions for a month."""
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.month == month,
            Transaction.is_user_modified == False,
            Transaction.business_account_id == business_id,
        )
        .all()
    )

    if not txns:
        calculate_monthly_metrics(db, month, business_id)
        return {"message": "No transactions to reclassify", "reprocessed": 0}

    txn_dicts = [
        {
            "date": t.date,
            "description": t.description,
            "amount": t.amount,
            "type": t.type or "outflow",
            "month": t.month,
        }
        for t in txns
    ]

    rules = _load_rules(db, business_id)
    classified = classifier.classify_all(txn_dicts, rules=rules)

    for original, result in zip(txns, classified):
        original.head = result.get("head")
        original.type = result.get("type", original.type)
        original.classification_confidence = result.get("classification_confidence")
        original.status = result.get("status", "unmapped")
        original.matched_rule_id = result.get("matched_rule_id")
        original.matched_rule_source = result.get("matched_rule_source")
        original.updated_at = datetime.utcnow()

    db.commit()
    calculate_monthly_metrics(db, month, business_id)

    mapped = sum(1 for r in classified if r.get("status") == "mapped")
    return {
        "message": f"Reprocessed {len(classified)} transactions",
        "reprocessed": len(classified),
        "mapped": mapped,
        "unmapped": len(classified) - mapped,
    }
