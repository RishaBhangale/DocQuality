"""
FastAPI API Routes.

Defines all REST endpoints for the document quality evaluation system.
Includes file upload, evaluation retrieval, and health check endpoints.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Request
from sqlalchemy.orm import Session

from compliance.config import settings
from compliance.database import get_db
from compliance.models.schemas import (
    ErrorResponse,
    EvaluationResponse,
    HealthResponse,
    UploadResponse,
)
from compliance.services.document_service import DocumentService
from compliance.services.evaluation_orchestrator import EvaluationOrchestrator
from compliance.services.visualization_service import VisualizationService

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple in-memory rate limiting dictionary for basic abuse protection
# Format: IP -> (request_count, window_reset_timestamp)
RATE_LIMIT_DB: dict[str, tuple[int, float]] = {}
RATE_LIMIT_MAX_REQUESTS = 5
RATE_LIMIT_WINDOW_SECONDS = 60

def check_rate_limit(request: Request):
    """Dependency to prevent IP flooding on expensive LLM endpoints."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    
    if client_ip in RATE_LIMIT_DB:
        count, reset_time = RATE_LIMIT_DB[client_ip]
        if now > reset_time:
            # Window expired, reset
            RATE_LIMIT_DB[client_ip] = (1, now + RATE_LIMIT_WINDOW_SECONDS)
        else:
            if count >= RATE_LIMIT_MAX_REQUESTS:
                raise HTTPException(
                    status_code=429, 
                    detail="Too many evaluation requests. Please wait a minute and try again."
                )
            RATE_LIMIT_DB[client_ip] = (count + 1, reset_time)
    else:
        RATE_LIMIT_DB[client_ip] = (1, now + RATE_LIMIT_WINDOW_SECONDS)

# Service instances
document_service = DocumentService()
orchestrator = EvaluationOrchestrator()
visualization_service = VisualizationService()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint.

    Returns system status and configuration information.
    """
    from compliance.services.llm_service import AzureFoundryLLMService
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
    """
    Test the LLM connection with a minimal request.

    Returns diagnostic information about whether the LLM is reachable.
    """
    from compliance.services.llm_service import AzureFoundryLLMService
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

    # Make a minimal test request
    try:
        url = llm._build_url()
        headers = llm._build_headers()
        payload = {
            "messages": [{"role": "user", "content": "Say hello in 3 words."}],
            "max_completion_tokens": 20,
        }

        # Add model field for serverless endpoints
        if llm._endpoint_type != "azure_openai":
            payload["model"] = llm.model

        start = time.time()
        resp = req.post(url, headers=headers, json=payload, timeout=30)
        elapsed = time.time() - start

        result["status_code"] = resp.status_code
        result["response_preview"] = resp.text[:500]

        if resp.status_code == 200:
            result["test_result"] = f"SUCCESS in {elapsed:.2f}s"
        else:
            result["test_result"] = f"FAILED with HTTP {resp.status_code}"
            result["error"] = resp.text[:500]
    except Exception as e:
        result["test_result"] = "FAILED"
        result["error"] = str(e)

    return result


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    tags=["Evaluation"],
)
async def evaluate_document(
    file: UploadFile = File(..., description="Document file to evaluate"),
    db: Session = Depends(get_db),
    _rate_limit: None = Depends(check_rate_limit),
):
    """
    Upload and evaluate a document for data quality.

    Accepts PDF, DOCX, TXT, PNG, JPG files up to 5MB.
    Triggers the full evaluation pipeline and returns structured results.

    Args:
        file: Uploaded document file.
        db: Database session (injected).

    Returns:
        Complete evaluation response with scores, metrics, and issues.
    """
    logger.info("Received evaluation request for file: %s", file.filename)

    # Validate file type
    try:
        document_service.validate_file_type(file.filename or "unknown")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Read file content
    content = await file.read()

    # Deep validate file content (prevent spoofing)
    try:
        document_service.validate_file_content(content, file.filename or "unknown")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate file size
    try:
        document_service.validate_file_size(len(content))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Save file temporarily
    file_path = await document_service.save_upload(file.filename or "document", content)

    try:
        # Run evaluation pipeline
        result = await orchestrator.evaluate_document(
            file_path=file_path,
            filename=file.filename or "document",
            db=db,
        )
        return result

    except RuntimeError as e:
        logger.error("Evaluation failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.exception("Unexpected error during evaluation")
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during evaluation: {str(e)}",
        )

    finally:
        # Clean up uploaded file
        document_service.cleanup_file(file_path)


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
    """
    Retrieve a stored evaluation by ID.

    Args:
        evaluation_id: UUID of the evaluation.
        db: Database session (injected).

    Returns:
        Complete evaluation response.
    """
    result = orchestrator.get_evaluation_by_id(evaluation_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return result


@router.get(
    "/evaluation/{evaluation_id}/charts",
    tags=["Visualization"],
)
async def get_evaluation_charts(
    evaluation_id: str,
    db: Session = Depends(get_db),
):
    """
    Get visualization chart data for an evaluation.

    Returns structured chart data (gauge, radar, bar, pie) that the
    frontend can render using charting libraries.

    Args:
        evaluation_id: UUID of the evaluation.
        db: Database session (injected).

    Returns:
        Chart data dictionary.
    """
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


@router.get(
    "/evaluations",
    tags=["Evaluation"],
)
async def list_evaluations(
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """
    List recent evaluations.

    Args:
        limit: Maximum number of evaluations to return.
        db: Database session (injected).

    Returns:
        List of evaluation summaries.
    """
    from compliance.models.db_models import Evaluation

    evaluations = (
        db.query(Evaluation)
        .order_by(Evaluation.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "evaluation_id": e.id,
            "short_id": e.short_id,
            "filename": e.filename,
            "document_type": e.document_type,
            "overall_score": e.overall_score,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in evaluations
    ]


# ── Phase 2: Corrections & Pipeline endpoints ──────────────────


@router.get(
    "/evaluations/{evaluation_id}/corrections",
    tags=["Corrections"],
)
async def get_corrections(
    evaluation_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve all correction proposals for an evaluation.

    Returns proposals grouped by metric_id, each with field_path,
    current_value, proposed_value, reason, and auto_applicable flag.
    """
    from compliance.services.correction_service import CorrectionService
    svc = CorrectionService()
    corrections = svc.get_corrections(evaluation_id, db)
    if not corrections:
        return {"corrections": [], "total": 0}

    # Group by metric
    grouped: dict = {}
    for c in corrections:
        key = c["metric_id"]
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(c)

    return {
        "corrections": corrections,
        "grouped": grouped,
        "total": len(corrections),
    }


