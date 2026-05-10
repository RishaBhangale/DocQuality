"""
FastAPI API Routes.

Defines all REST endpoints for the document quality evaluation system.
Includes file upload, evaluation retrieval, and health check endpoints.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from compliance.config import settings
from compliance.database import get_db, SessionLocal
from compliance.models.schemas import (
    ErrorResponse,
    EvaluationResponse,
    HealthResponse,
    UploadResponse,
)
from compliance.models.db_models import Evaluation
from compliance.services.document_service import DocumentService
from compliance.services.evaluation_orchestrator import EvaluationOrchestrator
from compliance.services.visualization_service import VisualizationService
from compliance.services.report_service import ReportService

logger = logging.getLogger(__name__)

from core.api.base_routes import create_base_router

router = create_base_router(
    workspace_name="compliance",
    orchestrator_cls=EvaluationOrchestrator,
    session_factory=SessionLocal,
    get_db=get_db,
    evaluation_model=Evaluation,
)

# Service instances for compliance-specific endpoints
document_service = DocumentService()
orchestrator = EvaluationOrchestrator()
report_service = ReportService()


@router.get("/evaluation/{evaluation_id}/report", tags=["Evaluation"])
async def download_evaluation_report(
    evaluation_id: str,
    db: Session = Depends(get_db),
):
    """Generate and download a PDF report for a compliance evaluation."""
    result = orchestrator.get_evaluation_by_id(evaluation_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    try:
        pdf_buffer = report_service.build_evaluation_report(result)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to generate report for %s: %s", evaluation_id, exc)
        raise HTTPException(status_code=500, detail="Failed to generate PDF report") from exc

    filename = report_service.build_report_filename(result.filename)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(pdf_buffer, media_type="application/pdf", headers=headers)


# ── Knowledge Base endpoints ───────────────────────────────────────────────

def _get_kb_service():
    """Create a KnowledgeBaseService for the compliance workspace."""
    from shared.knowledge_base.service import KnowledgeBaseService
    return KnowledgeBaseService(
        workspace="compliance",
        api_key=settings.FOUNDRY_API_KEY,
        endpoint=settings.FOUNDRY_ENDPOINT,
        model=settings.FOUNDRY_MODEL,
        api_version=settings.FOUNDRY_API_VERSION,
    )


def _get_kb_db():
    """Get a KB metadata database session."""
    from shared.knowledge_base.service import get_kb_session
    db = get_kb_session()
    try:
        yield db
    finally:
        db.close()


@router.post("/knowledge-base/upload", tags=["Knowledge Base"])
async def upload_kb_document(
    file: UploadFile = File(..., description="Reference document to add to the knowledge base"),
    kb_db: Session = Depends(_get_kb_db),
):
    """
    Upload a reference document to the compliance knowledge base.

    The document will be validated for domain relevance, then chunked
    and embedded for future RAG retrieval during evaluations.
    """
    logger.info("KB upload request: %s", file.filename)

    filename = file.filename or "document"

    # Validate file type (restrict to text-heavy formats)
    allowed_ext = {".pdf", ".docx", ".txt", ".md", ".doc"}
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in allowed_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Knowledge base accepts: {', '.join(sorted(allowed_ext))}",
        )

    content = await file.read()

    # Validate file size (5MB max per file)
    max_size = 5 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum: {max_size // (1024*1024)}MB")

    # Save file temporarily
    file_path = await document_service.save_upload(filename, content)

    try:
        kb_service = _get_kb_service()
        result = kb_service.add_document(file_path, filename, kb_db)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Upload failed"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("KB upload failed for %s", filename)
        raise HTTPException(status_code=500, detail=f"Knowledge base upload failed: {str(e)}")
    finally:
        document_service.cleanup_file(file_path)


@router.get("/knowledge-base/status", tags=["Knowledge Base"])
async def get_kb_status(kb_db: Session = Depends(_get_kb_db)):
    """Get the current status of the compliance knowledge base."""
    kb_service = _get_kb_service()
    return kb_service.get_status(kb_db)


@router.get("/knowledge-base/documents", tags=["Knowledge Base"])
async def list_kb_documents(kb_db: Session = Depends(_get_kb_db)):
    """List all documents in the compliance knowledge base."""
    kb_service = _get_kb_service()
    return {"documents": kb_service.list_documents(kb_db)}


@router.delete("/knowledge-base/documents/{doc_id}", tags=["Knowledge Base"])
async def remove_kb_document(doc_id: str, kb_db: Session = Depends(_get_kb_db)):
    """Remove a specific document from the compliance knowledge base."""
    kb_service = _get_kb_service()
    result = kb_service.remove_document(doc_id, kb_db)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Document not found"))

    return result


@router.delete("/knowledge-base", tags=["Knowledge Base"])
async def clear_kb(kb_db: Session = Depends(_get_kb_db)):
    """Clear the entire compliance knowledge base."""
    kb_service = _get_kb_service()
    return kb_service.clear_kb(kb_db)

