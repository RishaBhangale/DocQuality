"""
FastAPI API Routes.

Defines all REST endpoints for the document quality evaluation system.
Includes file upload (async job pattern), evaluation retrieval,
job status polling, history with filters, and health check endpoints.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from banking.config import settings
from banking.database import get_db
from banking.models.db_models import Evaluation, Job
from banking.models.schemas import (
    ErrorResponse,
    EvaluationResponse,
    HealthResponse,
    JobResponse,
    JobStatus,
    UploadResponse,
)
from banking.services.document_service import DocumentService
from banking.services.evaluation_orchestrator import EvaluationOrchestrator, evaluate_document_job
from banking.services.report_service import ReportService
from banking.services.visualization_service import VisualizationService

logger = logging.getLogger(__name__)

router = APIRouter()

# Service instances
document_service = DocumentService()
orchestrator = EvaluationOrchestrator()
visualization_service = VisualizationService()
report_service = ReportService()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Health check — returns system status and LLM configuration info."""
    from banking.services.llm_service import AzureFoundryLLMService
    llm = AzureFoundryLLMService()

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        llm_configured=llm.is_configured,
        llm_endpoint_type=llm._endpoint_type if llm.is_configured else "not_configured",
        llm_model=settings.FOUNDRY_MODEL or "not_set",
        llm_endpoint_set=bool(settings.FOUNDRY_ENDPOINT),
        llm_key_set=bool(settings.FOUNDRY_API_KEY),
    )


@router.get("/debug/llm-test", tags=["Debug"])
async def test_llm_connection():
    """Test the LLM connection with a minimal request."""
    from banking.services.llm_service import AzureFoundryLLMService
    import requests as req
    import time

    llm = AzureFoundryLLMService()

    result = {
        "configured": llm.is_configured,
        "endpoint_type": llm._endpoint_type,
        "model": llm.model,
        "endpoint_preview": llm.endpoint[:80] + "..." if len(llm.endpoint) > 80 else llm.endpoint,
        "url_built": llm._build_url(),
        "test_result": None,
        "error": None,
        "status_code": None,
        "response_preview": None,
    }

    if not llm.is_configured:
        result["error"] = "LLM not configured. Set FOUNDRY_API_KEY and FOUNDRY_ENDPOINT in .env"
        return result

    try:
        url = llm._build_url()
        headers = llm._build_headers()
        payload = {
            "messages": [{"role": "user", "content": "Say hello in 3 words."}],
            "max_completion_tokens": 20,
        }
        if llm._endpoint_type != "azure_openai":
            payload["model"] = llm.model

        start = time.time()
        resp = req.post(url, headers=headers, json=payload, timeout=30)
        elapsed = time.time() - start

        result["status_code"] = resp.status_code
        result["response_preview"] = resp.text[:500]
        result["test_result"] = (
            f"SUCCESS in {elapsed:.2f}s" if resp.status_code == 200
            else f"FAILED with HTTP {resp.status_code}"
        )
        if resp.status_code != 200:
            result["error"] = resp.text[:500]
    except Exception as exc:
        result["test_result"] = "FAILED"
        result["error"] = str(exc)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation endpoints (async job pattern)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/evaluate",
    response_model=JobResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["Evaluation"],
)
async def start_evaluation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to evaluate"),
    db: Session = Depends(get_db),
):
    """
    Upload a document and start an async evaluation job.

    The file is saved to disk and an evaluation job is queued immediately.
    A job_id is returned so the client can poll GET /api/job/{job_id}
    for progress, then fetch GET /api/evaluation/{evaluation_id} on completion.

    Accepts: PDF, DOCX, PNG, JPG, JPEG, XLSX, XLS
    """
    logger.info("Received evaluation request for file: %s", file.filename)

    try:
        document_service.validate_file_type(file.filename or "unknown")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    content = await file.read()

    try:
        document_service.validate_file_size(len(content))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Save file permanently — background task will clean it up
    file_path = await document_service.save_upload(file.filename or "document", content)
    filename = file.filename or "document"

    # Create job record
    job_id = str(uuid.uuid4())
    job = Job(
        id=job_id,
        filename=filename,
        file_path=file_path,
        status="queued",
        progress_message="Job queued — waiting for worker…",
    )
    db.add(job)
    db.commit()

    # Queue background evaluation (creates its own DB session)
    background_tasks.add_task(evaluate_document_job, job_id, file_path, filename)

    logger.info("Queued evaluation job %s for %s", job_id, filename)
    return JobResponse(
        job_id=job_id,
        filename=filename,
        status="queued",
        message="Evaluation started. Poll GET /api/job/{job_id} for progress.",
    )


