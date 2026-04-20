"""
Evaluation Orchestrator.

Coordinates the full 10-step agentic evaluation pipeline:
1.  Extract text + tables from document
2.  Deterministic Rule Engine  (rule-based, document-agnostic scoring)
3.  Classification Agent  (fast LLM classification for banking domain routing)
4.  Strict LLM Quality Validation  (validate/challenge/refine deterministic output)
5.  Domain Specialist Agent  (banking-specific deep analysis, chunked)
6.  Banking Rule Engine  (regulatory thresholds + dependency block)
7.  S_Bank composite score  (domain-weighted banking KPI)
8.  Dependency Block check  (legal hold flag when critical metrics fail)
9.  Consolidation Agent  (dedupe/merge recommendations + issues)
10. Remediation Agent  (specific actionable fix instructions)

Background job support: evaluate_document_job() is the BackgroundTasks
entry point. It creates its own DB session so FastAPI can close the
request session before the long-running work begins.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from banking.config import settings
from banking.models.db_models import Evaluation, Issue, Job
from banking.models.schemas import (
    BankingMetric,
    EvaluationResponse,
    IssueSchema,
    MetricResult,
)
from banking.services.banking_rule_engine import (
    BankingRuleEngine,
)
from banking.services.document_service import DocumentService
from banking.services.llm_service import AzureFoundryLLMService
from banking.services.rule_engine import RuleEngine
from banking.services.scoring_engine import ScoringEngine
from banking.services.visualization_service import VisualizationService

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Module-level background task helpers
# ─────────────────────────────────────────────────────────────────────────────

def _update_job(
    db: Session,
    job_id: str,
    *,
    status: str | None = None,
    progress: str | None = None,
    evaluation_id: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update job record fields and commit."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return
    if status:
        job.status = status
    if progress:
        job.progress_message = progress
    if evaluation_id:
        job.evaluation_id = evaluation_id
    if error_message:
        job.error_message = error_message
    if status in ("completed", "failed"):
        job.completed_at = datetime.now(timezone.utc)
    db.commit()


def evaluate_document_job(job_id: str, file_path: str, filename: str) -> None:
    """
    Background task entry point for document evaluation.

    Creates its own SQLAlchemy session (request session is already closed).
    Updates job status/progress as the pipeline progresses.
    Cleans up the temporary file when done.
    """
    from banking.database import SessionLocal  # local import to avoid startup order issues

    db = SessionLocal()
    try:
        _update_job(db, job_id, status="processing", progress="Initialising evaluation pipeline…")
        orchestrator = EvaluationOrchestrator()

        import asyncio  # noqa: PLC0415

        result = asyncio.run(
            orchestrator.evaluate_document(file_path, filename, db, job_id=job_id)
        )

        _update_job(db, job_id, status="completed", evaluation_id=result.evaluation_id)
        logger.info("Job %s completed: evaluation_id=%s", job_id, result.evaluation_id)

    except Exception as exc:
        try:
            db.rollback()
        except Exception as rb_exc:
            logger.warning("Failed to rollback database session: %s", rb_exc)
        logger.exception("Job %s failed: %s", job_id, exc)
        _update_job(db, job_id, status="failed", error_message=str(exc)[:500])

    finally:
        # Clean up temporary file
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


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator class
# ─────────────────────────────────────────────────────────────────────────────

class EvaluationOrchestrator:
    """
    Orchestrates the complete document quality evaluation pipeline.

    Combines five LLM agents (all using the same Azure Foundry endpoint)
    with deterministic rule evaluation for a hybrid quality assessment.
    """

    def __init__(self) -> None:
        """Initialize all service dependencies."""
        self.document_service = DocumentService()
        self.llm_service = AzureFoundryLLMService()
        self.rule_engine = RuleEngine()
        self.scoring_engine = ScoringEngine()
        self.visualization_service = VisualizationService()
        self.banking_rule_engine = BankingRuleEngine()

    # ── Progress helper ────────────────────────────────────────────────────

    def _progress(self, db: Session | None, job_id: str | None, message: str) -> None:
        if db and job_id:
            _update_job(db, job_id, progress=message)
        logger.info("[%s] %s", job_id or "direct", message)

    # ── Main evaluation pipeline ───────────────────────────────────────────

    async def evaluate_document(
        self,
        file_path: str,
        filename: str,
        db: Session,
        job_id: str | None = None,
    ) -> EvaluationResponse:
        """
        Execute the full 10-step agentic evaluation pipeline.

        Args:
            file_path: Path to the saved document on disk.
            filename: Original upload filename.
            db: Database session.
            job_id: Optional job UUID — when set, progress messages are written to the Job table.

        Returns:
            Complete EvaluationResponse.
        """
        # ── Step 1: Extract text + tables ──────────────────────────────────
        self._progress(db, job_id, "Step 1/10: Extracting text and tables from document…")
        document_text, table_text, ocr_confidence = (
            self.document_service.extract_text_and_tables(file_path)
        )
        if not document_text.strip():
            raise RuntimeError(
                "No text could be extracted from the document. "
                "The file may be empty, corrupted, or contain only images without OCR support."
            )
        combined_text = (document_text + "\n\n" + table_text).strip()
        logger.info("Extracted %d chars of text, %d chars of tables", len(document_text), len(table_text))

        # ── Step 2: Deterministic scoring engine (full document) ───────────
        self._progress(db, job_id, "Step 2/10: Running deterministic scoring engine…")
        all_issues: list[IssueSchema] = []
        det_metric_scores: dict[str, float] = {}

        fields = self.rule_engine.extract_basic_fields_from_text(combined_text)
        det_doc_type = "unknown"

        completeness_score, completeness_issues = self.rule_engine.calculate_completeness(fields, det_doc_type)
        det_metric_scores["completeness"] = completeness_score
        all_issues.extend(completeness_issues)

        validity_score, validity_issues = self.rule_engine.calculate_validity(fields)
        det_metric_scores["validity"] = validity_score
        all_issues.extend(validity_issues)

        consistency_score, consistency_issues = self.rule_engine.calculate_consistency(fields)
        det_metric_scores["consistency"] = consistency_score
        all_issues.extend(consistency_issues)

        accuracy_score, accuracy_issues = self.rule_engine.calculate_accuracy(fields, combined_text)
        det_metric_scores["accuracy"] = accuracy_score
        all_issues.extend(accuracy_issues)

        timeliness_score, timeliness_issues = self.rule_engine.calculate_timeliness(fields)
        det_metric_scores["timeliness"] = timeliness_score
        all_issues.extend(timeliness_issues)

        uniqueness_score, uniqueness_issues = self.rule_engine.calculate_uniqueness(fields)
        det_metric_scores["uniqueness"] = uniqueness_score
        all_issues.extend(uniqueness_issues)

        det_overall_score = self.scoring_engine.apply_weighted_scoring_for_domain(det_metric_scores, None)
        det_recommendations = self.rule_engine.generate_deterministic_recommendations(all_issues, det_metric_scores)

        deterministic_breakdown: dict[str, dict] = {}
        for metric_name, score in det_metric_scores.items():
            metric_issues = [
                i.model_dump()
                for i in all_issues
                if self._issue_belongs_to_metric(i, metric_name)
            ]
            weight = float(settings.METRIC_WEIGHTS.get(metric_name, 0.0))
            deterministic_breakdown[metric_name] = {
                "score": float(score),
                "weight": weight,
                "weighted_contribution": round(float(score) * weight, 2),
                "issues": metric_issues,
            }

        deterministic_output: dict = {
            "document_type": det_doc_type,
            "overall_score": det_overall_score,
            "metrics": deterministic_breakdown,
            "extracted_fields": fields,
            "issues": [i.model_dump() for i in all_issues],
            "recommendations": det_recommendations,
        }

        # ── Step 3: Classification agent (LLM-only document type) ────────
        self._progress(db, job_id, "Step 3/10: Running classification agent…")
        classification: dict = {}
        pre_classified_type = ""
        pre_classified_domain: str | None = None
        llm_confidence = 0

        if self.llm_service.is_configured:
            try:
                classification = self.llm_service.classify_document(
                    combined_text,
                    filename=filename,
                )
                pre_classified_type = classification.get("document_type", "") or ""
                pre_classified_domain = classification.get("banking_domain")
                pre_classified_domain = str(pre_classified_domain).strip() if pre_classified_domain and str(pre_classified_domain).lower() not in {"null", "none"} else None
                llm_confidence = classification.get("confidence", 0) or 0
                logger.info(
                    "Classification: type=%s domain=%s confidence=%s",
                    pre_classified_type, pre_classified_domain, llm_confidence
                )
            except Exception as exc:
                logger.warning("Classification agent failed: %s", exc)

        # LLM-led document type/domain selection for routing and display.
        # We intentionally do not use deterministic type/domain fallbacks here,
        # to avoid inconsistencies such as unknown document type with banking
        # domain metrics shown from keyword-only routing.
        document_type = pre_classified_type or "unknown"

        banking_domain: str | None = pre_classified_domain

        # Fire domain specialist in a background thread (overlaps strict LLM eval).
        import asyncio as _asyncio  # noqa: PLC0415
        _specialist_task = None
        _specialist_domain: str | None = None

        def _launch_specialist_for(domain: str):
            """Launch the domain specialist agent with deterministic baselines."""
            deterministic_baselines: dict[str, float] = {}
            try:
                det_banking = self.banking_rule_engine.evaluate_domain(
                    banking_domain=domain,
                    document_text=combined_text,
                    fields=fields,
                    llm_domain_scores=None,
                )
                for m in det_banking:
                    code = m.get("metric_code")
                    if not code:
                        continue
                    try:
                        deterministic_baselines[code] = float(
                            m.get("deterministic_score", m.get("score", 0))
                        )
                    except Exception:
                        continue
            except Exception as exc:
                logger.warning("Failed to compute deterministic banking baselines: %s", exc)

            return (
                _asyncio.ensure_future(
                    _asyncio.to_thread(
                        self.llm_service.evaluate_domain_specialist,
                        combined_text,
                        domain,
                        fields,
                        deterministic_baselines or None,
                    )
                ),
                domain,
            )

        if banking_domain and self.llm_service.is_configured:
            _specialist_task, _specialist_domain = _launch_specialist_for(banking_domain)

        # ── Step 4: Strict LLM validation/refinement ───────────────────────
        self._progress(db, job_id, "Step 4/10: Running strict LLM quality validation…")
        strict_llm = None
        llm_raw: str = ""
        llm_metric_reasoning: dict[str, str] = {}
        refined_scores: dict[str, float] = det_metric_scores.copy()
        llm_recommendations: list[str] = []
        llm_issues: list[IssueSchema] = []

        # Retrieve KB context for RAG-enhanced evaluation
        reference_context: list[str] = []
        try:
            from shared.knowledge_base.service import KnowledgeBaseService, get_kb_session
            from banking.config import settings as banking_settings
            kb_db = get_kb_session()
            kb_service = KnowledgeBaseService(
                workspace="banking",
                api_key=banking_settings.FOUNDRY_API_KEY,
                endpoint=banking_settings.FOUNDRY_ENDPOINT,
                model=banking_settings.FOUNDRY_MODEL,
                api_version=banking_settings.FOUNDRY_API_VERSION,
            )
            if kb_service.is_ready(kb_db):
                logger.info("Banking KB is ready. Retrieving reference context for RAG...")
                reference_context = kb_service.retrieve_context(combined_text)
            kb_db.close()
        except Exception as exc:
            logger.warning("Failed to retrieve banking KB context: %s", exc)

        try:
            strict_llm, llm_raw = self.llm_service.evaluate_quality_strict(combined_text, deterministic_output, reference_context)
            llm_recommendations = strict_llm.recommendations or []
            llm_issues = strict_llm.issues_observations or []

            # Preserve the 70/30 hybrid model for core integrity metrics.
            MAX_DELTA = 15.0
            for metric_name, det_score in det_metric_scores.items():
                md = (strict_llm.document_integrity_score.metrics or {}).get(metric_name)
                if md is None:
                    continue
                try:
                    proposed = float(md.score)
                except Exception:
                    continue

                det_s = float(det_score)
                llm_s = proposed
                lo = det_s - MAX_DELTA
                hi = det_s + MAX_DELTA
                llm_used = max(lo, min(hi, llm_s))

                blended = (det_s * 0.7) + (llm_used * 0.3)
                refined_scores[metric_name] = self.scoring_engine.clamp_score(blended)
                llm_metric_reasoning[metric_name] = (md.reasoning or "").strip()
        except Exception as exc:
            logger.warning("Strict LLM validation failed: %s", exc)

        # Optional LLM-only refinement: if Agent 1 returned unknown, accept
        # document_type from strict quality LLM output when present.
        if (
            (not document_type or document_type == "unknown")
            and strict_llm
            and getattr(strict_llm, "document_type", None)
        ):
            candidate_type = str(strict_llm.document_type).strip()
            if candidate_type:
                document_type = candidate_type
                
                strict_domain = getattr(strict_llm, "banking_domain", None)
                strict_domain = (str(strict_domain).strip() if strict_domain and str(strict_domain).lower() not in {"null", "none"} else None)

                if strict_domain and strict_domain != banking_domain:
                    prev_domain = banking_domain
                    banking_domain = strict_domain
                    if (
                        banking_domain
                        and self.llm_service.is_configured
                        and banking_domain != _specialist_domain
                    ):
                        if _specialist_task is not None and not _specialist_task.done():
                            _specialist_task.cancel()
                        _specialist_task, _specialist_domain = _launch_specialist_for(banking_domain)
                        logger.info(
                            "Domain specialist relaunched for refined domain: %s (was %s)",
                            banking_domain,
                            prev_domain,
                        )

                logger.info("Document type refined from strict LLM output: %s", document_type)

        # Reconcile document_type using strict LLM output even when the
        # classifier returned a non-unknown type. Keep this logic generic
        # (no hard-coded document types). Only override when the strict agent
        # is clearly self-consistent (its type is explicitly referenced in its
        # own summary/risk text) or when the classifier confidence is not high.
        strict_type = ""
        if strict_llm and getattr(strict_llm, "document_type", None):
            strict_type = str(strict_llm.document_type or "").strip()

        def _is_generic_type(t: str) -> bool:
            return (t or "").strip().lower() in {"invoice", "contract", "report", "letter", "form", "unknown"}

        if strict_type and strict_type != document_type:
            strict_exec = (getattr(strict_llm, "executive_summary", "") or "") if strict_llm else ""
            strict_risk = (getattr(strict_llm, "risk_assessment", "") or "") if strict_llm else ""
            strict_type_lower = strict_type.lower()
            self_consistent = (
                strict_type_lower in strict_exec.lower()
                or strict_type_lower in strict_risk.lower()
            )

            override = False
            if _is_generic_type(document_type):
                override = True
            elif self_consistent:
                override = True
            elif llm_confidence < 90:
                override = True

            if override:
                prev_type = document_type
                document_type = strict_type
                logger.info(
                    "Document type reconciled from strict LLM output: %s (was %s)",
                    document_type,
                    prev_type,
                )

                # If strict LLM also provided a banking_domain, prefer it.
                strict_domain = getattr(strict_llm, "banking_domain", None) if strict_llm else None
                strict_domain = (str(strict_domain).strip() if strict_domain and str(strict_domain).lower() not in {"null", "none"} else None)

                if strict_domain and strict_domain != banking_domain:
                    prev_domain = banking_domain
                    banking_domain = strict_domain
                    if (
                        banking_domain
                        and self.llm_service.is_configured
                        and banking_domain != _specialist_domain
                    ):
                        if _specialist_task is not None and not _specialist_task.done():
                            _specialist_task.cancel()
                        _specialist_task, _specialist_domain = _launch_specialist_for(banking_domain)
                        logger.info(
                            "Domain specialist relaunched for reconciled domain: %s (was %s)",
                            banking_domain,
                            prev_domain,
                        )

        # If document_type is still generic, run one more classification pass
        # with strict-summary hints to obtain a more specific document label.
        if (
            self.llm_service.is_configured
            and _is_generic_type(document_type)
            and strict_llm
            and (strict_llm.executive_summary or strict_llm.risk_assessment)
        ):
            try:
                refined = self.llm_service.classify_document(
                    combined_text,
                    filename=filename,
                    strict_executive_summary=strict_llm.executive_summary or "",
                    strict_risk_assessment=strict_llm.risk_assessment or "",
                )
                refined_type = (refined.get("document_type") or "").strip()
                refined_domain = refined.get("banking_domain")
                refined_domain = (str(refined_domain).strip() if refined_domain and str(refined_domain).lower() not in {"null", "none"} else None)
                refined_conf = int(refined.get("confidence", 0) or 0)

                if refined_type and not _is_generic_type(refined_type) and refined_conf >= 65:
                    logger.info(
                        "Document type refined via hinted classification: %s (was %s, confidence=%s)",
                        refined_type,
                        document_type,
                        refined_conf,
                    )
                    document_type = refined_type

                if refined_domain and refined_domain != banking_domain and refined_conf >= 65:
                    prev_domain = banking_domain
                    banking_domain = refined_domain
                    logger.info(
                        "Banking domain refined via hinted classification: %s (was %s)",
                        banking_domain,
                        prev_domain,
                    )

                    if banking_domain and self.llm_service.is_configured and banking_domain != _specialist_domain:
                        if _specialist_task is not None and not _specialist_task.done():
                            _specialist_task.cancel()
                        _specialist_task, _specialist_domain = _launch_specialist_for(banking_domain)
            except Exception as exc:
                logger.warning("Hinted classification refinement failed: %s", exc)

        # Add LLM issues (will be consolidated later)
        for li in llm_issues:
            if isinstance(li, IssueSchema):
                all_issues.append(li)

        final_scores: dict[str, float] = refined_scores
        metric_reasoning: dict[str, str] = llm_metric_reasoning

        # ── Collect Domain Specialist results (ran concurrently) ───────────
        specialist_payload: dict = {}
        if _specialist_task:
            try:
                specialist_result = await _specialist_task
                for k, v in (specialist_result or {}).items():
                    if k in ("specialist_notes",):
                        continue
                    if isinstance(v, dict):
                        specialist_payload[k] = v
                    else:
                        specialist_payload[k] = {"score": v}
                specialist_scores_only = {
                    k: (v.get("score", 0) if isinstance(v, dict) else v)
                    for k, v in specialist_payload.items()
                }
                logger.info("Domain specialist scores: %s", specialist_scores_only)
            except Exception as exc:
                logger.warning("Domain specialist agent failed: %s", exc)

        llm_domain_scores_full: dict = {}
        llm_domain_scores_full.update(specialist_payload)

        # ── Step 6: Banking Rule Engine ─────────────────────────────────────
        self._progress(db, job_id, "Step 6/10: Computing banking domain metrics…")
        raw_banking: list[dict] = []
        banking_metrics: list[BankingMetric] = []

        if banking_domain:
            try:
                raw_banking = self.banking_rule_engine.evaluate_domain(
                    banking_domain=banking_domain,
                    document_text=combined_text,
                    fields=fields,
                    llm_domain_scores=llm_domain_scores_full or None,
                )

                # Generate banking-specific issues for failing metrics
                banking_issues = self.banking_rule_engine.extract_banking_issues(
                    raw_banking, banking_domain
                )
                for bi in banking_issues:
                    all_issues.append(
                        IssueSchema(
                            field_name=bi["field_name"],
                            issue_type=bi["issue_type"],
                            description=bi["description"],
                            severity=bi["severity"],
                            regulation_reference=bi.get("regulation_reference"),
                            metric_dimension=bi.get("metric_dimension"),
                        )
                    )

                banking_metrics = [
                    BankingMetric(
                        name=m["name"],
                        score=m["score"],
                        description=m["description"],
                        calculation_logic=m["calculation_logic"],
                        risk_impact=m["risk_impact"],
                        reasoning=m.get("reasoning", ""),
                        metric_code=m.get("metric_code", ""),
                        deterministic_score=m.get("deterministic_score", m["score"]),
                        llm_score=m.get("llm_score"),
                        confidence=m.get("confidence", 1.0),
                        regulatory_pass_threshold=m.get("regulatory_pass_threshold"),
                        regulatory_reference=m.get("regulatory_reference", ""),
                        passes_regulatory_threshold=m.get("passes_regulatory_threshold", True),
                    )
                    for m in raw_banking
                ]
                logger.info("Banking evaluation complete: %d domain metrics", len(banking_metrics))
            except Exception as exc:
                logger.error("Banking rule engine failed: %s", exc)

        # ── Step 7: S_Bank composite score ──────────────────────────────────
        self._progress(db, job_id, "Step 7/10: Computing S_Bank composite score…")
        banking_overall_score: float | None = None
        if banking_metrics:
            banking_overall_score = self.scoring_engine.compute_banking_score(
                raw_banking, banking_domain
            )
            logger.info("S_Bank = %.1f (domain: %s)", banking_overall_score, banking_domain)

        # ── Step 8: Dependency Block / Legal Hold ───────────────────────────
        self._progress(db, job_id, "Step 8/10: Checking regulatory dependency blocks…")
        legal_hold = False
        legal_hold_reason = ""
        if banking_domain and raw_banking:
            legal_hold, legal_hold_reason = self.banking_rule_engine.check_dependency_block(
                banking_domain, raw_banking, combined_text
            )
            if legal_hold:
                logger.warning("LEGAL HOLD triggered: %s", legal_hold_reason)

        # ── Compute weighted overall score (domain-adaptive) ─────────────────
        overall_score = self.scoring_engine.apply_weighted_scoring_for_domain(
            final_scores, banking_domain
        )
        overall_status = self.scoring_engine.determine_status(overall_score)

        # ── Build metric results ────────────────────────────────────────────
        metrics: list[MetricResult] = []
        for metric_name, score in final_scores.items():
            clamped = self.scoring_engine.clamp_score(score)
            status = self.scoring_engine.determine_metric_status(clamped)
            metric_issues = [
                i for i in all_issues if self._issue_belongs_to_metric(i, metric_name)
            ]
            metrics.append(MetricResult(
                name=metric_name.capitalize(),
                score=clamped,
                description=self.scoring_engine.get_metric_description(metric_name),
                status_message=self.scoring_engine.get_status_message(metric_name, clamped, metric_issues),
                status=status,
                weight=settings.METRIC_WEIGHTS.get(metric_name, 0),
                reasoning=metric_reasoning.get(metric_name, ""),
            ))

        # ── Step 9: Consolidation Agent (recommendations + issues) ─────────
        self._progress(db, job_id, "Step 9/10: Consolidating recommendations and issues…")
        final_recommendations: list[str] = []
        final_issues: list[IssueSchema] = []

        deterministic_output_for_consolidation = {
            **deterministic_output,
            "issues": [i.model_dump() for i in all_issues],
            "recommendations": det_recommendations,
        }
        llm_output_for_consolidation = {
            "recommendations": llm_recommendations,
            "issues_observations": [i.model_dump() for i in llm_issues],
        }
        try:
            consolidation, _ = self.llm_service.consolidate_recommendations_and_issues(
                deterministic_output_for_consolidation,
                llm_output_for_consolidation,
            )
            final_recommendations = consolidation.recommendations or []
            final_issues = consolidation.issues_observations or []
        except Exception as exc:
            logger.warning("Consolidation agent failed: %s", exc)
            final_recommendations = (det_recommendations or []) + (llm_recommendations or [])
            final_issues = all_issues

        # ── Step 10: Remediation Agent ─────────────────────────────────────
        self._progress(db, job_id, "Step 10/10: Generating remediation plan…")
        remediation_plan: list[dict] = []
        if self.llm_service.is_configured:
            try:
                low_metrics = [
                    {"name": m["name"], "score": m["score"]}
                    for m in raw_banking
                    if m.get("score", 100) < 75
                ] + [
                    {"name": m.name, "score": m.score}
                    for m in metrics
                    if m.score < 75
                ]
                remediation_plan = self.llm_service.generate_remediation(
                    doc_type=document_type,
                    banking_domain=banking_domain,
                    issues=final_issues or all_issues,
                    low_metrics=low_metrics[:10],
                )
            except Exception as exc:
                logger.warning("Remediation agent failed: %s", exc)

        # ── Finalize & Persist ────────────────────────────────────────────
        self._progress(db, job_id, "Finalizing and saving evaluation results…")

        # ── Persist to database ────────────────────────────────────────────
        evaluation = self._persist_evaluation(
            db=db,
            filename=filename,
            document_type=document_type,
            overall_score=overall_score,
            overall_status=overall_status,
            metrics=metrics,
            issues=final_issues or all_issues,
            llm_raw=llm_raw,
            extracted_fields=fields,
            metric_reasoning=metric_reasoning,
            executive_summary=(strict_llm.executive_summary if strict_llm else ""),
            risk_summary=(strict_llm.risk_assessment if strict_llm else ""),
            recommendations=final_recommendations or det_recommendations,
            banking_domain=banking_domain,
            banking_metrics=banking_metrics,
            banking_overall_score=banking_overall_score,
            legal_hold=legal_hold,
            legal_hold_reason=legal_hold_reason,
            remediation_plan=remediation_plan,
        )

        logger.info(
            "Evaluation complete: %s | Score=%.1f | Status=%s | Issues=%d | Domain=%s | S_Bank=%s | LegalHold=%s",
            filename, overall_score, overall_status, len(all_issues),
            banking_domain or "N/A",
            f"{banking_overall_score:.1f}" if banking_overall_score else "N/A",
            legal_hold,
        )

        return EvaluationResponse(
            evaluation_id=evaluation.id,
            filename=filename,
            document_type=document_type,
            overall_score=overall_score,
            overall_status=overall_status,
            metrics=metrics,
            issues=final_issues or all_issues,
            executive_summary=(strict_llm.executive_summary if strict_llm else ""),
            risk_summary=(strict_llm.risk_assessment if strict_llm else ""),
            recommendations=final_recommendations or det_recommendations,
            created_at=evaluation.created_at,
            banking_domain=banking_domain,
            banking_metrics=banking_metrics,
            banking_overall_score=banking_overall_score,
            legal_hold=legal_hold,
            legal_hold_reason=legal_hold_reason,
            remediation_plan=remediation_plan,
        )

    def _persist_evaluation(
        self,
        db: Session,
        filename: str,
        document_type: str,
        overall_score: float,
        overall_status: str,
        metrics: list[MetricResult],
        issues: list[IssueSchema],
        llm_raw: str,
        extracted_fields: dict,
        metric_reasoning: dict[str, str],
        executive_summary: str,
        risk_summary: str,
        recommendations: list[str],
        banking_domain: str | None = None,
        banking_metrics: list[BankingMetric] | None = None,
        banking_overall_score: float | None = None,
        legal_hold: bool = False,
        legal_hold_reason: str = "",
        remediation_plan: list[dict] | None = None,
    ) -> Evaluation:
        """Persist evaluation + issues to the database and return the ORM object."""
        evaluation = Evaluation(
            filename=filename,
            document_type=document_type,
            overall_score=overall_score,
            status=overall_status,
            metrics_json=json.dumps([m.model_dump() for m in metrics]),
            llm_raw_response=llm_raw,
            executive_summary=executive_summary or "",
            risk_summary=risk_summary or "",
            recommendations_json=json.dumps(recommendations or []),
            extracted_fields_json=json.dumps(extracted_fields or {}),
            metric_reasoning_json=json.dumps(metric_reasoning or {}),
            banking_domain=banking_domain,
            banking_metrics_json=json.dumps(
                [m.model_dump() for m in banking_metrics] if banking_metrics else []
            ),
            banking_overall_score=banking_overall_score,
            legal_hold=legal_hold,
            legal_hold_reason=legal_hold_reason,
            remediation_plan_json=json.dumps(remediation_plan or []),
        )
        db.add(evaluation)
        db.flush()

        for issue in issues:
            db_issue = Issue(
                evaluation_id=evaluation.id,
                field_name=issue.field_name,
                issue_type=issue.issue_type,
                description=issue.description,
                severity=issue.severity,
                regulation_reference=getattr(issue, "regulation_reference", None),
                metric_dimension=getattr(issue, "metric_dimension", None),
            )
            db.add(db_issue)

        db.commit()
        db.refresh(evaluation)
        logger.info("Persisted evaluation %s with %d issues", evaluation.id, len(issues))
        return evaluation

    def _issue_belongs_to_metric(self, issue: IssueSchema, metric_name: str) -> bool:
        """Check if an issue belongs to the given metric dimension."""
        issue_metric_map = {
            "Missing Field": "completeness",
            "Invalid Format": "validity",
            "Inconsistent Value": "consistency",
            "Logical Inconsistency": "consistency",
            "Unverifiable Value": "accuracy",
            "Implausible Value": "accuracy",
            "Expired Date": "timeliness",
            "Outdated Data": "timeliness",
            "Future Date": "timeliness",
            "Duplicate Entry": "uniqueness",
            "Duplicate Value": "uniqueness",
        }
        return issue_metric_map.get(issue.issue_type, "") == metric_name

    def get_evaluation_by_id(
        self, evaluation_id: str, db: Session
    ) -> Optional[EvaluationResponse]:
        """Retrieve and reconstruct a stored evaluation by its UUID."""
        evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        if not evaluation:
            return None

        metrics_data = json.loads(evaluation.metrics_json or "[]")
        metrics = [MetricResult(**m) for m in metrics_data]

        issues_data = [
            IssueSchema(
                field_name=i.field_name,
                issue_type=i.issue_type,
                description=i.description,
                severity=i.severity,
                regulation_reference=i.regulation_reference,
                metric_dimension=i.metric_dimension,
            )
            for i in evaluation.issues
        ]

        recommendations = json.loads(evaluation.recommendations_json or "[]")
        banking_metrics_raw = json.loads(evaluation.banking_metrics_json or "[]")
        stored_banking_metrics = [BankingMetric(**bm) for bm in banking_metrics_raw]
        remediation_plan = json.loads(evaluation.remediation_plan_json or "[]")

        return EvaluationResponse(
            evaluation_id=evaluation.id,
            filename=evaluation.filename,
            document_type=evaluation.document_type or "unknown",
            overall_score=evaluation.overall_score or 0,
            overall_status=evaluation.status,
            metrics=metrics,
            issues=issues_data,
            executive_summary=evaluation.executive_summary or "",
            risk_summary=evaluation.risk_summary or "",
            recommendations=recommendations,
            created_at=evaluation.created_at,
            banking_domain=evaluation.banking_domain,
            banking_metrics=stored_banking_metrics,
            banking_overall_score=evaluation.banking_overall_score,
            legal_hold=evaluation.legal_hold or False,
            legal_hold_reason=evaluation.legal_hold_reason or "",
            remediation_plan=remediation_plan,
        )
