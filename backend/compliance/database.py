"""
Database configuration and session management.

Provides SQLAlchemy engine, session factory, and base model
for SQLite persistence.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from compliance.config import settings
from core.models.db_models import Job


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
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Compliance init_db: DATABASE_URL = %s", settings.DATABASE_URL)
    logger.info("Compliance init_db: engine URL = %s", str(engine.url))

    from compliance.models.db_models import Evaluation, Issue  # noqa: F401
    Base.metadata.create_all(bind=engine)

    Job.__table__.create(bind=engine, checkfirst=True)

    # ── Lightweight migration: add columns if they don't exist yet ──
    # Required because SQLAlchemy's create_all does not ALTER existing tables.
    import sqlalchemy as sa

    with engine.connect() as conn:
        # ── Evaluations table migrations ──
        existing_eval_cols = {
            row[1]
            for row in conn.execute(sa.text("PRAGMA table_info(evaluations)"))
        }

        migration_columns = [
            ("short_id", "ALTER TABLE evaluations ADD COLUMN short_id VARCHAR(10)"),
            ("semantic_type", "ALTER TABLE evaluations ADD COLUMN semantic_type VARCHAR(50) DEFAULT 'general'"),
            ("banking_domain", "ALTER TABLE evaluations ADD COLUMN banking_domain VARCHAR(100)"),
            ("banking_metrics_json", "ALTER TABLE evaluations ADD COLUMN banking_metrics_json TEXT"),
            ("banking_overall_score", "ALTER TABLE evaluations ADD COLUMN banking_overall_score REAL"),
            ("legal_hold", "ALTER TABLE evaluations ADD COLUMN legal_hold INTEGER NOT NULL DEFAULT 0"),
            ("legal_hold_reason", "ALTER TABLE evaluations ADD COLUMN legal_hold_reason TEXT"),
            ("remediation_plan_json", "ALTER TABLE evaluations ADD COLUMN remediation_plan_json TEXT"),
            ("workspace", "ALTER TABLE evaluations ADD COLUMN workspace VARCHAR(20) DEFAULT 'compliance'"),
        ]
        for col_name, ddl in migration_columns:
            if col_name not in existing_eval_cols:
                conn.execute(sa.text(ddl))

        if "workspace" in existing_eval_cols or "workspace" in {c for c, _ in migration_columns}:
            conn.execute(
                sa.text(
                    "UPDATE evaluations SET workspace = 'compliance' "
                    "WHERE workspace IS NULL OR workspace = '' OR workspace = 'unknown'"
                )
            )

        # ── Issues table migrations ──
        existing_issue_cols = {
            row[1]
            for row in conn.execute(sa.text("PRAGMA table_info(issues)"))
        }
        issue_migrations = [
            ("metric_name", "ALTER TABLE issues ADD COLUMN metric_name VARCHAR(200)"),
            ("regulation_reference", "ALTER TABLE issues ADD COLUMN regulation_reference VARCHAR(100)"),
            ("metric_dimension", "ALTER TABLE issues ADD COLUMN metric_dimension VARCHAR(100)"),
        ]
        for col_name, ddl in issue_migrations:
            if col_name not in existing_issue_cols:
                conn.execute(sa.text(ddl))

        # ── Jobs table migrations ──
        try:
            existing_job_cols = {
                row[1]
                for row in conn.execute(sa.text("PRAGMA table_info(jobs)"))
            }
            if existing_job_cols:  # table exists
                job_migrations = [
                    ("workspace", "ALTER TABLE jobs ADD COLUMN workspace VARCHAR(20) DEFAULT 'compliance'"),
                ]
                for col_name, ddl in job_migrations:
                    if col_name not in existing_job_cols:
                        conn.execute(sa.text(ddl))
        except Exception:
            pass  # jobs table may not exist in older compliance DBs

        conn.commit()
