"""
Scoring Engine.

Applies weighted scoring to metric results, normalizes scores,
and determines overall quality status. Works with dynamic metric
definitions from config.py.
"""

import logging
from typing import Any

from app.config import MetricDefinition, ALL_METRIC_DEFINITIONS

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    Deterministic scoring engine for document quality evaluation.

    Applies configurable weights, clamps scores, and determines
    quality status thresholds.
    """

    # Quality status thresholds
    GOOD_THRESHOLD: float = 90.0
    MODERATE_THRESHOLD: float = 70.0

    def clamp_score(self, score: float) -> float:
        """Clamp a score to the valid range 0–100."""
        return max(0.0, min(100.0, round(score, 1)))

    def apply_weighted_scoring(
        self,
        scores: dict[str, float],
        metrics: list[MetricDefinition],
    ) -> float:
        """
        Compute the weighted overall score from individual metric scores.

        Only uses weights from core metrics. Type-specific metrics contribute
        to the overall score at a reduced weight.

        Args:
            scores: Dictionary mapping metric_id to score (0–100).
            metrics: List of active MetricDefinition objects.

        Returns:
            Weighted overall score clamped to 0–100.
        """
        total_score = 0.0
        total_weight = 0.0

        for metric_def in metrics:
            score = scores.get(metric_def.id, 0.0)
            clamped = self.clamp_score(score)

            if metric_def.category == "core":
                weight = metric_def.weight
            else:
                # Type-specific metrics contribute at lower weight
                weight = 0.05

            total_score += clamped * weight
            total_weight += weight
            logger.debug(
                "Metric: %s | Score: %.1f | Weight: %.2f | Contribution: %.2f",
                metric_def.id, clamped, weight, clamped * weight,
            )

        if total_weight > 0:
            overall = total_score / total_weight
        else:
            overall = 0.0

        overall = self.clamp_score(overall)
        logger.info("Weighted overall score: %.1f", overall)
        return overall

    def determine_status(self, score: float) -> str:
        """
        Determine quality status from score value.

        >= 90 → Good
        70–89 → Moderate (warning)
        < 70 → Critical
        """
        if score >= self.GOOD_THRESHOLD:
            return "good"
        elif score >= self.MODERATE_THRESHOLD:
            return "warning"
        else:
            return "critical"

    def determine_metric_status(self, score: float) -> str:
        """Determine status for an individual metric."""
        return self.determine_status(score)

    def get_status_message(self, metric_name: str, score: float, issues: list = None) -> str:
        """Generate a human-readable status message for a metric."""
        if issues is None:
            issues = []

        issues_count = len(issues)
        status = self.determine_metric_status(score)

        if status == "good" and issues_count == 0:
            return f"{metric_name} meets quality standards"

        elif status == "good":
            return f"{issues_count} minor observation(s) noted"

        critical = sum(1 for i in issues if i.severity == "critical")
        moderate = sum(1 for i in issues if i.severity == "warning")

        parts = []
        if critical > 0:
            parts.append(f"{critical} critical")
        if moderate > 0:
            parts.append(f"{moderate} moderate")

        if parts:
            return f"{' and '.join(parts)} issue(s) detected"

        return f"{issues_count} issue(s) requiring review"

    def blend_scores(
        self,
        deterministic_score: float,
        llm_score: float,
        deterministic_weight: float = 0.7,
    ) -> float:
        """
        Blend deterministic and LLM-suggested scores.

        The deterministic score always has higher weight to ensure
        reproducibility. LLM scores serve as a semantic adjustment.
        """
        llm_weight = 1.0 - deterministic_weight
        blended = (
            self.clamp_score(deterministic_score) * deterministic_weight
            + self.clamp_score(llm_score) * llm_weight
        )
        return self.clamp_score(blended)
