import logging
import os
import uuid
import asyncio
from typing import Optional, Callable, Type

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.models.db_models import Job, Evaluation
from core.models.schemas import (
    ErrorResponse,
    EvaluationResponse,
    JobResponse,
    JobStatus,
    HealthResponse,
)
from core.services.document_service import DocumentService

logger = logging.getLogger(__name__)

def update_job(db: Session, job_id: str, status: str, progress: str = "", evaluation_id: str = None, error_message: str = None):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job:
        job.status = status
        if progress:
            job.progress_message = progress
        if evaluation_id:
            job.evaluation_id = evaluation_id
        if error_message:
            job.error_message = error_message
        if status in ["completed", "failed"]:
            from datetime import datetime, timezone
            job.completed_at = datetime.now(timezone.utc)
        db.commit()

def create_base_router(
    workspace_name: str,
    orchestrator_cls: Type,
    session_factory: Callable[[], Session],
    get_db: Callable,
    evaluation_model: Type = Evaluation,
) -> APIRouter:
    """
    Creates a FastAPI router with unified endpoints for document evaluation
    using the async background job pattern.
    """
    router = APIRouter()
    document_service = DocumentService()
    
    @router.get("/health", response_model=HealthResponse, tags=["System"])
    async def health_check():
        from core.services.base_llm_service import BaseLLMService
        from core.config import settings
        llm = BaseLLMService()
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
        from core.services.base_llm_service import BaseLLMService
        import requests as req
        import time
        llm = BaseLLMService()
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
            if resp.status_code == 200:
                result["test_result"] = f"SUCCESS in {elapsed:.2f}s"
            else:
                result["test_result"] = f"FAILED with HTTP {resp.status_code}"
                result["error"] = resp.text[:500]
        except Exception as e:
            result["test_result"] = "FAILED"
            result["error"] = str(e)
        return result

    def evaluate_document_job(job_id: str, file_path: str, filename: str):
        db = session_factory()
        try:
            update_job(db, job_id, status="processing", progress="Initialising evaluation pipeline…")
            orchestrator = orchestrator_cls()
            
            # Banking orchestrator takes job_id
            import inspect
            sig = inspect.signature(orchestrator.evaluate_document)
            
            kwargs = {}
            if "job_id" in sig.parameters:
                kwargs["job_id"] = job_id
                
            result = asyncio.run(
                orchestrator.evaluate_document(file_path=file_path, filename=filename, db=db, **kwargs)
            )
            
            update_job(db, job_id, status="completed", evaluation_id=result.evaluation_id)
            logger.info("Job %s completed: evaluation_id=%s", job_id, result.evaluation_id)
        except Exception as exc:
            try:
                db.rollback()
            except Exception as rb_exc:
                logger.warning("Failed to rollback database session: %s", rb_exc)
            logger.exception("Job %s failed: %s", job_id, exc)
            update_job(db, job_id, status="failed", error_message=str(exc)[:500])
        finally:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except OSError as cleanup_error:
                logger.warning("Failed to clean up temporary file %s: %s", file_path, cleanup_error)
            finally:
                try:
                    db.close()
                except Exception as db_error:
                    logger.warning("Failed to close database session: %s", db_error)

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
        logger.info("[%s] Received evaluation request for file: %s", workspace_name, file.filename)
        
        try:
            document_service.validate_file_type(file.filename or "unknown")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
            
        content = await file.read()
        
        max_size = 5 * 1024 * 1024  # 5 MB
        if len(content) > max_size:
            raise HTTPException(status_code=400, detail=f"File too large ({len(content)} bytes). Maximum size: {max_size // (1024*1024)}MB.")
            
        file_path = await document_service.save_upload(file.filename or "document", content)
        filename = file.filename or "document"
        
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            filename=filename,
            file_path=file_path,
            status="queued",
            progress_message="Job queued — waiting for worker…",
            workspace=workspace_name,
        )
        db.add(job)
        db.commit()
        
        background_tasks.add_task(evaluate_document_job, job_id, file_path, filename)
        
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
    async def get_job_status(job_id: str, db: Session = Depends(get_db)):
        job = db.query(Job).filter(Job.id == job_id, Job.workspace == workspace_name).first()
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
    async def get_evaluation(evaluation_id: str, db: Session = Depends(get_db)):
        orchestrator = orchestrator_cls()
        result = orchestrator.get_evaluation_by_id(evaluation_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        return result

    @router.get("/evaluation/{evaluation_id}/charts", tags=["Visualization"])
    async def get_evaluation_charts(evaluation_id: str, db: Session = Depends(get_db)):
        from core.services.visualization_service import VisualizationService
        visualization_service = VisualizationService()
        orchestrator = orchestrator_cls()
        result = orchestrator.get_evaluation_by_id(evaluation_id, db)
        if not result:
            raise HTTPException(status_code=404, detail="Evaluation not found")
        # Prefer core metrics for radar/bar when split exists (compliance-style UX)
        chart_metrics = result.metrics
        core = getattr(result, "core_metrics", None)
        if core:
            chart_metrics = core

        charts = visualization_service.generate_full_visualization_data(
            overall_score=result.overall_score,
            status=result.overall_status,
            metrics=chart_metrics,
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
        model = evaluation_model
        query = db.query(model)
        if hasattr(model, "workspace"):
            query = query.filter(
                or_(
                    model.workspace == workspace_name,
                    model.workspace.is_(None),
                    model.workspace == "",
                    model.workspace == "unknown",
                )
            )
        if hasattr(model, "created_at"):
            query = query.order_by(model.created_at.desc())
        else:
            query = query.order_by(model.id.desc())
        
        if domain and hasattr(model, "banking_domain"):
            query = query.filter(model.banking_domain.ilike(f"%{domain}%"))
        if legal_hold is not None and hasattr(model, "legal_hold"):
            query = query.filter(model.legal_hold == legal_hold)
        if search and hasattr(model, "filename"):
            query = query.filter(model.filename.ilike(f"%{search}%"))
            
        total = query.count()
        evaluations = query.offset(offset).limit(limit).all()
        
        return {
            "total": total,
            "items": [
                {
                    "evaluation_id": getattr(e, "id", None),
                    "short_id": getattr(e, "short_id", None),
                    "filename": getattr(e, "filename", None),
                    "document_type": getattr(e, "document_type", None),
                    "overall_score": getattr(e, "overall_score", None),
                    "overall_status": getattr(e, "status", None),
                    "banking_domain": getattr(e, "banking_domain", None),
                    "banking_overall_score": getattr(e, "banking_overall_score", None),
                    "legal_hold": bool(getattr(e, "legal_hold", False)),
                    "created_at": getattr(e, "created_at", None).isoformat() if getattr(e, "created_at", None) else None,
                }
                for e in evaluations
            ],
        }

    return router
