"""
Evaluation Orchestrator.

The brain of the system. Coordinates the full evaluation workflow:
1. Extract text from document
2. Call LLM for structured extraction + reasoning
3. Run deterministic rule engine (core metrics)
3.5. Run type-specific metric engine
4. Blend scores
5. Compute weighted overall score
6. Build metric results
7. Persist to database
8. Return structured response
"""

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.db_models import Evaluation, Issue
from app.models.schemas import (
    EvaluationResponse,
    IssueSchema,
    LLMExtractionResponse,
    MetricResult,
    TypeSpecificMetricResult,
)
from app.services.document_service import DocumentService
from app.services.insight_engine import generate_insights
from app.services.llm_service import AzureFoundryLLMService
from app.services.rule_engine import RuleEngine
from app.services.scoring_engine import ScoringEngine
from app.services.type_specific_engine import evaluate_type_specific
from app.services.visualization_service import VisualizationService

logger = logging.getLogger(__name__)


class EvaluationOrchestrator:
    """
    Orchestrates the complete document quality evaluation pipeline.

    Combines LLM-assisted extraction with deterministic rule evaluation
    to produce a hybrid quality assessment.
    """

    def __init__(self) -> None:
        """Initialize all service dependencies."""
        self.document_service = DocumentService()
        self.llm_service = AzureFoundryLLMService()
        self.rule_engine = RuleEngine()
        self.scoring_engine = ScoringEngine()
        self.visualization_service = VisualizationService()

    async def evaluate_document(
        self, file_path: str, filename: str, db: Session
    ) -> EvaluationResponse:
        """
        Execute the full evaluation pipeline for a document.

        Args:
            file_path: Path to the uploaded file on disk.
            filename: Original filename.
            db: Database session.

        Returns:
            Complete EvaluationResponse with core + type-specific metrics.

        Raises:
            RuntimeError: If critical evaluation steps fail.
        """
        logger.info("Starting evaluation for: %s", filename)

        # Step 1: Extract text from document
        logger.info("Step 1: Extracting text from document...")
        document_text = self.document_service.extract_text(file_path)

        if not document_text.strip():
            raise RuntimeError(
                "No text could be extracted from the document. "
                "The file may be empty, corrupted, or contain only images without OCR support."
            )

        logger.info("Extracted %d characters of text", len(document_text))

        # Step 2: Call LLM for structured extraction
        llm_response: Optional[LLMExtractionResponse] = None
        llm_raw: str = ""

        try:
            if self.llm_service.is_configured:
                logger.info("Step 2: Calling Azure Foundry LLM...")
                llm_response, llm_raw = self.llm_service.extract_and_evaluate(document_text)
                logger.info("LLM extraction successful. Document type: %s", llm_response.document_type)
            else:
                logger.warning("LLM is not configured. Using fallback response.")
                llm_response = self.llm_service.get_fallback_response(document_text)
        except RuntimeError as e:
            logger.error("LLM extraction failed: %s. Falling back to deterministic-only.", str(e))
            llm_response = self.llm_service.get_fallback_response(document_text)

        # Step 3: Run deterministic rule engine
        logger.info("Step 3: Running deterministic rule engine...")
        fields = llm_response.fields if llm_response else {}
        document_type = llm_response.document_type if llm_response else "unknown"

        # Fallback: local keyword-based document type detection
        if document_type == "unknown":
            document_type = self._detect_document_type_local(document_text, filename)
            logger.info("Local doc type detection: %s", document_type)

        all_issues: list[IssueSchema] = []
        metric_scores: dict[str, float] = {}

        # Calculate each metric deterministically
        completeness_score, completeness_issues = self.rule_engine.calculate_completeness(
            fields, document_type
        )
        metric_scores["completeness"] = completeness_score
        all_issues.extend(completeness_issues)

        validity_score, validity_issues = self.rule_engine.calculate_validity(fields)
        metric_scores["validity"] = validity_score
        all_issues.extend(validity_issues)

        consistency_score, consistency_issues = self.rule_engine.calculate_consistency(fields)
        metric_scores["consistency"] = consistency_score
        all_issues.extend(consistency_issues)

        accuracy_score, accuracy_issues = self.rule_engine.calculate_accuracy(fields, document_text)
        metric_scores["accuracy"] = accuracy_score
        all_issues.extend(accuracy_issues)

        timeliness_score, timeliness_issues = self.rule_engine.calculate_timeliness(fields)
        metric_scores["timeliness"] = timeliness_score
        all_issues.extend(timeliness_issues)

        uniqueness_score, uniqueness_issues = self.rule_engine.calculate_uniqueness(fields)
        metric_scores["uniqueness"] = uniqueness_score
        all_issues.extend(uniqueness_issues)

        # Step 4: Blend with LLM semantic scores (deterministic weighted at 70%)
        logger.info("Step 4: Blending deterministic and LLM scores...")
        blended_scores: dict[str, float] = {}

        if llm_response and llm_response.semantic_evaluation:
            semantic = llm_response.semantic_evaluation
            llm_scores = {
                "completeness": semantic.completeness,
                "accuracy": semantic.accuracy,
                "consistency": semantic.consistency,
                "validity": semantic.validity,
                "timeliness": semantic.timeliness,
                "uniqueness": semantic.uniqueness,
            }
            for metric_name in metric_scores:
                blended_scores[metric_name] = self.scoring_engine.blend_scores(
                    metric_scores[metric_name],
                    llm_scores.get(metric_name, 0),
                )
        else:
            blended_scores = metric_scores.copy()

        # Step 4.5: Run type-specific metrics
        logger.info("Step 4.5: Running type-specific metric engine...")
        raw_json = None
        from pathlib import Path as PathLib
        file_ext = PathLib(file_path).suffix.lower()

        # Extension-based type forcing — ensures correct type-specific metrics
        EXT_TO_TYPE = {
            ".json": "json",
            ".csv": "tabular",
            ".xml": "markup",
            ".html": "markup",
            ".htm": "markup",
            ".eml": "email",
        }

        if file_ext == ".json":
            try:
                raw_json = self.document_service.extract_raw_json(file_path)
            except Exception as e:
                logger.warning("Failed to load raw JSON: %s", str(e))

        # Use extension mapping if available, otherwise fall back to LLM doc type
        type_for_metrics = EXT_TO_TYPE.get(file_ext, document_type)
        logger.info("Type for metrics: %s (ext=%s, llm_type=%s)", type_for_metrics, file_ext, document_type)

        type_specific_results = evaluate_type_specific(
            document_type=type_for_metrics,
            fields=fields,
            text=document_text,
            file_path=file_path,
            raw_json=raw_json,
        )

        type_specific_metrics = [
            TypeSpecificMetricResult(
                name=r.name,
                score=r.score,
                description=r.description,
                status=r.status,
                details=r.details,
                document_type=r.document_type,
            )
            for r in type_specific_results
        ]

        # Compute type-specific average score
        type_specific_score = None
        if type_specific_metrics:
            type_specific_score = round(
                sum(m.score for m in type_specific_metrics) / len(type_specific_metrics), 1
            )
            logger.info(
                "Type-specific metrics: %d metrics, avg score: %.1f",
                len(type_specific_metrics), type_specific_score
            )

        # Step 5: Compute weighted overall score
        logger.info("Step 5: Computing weighted overall score...")
        overall_score = self.scoring_engine.apply_weighted_scoring(blended_scores)
        overall_status = self.scoring_engine.determine_status(overall_score)

        # Step 6: Build metric results
        logger.info("Step 6: Building metric results...")
        metric_reasoning = (
            llm_response.metric_reasoning if llm_response else {}
        )

        metrics: list[MetricResult] = []
        for metric_name, score in blended_scores.items():
            clamped = self.scoring_engine.clamp_score(score)
            status = self.scoring_engine.determine_metric_status(clamped)
            metric_issues = [
                i for i in all_issues
                if self._issue_belongs_to_metric(i, metric_name)
            ]

            metrics.append(MetricResult(
                name=metric_name.capitalize(),
                score=clamped,
                description=self.scoring_engine.get_metric_description(metric_name),
                status_message=self.scoring_engine.get_status_message(
                    metric_name, clamped, metric_issues
                ),
                status=status,
                weight=settings.METRIC_WEIGHTS.get(metric_name, 0),
                reasoning=metric_reasoning.get(metric_name, ""),
            ))

        # Step 7: Persist to database
        logger.info("Step 7: Persisting evaluation to database...")
        evaluation = self._persist_evaluation(
            db=db,
            filename=filename,
            document_type=document_type,
            overall_score=overall_score,
            overall_status=overall_status,
            metrics=metrics,
            type_specific_metrics=type_specific_metrics,
            type_specific_score=type_specific_score,
            issues=all_issues,
            llm_raw=llm_raw,
            llm_response=llm_response,
        )

        # Step 8: Generate deterministic insights (fallback for LLM)
        logger.info("Step 8: Generating deterministic AI insights...")
        ts_dicts = [m.model_dump() for m in type_specific_metrics] if type_specific_metrics else None
        local_insights = generate_insights(
            document_type=document_type,
            core_metrics=blended_scores,
            type_specific_metrics=ts_dicts,
            issues_count=len(all_issues),
        )

        # Use LLM summaries if available, otherwise fall back to deterministic insights
        executive_summary = (
            llm_response.executive_summary
            if llm_response and llm_response.executive_summary
            else local_insights["executive_summary"]
        )
        risk_summary = (
            llm_response.risk_summary
            if llm_response and llm_response.risk_summary
            else local_insights["risk_summary"]
        )
        recommendations = (
            llm_response.recommendations
            if llm_response and llm_response.recommendations
            else local_insights["recommendations"]
        )

        # Step 9: Build response
        logger.info(
            "Evaluation complete: %s | Score: %.1f | Status: %s | Issues: %d",
            filename, overall_score, overall_status, len(all_issues)
        )

        return EvaluationResponse(
            evaluation_id=evaluation.id,
            filename=filename,
            document_type=document_type,
            overall_score=overall_score,
            overall_status=overall_status,
            metrics=metrics,
            type_specific_metrics=type_specific_metrics,
            type_specific_score=type_specific_score,
            issues=all_issues,
            executive_summary=executive_summary,
            risk_summary=risk_summary,
            recommendations=recommendations,
            created_at=evaluation.created_at,
        )

    def _persist_evaluation(
        self,
        db: Session,
        filename: str,
        document_type: str,
        overall_score: float,
        overall_status: str,
        metrics: list[MetricResult],
        type_specific_metrics: list[TypeSpecificMetricResult],
        type_specific_score: Optional[float],
        issues: list[IssueSchema],
        llm_raw: str,
        llm_response: Optional[LLMExtractionResponse],
    ) -> Evaluation:
        """
        Persist evaluation results to the database.

        Args:
            db: Database session.
            filename: Original filename.
            document_type: Detected document type.
            overall_score: Overall quality score.
            overall_status: Overall quality status.
            metrics: List of core metric results.
            type_specific_metrics: List of type-specific metric results.
            type_specific_score: Average type-specific score.
            issues: List of detected issues.
            llm_raw: Raw LLM response string.
            llm_response: Parsed LLM response.

        Returns:
            Created Evaluation ORM object.
        """
        evaluation = Evaluation(
            filename=filename,
            document_type=document_type,
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
            type_specific_metrics_json=json.dumps(
                [m.model_dump() for m in type_specific_metrics]
            ) if type_specific_metrics else None,
            type_specific_score=type_specific_score,
        )

        db.add(evaluation)
        db.flush()  # Get the ID

        # Persist issues
        for issue in issues:
            db_issue = Issue(
                evaluation_id=evaluation.id,
                field_name=issue.field_name,
                issue_type=issue.issue_type,
                description=issue.description,
                severity=issue.severity,
            )
            db.add(db_issue)

        db.commit()
        db.refresh(evaluation)

        logger.info("Persisted evaluation %s with %d issues", evaluation.id, len(issues))
        return evaluation

    def _issue_belongs_to_metric(self, issue: IssueSchema, metric_name: str) -> bool:
        """
        Determine if an issue belongs to a specific metric category.

        Args:
            issue: The issue to classify.
            metric_name: The metric name to check against.

        Returns:
            True if the issue belongs to the metric.
        """
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

    @staticmethod
    def _detect_document_type_local(text: str, filename: str = "") -> str:
        """
        Local keyword-based document type detection fallback.

        Used when the LLM is unavailable or returns 'unknown'.
        Checks file extension first, then scans text for keywords.

        Args:
            text: Document text content.
            filename: Original filename.

        Returns:
            Detected document type string.
        """
        # Check file extension first
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if ext == "json":
            return "json"

        t = text.lower()

        # Invoice keywords
        if any(kw in t for kw in ["invoice", "bill to", "payment due", "subtotal", "amount due"]):
            return "invoice"

        # Contract keywords
        if any(kw in t for kw in [
            "agreement", "contract", "termination", "hereby", "parties",
            "whereas", "governing law", "indemnif", "confidential"
        ]):
            return "contract"

        # Social media keywords
        if any(kw in t for kw in [
            "http://", "https://", "#", "@", "comment", "tweet", "post",
            "follower", "retweet", "hashtag", "like", "share"
        ]):
            return "social_media"

        # Email keywords
        if any(kw in t for kw in ["subject:", "from:", "to:", "dear", "sincerely", "regards"]):
            return "letter"

        # Report keywords
        if any(kw in t for kw in ["executive summary", "table of contents", "findings", "methodology"]):
            return "report"

        return "unknown"

    def get_evaluation_by_id(
        self, evaluation_id: str, db: Session
    ) -> Optional[EvaluationResponse]:
        """
        Retrieve a stored evaluation by its ID.

        Args:
            evaluation_id: UUID of the evaluation.
            db: Database session.

        Returns:
            EvaluationResponse if found, None otherwise.
        """
        evaluation = db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        if not evaluation:
            return None

        # Reconstruct from stored data
        metrics_data = json.loads(evaluation.metrics_json or "[]")
        metrics = [MetricResult(**m) for m in metrics_data]

        issues_data = [
            IssueSchema(
                field_name=i.field_name,
                issue_type=i.issue_type,
                description=i.description,
                severity=i.severity,
            )
            for i in evaluation.issues
        ]

        recommendations = json.loads(evaluation.recommendations_json or "[]")

        # Reconstruct type-specific metrics
        type_specific_metrics = []
        if evaluation.type_specific_metrics_json:
            ts_data = json.loads(evaluation.type_specific_metrics_json)
            type_specific_metrics = [TypeSpecificMetricResult(**m) for m in ts_data]

        return EvaluationResponse(
            evaluation_id=evaluation.id,
            filename=evaluation.filename,
            document_type=evaluation.document_type or "unknown",
            overall_score=evaluation.overall_score or 0,
            overall_status=evaluation.status,
            metrics=metrics,
            type_specific_metrics=type_specific_metrics,
            type_specific_score=evaluation.type_specific_score,
            issues=issues_data,
            executive_summary=evaluation.executive_summary or "",
            risk_summary=evaluation.risk_summary or "",
            recommendations=recommendations,
            created_at=evaluation.created_at,
        )
