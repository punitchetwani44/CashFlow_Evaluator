import os
_db_url = os.environ.get('DATABASE_URL', 'sqlite:///./cashflow.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
os.environ['DATABASE_URL'] = _db_url
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Schema migrations (SQLite-compatible, idempotent)
# ---------------------------------------------------------------------------

def _get_existing_columns(conn, table_name: str) -> set:
    """Return the set of column names that already exist in *table_name*."""
    result = conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in result.fetchall()}


def run_migrations(db_engine) -> None:
    """Add any new columns that are not yet present in the live DB.

    Safe to call on every startup — each ALTER TABLE is guarded by an
    existence check so already-migrated columns are silently skipped.
    """
    migrations: dict[str, list[tuple[str, str]]] = {
        "classification_rules": [
            ("rule_type",           "VARCHAR(20) NOT NULL DEFAULT 'user_learned'"),
            ("pattern",             "TEXT"),
            ("normalized_vendor",   "VARCHAR(200)"),
            ("is_enabled",          "BOOLEAN NOT NULL DEFAULT 1"),
            ("confidence",          "FLOAT NOT NULL DEFAULT 0.95"),
            ("confirmation_count",  "INTEGER NOT NULL DEFAULT 0"),
            ("scope",               "VARCHAR(20) NOT NULL DEFAULT 'user'"),
            # Multi-tenant
            ("business_account_id", "INTEGER"),
        ],
        "transactions": [
            ("matched_rule_id",     "INTEGER"),
            ("matched_rule_source", "VARCHAR(30)"),
            # Multi-tenant
            ("business_account_id", "INTEGER"),
        ],
        "uploads": [
            ("business_account_id", "INTEGER"),
        ],
        "monthly_metrics": [
            ("business_account_id", "INTEGER"),
        ],
        "ai_insights": [
            ("business_account_id", "INTEGER"),
        ],
    }

    with db_engine.connect() as conn:
        for table, columns in migrations.items():
            # Skip tables that don't exist yet (create_all handles them)
            try:
                existing = _get_existing_columns(conn, table)
            except Exception:
                continue
            for col_name, col_def in columns:
                if col_name not in existing:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    )
                    conn.commit()

    # ── Performance index for aggregate queries ──────────────────────────────
    # Composite index on (business_account_id, month) speeds up the GROUP BY
    # query in calculate_aggregate_metrics() for large datasets.
    with db_engine.connect() as conn:
        try:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_transactions_ba_month "
                "ON transactions (business_account_id, month)"
            ))
            conn.commit()
        except Exception:
            pass  # index may already exist or table not yet created
