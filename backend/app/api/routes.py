"""
FastAPI API Routes.

Defines all REST endpoints for the document quality evaluation system.
Includes file upload, evaluation retrieval, and health check endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.schemas import (
    ErrorResponse,
    EvaluationResponse,
    HealthResponse,
    UploadResponse,
)
from app.services.document_service import DocumentService
from app.services.evaluation_orchestrator import EvaluationOrchestrator
from app.services.visualization_service import VisualizationService

logger = logging.getLogger(__name__)

router = APIRouter()

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
    from app.services.llm_service import AzureFoundryLLMService
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
    from app.services.llm_service import AzureFoundryLLMService
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
):
    """
    Upload and evaluate a document for data quality.

    Accepts PDF, DOCX, PNG, JPG files up to 5MB.
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
    from app.models.db_models import Evaluation

    evaluations = (
        db.query(Evaluation)
        .order_by(Evaluation.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "evaluation_id": e.id,
            "filename": e.filename,
            "document_type": e.document_type,
            "overall_score": e.overall_score,
            "status": e.status,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in evaluations
    ]
