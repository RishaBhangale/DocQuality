"""
Correction Service — Phase 2.

Generates deterministic and LLM-assisted correction proposals for
failing metrics. Proposals can be auto-applied or reviewed manually.
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from compliance.models.db_models import CorrectionProposal, Evaluation
from compliance.models.schemas import MetricResult

logger = logging.getLogger(__name__)


class CorrectionService:
    """
    Generates correction proposals for documents with failing metrics.

    Two types:
    - Deterministic: date normalization, field standardization, etc.
    - LLM-suggested: textual improvement proposals from the AI.
    """

    def generate_corrections(
        self,
        evaluation_id: str,
        metrics: list[MetricResult],
        fields: dict[str, Any],
        raw_text: str,
        db: Session,
    ) -> list[CorrectionProposal]:
        """
        Generate correction proposals for all failing metrics.

        Args:
            evaluation_id: ID of the evaluation.
            metrics: List of MetricResult objects from the evaluation.
            fields: Extracted fields from the LLM.
            raw_text: Raw document text.
            db: Database session.

        Returns:
            List of CorrectionProposal records created.
        """
        proposals: list[CorrectionProposal] = []

        for metric in metrics:
            if metric.score >= 90:
                continue  # Skip metrics that pass

            metric_proposals = self._generate_for_metric(
                evaluation_id, metric, fields, raw_text
            )
            proposals.extend(metric_proposals)

        # Persist all proposals
        for p in proposals:
            db.add(p)

        logger.info(
            "Generated %d correction proposals for evaluation %s",
            len(proposals), evaluation_id,
        )
        return proposals

    def _generate_for_metric(
        self,
        evaluation_id: str,
        metric: MetricResult,
        fields: dict[str, Any],
        raw_text: str,
    ) -> list[CorrectionProposal]:
        """Route to metric-specific correction generators."""
        generators = {
            "completeness": self._corrections_completeness,
            "validity": self._corrections_validity,
            "timeliness": self._corrections_timeliness,
            "consistency": self._corrections_consistency,
            "accuracy": self._corrections_accuracy,
            "uniqueness": self._corrections_uniqueness,
            # Type-specific
            "isms_doc_control": self._corrections_isms_doc_control,
            "ropa_completeness": self._corrections_ropa,
            "ai_risk_assessment_doc": self._corrections_ai_risk,
        }

        generator = generators.get(metric.id, self._corrections_generic)
        return generator(evaluation_id, metric, fields, raw_text)

    # ── Deterministic correction generators ──────────────────────

    def _corrections_completeness(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        proposals = []
        expected_sections = [
            "purpose", "scope", "roles", "responsibilities",
            "procedures", "references", "revision history",
        ]
        text_lower = raw_text.lower()
        for section in expected_sections:
            if section not in text_lower:
                proposals.append(CorrectionProposal(
                    evaluation_id=eval_id,
                    metric_id="completeness",
                    field_path=f"sections.{section}",
                    current_value=None,
                    proposed_value=f"Add a '{section.title()}' section to the document.",
                    reason=f"Standard documents typically include a '{section}' section for completeness.",
                    auto_applicable=False,
                ))
        # Check for missing author/owner
        if not fields.get("author") and not fields.get("owner"):
            proposals.append(CorrectionProposal(
                evaluation_id=eval_id,
                metric_id="completeness",
                field_path="metadata.author",
                current_value=None,
                proposed_value="Add document author/owner attribution.",
                reason="Document ownership is required for accountability and traceability.",
                auto_applicable=False,
            ))
        return proposals

    def _corrections_validity(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        proposals = []
        # Check for malformed dates
        date_pattern = re.compile(r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b')
        for match in date_pattern.finditer(raw_text):
            raw_date = match.group()
            # If date uses ambiguous format (DD/MM vs MM/DD), suggest ISO format
            proposals.append(CorrectionProposal(
                evaluation_id=eval_id,
                metric_id="validity",
                field_path="dates",
                current_value=raw_date,
                proposed_value=f"Normalize to ISO 8601 format (YYYY-MM-DD).",
                reason="Ambiguous date format detected. ISO 8601 eliminates regional interpretation differences.",
                auto_applicable=True,
            ))
            if len(proposals) >= 3:
                break
        return proposals

    def _corrections_timeliness(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        proposals = []
        # If no review date found
        has_review = any(
            kw in raw_text.lower()
            for kw in ["review date", "next review", "reviewed on", "valid until"]
        )
        if not has_review:
            proposals.append(CorrectionProposal(
                evaluation_id=eval_id,
                metric_id="timeliness",
                field_path="metadata.review_date",
                current_value=None,
                proposed_value="Add a 'Review Date' or 'Valid Until' field.",
                reason="Document lacks a scheduled review date — required for compliance lifecycle management.",
                auto_applicable=False,
            ))
        return proposals

    def _corrections_consistency(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        return []  # Consistency issues typically require human judgment

    def _corrections_accuracy(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        proposals = []
        # Check for "TBD", "N/A", "TODO" placeholders
        placeholders = re.findall(r'\b(TBD|TODO|N/A|PLACEHOLDER|TBC|XXX)\b', raw_text, re.IGNORECASE)
        if placeholders:
            proposals.append(CorrectionProposal(
                evaluation_id=eval_id,
                metric_id="accuracy",
                field_path="content.placeholders",
                current_value=f"Found {len(placeholders)} placeholder(s): {', '.join(set(p.upper() for p in placeholders[:5]))}",
                proposed_value="Replace all placeholder values with actual data.",
                reason="Placeholder text indicates incomplete content that will affect document accuracy.",
                auto_applicable=False,
            ))
        return proposals

    def _corrections_uniqueness(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        return []  # Deduplication requires semantic analysis

    # ── Type-specific correction generators ──────────────────────

    def _corrections_isms_doc_control(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        proposals = []
        text_lower = raw_text.lower()
        required = {
            "version": "Add a version number (e.g., 'Version: 1.0') for document control.",
            "classification": "Add a document classification level (e.g., 'Internal', 'Confidential').",
            "document owner": "Specify the document owner for accountability.",
        }
        for field, fix in required.items():
            if field not in text_lower:
                proposals.append(CorrectionProposal(
                    evaluation_id=eval_id,
                    metric_id="isms_doc_control",
                    field_path=f"doc_control.{field.replace(' ', '_')}",
                    current_value=None,
                    proposed_value=fix,
                    reason=f"ISO 27001 Clause 7.5 requires '{field}' for documented information.",
                    auto_applicable=False,
                ))
        return proposals

    def _corrections_ropa(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        proposals = []
        text_lower = raw_text.lower()
        ropa_fields = {
            "lawful basis": "Specify the lawful basis for each processing activity (GDPR Art. 6).",
            "retention": "Add retention periods for each data category.",
            "recipients": "List all data recipients including processors.",
        }
        for field, fix in ropa_fields.items():
            if field not in text_lower:
                proposals.append(CorrectionProposal(
                    evaluation_id=eval_id,
                    metric_id="ropa_completeness",
                    field_path=f"ropa.{field.replace(' ', '_')}",
                    current_value=None,
                    proposed_value=fix,
                    reason=f"ISO 27701 & GDPR Art. 30 require '{field}' in Records of Processing.",
                    auto_applicable=False,
                ))
        return proposals

    def _corrections_ai_risk(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        proposals = []
        text_lower = raw_text.lower()
        required = {
            "risk identification": "Add structured risk entries with scenario, likelihood, impact, and mitigation.",
            "risk treatment": "Document how each identified risk is treated (mitigate, transfer, accept, avoid).",
        }
        for field, fix in required.items():
            if field not in text_lower:
                proposals.append(CorrectionProposal(
                    evaluation_id=eval_id,
                    metric_id="ai_risk_assessment_doc",
                    field_path=f"ai_risk.{field.replace(' ', '_')}",
                    current_value=None,
                    proposed_value=fix,
                    reason=f"ISO 42001 Clause 6.1.2 requires '{field}' for AI risk assessments.",
                    auto_applicable=False,
                ))
        return proposals

    def _corrections_generic(
        self, eval_id: str, metric: MetricResult, fields: dict, raw_text: str
    ) -> list[CorrectionProposal]:
        """Generic fallback — return a suggestion based on the metric's score."""
        if metric.score < 50:
            return [CorrectionProposal(
                evaluation_id=eval_id,
                metric_id=metric.id,
                field_path="general",
                current_value=None,
                proposed_value=f"Review and improve the '{metric.name}' dimension of this document.",
                reason=f"Score of {metric.score}% indicates significant gaps in {metric.name.lower()}.",
                auto_applicable=False,
            )]
        return []

    def get_corrections(self, evaluation_id: str, db: Session) -> list[dict]:
        """Retrieve all correction proposals for an evaluation."""
        proposals = (
            db.query(CorrectionProposal)
            .filter(CorrectionProposal.evaluation_id == evaluation_id)
            .order_by(CorrectionProposal.metric_id)
            .all()
        )
        return [
            {
                "id": p.id,
                "metric_id": p.metric_id,
                "field_path": p.field_path,
                "current_value": p.current_value,
                "proposed_value": p.proposed_value,
                "reason": p.reason,
                "auto_applicable": p.auto_applicable,
                "applied": p.applied,
            }
            for p in proposals
        ]
