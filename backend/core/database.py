"""
Unified database configuration and session management.

Provides SQLAlchemy engine, session factory, and base model
for SQLite persistence. Used by both Banking and Compliance workspaces.

Merges Banking's robust path resolution and migration-aware init_db()
with a clean shared interface.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ─── Path Resolution ────────────────────────────────────────────────────────

_BACKEND_DIR = Path(__file__).resolve().parent.parent


def _default_database_url(workspace: str = "unified") -> str:
    """Build a default SQLite URL for the given workspace."""
    db_path = (_BACKEND_DIR / "data" / workspace / "document_quality.db").resolve()
    return f"sqlite:///{db_path.as_posix()}"


def _normalize_database_url(database_url: str) -> str:
    """Resolve relative SQLite paths to absolute paths anchored to the backend dir."""
    if not database_url:
        return _default_database_url()
    if not database_url.startswith("sqlite:///"):
        return database_url
    if database_url.endswith(":memory:"):
        return database_url

    relative_path = database_url.removeprefix("sqlite:///")
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return database_url

    resolved_path = (_BACKEND_DIR / candidate).resolve()
    return f"sqlite:///{resolved_path.as_posix()}"


# ─── Engine & Session Factory ───────────────────────────────────────────────

def create_workspace_engine(database_url: str):
    """Create a SQLAlchemy engine for the given database URL."""
    normalized = _normalize_database_url(database_url)
    return create_engine(
        normalized,
        connect_args={"check_same_thread": False},  # Required for SQLite
        echo=False,
    )


Base = declarative_base()


def create_session_factory(engine):
    """Create a sessionmaker bound to the given engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_dependency(session_factory):
    """Create a FastAPI-compatible dependency that yields DB sessions."""
    def get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()
    return get_db


# ─── Database Initialization ────────────────────────────────────────────────

def init_db(engine) -> None:
    """
    Initialize database tables and apply lightweight schema migrations.

    Uses PRAGMA table_info to detect missing columns and ALTERs them in,
    so that SQLAlchemy's create_all() limitations are handled gracefully.
    """
    # Import models so they register with Base.metadata
    import core.models.db_models  # noqa: F401
    import core.models.monitor_models  # noqa: F401  — creates monitor_events + monitor_daily_summaries

    Base.metadata.create_all(bind=engine)

    # ── Lightweight migration: add columns if they don't exist yet ──
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
            ("workspace", "ALTER TABLE evaluations ADD COLUMN workspace VARCHAR(20) DEFAULT 'unknown'"),
        ]
        for col_name, ddl in migration_columns:
            if col_name not in existing_eval_cols:
                conn.execute(sa.text(ddl))

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
        existing_job_cols = {
            row[1]
            for row in conn.execute(sa.text("PRAGMA table_info(jobs)"))
        }
        job_migrations = [
            ("workspace", "ALTER TABLE jobs ADD COLUMN workspace VARCHAR(20) DEFAULT 'unknown'"),
        ]
        for col_name, ddl in job_migrations:
            if col_name not in existing_job_cols:
                conn.execute(sa.text(ddl))

        conn.commit()
