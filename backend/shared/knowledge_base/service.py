"""
Knowledge Base Service.

Core orchestration layer for knowledge base operations:
- Add/remove reference documents
- Domain validation
- Text extraction, chunking, and embedding
- RAG retrieval for evaluation pipeline
"""

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from shared.knowledge_base.models import KBBase, KnowledgeBase, KBDocument
from shared.knowledge_base.embeddings import (
    chunk_text,
    add_chunks_to_collection,
    remove_chunks_for_document,
    query_collection,
    clear_collection,
    get_collection_stats,
)
from shared.knowledge_base.domain_validator import validate_domain, ValidationResult

logger = logging.getLogger(__name__)

# ── KB Database (separate from app databases) ────────────────────────────────

_kb_engine = None
_KBSessionLocal = None


def _get_kb_db_path() -> str:
    """Get path to the KB metadata database."""
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_base"
    data_dir.mkdir(parents=True, exist_ok=True)
    return str(data_dir / "kb_metadata.db")


def get_kb_session() -> Session:
    """Get a new KB database session."""
    global _kb_engine, _KBSessionLocal

    if _kb_engine is None:
        db_path = _get_kb_db_path()
        db_url = f"sqlite:///{db_path}"
        _kb_engine = create_engine(db_url, connect_args={"check_same_thread": False}, echo=False)
        KBBase.metadata.create_all(bind=_kb_engine)
        _KBSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_kb_engine)
        logger.info("KB metadata database initialized at: %s", db_path)

    return _KBSessionLocal()


# ── Text Extraction (reuse existing services) ───────────────────────────────

def _extract_text_from_file(file_path: str) -> str:
    """
    Extract text from a document file.

    Tries compliance DocumentService first (supports PDF, DOCX, TXT, MD).
    """
    try:
        from compliance.services.document_service import DocumentService
        svc = DocumentService()
        return svc.extract_text(file_path)
    except Exception as e:
        logger.warning("Compliance DocumentService failed, trying basic extraction: %s", e)

    # Basic fallback for TXT files
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash for deduplication."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ── Main Service Class ───────────────────────────────────────────────────────

# Max limits
MAX_DOCUMENTS_PER_KB = 20
MAX_TOTAL_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


