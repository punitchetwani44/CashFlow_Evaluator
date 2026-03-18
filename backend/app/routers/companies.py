"""Companies router — /api/companies/*

All endpoints require super_admin EXCEPT:
  - company_admin can manage their own company's business accounts
"""
import re
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Company, BusinessAccount, User, UserSession, UserBusinessAccess
from ..schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse,
    BusinessAccountCreate, BusinessAccountUpdate, BusinessAccountResponse,
    InactivateRequest,
)
from ..auth.dependencies import get_current_user
from ..services.audit_service import create_audit_log, AuditAction

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ─────────────────────────────────────────────────────────────────────────────
# GET /  — list all companies (super_admin only)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", response_model=List[CompanyResponse])
def list_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    return db.query(Company).all()


# ─────────────────────────────────────────────────────────────────────────────
# POST /  — create company (super_admin only)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", response_model=CompanyResponse, status_code=201)
def create_company(
    body: CompanyCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")

    slug = _slugify(body.name)
    existing = db.query(Company).filter(Company.slug == slug).first()
    if existing:
        raise HTTPException(status_code=409, detail="Company with this name already exists")

    company = Company(
        name=body.name,
        slug=slug,
        plan=body.plan,
        max_business_accounts=body.max_business_accounts,
        created_by=current_user.id,
    )
    db.add(company)
    db.flush()   # get company.id before creating BA

    # Auto-create a default Business Account for the new company
    default_ba = BusinessAccount(
        company_id=company.id,
        name=f"{body.name} — Main Account",
        description="Auto-created default business account",
        created_by=current_user.id,
    )
    db.add(default_ba)
    db.commit()
    db.refresh(company)
    return company


# ─────────────────────────────────────────────────────────────────────────────
# GET /{id}
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin" and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


# ─────────────────────────────────────────────────────────────────────────────
# PUT /{id}
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    body: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    if body.name is not None:
        company.name = body.name
        company.slug = _slugify(body.name)
    if body.plan is not None:
        company.plan = body.plan
    if body.max_business_accounts is not None:
        company.max_business_accounts = body.max_business_accounts

    db.commit()
    db.refresh(company)
    return company


# ─────────────────────────────────────────────────────────────────────────────
# POST /{id}/inactivate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{company_id}/inactivate")
def inactivate_company(
    company_id: int,
    body: InactivateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if company.id == current_user.company_id:
        raise HTTPException(status_code=400, detail="Cannot inactivate your own company")

    company.is_active = False
    company.inactive_reason = body.reason
    company.inactive_at = datetime.now(timezone.utc)

    # Revoke all sessions of all users in this company
    users = db.query(User).filter(User.company_id == company_id).all()
    for user in users:
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_revoked == False,
        ).update({"is_revoked": True})
    db.commit()

    create_audit_log(
        db, action=AuditAction.COMPANY_INACTIVATED,
        actor_user_id=current_user.id,
        target_company_id=company_id,
        ip_address=_get_client_ip(request),
        extra={"reason": body.reason},
    )
    return {"message": f"Company '{company.name}' inactivated. All user sessions revoked."}


# ─────────────────────────────────────────────────────────────────────────────
# POST /{id}/reactivate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{company_id}/reactivate")
def reactivate_company(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin only")
    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company.is_active = True
    company.inactive_reason = None
    company.inactive_at = None
    db.commit()

    create_audit_log(
        db, action=AuditAction.COMPANY_REACTIVATED,
        actor_user_id=current_user.id,
        target_company_id=company_id,
        ip_address=_get_client_ip(request),
    )
    return {"message": f"Company '{company.name}' reactivated"}


# ─────────────────────────────────────────────────────────────────────────────
# GET /{id}/business-accounts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{company_id}/business-accounts", response_model=List[BusinessAccountResponse])
def list_business_accounts(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "super_admin" and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return db.query(BusinessAccount).filter(
        BusinessAccount.company_id == company_id
    ).all()


# ─────────────────────────────────────────────────────────────────────────────
# POST /{id}/business-accounts  — create BA
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{company_id}/business-accounts", response_model=BusinessAccountResponse, status_code=201)
def create_business_account(
    company_id: int,
    body: BusinessAccountCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # company_admin can create BA for their own company; super_admin for any
    if current_user.role not in ("super_admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if current_user.role == "company_admin" and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Can only create BAs for your own company")

    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Check plan limit
    existing_count = db.query(BusinessAccount).filter(
        BusinessAccount.company_id == company_id,
        BusinessAccount.is_active == True,
    ).count()
    if existing_count >= company.max_business_accounts:
        raise HTTPException(
            status_code=403,
            detail=f"Plan limit reached: max {company.max_business_accounts} business accounts",
        )

    ba = BusinessAccount(
        company_id=company_id,
        name=body.name,
        description=body.description,
        created_by=current_user.id,
    )
    db.add(ba)
    db.commit()
    db.refresh(ba)

    create_audit_log(
        db, action=AuditAction.BA_CREATED,
        actor_user_id=current_user.id,
        target_company_id=company_id,
        target_business_account_id=ba.id,
        ip_address=_get_client_ip(request),
    )
    return ba


# ─────────────────────────────────────────────────────────────────────────────
# PUT /{id}/business-accounts/{ba_id}
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{company_id}/business-accounts/{ba_id}", response_model=BusinessAccountResponse)
def update_business_account(
    company_id: int,
    ba_id: int,
    body: BusinessAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("super_admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    ba = db.query(BusinessAccount).filter(
        BusinessAccount.id == ba_id,
        BusinessAccount.company_id == company_id,
    ).first()
    if ba is None:
        raise HTTPException(status_code=404, detail="Business account not found")

    if body.name is not None:
        ba.name = body.name
    if body.description is not None:
        ba.description = body.description
    db.commit()
    db.refresh(ba)
    return ba


# ─────────────────────────────────────────────────────────────────────────────
# POST /{id}/business-accounts/{ba_id}/inactivate
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{company_id}/business-accounts/{ba_id}/inactivate")
def inactivate_business_account(
    company_id: int,
    ba_id: int,
    body: InactivateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("super_admin", "company_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    ba = db.query(BusinessAccount).filter(
        BusinessAccount.id == ba_id,
        BusinessAccount.company_id == company_id,
    ).first()
    if ba is None:
        raise HTTPException(status_code=404, detail="Business account not found")

    ba.is_active = False
    db.commit()

    create_audit_log(
        db, action=AuditAction.BA_INACTIVATED,
        actor_user_id=current_user.id,
        target_company_id=company_id,
        target_business_account_id=ba_id,
        ip_address=_get_client_ip(request),
        extra={"reason": body.reason},
    )
    return {"message": f"Business account '{ba.name}' inactivated"}
