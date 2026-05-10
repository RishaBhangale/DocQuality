"""
SQLAlchemy ORM models for database persistence.

Defines the evaluations, metric_results, issues tables (Phase 1)
and Bronze/Silver/Gold pipeline tables (Phase 2).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Integer, Boolean, BigInteger
from sqlalchemy.orm import relationship

from compliance.database import Base


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())



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


# ═══════════════════════════════════════════════════════════════════
# Phase 1 — Core evaluation tables
# ═══════════════════════════════════════════════════════════════════


class Evaluation(Base):
    """Evaluation record storing the full result of a document quality analysis."""

    __tablename__ = "evaluations"

    id: str = Column(String(36), primary_key=True, default=generate_uuid)
    short_id: str = Column(String(10), unique=True, index=True, nullable=True)
    filename: str = Column(String(255), nullable=False)
    document_type: str = Column(String(100), nullable=True)
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

    workspace: str = Column(String(20), nullable=True, default="compliance")

    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    issues = relationship("Issue", back_populates="evaluation", cascade="all, delete-orphan")
    metric_results = relationship("MetricResultRow", back_populates="evaluation", cascade="all, delete-orphan")
    correction_proposals = relationship("CorrectionProposal", back_populates="evaluation", cascade="all, delete-orphan")


    def __repr__(self) -> str:
        return f"<Evaluation(id={self.id}, filename={self.filename}, score={self.overall_score})>"


class MetricResultRow(Base):
    """Individual metric result stored as a first-class DB row."""

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
    metric_name: str = Column(String(200), nullable=True)

    # Relationship
    evaluation = relationship("Evaluation", back_populates="issues")

    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, field={self.field_name}, severity={self.severity})>"
