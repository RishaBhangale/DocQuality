#!/usr/bin/env python3
"""
Database Migration Script — Unified Schema.

Reads existing Banking and Compliance SQLite databases and migrates
their data into a single unified database used by the core module.

Usage:
    cd backend/
    python -m scripts.migrate_databases

The script:
1. Creates the unified DB at data/unified/document_quality.db
2. Reads Banking data from data/banking/document_quality.db
3. Reads Compliance data from data/compliance/document_quality.db
4. Maps both into the unified schema, handling column mismatches
5. Reports migration statistics
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add backend to path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

import sqlalchemy as sa
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.database import Base, _default_database_url, init_db


def _get_engine(db_path: Path):
    """Create an engine for a SQLite file."""
    if not db_path.exists():
        return None
    url = f"sqlite:///{db_path.as_posix()}"
    return create_engine(url, connect_args={"check_same_thread": False}, echo=False)


def _table_exists(engine, table_name: str) -> bool:
    """Check if a table exists in the database."""
    with engine.connect() as conn:
        result = conn.execute(
            text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        )
        return result.fetchone() is not None


def _get_columns(engine, table_name: str) -> set[str]:
    """Get column names for a table."""
    with engine.connect() as conn:
        result = conn.execute(text(f"PRAGMA table_info({table_name})"))
        return {row[1] for row in result}


def migrate_evaluations(source_engine, target_session, workspace: str, stats: dict):
    """Migrate evaluations from a workspace DB to the unified DB."""
    if not _table_exists(source_engine, "evaluations"):
        print(f"  ⚠ No evaluations table in {workspace} DB — skipping")
        return

    source_cols = _get_columns(source_engine, "evaluations")
    count = 0

    with source_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM evaluations")).mappings().all()

        for row in rows:
            row_dict = dict(row)
            eval_id = row_dict.get("id", "")

            # Check if already migrated
            existing = target_session.execute(
                text("SELECT id FROM evaluations WHERE id = :id"),
                {"id": eval_id},
            ).fetchone()
            if existing:
                continue

            # Build unified evaluation record
            target_session.execute(
                text("""
                    INSERT INTO evaluations (
                        id, short_id, filename, document_type, semantic_type,
                        overall_score, status, metrics_json, llm_raw_response,
                        executive_summary, risk_summary, recommendations_json,
                        extracted_fields_json, metric_reasoning_json,
                        banking_domain, banking_metrics_json, banking_overall_score,
                        legal_hold, legal_hold_reason, remediation_plan_json,
                        workspace, created_at
                    ) VALUES (
                        :id, :short_id, :filename, :document_type, :semantic_type,
                        :overall_score, :status, :metrics_json, :llm_raw_response,
                        :executive_summary, :risk_summary, :recommendations_json,
                        :extracted_fields_json, :metric_reasoning_json,
                        :banking_domain, :banking_metrics_json, :banking_overall_score,
                        :legal_hold, :legal_hold_reason, :remediation_plan_json,
                        :workspace, :created_at
                    )
                """),
                {
                    "id": eval_id,
                    "short_id": row_dict.get("short_id"),
                    "filename": row_dict.get("filename", "unknown"),
                    "document_type": row_dict.get("document_type"),
                    "semantic_type": row_dict.get("semantic_type", "general"),
                    "overall_score": row_dict.get("overall_score"),
                    "status": row_dict.get("status", "pending"),
                    "metrics_json": row_dict.get("metrics_json"),
                    "llm_raw_response": row_dict.get("llm_raw_response"),
                    "executive_summary": row_dict.get("executive_summary"),
                    "risk_summary": row_dict.get("risk_summary"),
                    "recommendations_json": row_dict.get("recommendations_json"),
                    "extracted_fields_json": row_dict.get("extracted_fields_json"),
                    "metric_reasoning_json": row_dict.get("metric_reasoning_json"),
                    "banking_domain": row_dict.get("banking_domain"),
                    "banking_metrics_json": row_dict.get("banking_metrics_json"),
                    "banking_overall_score": row_dict.get("banking_overall_score"),
                    "legal_hold": bool(row_dict.get("legal_hold", False)),
                    "legal_hold_reason": row_dict.get("legal_hold_reason"),
                    "remediation_plan_json": row_dict.get("remediation_plan_json"),
                    "workspace": workspace,
                    "created_at": row_dict.get("created_at", datetime.now(timezone.utc).isoformat()),
                },
            )
            count += 1

    target_session.commit()
    stats[f"{workspace}_evaluations"] = count
    print(f"  ✓ Migrated {count} evaluations from {workspace}")


def migrate_issues(source_engine, target_session, workspace: str, stats: dict):
    """Migrate issues from a workspace DB to the unified DB."""
    if not _table_exists(source_engine, "issues"):
        print(f"  ⚠ No issues table in {workspace} DB — skipping")
        return

    source_cols = _get_columns(source_engine, "issues")
    count = 0

    with source_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM issues")).mappings().all()

        for row in rows:
            row_dict = dict(row)

            # Check if evaluation exists in target
            eval_id = row_dict.get("evaluation_id")
            eval_exists = target_session.execute(
                text("SELECT id FROM evaluations WHERE id = :id"),
                {"id": eval_id},
            ).fetchone()
            if not eval_exists:
                continue

            target_session.execute(
                text("""
                    INSERT INTO issues (
                        evaluation_id, field_name, issue_type, description, severity,
                        metric_name, regulation_reference, metric_dimension
                    ) VALUES (
                        :evaluation_id, :field_name, :issue_type, :description, :severity,
                        :metric_name, :regulation_reference, :metric_dimension
                    )
                """),
                {
                    "evaluation_id": eval_id,
                    "field_name": row_dict.get("field_name", "unknown"),
                    "issue_type": row_dict.get("issue_type", "unknown"),
                    "description": row_dict.get("description", ""),
                    "severity": row_dict.get("severity", "warning"),
                    "metric_name": row_dict.get("metric_name"),
                    "regulation_reference": row_dict.get("regulation_reference"),
                    "metric_dimension": row_dict.get("metric_dimension"),
                },
            )
            count += 1

    target_session.commit()
    stats[f"{workspace}_issues"] = count
    print(f"  ✓ Migrated {count} issues from {workspace}")


def migrate_jobs(source_engine, target_session, workspace: str, stats: dict):
    """Migrate jobs from a workspace DB to the unified DB."""
    if not _table_exists(source_engine, "jobs"):
        return

    count = 0
    with source_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM jobs")).mappings().all()

        for row in rows:
            row_dict = dict(row)
            job_id = row_dict.get("id", "")

            existing = target_session.execute(
                text("SELECT id FROM jobs WHERE id = :id"),
                {"id": job_id},
            ).fetchone()
            if existing:
                continue

            target_session.execute(
                text("""
                    INSERT INTO jobs (
                        id, filename, file_path, status, progress_message,
                        evaluation_id, error_message, workspace, created_at, completed_at
                    ) VALUES (
                        :id, :filename, :file_path, :status, :progress_message,
                        :evaluation_id, :error_message, :workspace, :created_at, :completed_at
                    )
                """),
                {
                    "id": job_id,
                    "filename": row_dict.get("filename", "unknown"),
                    "file_path": row_dict.get("file_path"),
                    "status": row_dict.get("status", "completed"),
                    "progress_message": row_dict.get("progress_message"),
                    "evaluation_id": row_dict.get("evaluation_id"),
                    "error_message": row_dict.get("error_message"),
                    "workspace": workspace,
                    "created_at": row_dict.get("created_at"),
                    "completed_at": row_dict.get("completed_at"),
                },
            )
            count += 1

    target_session.commit()
    stats[f"{workspace}_jobs"] = count
    if count > 0:
        print(f"  ✓ Migrated {count} jobs from {workspace}")


def migrate_metric_results(source_engine, target_session, workspace: str, stats: dict):
    """Migrate metric_results from a workspace DB to the unified DB."""
    if not _table_exists(source_engine, "metric_results"):
        return

    count = 0
    with source_engine.connect() as conn:
        rows = conn.execute(text("SELECT * FROM metric_results")).mappings().all()

        for row in rows:
            row_dict = dict(row)
            eval_id = row_dict.get("evaluation_id")

            eval_exists = target_session.execute(
                text("SELECT id FROM evaluations WHERE id = :id"),
                {"id": eval_id},
            ).fetchone()
            if not eval_exists:
                continue

            target_session.execute(
                text("""
                    INSERT INTO metric_results (
                        evaluation_id, metric_id, name, category, score,
                        severity, details_json, linked_standards_json
                    ) VALUES (
                        :evaluation_id, :metric_id, :name, :category, :score,
                        :severity, :details_json, :linked_standards_json
                    )
                """),
                {
                    "evaluation_id": eval_id,
                    "metric_id": row_dict.get("metric_id", ""),
                    "name": row_dict.get("name", ""),
                    "category": row_dict.get("category", "core"),
                    "score": row_dict.get("score", 0.0),
                    "severity": row_dict.get("severity"),
                    "details_json": row_dict.get("details_json"),
                    "linked_standards_json": row_dict.get("linked_standards_json"),
                },
            )
            count += 1

    target_session.commit()
    stats[f"{workspace}_metric_results"] = count
    if count > 0:
        print(f"  ✓ Migrated {count} metric results from {workspace}")


def main():
    print("=" * 60)
    print("DocQuality — Database Migration to Unified Schema")
    print("=" * 60)

    data_dir = _BACKEND_DIR / "data"
    banking_db = data_dir / "banking" / "document_quality.db"
    compliance_db = data_dir / "compliance" / "document_quality.db"
    unified_dir = data_dir / "unified"

    # Create unified directory
    unified_dir.mkdir(parents=True, exist_ok=True)

    # Create unified DB with schema
    unified_url = _default_database_url("unified")
    unified_engine = create_engine(
        unified_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
    init_db(unified_engine)
    print(f"\n✓ Created unified database at: {unified_dir / 'document_quality.db'}")

    UnifiedSession = sessionmaker(bind=unified_engine)
    session = UnifiedSession()

    stats: dict[str, int] = {}

    # ── Migrate Banking ──
    print(f"\n── Banking ({banking_db}) ──")
    banking_engine = _get_engine(banking_db)
    if banking_engine:
        migrate_evaluations(banking_engine, session, "banking", stats)
        migrate_issues(banking_engine, session, "banking", stats)
        migrate_jobs(banking_engine, session, "banking", stats)
        migrate_metric_results(banking_engine, session, "banking", stats)
    else:
        print("  ⚠ Banking database not found — skipping")

    # ── Migrate Compliance ──
    print(f"\n── Compliance ({compliance_db}) ──")
    compliance_engine = _get_engine(compliance_db)
    if compliance_engine:
        migrate_evaluations(compliance_engine, session, "compliance", stats)
        migrate_issues(compliance_engine, session, "compliance", stats)
        migrate_jobs(compliance_engine, session, "compliance", stats)
        migrate_metric_results(compliance_engine, session, "compliance", stats)
    else:
        print("  ⚠ Compliance database not found — skipping")

    session.close()

    # ── Summary ──
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    for key, count in sorted(stats.items()):
        print(f"  {key}: {count}")
    total = sum(stats.values())
    print(f"\n  Total records migrated: {total}")
    print("=" * 60)
    print("Done. ✓")


if __name__ == "__main__":
    main()
