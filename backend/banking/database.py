"""
Database configuration and session management.

Provides SQLAlchemy engine, session factory, and base model
for SQLite persistence.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from banking.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency injection for database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables and apply lightweight schema migrations."""
    from banking.models.db_models import Evaluation, Issue, Job  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # ── Lightweight migration: add columns if they don't exist yet ──
    # Required because SQLAlchemy's create_all does not ALTER existing tables.
    import sqlalchemy as sa

    with engine.connect() as conn:
        # Evaluate existing evaluation columns
        existing_eval_cols = {
            row[1]
            for row in conn.execute(sa.text("PRAGMA table_info(evaluations)"))
        }
        _add_column_if_missing = lambda col, ddl: (  # noqa: E731
            conn.execute(sa.text(ddl)) if col not in existing_eval_cols else None
        )
        _add_column_if_missing(
            "banking_domain",
            "ALTER TABLE evaluations ADD COLUMN banking_domain VARCHAR(100)",
        )
        _add_column_if_missing(
            "banking_metrics_json",
            "ALTER TABLE evaluations ADD COLUMN banking_metrics_json TEXT",
        )
        _add_column_if_missing(
            "banking_overall_score",
            "ALTER TABLE evaluations ADD COLUMN banking_overall_score REAL",
        )
        _add_column_if_missing(
            "legal_hold",
            "ALTER TABLE evaluations ADD COLUMN legal_hold INTEGER NOT NULL DEFAULT 0",
        )
        _add_column_if_missing(
            "legal_hold_reason",
            "ALTER TABLE evaluations ADD COLUMN legal_hold_reason TEXT",
        )
        _add_column_if_missing(
            "remediation_plan_json",
            "ALTER TABLE evaluations ADD COLUMN remediation_plan_json TEXT",
        )

        # Migrate issues table — add regulation_reference and metric_dimension
        existing_issue_cols = {
            row[1]
            for row in conn.execute(sa.text("PRAGMA table_info(issues)"))
        }
        if "regulation_reference" not in existing_issue_cols:
            conn.execute(
                sa.text("ALTER TABLE issues ADD COLUMN regulation_reference VARCHAR(100)")
            )
        if "metric_dimension" not in existing_issue_cols:
            conn.execute(
                sa.text("ALTER TABLE issues ADD COLUMN metric_dimension VARCHAR(100)")
            )

        conn.commit()