@router.get(
    "/job/{job_id}",
    response_model=JobStatus,
    responses={404: {"model": ErrorResponse}},
    tags=["Evaluation"],
)
async def get_job_status(
    job_id: str,
    db: Session = Depends(get_db),
):
    """
    Poll the status of an async evaluation job.

    status values:
      queued → processing → completed | failed

    When status=completed, evaluation_id is populated and you can call
    GET /api/evaluation/{evaluation_id} for the full results.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatus(
        job_id=job.id,
        filename=job.filename,
        status=job.status,
        progress_message=job.progress_message or "",
        evaluation_id=job.evaluation_id,
        error_message=job.error_message,
        created_at=job.created_at,
    )


@router.get(
    "/evaluation/{evaluation_id}",
    response_model=EvaluationResponse,
    responses={404: {"model": ErrorResponse}},
    tags=["Evaluation"],
)
async def get_evaluation(
    evaluation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a completed evaluation by its ID."""
    result = orchestrator.get_evaluation_by_id(evaluation_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return result


@router.get("/evaluation/{evaluation_id}/report", tags=["Evaluation"])
async def download_evaluation_report(
    evaluation_id: str,
    db: Session = Depends(get_db),
):
    """Generate and download a professional PDF report for an evaluation."""
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


@router.get("/evaluation/{evaluation_id}/charts", tags=["Visualization"])
async def get_evaluation_charts(evaluation_id: str, db: Session = Depends(get_db)):
    """Get chart data for a completed evaluation."""
    result = orchestrator.get_evaluation_by_id(evaluation_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    charts = visualization_service.generate_full_visualization_data(
        overall_score=result.overall_score,
        status=result.overall_status,
        metrics=result.metrics,
        issues=result.issues,
    )
    return charts


@router.get("/evaluations", tags=["Evaluation"])
async def list_evaluations(
    limit: int = 20,
    offset: int = 0,
    domain: Optional[str] = None,
    legal_hold: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    List evaluations with optional filters for the history panel.

    Query params:
      - domain: filter by banking_domain substring
      - legal_hold: true/false to filter by legal hold status
      - search: filename substring search
      - limit / offset: pagination
    """
    query = db.query(Evaluation).order_by(Evaluation.created_at.desc())

    if domain:
        query = query.filter(Evaluation.banking_domain.ilike(f"%{domain}%"))
    if legal_hold is not None:
        query = query.filter(Evaluation.legal_hold == legal_hold)
    if search:
        query = query.filter(Evaluation.filename.ilike(f"%{search}%"))

    total = query.count()
    evaluations = query.offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "evaluation_id": e.id,
                "filename": e.filename,
                "document_type": e.document_type,
                "overall_score": e.overall_score,
                "banking_domain": e.banking_domain,
                "banking_overall_score": e.banking_overall_score,
                "legal_hold": e.legal_hold or False,
                "status": e.status,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in evaluations
        ],
    }


# ── Knowledge Base endpoints ───────────────────────────────────────────────

def _get_kb_service():
    """Create a KnowledgeBaseService for the banking workspace."""
    from shared.knowledge_base.service import KnowledgeBaseService
    return KnowledgeBaseService(
        workspace="banking",
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
    Upload a reference document to the banking knowledge base.

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
    """Get the current status of the banking knowledge base."""
    kb_service = _get_kb_service()
    return kb_service.get_status(kb_db)


@router.get("/knowledge-base/documents", tags=["Knowledge Base"])
async def list_kb_documents(kb_db: Session = Depends(_get_kb_db)):
    """List all documents in the banking knowledge base."""
    kb_service = _get_kb_service()
    return {"documents": kb_service.list_documents(kb_db)}


@router.delete("/knowledge-base/documents/{doc_id}", tags=["Knowledge Base"])
async def remove_kb_document(doc_id: str, kb_db: Session = Depends(_get_kb_db)):
    """Remove a specific document from the banking knowledge base."""
    kb_service = _get_kb_service()
    result = kb_service.remove_document(doc_id, kb_db)

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "Document not found"))

    return result


@router.delete("/knowledge-base", tags=["Knowledge Base"])
async def clear_kb(kb_db: Session = Depends(_get_kb_db)):
    """Clear the entire banking knowledge base."""
    kb_service = _get_kb_service()
    return kb_service.clear_kb(kb_db)