class KnowledgeBaseService:
    """
    Manages knowledge base operations for a specific workspace.

    Each workspace (compliance / banking) has its own isolated knowledge base
    with separate ChromaDB collection and metadata records.
    """

    def __init__(
        self,
        workspace: str,
        *,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_version: Optional[str] = None,
    ):
        if workspace not in ("compliance", "banking"):
            raise ValueError(f"Invalid workspace: {workspace}. Must be 'compliance' or 'banking'.")

        self.workspace = workspace
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.api_version = api_version

    # ── KB CRUD ──────────────────────────────────────────────────────────────

    def get_or_create_kb(self, db: Session) -> KnowledgeBase:
        """Get or create the knowledge base for this workspace."""
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.workspace == self.workspace).first()
        if not kb:
            kb = KnowledgeBase(
                workspace=self.workspace,
                name=f"{self.workspace.title()} Knowledge Base",
                status="empty",
            )
            db.add(kb)
            db.commit()
            db.refresh(kb)
            logger.info("Created new knowledge base for workspace: %s", self.workspace)
        return kb

    def get_status(self, db: Session) -> dict:
        """Get the current status of the knowledge base."""
        kb = self.get_or_create_kb(db)
        chroma_stats = get_collection_stats(self.workspace)

        docs = db.query(KBDocument).filter(
            KBDocument.knowledge_base_id == kb.id,
            KBDocument.domain_validation_status == "valid",
        ).all()

        return {
            "workspace": self.workspace,
            "status": kb.status,
            "document_count": len(docs),
            "chunk_count": chroma_stats["total_chunks"],
            "name": kb.name,
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        }

    def list_documents(self, db: Session) -> list[dict]:
        """List all documents in this knowledge base."""
        kb = self.get_or_create_kb(db)
        docs = db.query(KBDocument).filter(
            KBDocument.knowledge_base_id == kb.id,
        ).order_by(KBDocument.uploaded_at.desc()).all()

        return [
            {
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "status": doc.domain_validation_status,
                "reason": doc.domain_validation_reason,
                "confidence": doc.domain_confidence,
                "chunk_count": doc.chunk_count,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
            }
            for doc in docs
        ]

    # ── Add Document ─────────────────────────────────────────────────────────

    def add_document(
        self,
        file_path: str,
        filename: str,
        db: Session,
    ) -> dict:
        """
        Add a reference document to the knowledge base.

        Steps:
        1. Check limits (document count, total size)
        2. Extract text
        3. Validate domain relevance
        4. Chunk text
        5. Embed and store in ChromaDB
        6. Update metadata

        Returns a dict with status, document info, and validation result.
        """
        kb = self.get_or_create_kb(db)

        # ── Check limits ──────────────────────────────────────────────────
        valid_docs = db.query(KBDocument).filter(
            KBDocument.knowledge_base_id == kb.id,
            KBDocument.domain_validation_status == "valid",
        ).all()

        if len(valid_docs) >= MAX_DOCUMENTS_PER_KB:
            return {
                "success": False,
                "error": f"Maximum document limit reached ({MAX_DOCUMENTS_PER_KB}). "
                         "Remove existing documents before adding new ones.",
            }

        total_size = sum(d.file_size or 0 for d in valid_docs)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        if total_size + file_size > MAX_TOTAL_SIZE_BYTES:
            return {
                "success": False,
                "error": f"Total KB size would exceed {MAX_TOTAL_SIZE_BYTES // (1024*1024)}MB limit.",
            }

        # ── Check for duplicate ───────────────────────────────────────────
        file_hash = _compute_file_hash(file_path)
        existing = db.query(KBDocument).filter(
            KBDocument.knowledge_base_id == kb.id,
            KBDocument.file_hash == file_hash,
        ).first()

        if existing:
            return {
                "success": False,
                "error": f"Document '{existing.filename}' is already in the knowledge base (duplicate detected).",
            }

        # ── Extract text ──────────────────────────────────────────────────
        document_text = _extract_text_from_file(file_path)
        if not document_text or len(document_text.strip()) < 100:
            return {
                "success": False,
                "error": "Could not extract sufficient text from the document. "
                         "The file may be empty, corrupted, or contain only images.",
            }

        # ── Domain validation ─────────────────────────────────────────────
        validation = validate_domain(
            document_text,
            self.workspace,
            api_key=self.api_key,
            endpoint=self.endpoint,
            model=self.model,
            api_version=self.api_version,
        )

        # Create document record
        kb_doc = KBDocument(
            knowledge_base_id=kb.id,
            filename=filename,
            file_hash=file_hash,
            file_size=file_size,
            domain_validation_status="valid" if validation.is_valid else "rejected",
            domain_validation_reason=validation.reason,
            domain_confidence=validation.confidence,
        )
        db.add(kb_doc)

        if not validation.is_valid:
            db.commit()
            return {
                "success": False,
                "error": f"Domain validation failed: {validation.reason}",
                "validation": {
                    "is_valid": False,
                    "reason": validation.reason,
                    "confidence": validation.confidence,
                },
                "document_id": kb_doc.id,
            }

        # ── Chunk and embed ───────────────────────────────────────────────
        kb.status = "building"
        db.commit()

        chunks = chunk_text(document_text)
        chunk_count = add_chunks_to_collection(
            workspace=self.workspace,
            doc_id=kb_doc.id,
            filename=filename,
            chunks=chunks,
        )

        # ── Update metadata ───────────────────────────────────────────────
        kb_doc.chunk_count = chunk_count

        # Recount valid documents
        valid_count = db.query(KBDocument).filter(
            KBDocument.knowledge_base_id == kb.id,
            KBDocument.domain_validation_status == "valid",
        ).count()

        chroma_stats = get_collection_stats(self.workspace)

        kb.document_count = valid_count
        kb.chunk_count = chroma_stats["total_chunks"]
        kb.status = "ready" if valid_count > 0 else "empty"
        kb.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info(
            "Added document '%s' to %s KB: %d chunks, validation=%s",
            filename, self.workspace, chunk_count, validation.is_valid,
        )

        return {
            "success": True,
            "document": {
                "id": kb_doc.id,
                "filename": filename,
                "chunk_count": chunk_count,
                "file_size": file_size,
            },
            "validation": {
                "is_valid": True,
                "reason": validation.reason,
                "confidence": validation.confidence,
            },
            "kb_status": {
                "document_count": valid_count,
                "chunk_count": chroma_stats["total_chunks"],
                "status": kb.status,
            },
        }

    # ── Remove Document ──────────────────────────────────────────────────────

    def remove_document(self, doc_id: str, db: Session) -> dict:
        """Remove a document from the knowledge base."""
        kb = self.get_or_create_kb(db)

        doc = db.query(KBDocument).filter(
            KBDocument.id == doc_id,
            KBDocument.knowledge_base_id == kb.id,
        ).first()

        if not doc:
            return {"success": False, "error": "Document not found."}

        # Remove from ChromaDB
        removed = remove_chunks_for_document(self.workspace, doc_id)

        # Remove from database
        db.delete(doc)

        # Recount
        valid_count = db.query(KBDocument).filter(
            KBDocument.knowledge_base_id == kb.id,
            KBDocument.domain_validation_status == "valid",
            KBDocument.id != doc_id,  # Exclude the one being deleted
        ).count()

        chroma_stats = get_collection_stats(self.workspace)

        kb.document_count = valid_count
        kb.chunk_count = chroma_stats["total_chunks"]
        kb.status = "ready" if valid_count > 0 else "empty"
        kb.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info("Removed document %s from %s KB (%d chunks)", doc_id, self.workspace, removed)

        return {
            "success": True,
            "removed_chunks": removed,
            "kb_status": {
                "document_count": valid_count,
                "chunk_count": chroma_stats["total_chunks"],
                "status": kb.status,
            },
        }

    # ── Clear KB ─────────────────────────────────────────────────────────────

    def clear_kb(self, db: Session) -> dict:
        """Clear the entire knowledge base (all documents and chunks)."""
        kb = self.get_or_create_kb(db)

        # Clear ChromaDB
        removed = clear_collection(self.workspace)

        # Clear documents from DB
        db.query(KBDocument).filter(KBDocument.knowledge_base_id == kb.id).delete()

        kb.document_count = 0
        kb.chunk_count = 0
        kb.status = "empty"
        kb.updated_at = datetime.now(timezone.utc)

        db.commit()

        logger.info("Cleared %s KB: %d chunks removed", self.workspace, removed)

        return {
            "success": True,
            "removed_chunks": removed,
        }

    # ── RAG Retrieval ────────────────────────────────────────────────────────

    def retrieve_context(
        self,
        query_text: str,
        top_k: int = 5,
    ) -> list[str]:
        """
        Retrieve relevant reference chunks for evaluation context.

        This is the method called by the evaluation orchestrator to
        inject KB context into LLM prompts.

        Returns a list of text strings (the relevant chunks).
        """
        results = query_collection(
            workspace=self.workspace,
            query_text=query_text[:3000],  # Limit query text for embedding
            top_k=top_k,
        )

        if not results:
            return []

        # Filter by minimum relevance score
        MIN_SCORE = 0.3
        relevant = [r for r in results if r.get("score", 0) >= MIN_SCORE]

        context_chunks = []
        for r in relevant:
            source = r.get("filename", "unknown")
            text = r.get("text", "")
            context_chunks.append(f"[Source: {source}]\n{text}")

        logger.info(
            "Retrieved %d/%d relevant chunks from %s KB (query: %d chars)",
            len(context_chunks), len(results), self.workspace, len(query_text[:3000]),
        )

        return context_chunks

    def is_ready(self, db: Session) -> bool:
        """Check if the knowledge base has indexed documents and is ready for retrieval."""
        kb = self.get_or_create_kb(db)
        return kb.status == "ready" and kb.document_count > 0
