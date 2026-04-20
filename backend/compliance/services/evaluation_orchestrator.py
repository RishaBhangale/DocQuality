"""
Evaluation Orchestrator.

The brain of the system. Coordinates the full evaluation workflow:
1. Ingest → Bronze layer (DocumentRaw with file hash + dedup)
2. Extract text → Silver layer (DocumentExtracted)
3. Classify semantic type via LLM
4. Resolve applicable metrics from config
5. Call LLM for dynamic structured extraction + reasoning
6. Run deterministic rule engine for all applicable metrics
7. Blend deterministic and LLM scores
8. Normalize → Gold layer (DocumentNormalized)
9. Persist to database (MetricResultRow + Evaluation)
10. Generate correction proposals
11. Return structured response
"""

import hashlib
import json
import logging
import os
import time
from typing import Optional

from sqlalchemy.orm import Session

from compliance.config import (
    MetricDefinition,
    LinkedStandardRef,
    get_metrics_for_type,
    get_core_metrics,
    get_type_specific_metrics,
    DOC_TYPE_TO_STANDARDS,
    STANDARDS_CATALOG,
)
from compliance.models.db_models import (
    Evaluation, Issue, MetricResultRow,
    DocumentRaw, DocumentExtracted, IngestionEvent,
)
from compliance.models.schemas import (
    EvaluationResponse,
    IssueSchema,
    LLMExtractionResponse,
    MetricResult,
    LinkedStandardResponse,
)
from compliance.services.document_service import DocumentService
from compliance.services.llm_service import AzureFoundryLLMService
from compliance.services.rule_engine import execute_rule
from compliance.services.scoring_engine import ScoringEngine
from compliance.services.visualization_service import VisualizationService
from compliance.services.normalization_service import NormalizationService
from compliance.services.correction_service import CorrectionService

logger = logging.getLogger(__name__)


