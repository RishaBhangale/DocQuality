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


# ═══════════════════════════════════════════════════════════════════
# Phase 2 — Bronze / Silver / Gold pipeline tables
# ═══════════════════════════════════════════════════════════════════


class DocumentRaw(Base):
    """Bronze layer — raw document metadata and file hash for dedup."""

    __tablename__ = "document_raw"

    id: str = Column(String(36), primary_key=True, default=generate_uuid)
    file_hash: str = Column(String(64), nullable=False, unique=True, index=True)
    filename: str = Column(String(255), nullable=False)
    mime_type: str = Column(String(100), nullable=True)
    size_bytes: int = Column(BigInteger, nullable=True)
    storage_uri: str = Column(Text, nullable=True)
    ingested_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    extracted = relationship("DocumentExtracted", back_populates="raw", uselist=False, cascade="all, delete-orphan")
    evaluations = relationship("Evaluation", back_populates="document_raw")
    ingestion_events = relationship("IngestionEvent", back_populates="document_raw", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DocumentRaw(id={self.id}, filename={self.filename}, hash={self.file_hash[:8]}…)>"


class DocumentExtracted(Base):
    """Silver layer — extracted text, classified type, and language detection."""

    __tablename__ = "document_extracted"

    id: str = Column(String(36), primary_key=True, default=generate_uuid)
    document_raw_id: str = Column(
        String(36), ForeignKey("document_raw.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    semantic_type: str = Column(String(50), nullable=False, default="general")
    language: str = Column(String(10), nullable=True, default="en")
    token_count: int = Column(Integer, nullable=True)
    raw_text: str = Column(Text, nullable=True)
    extracted_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    raw = relationship("DocumentRaw", back_populates="extracted")
    normalized = relationship("DocumentNormalized", back_populates="extracted", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<DocumentExtracted(id={self.id}, type={self.semantic_type}, tokens={self.token_count})>"


class DocumentNormalized(Base):
    """Gold layer — structured, validated fields per semantic type."""

    __tablename__ = "document_normalized"

    id: str = Column(String(36), primary_key=True, default=generate_uuid)
    document_extracted_id: str = Column(
        String(36), ForeignKey("document_extracted.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    version: int = Column(Integer, nullable=False, default=1)
    structured_fields_json: str = Column(Text, nullable=True)
    validation_errors_json: str = Column(Text, nullable=True)
    normalized_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    extracted = relationship("DocumentExtracted", back_populates="normalized")

    def __repr__(self) -> str:
        return f"<DocumentNormalized(id={self.id}, version={self.version})>"


class IngestionEvent(Base):
    """Audit log for pipeline ingestion steps — observability."""

    __tablename__ = "ingestion_events"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    document_raw_id: str = Column(
        String(36), ForeignKey("document_raw.id", ondelete="CASCADE"), nullable=False
    )
    stage: str = Column(String(30), nullable=False)  # ingest | extract | normalize | evaluate
    status: str = Column(String(20), nullable=False, default="success")  # success | failed
    message: str = Column(Text, nullable=True)
    duration_ms: int = Column(Integer, nullable=True)
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    document_raw = relationship("DocumentRaw", back_populates="ingestion_events")

    def __repr__(self) -> str:
        return f"<IngestionEvent(stage={self.stage}, status={self.status})>"


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
    # Phase 2: link to bronze layer
    document_raw_id: str = Column(
        String(36), ForeignKey("document_raw.id", ondelete="SET NULL"), nullable=True
    )
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    issues = relationship("Issue", back_populates="evaluation", cascade="all, delete-orphan")
    metric_results = relationship("MetricResultRow", back_populates="evaluation", cascade="all, delete-orphan")
    correction_proposals = relationship("CorrectionProposal", back_populates="evaluation", cascade="all, delete-orphan")
    document_raw = relationship("DocumentRaw", back_populates="evaluations")

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
