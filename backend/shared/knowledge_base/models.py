"""
SQLAlchemy ORM models for Knowledge Base metadata.

Vector embeddings are stored in ChromaDB (separate from SQLite).
These models only track document metadata and KB state.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Text, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship, declarative_base

KBBase = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


class KnowledgeBase(KBBase):
    """One knowledge base per workspace (compliance / banking)."""

    __tablename__ = "knowledge_bases"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    workspace: str = Column(String(20), nullable=False, unique=True, index=True)  # "compliance" | "banking"
    name: str = Column(String(255), nullable=False, default="Default Knowledge Base")
    description: str = Column(Text, nullable=True)
    status: str = Column(String(20), nullable=False, default="empty")  # empty | building | ready | error
    document_count: int = Column(Integer, nullable=False, default=0)
    chunk_count: int = Column(Integer, nullable=False, default=0)
    created_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Column(
        DateTime, nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    documents = relationship("KBDocument", back_populates="knowledge_base", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<KnowledgeBase(workspace={self.workspace}, docs={self.document_count}, status={self.status})>"


class KBDocument(KBBase):
    """Each uploaded reference file within a knowledge base."""

    __tablename__ = "kb_documents"

    id: str = Column(String(36), primary_key=True, default=_uuid)
    knowledge_base_id: str = Column(
        String(36), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    filename: str = Column(String(255), nullable=False)
    file_hash: str = Column(String(64), nullable=False, index=True)
    file_size: int = Column(Integer, nullable=True)
    domain_validation_status: str = Column(String(20), nullable=False, default="pending")  # pending | valid | rejected
    domain_validation_reason: str = Column(Text, nullable=True)
    domain_confidence: float = Column(Float, nullable=True)
    chunk_count: int = Column(Integer, nullable=False, default=0)
    uploaded_at: datetime = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")

    def __repr__(self) -> str:
        return f"<KBDocument(filename={self.filename}, status={self.domain_validation_status})>"
