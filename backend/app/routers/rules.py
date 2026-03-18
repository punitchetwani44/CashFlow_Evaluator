"""
routers/rules.py
~~~~~~~~~~~~~~~~
REST CRUD for ClassificationRule + a /seed endpoint that idempotently
populates built-in vendor and regex rules.

User rules are scoped per business account.
System rules (scope='system') are shared (NULL business_account_id).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List, Optional

from ..database import get_db
from ..models import ClassificationRule, User
from ..schemas import RuleCreate, RuleUpdate, RuleResponse, RulesStatsResponse
from ..services.rule_engine import (
    _BUILT_IN_VENDORS,
    _BUILT_IN_REGEX,
    normalize_vendor,
)
from ..auth.dependencies import get_current_user, get_active_business_id

router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _rule_or_404(db: Session, rule_id: int) -> ClassificationRule:
    rule = db.query(ClassificationRule).filter(ClassificationRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


def _scoped_rule_or_404(db: Session, rule_id: int, business_id: int) -> ClassificationRule:
    """Fetch a rule that belongs to this BA or is a system rule."""
    rule = db.query(ClassificationRule).filter(
        ClassificationRule.id == rule_id,
        or_(
            ClassificationRule.business_account_id == business_id,
            ClassificationRule.scope == "system",
        ),
    ).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


# ─── Seeding (unchanged — system rules have NULL business_account_id) ─────────

def seed_built_in_rules(db: Session) -> int:
    """Idempotently insert all built-in vendor + regex rules.

    Returns the number of new rules inserted (0 if already seeded).
    """
    inserted = 0

    for vendor_token, (head, typ, confidence) in _BUILT_IN_VENDORS.items():
        key_phrase = f"__vendor__{vendor_token}"
        existing = (
            db.query(ClassificationRule)
            .filter(ClassificationRule.key_phrase == key_phrase)
            .first()
        )
        if not existing:
            rule = ClassificationRule(
                key_phrase=key_phrase,
                head=head,
                type=typ,
                rule_type="vendor_exact",
                normalized_vendor=vendor_token,
                is_enabled=True,
                confidence=confidence,
                scope="system",
                business_account_id=None,   # system rules are global
                use_count=0,
                confirmation_count=0,
            )
            db.add(rule)
            inserted += 1

    for idx, (pattern, head, typ, confidence) in enumerate(_BUILT_IN_REGEX):
        key_phrase = f"__regex__{idx:02d}"
        existing = (
            db.query(ClassificationRule)
            .filter(ClassificationRule.key_phrase == key_phrase)
            .first()
        )
        if not existing:
            rule = ClassificationRule(
                key_phrase=key_phrase,
                head=head,
                type=typ,
                rule_type="regex_keyword",
                pattern=pattern,
                is_enabled=True,
                confidence=confidence,
                scope="system",
                business_account_id=None,
                use_count=0,
                confirmation_count=0,
            )
            db.add(rule)
            inserted += 1

    db.commit()
    return inserted


# ─── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=RulesStatsResponse)
def get_rules_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    all_rules = db.query(ClassificationRule).filter(
        or_(
            ClassificationRule.business_account_id == business_id,
            ClassificationRule.scope == "system",
        )
    ).all()
    total = len(all_rules)
    active = sum(1 for r in all_rules if getattr(r, "is_enabled", True))
    user_learned = sum(1 for r in all_rules if getattr(r, "rule_type", "user_learned") == "user_learned")
    vendor_exact = sum(1 for r in all_rules if getattr(r, "rule_type", "") == "vendor_exact")
    regex_kw = sum(1 for r in all_rules if getattr(r, "rule_type", "") == "regex_keyword")
    system_rules = sum(1 for r in all_rules if getattr(r, "scope", "user") == "system")
    return RulesStatsResponse(
        total=total,
        active=active,
        user_learned=user_learned,
        vendor_exact=vendor_exact,
        regex_keyword=regex_kw,
        system_rules=system_rules,
    )


# ─── CRUD ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=List[RuleResponse])
def list_rules(
    rule_type: Optional[str] = None,
    is_enabled: Optional[bool] = None,
    scope: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    q = db.query(ClassificationRule).filter(
        or_(
            ClassificationRule.business_account_id == business_id,
            ClassificationRule.scope == "system",
        )
    )
    if rule_type:
        q = q.filter(ClassificationRule.rule_type == rule_type)
    if is_enabled is not None:
        q = q.filter(ClassificationRule.is_enabled == is_enabled)
    if scope:
        q = q.filter(ClassificationRule.scope == scope)
    return q.order_by(
        ClassificationRule.scope.desc(),
        ClassificationRule.use_count.desc(),
        ClassificationRule.id,
    ).all()


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    data: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    existing = (
        db.query(ClassificationRule)
        .filter(
            ClassificationRule.key_phrase == data.key_phrase,
            or_(
                ClassificationRule.business_account_id == business_id,
                ClassificationRule.scope == "system",
            ),
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A rule with key_phrase '{data.key_phrase}' already exists (id={existing.id}).",
        )

    norm_vendor = data.normalized_vendor
    if data.rule_type == "vendor_exact" and not norm_vendor:
        norm_vendor = normalize_vendor(data.key_phrase)

    rule = ClassificationRule(
        key_phrase=data.key_phrase,
        head=data.head,
        type=data.type,
        rule_type=data.rule_type,
        pattern=data.pattern,
        normalized_vendor=norm_vendor,
        is_enabled=data.is_enabled,
        confidence=data.confidence,
        scope=data.scope,
        business_account_id=business_id if data.scope != "system" else None,
        use_count=0,
        confirmation_count=0,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{rule_id}", response_model=RuleResponse)
def get_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    return _scoped_rule_or_404(db, rule_id, business_id)


@router.put("/{rule_id}", response_model=RuleResponse)
def update_rule(
    rule_id: int,
    data: RuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    rule = _scoped_rule_or_404(db, rule_id, business_id)

    # Protect system rules from scope changes
    if rule.scope == "system" and data.scope == "user":
        raise HTTPException(
            status_code=403, detail="Cannot demote a system rule to user scope"
        )

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)

    if (
        data.rule_type == "vendor_exact"
        and not data.normalized_vendor
        and rule.normalized_vendor is None
    ):
        rule.normalized_vendor = normalize_vendor(rule.key_phrase)

    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    rule = _scoped_rule_or_404(db, rule_id, business_id)
    if getattr(rule, "scope", "user") == "system":
        rule.is_enabled = False
        db.commit()
        return
    db.delete(rule)
    db.commit()


@router.post("/{rule_id}/promote", response_model=RuleResponse)
def promote_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    """Promote a user rule to system scope (requires confirmation_count >= 2)."""
    rule = _scoped_rule_or_404(db, rule_id, business_id)
    conf_count = getattr(rule, "confirmation_count", 0) or 0
    if conf_count < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rule must be confirmed at least 2 times before promoting "
                   f"(current confirmation_count={conf_count}).",
        )
    rule.scope = "system"
    rule.business_account_id = None   # system rules are shared
    db.commit()
    db.refresh(rule)
    return rule


# ─── Seed endpoint ─────────────────────────────────────────────────────────────

@router.post("/seed", status_code=status.HTTP_200_OK)
def seed_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    business_id: int = Depends(get_active_business_id),
):
    inserted = seed_built_in_rules(db)
    return {"inserted": inserted, "message": f"Seeded {inserted} new built-in rules."}
