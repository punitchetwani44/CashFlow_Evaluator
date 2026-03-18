from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, run_migrations
from .config import settings
from .routers import uploads, transactions, metrics, insights
from .routers import rules as rules_router
from .routers import auth as auth_router
from .routers import users as users_router
from .routers import companies as companies_router
from .middleware.auth_middleware import AuthMiddleware
from .middleware.tenant_middleware import TenantMiddleware

# 1. Create any brand-new tables
Base.metadata.create_all(bind=engine)

# 2. Add any new columns to *existing* tables (idempotent)
run_migrations(engine)

app = FastAPI(
    title="CashFlow Evaluator API",
    description="AI-powered cashflow analysis for Indian SMEs",
    version="1.0.0",
)

# ── Middleware stack (added in reverse execution order) ───────────────────────
# Starlette executes middleware in LIFO order:
#   Request:  CORS → Auth → Tenant → Router
#   Response: Router → Tenant → Auth → CORS
app.add_middleware(TenantMiddleware)   # runs second on request
app.add_middleware(AuthMiddleware)     # runs first on request
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "X-CSRF-Token"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(transactions.router, prefix="/api/transactions", tags=["Transactions"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(insights.router, prefix="/api/insights", tags=["AI Insights"])
app.include_router(rules_router.router, prefix="/api/rules", tags=["Rules"])
app.include_router(auth_router.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users_router.router, prefix="/api/users", tags=["Users"])
app.include_router(companies_router.router, prefix="/api/companies", tags=["Companies"])


@app.on_event("startup")
async def _startup():
    """Run all idempotent startup tasks in order."""
    from .database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # ── 1. Seed built-in classification rules ─────────────────────────────
        from .routers.rules import seed_built_in_rules
        seed_built_in_rules(db)

        # ── 2. Ensure default Company + BusinessAccount exist ─────────────────
        from .models import Company, BusinessAccount, User, UserBusinessAccess
        import re
        from argon2 import PasswordHasher
        from datetime import datetime

        company = db.query(Company).first()
        if company is None:
            slug = re.sub(r"[^a-z0-9]+", "-",
                          settings.default_company_name.lower()).strip("-")
            company = Company(
                name=settings.default_company_name,
                slug=slug,
                plan="starter",
            )
            db.add(company)
            db.flush()          # get company.id before BA insert

        ba = db.query(BusinessAccount).filter(
            BusinessAccount.company_id == company.id
        ).first()
        if ba is None:
            ba = BusinessAccount(
                company_id=company.id,
                name=settings.default_business_account_name,
                description="Auto-created default account",
            )
            db.add(ba)
            db.flush()          # get ba.id before backfill

        db.commit()             # commit company + BA before UPDATE

        # ── 3. Backfill existing rows that have no business_account_id ────────
        for table in ("uploads", "transactions", "monthly_metrics",
                      "ai_insights", "classification_rules"):
            db.execute(text(
                f"UPDATE {table} "
                f"SET business_account_id = :ba_id "
                f"WHERE business_account_id IS NULL"
            ), {"ba_id": ba.id})
        db.commit()

        # ── 4. Seed super-admin user if none exists ───────────────────────────
        super_admin = db.query(User).filter(User.role == "super_admin").first()
        if super_admin is None:
            ph = PasswordHasher()
            hashed = ph.hash(settings.super_admin_password)
            admin = User(
                company_id=company.id,
                email=settings.super_admin_email,
                hashed_password=hashed,
                full_name="Super Admin",
                role="super_admin",
                is_active=True,
                password_changed_at=datetime.utcnow(),
            )
            db.add(admin)
            db.flush()

            # Give super-admin access to the default BA
            access = UserBusinessAccess(
                user_id=admin.id,
                business_account_id=ba.id,
                can_switch=True,
            )
            db.add(access)
            db.commit()
            print(f"[startup] Super-admin created: {settings.super_admin_email}")
        else:
            print(f"[startup] Super-admin already exists ({super_admin.email})")

    except Exception as exc:
        db.rollback()
        print(f"[startup] ERROR during seed: {exc}")
        raise
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "CashFlow Evaluator API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok"}
