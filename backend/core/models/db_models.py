"""
Unified SQLAlchemy ORM models for database persistence.

Merges Banking and Compliance models into a single schema:
- Evaluation: unified with fields from both workspaces
- Issue: union of both field sets
- MetricResultRow: from Compliance (Banking adopts)
- Job: from Banking (Compliance adopts)
- CorrectionProposal: from Compliance
"""

import secrets
import string
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, String, Float, Text, DateTime,
    ForeignKey, Integer, BigInteger,
)
from sqlalchemy.orm import relationship

from core.database import Base


# ─── ID Generators ──────────────────────────────────────────────────────────

EVALUATION_ID_PREFIX = "C5iDQI"
EVALUATION_SUFFIX_LENGTH = 6
EVALUATION_SUFFIX_ALPHABET = string.ascii_uppercase + string.digits


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


def generate_evaluation_id() -> str:
    """Generate a branded evaluation ID like C5iDQI-YYYYMMDD-7K9M2P."""
    generated_on = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_suffix = "".join(
        secrets.choice(EVALUATION_SUFFIX_ALPHABET)
        for _ in range(EVALUATION_SUFFIX_LENGTH)
    )
    return f"{EVALUATION_ID_PREFIX}-{generated_on}-{unique_suffix}"


# ═══════════════════════════════════════════════════════════════════
# Background Job table (from Banking — Compliance adopts)
# ═══════════════════════════════════════════════════════════════════


class Job(Base):
    """Background evaluation job tracking table."""

    __tablename__ = "jobs"

    id: str = Column(String(36), primary_key=True, default=generate_uuid)
    filename: str = Column(String(255), nullable=False)
    file_path: str = Column(String(500), nullable=True)
    status: str = Column(String(20), nullable=False, default="queued")
    # queued → processing → completed | failed
    progress_message: str = Column(String(300), nullable=True)
    evaluation_id: str = Column(String(36), nullable=True)
    error_message: str = Column(Text, nullable=True)
    workspace: str = Column(String(20), nullable=True, default="unknown")
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, filename={self.filename}, status={self.status})>"


# ═══════════════════════════════════════════════════════════════════
# Core Evaluation tables (unified from both workspaces)
# ═══════════════════════════════════════════════════════════════════


class Evaluation(Base):
    """
    Unified evaluation record storing the full result of a document quality analysis.

    Contains fields from both Banking and Compliance workspaces:
    - Core fields: shared by both
    - Compliance fields: semantic_type, short_id
    - Banking fields: banking_domain, banking_metrics_json, banking_overall_score,
                      legal_hold, legal_hold_reason, remediation_plan_json
    """

    __tablename__ = "evaluations"

    id: str = Column(String(36), primary_key=True, default=generate_evaluation_id)
    short_id: str = Column(String(10), unique=True, index=True, nullable=True)
    filename: str = Column(String(255), nullable=False)
    document_type: str = Column(String(100), nullable=True)
    # Compliance: semantic document type (isms_policy, ai_policy, etc.)
    semantic_type: str = Column(String(50), nullable=True, default="general")
    overall_score: float = Column(Float, nullable=True)
    status: str = Column(String(20), nullable=False, default="pending")
    metrics_json: str = Column(Text, nullable=True)
    llm_raw_response: str = Column(Text, nullable=True)
    executive_summary: str = Column(Text, nullable=True)
    risk_summary: str = Column(Text, nullable=True)
    recommendations_json: str = Column(Text, nullable=True)
    extracted_fields_json: str = Column(Text, nullable=True)
    metric_reasoning_json: str = Column(Text, nullable=True)
    # Banking domain intelligence
    banking_domain: str = Column(String(100), nullable=True)
    banking_metrics_json: str = Column(Text, nullable=True)
    banking_overall_score: float = Column(Float, nullable=True)
    # Legal hold — triggered when critical banking dependencies fail
    legal_hold: bool = Column(Boolean, nullable=False, default=False)
    legal_hold_reason: str = Column(Text, nullable=True)
    # Remediation plan from remediation agent
    remediation_plan_json: str = Column(Text, nullable=True)
    # Workspace identifier
    workspace: str = Column(String(20), nullable=True, default="unknown")
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    issues = relationship("Issue", back_populates="evaluation", cascade="all, delete-orphan")
    metric_results = relationship("MetricResultRow", back_populates="evaluation", cascade="all, delete-orphan")
    correction_proposals = relationship("CorrectionProposal", back_populates="evaluation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, filename={self.filename}, score={self.overall_score})>"


class Issue(Base):
    """
    Unified issue detected during document quality evaluation.

    Contains fields from both workspaces:
    - Compliance: metric_name
    - Banking: regulation_reference, metric_dimension
    """

    __tablename__ = "issues"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: str = Column(
        String(36), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    field_name: str = Column(String(255), nullable=False)
    issue_type: str = Column(String(100), nullable=False)
    description: str = Column(Text, nullable=False)
    severity: str = Column(String(20), nullable=False)
    # Compliance field
    metric_name: str = Column(String(200), nullable=True)
    # Banking fields
    regulation_reference: str = Column(String(100), nullable=True)
    metric_dimension: str = Column(String(100), nullable=True)

    # Relationship
    evaluation = relationship("Evaluation", back_populates="issues")

    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, field={self.field_name}, severity={self.severity})>"


class MetricResultRow(Base):
    """
    Individual metric result stored as a first-class DB row.

    From Compliance — Banking adopts this for per-metric persistence.
    """

    __tablename__ = "metric_results"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: str = Column(
        String(36), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    metric_id: str = Column(String(100), nullable=False)
    name: str = Column(String(200), nullable=False)
    category: str = Column(String(20), nullable=False, default="core")
    score: float = Column(Float, nullable=False, default=0.0)
    severity: str = Column(String(20), nullable=True)
    details_json: str = Column(Text, nullable=True)
    linked_standards_json: str = Column(Text, nullable=True)

    # Relationship
    evaluation = relationship("Evaluation", back_populates="metric_results")

    def __repr__(self) -> str:
        return f"<MetricResultRow(metric_id={self.metric_id}, score={self.score})>"


class CorrectionProposal(Base):
    """Proposed corrections for a specific evaluation, grouped by metric."""

    __tablename__ = "correction_proposals"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: str = Column(
        String(36), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    metric_id: str = Column(String(100), nullable=False)
    field_path: str = Column(String(255), nullable=False)
    current_value: str = Column(Text, nullable=True)
    proposed_value: str = Column(Text, nullable=False)
    reason: str = Column(Text, nullable=False)
    auto_applicable: bool = Column(Boolean, nullable=False, default=False)
    applied: bool = Column(Boolean, nullable=False, default=False)
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    evaluation = relationship("Evaluation", back_populates="correction_proposals")

    def __repr__(self) -> str:
        return f"<CorrectionProposal(metric={self.metric_id}, field={self.field_path}, auto={self.auto_applicable})>"
