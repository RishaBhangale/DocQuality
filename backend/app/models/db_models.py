"""
SQLAlchemy ORM models for database persistence.

Defines the evaluations and issues tables for storing
document quality evaluation results.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database import Base


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


class Evaluation(Base):
    """Evaluation record storing the full result of a document quality analysis."""

    __tablename__ = "evaluations"

    id: str = Column(String(36), primary_key=True, default=generate_uuid)
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
    type_specific_metrics_json: str = Column(Text, nullable=True)
    type_specific_score: float = Column(Float, nullable=True)
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

    # Relationship back to evaluation
    evaluation = relationship("Evaluation", back_populates="issues")

    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, field={self.field_name}, severity={self.severity})>"
