"""
SQLAlchemy ORM models for database persistence.

Defines the evaluations, issues, and jobs tables for storing
document quality evaluation results and background job state.
"""

import secrets
import string
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, String, Float, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from banking.database import Base


EVALUATION_ID_PREFIX = "C5iDQI"
EVALUATION_SUFFIX_LENGTH = 6
EVALUATION_SUFFIX_ALPHABET = string.ascii_uppercase + string.digits


def generate_job_uuid() -> str:
    """Generate a UUID for job tracking records."""
    return str(uuid.uuid4())


def generate_evaluation_id() -> str:
    """Generate an evaluation ID like C5iDQI-YYYYMMDD-7K9M2P."""
    generated_on = datetime.now(timezone.utc).strftime("%Y%m%d")
    unique_suffix = "".join(
        secrets.choice(EVALUATION_SUFFIX_ALPHABET)
        for _ in range(EVALUATION_SUFFIX_LENGTH)
    )
    return f"{EVALUATION_ID_PREFIX}-{generated_on}-{unique_suffix}"


class Job(Base):
    """Background evaluation job tracking table."""

    __tablename__ = "jobs"

    id: str = Column(String(36), primary_key=True, default=generate_job_uuid)
    filename: str = Column(String(255), nullable=False)
    file_path: str = Column(String(500), nullable=True)
    status: str = Column(String(20), nullable=False, default="queued")
    # queued → processing → completed | failed
    progress_message: str = Column(String(300), nullable=True)
    evaluation_id: str = Column(String(36), nullable=True)
    error_message: str = Column(Text, nullable=True)
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, filename={self.filename}, status={self.status})>"


class Evaluation(Base):
    """Evaluation record storing the full result of a document quality analysis."""

    __tablename__ = "evaluations"

    id: str = Column(String(36), primary_key=True, default=generate_evaluation_id)
    filename: str = Column(String(255), nullable=False)
    document_type: str = Column(String(100), nullable=True)
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
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship to issues
    issues = relationship("Issue", back_populates="evaluation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, filename={self.filename}, score={self.overall_score})>"


class Issue(Base):
    """Individual issue detected during document quality evaluation."""

    __tablename__ = "issues"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_id: str = Column(
        String(36), ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    field_name: str = Column(String(255), nullable=False)
    issue_type: str = Column(String(100), nullable=False)
    description: str = Column(Text, nullable=False)
    severity: str = Column(String(20), nullable=False)
    regulation_reference: str = Column(String(100), nullable=True)
    metric_dimension: str = Column(String(100), nullable=True)

    # Relationship back to evaluation
    evaluation = relationship("Evaluation", back_populates="issues")

    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, field={self.field_name}, severity={self.severity})>"