class EvaluationOrchestrator:
    """
    Orchestrates the complete document quality evaluation pipeline.

    Combines LLM-assisted extraction with deterministic rule evaluation
    to produce a hybrid quality assessment, routed dynamically by
    semantic document type.
    """

    def __init__(self) -> None:
        """Initialize all service dependencies."""
        self.document_service = DocumentService()
        self.llm_service = AzureFoundryLLMService()
        self.scoring_engine = ScoringEngine()
        self.visualization_service = VisualizationService()
        self.normalization_service = NormalizationService()
        self.correction_service = CorrectionService()

    async def evaluate_document(
        self, file_path: str, filename: str, db: Session
    ) -> EvaluationResponse:
        """Execute the full evaluation pipeline for a document."""
        logger.info("Starting evaluation for: %s", filename)

        # ── Step 1: Ingest → Bronze layer ─────────────────────────────────
        logger.info("Step 1: Ingesting document into bronze layer...")
        t0 = time.time()
        document_text = self.document_service.extract_text(file_path)

        if not document_text.strip():
            raise RuntimeError(
                "No text could be extracted from the document. "
                "The file may be empty, corrupted, or contain only images without OCR support."
            )

        # Hash file for dedup
        file_hash = self._compute_file_hash(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        # Upsert bronze record
        doc_raw = db.query(DocumentRaw).filter(DocumentRaw.file_hash == file_hash).first()
        if not doc_raw:
            doc_raw = DocumentRaw(
                file_hash=file_hash,
                filename=filename,
                mime_type=self._guess_mime(filename),
                size_bytes=file_size,
                storage_uri=file_path,
            )
            db.add(doc_raw)
            db.flush()

        # Log ingestion event
        ingest_ms = int((time.time() - t0) * 1000)
        db.add(IngestionEvent(
            document_raw_id=doc_raw.id, stage="ingest",
            status="success", message=f"Extracted {len(document_text)} chars",
            duration_ms=ingest_ms,
        ))

        logger.info("Extracted %d characters | Hash: %s", len(document_text), file_hash[:12])

        # ── Step 2: Classify → Silver layer ──────────────────────────────
        logger.info("Step 2: Classifying document semantic type...")
        t1 = time.time()
        semantic_type = self.llm_service.classify_semantic_type(document_text)
        logger.info("Document classified as: %s", semantic_type)

        # Create/update silver record
        doc_extracted = doc_raw.extracted
        if not doc_extracted:
            doc_extracted = DocumentExtracted(
                document_raw_id=doc_raw.id,
                semantic_type=semantic_type,
                token_count=len(document_text.split()),
                raw_text=document_text[:50000],  # cap storage
            )
            db.add(doc_extracted)
            db.flush()

        classify_ms = int((time.time() - t1) * 1000)
        db.add(IngestionEvent(
            document_raw_id=doc_raw.id, stage="extract",
            status="success", message=f"Type: {semantic_type}",
            duration_ms=classify_ms,
        ))

        # ── Step 3: Resolve applicable metrics ───────────────────────────
        logger.info("Step 3: Resolving applicable metrics...")
        active_metrics = get_metrics_for_type(semantic_type)
        core_metric_defs = [m for m in active_metrics if m.category == "core"]
        type_specific_defs = [m for m in active_metrics if m.category == "type_specific"]
        logger.info(
            "Active metrics: %d core + %d type-specific = %d total",
            len(core_metric_defs), len(type_specific_defs), len(active_metrics),
        )

        # ── Step 4: Call LLM for dynamic extraction ──────────────────────
        llm_response: Optional[LLMExtractionResponse] = None
        llm_raw: str = ""

        try:
            if self.llm_service.is_configured:
                # Setup KB RAG retrieval
                reference_context = []
                try:
                    from shared.knowledge_base.service import KnowledgeBaseService, get_kb_session
                    from compliance.config import settings
                    kb_db = get_kb_session()
                    kb_service = KnowledgeBaseService(
                        workspace="compliance",
                        api_key=settings.FOUNDRY_API_KEY,
                        endpoint=settings.FOUNDRY_ENDPOINT,
                        model=settings.FOUNDRY_MODEL,
                        api_version=settings.FOUNDRY_API_VERSION,
                    )
                    if kb_service.is_ready(kb_db):
                        logger.info("KB is ready. Retrieving reference context for RAG...")
                        reference_context = kb_service.retrieve_context(document_text)
                    kb_db.close()
                except Exception as exc:
                    logger.warning("Failed to retrieve KB context during evaluation: %s", exc)

                logger.info("Step 4: Calling LLM with dynamic prompt (%d metrics)...", len(active_metrics))
                llm_response, llm_raw = self.llm_service.extract_and_evaluate(
                    document_text,
                    semantic_type=semantic_type,
                    metrics=active_metrics,
                    reference_context=reference_context,
                )
                logger.info("LLM extraction successful. Document type: %s", llm_response.document_type)
            else:
                logger.warning("LLM not configured. Using fallback response.")
                llm_response = self.llm_service.get_fallback_response(document_text, semantic_type)
        except RuntimeError as e:
            logger.error("LLM extraction failed: %s. Falling back.", str(e))
            llm_response = self.llm_service.get_fallback_response(document_text, semantic_type)

        # ── Step 5: Run deterministic rule engine for all metrics ────────
        logger.info("Step 5: Running deterministic rule engine...")
        fields = llm_response.fields if llm_response else {}
        document_type = llm_response.document_type if llm_response else "unknown"

        all_issues: list[IssueSchema] = []
        deterministic_scores: dict[str, float] = {}
        metric_issues_map: dict[str, list[IssueSchema]] = {}

        for metric_def in active_metrics:
            score, issues = execute_rule(metric_def.rule_fn, fields, document_text)
            
            # Inject metric_name into deterministically generated issues
            for issue in issues:
                issue.metric_name = metric_def.name
                
            deterministic_scores[metric_def.id] = score
            metric_issues_map[metric_def.id] = issues
            all_issues.extend(issues)

        # ── Step 6: Blend with LLM semantic scores ──────────────────────
        logger.info("Step 6: Blending deterministic and LLM scores...")
        blended_scores: dict[str, float] = {}
        llm_scores = llm_response.semantic_scores if llm_response else {}

        for metric_def in active_metrics:
            det_score = deterministic_scores.get(metric_def.id, 0.0)
            llm_score = llm_scores.get(metric_def.id, 0.0)

            if llm_score > 0:
                blended_scores[metric_def.id] = self.scoring_engine.blend_scores(det_score, llm_score)
            else:
                blended_scores[metric_def.id] = det_score

        # ── Step 7: Build MetricResult objects ──────────────────────────
        logger.info("Step 7: Building metric results...")
        overall_score = self.scoring_engine.apply_weighted_scoring(blended_scores, active_metrics)
        overall_status = self.scoring_engine.determine_status(overall_score)

        metric_reasoning = llm_response.metric_reasoning if llm_response else {}

        all_metric_results: list[MetricResult] = []
        core_metrics: list[MetricResult] = []
        type_specific_metrics: list[MetricResult] = []

        for metric_def in active_metrics:
            clamped = self.scoring_engine.clamp_score(blended_scores.get(metric_def.id, 0.0))
            status = self.scoring_engine.determine_metric_status(clamped)
            issues_for_metric = metric_issues_map.get(metric_def.id, [])

            # Inject fallback issue if score is low but no issues
            if clamped < 70 and not issues_for_metric:
                fallback_issue = IssueSchema(
                    field_name=f"{metric_def.name} Semantic Analysis",
                    issue_type="Low Semantic Confidence",
                    description=(
                        f"AI contextually evaluated {metric_def.name} with a low score, "
                        f"indicating a significant risk or missing information."
                    ),
                    severity="critical" if clamped < 40 else "warning",
                    metric_name=metric_def.name,
                )
                issues_for_metric.append(fallback_issue)
                all_issues.append(fallback_issue)

            # Build linked standards response
            linked_standards = [
                LinkedStandardResponse(
                    standard_id=ls.standard_id,
                    control_id=ls.control_id,
                    clause=ls.clause,
                    description=ls.description,
                )
                for ls in metric_def.linked_standards
            ]

            result = MetricResult(
                id=metric_def.id,
                name=metric_def.name,
                category=metric_def.category,
                score=clamped,
                description=metric_def.description,
                status_message=self.scoring_engine.get_status_message(
                    metric_def.name, clamped, issues_for_metric,
                ),
                status=status,
                weight=metric_def.weight,
                reasoning=metric_reasoning.get(metric_def.id, ""),
                linked_standards=linked_standards,
            )

            all_metric_results.append(result)
            if metric_def.category == "core":
                core_metrics.append(result)
            else:
                type_specific_metrics.append(result)

        # Select 2 primary type-specific metrics (lowest-scoring)
        primary_type_metrics = sorted(
            type_specific_metrics, key=lambda m: m.score
        )[:2] if type_specific_metrics else []

        # ── Step 8: Normalize → Gold layer ───────────────────────────────
        logger.info("Step 8: Normalizing to gold layer...")
        t2 = time.time()
        try:
            normalized = self.normalization_service.normalize(
                extracted=doc_extracted,
                llm_fields=fields,
                db=db,
            )
            norm_ms = int((time.time() - t2) * 1000)
            db.add(IngestionEvent(
                document_raw_id=doc_raw.id, stage="normalize",
                status="success", message=f"v{normalized.version}",
                duration_ms=norm_ms,
            ))
        except Exception as e:
            logger.warning("Normalization failed (non-fatal): %s", str(e))
            db.add(IngestionEvent(
                document_raw_id=doc_raw.id, stage="normalize",
                status="failed", message=str(e)[:200],
            ))

        # ── Step 9: Persist evaluation ───────────────────────────────────
        logger.info("Step 9: Persisting evaluation to database...")
        evaluation = self._persist_evaluation(
            db=db,
            filename=filename,
            document_type=document_type,
            semantic_type=semantic_type,
            overall_score=overall_score,
            overall_status=overall_status,
            metrics=all_metric_results,
            issues=all_issues,
            llm_raw=llm_raw,
            llm_response=llm_response,
            document_raw_id=doc_raw.id,
        )

        # ── Step 10: Generate correction proposals ──────────────────────
        logger.info("Step 10: Generating correction proposals...")
        corrections = self.correction_service.generate_corrections(
            evaluation_id=evaluation.id,
            metrics=all_metric_results,
            fields=fields,
            raw_text=document_text,
            db=db,
        )
        db.commit()

        # ── Step 11: Build pipeline status ───────────────────────────────
        pipeline_status = {
            "ingest": "success",
            "extract": "success",
            "normalize": "success",
            "evaluate": "success",
            "corrections": len(corrections),
        }

        # ── Step 12: Return response ─────────────────────────────────────
        logger.info(
            "Evaluation complete: %s | Type: %s | Score: %.1f | Status: %s | Metrics: %d | Corrections: %d",
            filename, semantic_type, overall_score, overall_status,
            len(all_metric_results), len(corrections),
        )

        return EvaluationResponse(
            evaluation_id=evaluation.id,
            filename=filename,
            document_type=document_type,
            semantic_type=semantic_type,
            overall_score=overall_score,
            overall_status=overall_status,
            core_metrics=core_metrics,
            type_specific_metrics=type_specific_metrics,
            primary_type_metrics=primary_type_metrics,
            metrics=all_metric_results,
            issues=all_issues,
            executive_summary=llm_response.executive_summary if llm_response else "",
            risk_summary=llm_response.risk_summary if llm_response else "",
            recommendations=llm_response.recommendations if llm_response else [],
            pipeline_status=pipeline_status,
            corrections_count=len(corrections),
            created_at=evaluation.created_at,
        )

    def _persist_evaluation(
        self, db: Session,
        filename: str, document_type: str, semantic_type: str,
        overall_score: float, overall_status: str,
        metrics: list[MetricResult], issues: list[IssueSchema],
        llm_raw: str, llm_response: Optional[LLMExtractionResponse],
        document_raw_id: Optional[str] = None,
    ) -> Evaluation:
        """Persist evaluation results to the database."""
        import uuid
        generated_short_id = uuid.uuid4().hex[:6].upper()

        evaluation = Evaluation(
            short_id=generated_short_id,
            filename=filename,
            document_type=document_type,
            semantic_type=semantic_type,
            overall_score=overall_score,
            status=overall_status,
            metrics_json=json.dumps([m.model_dump() for m in metrics]),
            llm_raw_response=llm_raw,
            executive_summary=llm_response.executive_summary if llm_response else "",
            risk_summary=llm_response.risk_summary if llm_response else "",
            recommendations_json=json.dumps(
                llm_response.recommendations if llm_response else []
            ),
            extracted_fields_json=json.dumps(
                llm_response.fields if llm_response else {}
            ),
            metric_reasoning_json=json.dumps(
                llm_response.metric_reasoning if llm_response else {}
            ),
            document_raw_id=document_raw_id,
        )

        db.add(evaluation)
        db.flush()

        # Persist individual metric results as rows
        for m in metrics:
            row = MetricResultRow(
                evaluation_id=evaluation.id,
                metric_id=m.id,
                name=m.name,
                category=m.category,
                score=m.score,
                severity=m.status,
                details_json=json.dumps({
                    "description": m.description,
                    "status_message": m.status_message,
                    "reasoning": m.reasoning,
                }),
                linked_standards_json=json.dumps(
                    [ls.model_dump() for ls in m.linked_standards]
                ),
            )
            db.add(row)

        # Persist issues
        for issue in issues:
            db_issue = Issue(
                evaluation_id=evaluation.id,
                field_name=issue.field_name,
                issue_type=issue.issue_type,
                description=issue.description,
                severity=issue.severity,
                metric_name=issue.metric_name,
            )
            db.add(db_issue)

        db.commit()
        db.refresh(evaluation)

        logger.info(
            "Persisted evaluation %s with %d metric rows and %d issues",
            evaluation.id, len(metrics), len(issues),
        )
        return evaluation

    def get_evaluation_by_id(
        self, evaluation_id: str, db: Session
    ) -> Optional[EvaluationResponse]:
        """Retrieve a stored evaluation by its ID."""
        evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        if not evaluation:
            return None

        metrics_data = json.loads(evaluation.metrics_json or "[]")
        metrics = [MetricResult(**m) for m in metrics_data]

        core_metrics = [m for m in metrics if m.category == "core"]
        type_specific_metrics = [m for m in metrics if m.category == "type_specific"]
        primary_type_metrics = sorted(type_specific_metrics, key=lambda m: m.score)[:2]

        issues_data = [
            IssueSchema(
                field_name=i.field_name,
                issue_type=i.issue_type,
                description=i.description,
                severity=i.severity,
                metric_name=i.metric_name,
            )
            for i in evaluation.issues
        ]

        recommendations = json.loads(evaluation.recommendations_json or "[]")

        return EvaluationResponse(
            evaluation_id=evaluation.id,
            short_id=evaluation.short_id,
            filename=evaluation.filename,
            document_type=evaluation.document_type or "unknown",
            semantic_type=evaluation.semantic_type or "general",
            overall_score=evaluation.overall_score or 0,
            overall_status=evaluation.status,
            core_metrics=core_metrics,
            type_specific_metrics=type_specific_metrics,
            primary_type_metrics=primary_type_metrics,
            metrics=metrics,
            issues=issues_data,
            executive_summary=evaluation.executive_summary or "",
            risk_summary=evaluation.risk_summary or "",
            recommendations=recommendations,
            corrections_count=len(evaluation.correction_proposals) if evaluation.correction_proposals else 0,
            created_at=evaluation.created_at,
        )

    @staticmethod
    def _compute_file_hash(file_path: str) -> str:
        """Compute SHA-256 hash of a file for deduplication."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def _guess_mime(filename: str) -> str:
        """Guess MIME type from filename extension."""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime_map = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
            "txt": "text/plain",
            "md": "text/markdown",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
        }
        return mime_map.get(ext, "application/octet-stream")