@router.get(
    "/evaluations/{evaluation_id}/pipeline",
    tags=["Pipeline"],
)
async def get_pipeline_status(
    evaluation_id: str,
    db: Session = Depends(get_db),
):
    """
    Retrieve pipeline ingestion audit trail for an evaluation.

    Returns the sequence of pipeline stages (ingest → extract →
    normalize → evaluate) with status, timing, and messages.
    """
    from compliance.models.db_models import Evaluation, IngestionEvent

    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    events = []
    if evaluation.document_raw_id:
        events = (
            db.query(IngestionEvent)
            .filter(IngestionEvent.document_raw_id == evaluation.document_raw_id)
            .order_by(IngestionEvent.created_at)
            .all()
        )

    return {
        "evaluation_id": evaluation_id,
        "document_raw_id": evaluation.document_raw_id,
        "stages": [
            {
                "stage": e.stage,
                "status": e.status,
                "message": e.message,
                "duration_ms": e.duration_ms,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.post(
    "/evaluations/{evaluation_id}/corrections/{proposal_id}/apply",
    tags=["Corrections"],
)
async def apply_correction(
    evaluation_id: str,
    proposal_id: int,
    db: Session = Depends(get_db),
):
    """
    Mark a specific correction proposal as applied.
    """
    from compliance.models.db_models import CorrectionProposal
    
    proposal = db.query(CorrectionProposal).filter(
        CorrectionProposal.id == proposal_id,
        CorrectionProposal.evaluation_id == evaluation_id
    ).first()
    
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
        
    proposal.applied = True
    db.commit()
    return {"status": "success", "applied": True}


@router.get(
    "/evaluations/{evaluation_id}/download-fixed",
    tags=["Corrections"],
)
async def download_fixed_document(
    evaluation_id: str,
    db: Session = Depends(get_db),
):
    """
    Apply accepted corrections to the extracted document text
    and return it as a downloadable file.
    """
    from fastapi.responses import PlainTextResponse
    from compliance.models.db_models import Evaluation, CorrectionProposal
    
    evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
    if not evaluation or not evaluation.document_raw_id:
        raise HTTPException(status_code=404, detail="Evaluation or source document not found")
        
    extracted = evaluation.document_raw.extracted
    if not extracted or not extracted.raw_text:
        raise HTTPException(status_code=404, detail="Extracted document text not found")
        
    # Get all applied proposals
    applied_proposals = db.query(CorrectionProposal).filter(
        CorrectionProposal.evaluation_id == evaluation_id,
        CorrectionProposal.applied == True,
        CorrectionProposal.auto_applicable == True
    ).all()
    
    # Simple search & replace for deterministic fixes
    patched_text = extracted.raw_text
    applied_count = 0
    
    for p in applied_proposals:
        if p.current_value and p.current_value in patched_text:
            if p.metric_id == "validity" and p.field_path == "dates":
                # Special hack for date formatting since PoC proposed value is text
                patched_text = patched_text.replace(p.current_value, "YYYY-MM-DD")
            else:
                patched_text = patched_text.replace(p.current_value, p.proposed_value)
            applied_count += 1
            
    filename = evaluation.filename
    base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    out_filename = f"{base_name}_fixed.md"
    
    return PlainTextResponse(
        content=patched_text,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{out_filename}"',
            "X-Applied-Corrections": str(applied_count)
        }
    )
