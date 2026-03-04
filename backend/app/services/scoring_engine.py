"""
Scoring Engine.

Applies weighted scoring to metric results, normalizes scores,
and determines overall quality status. The LLM never decides
the final score — this engine does.
"""

import logging
from typing import Any

from app.config import settings

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

    def __init__(self) -> None:
        """Initialize the scoring engine with configured weights."""
        self.weights: dict[str, float] = settings.METRIC_WEIGHTS.copy()

    def clamp_score(self, score: float) -> float:
        """
        Clamp a score to the valid range 0–100.

        Args:
            score: Raw score value.

        Returns:
            Clamped score between 0 and 100.
        """
        return max(0.0, min(100.0, round(score, 1)))

    def apply_weighted_scoring(self, metrics_dict: dict[str, float]) -> float:
        """
        Compute the weighted overall score from individual metric scores.

        Formula: overall = sum(metric_score * weight) for all metrics

        Args:
            metrics_dict: Dictionary mapping metric names to their scores (0–100).

        Returns:
            Weighted overall score clamped to 0–100.
        """
        total_score = 0.0
        total_weight = 0.0

        for metric_name, weight in self.weights.items():
            score = metrics_dict.get(metric_name, 0.0)
            clamped = self.clamp_score(score)
            total_score += clamped * weight
            total_weight += weight
            logger.debug(
                "Metric: %s | Score: %.1f | Weight: %.2f | Contribution: %.2f",
                metric_name, clamped, weight, clamped * weight
            )

        # Normalize if weights don't sum to 1.0 (they should, but handle gracefully)
        if total_weight > 0 and abs(total_weight - 1.0) > 0.001:
            logger.warning("Metric weights sum to %.3f (expected 1.0). Normalizing.", total_weight)
            total_score = total_score / total_weight

        overall = self.clamp_score(total_score)
        logger.info("Weighted overall score: %.1f", overall)
        return overall

    def determine_status(self, score: float) -> str:
        """
        Determine quality status from score value.

        >= 90 → Good
        70–89 → Moderate (warning)
        < 70 → Critical

        Args:
            score: Overall quality score (0–100).

        Returns:
            Status string: 'good', 'warning', or 'critical'.
        """
        if score >= self.GOOD_THRESHOLD:
            return "good"
        elif score >= self.MODERATE_THRESHOLD:
            return "warning"
        else:
            return "critical"

    def determine_metric_status(self, score: float) -> str:
        """
        Determine status for an individual metric.

        Uses the same thresholds as overall status.

        Args:
            score: Metric score (0–100).

        Returns:
            Status string: 'good', 'warning', or 'critical'.
        """
        return self.determine_status(score)

    def get_status_message(self, metric_name: str, score: float, issues: list = None) -> str:
        """
        Generate a human-readable status message for a metric.

        Counts actual issue severities so the message matches the
        Issues & Observations table exactly.

        Args:
            metric_name: Name of the metric.
            score: Metric score.
            issues: List of IssueSchema objects belonging to this metric.

        Returns:
            Status message string.
        """
        if issues is None:
            issues = []

        issues_count = len(issues)
        status = self.determine_metric_status(score)

        if status == "good" and issues_count == 0:
            messages = {
                "completeness": "All required fields are present",
                "accuracy": "All extracted values passed validation",
                "consistency": "All field relationships are logically consistent",
                "validity": "All fields conform to expected formats",
                "timeliness": "All dates and time-sensitive data are current",
                "uniqueness": "No duplicate entries found",
            }
            return messages.get(metric_name.lower(), f"{metric_name} meets quality standards")

        elif status == "good":
            return f"{issues_count} minor observation(s) noted"

        # Count by actual severity from the issues
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

    def get_metric_description(self, metric_name: str) -> str:
        """
        Get the standard description for a metric.

        Args:
            metric_name: Name of the metric.

        Returns:
            Description string.
        """
        descriptions = {
            "completeness": "Measures presence of required fields",
            "accuracy": "Validates extracted data correctness",
            "consistency": "Checks logical field relationships",
            "validity": "Ensures format compliance",
            "timeliness": "Assesses data recency",
            "uniqueness": "Identifies duplicate entries",
        }
        return descriptions.get(metric_name.lower(), f"Evaluates {metric_name.lower()}")

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

        Args:
            deterministic_score: Score from the rule engine.
            llm_score: Score suggested by the LLM.
            deterministic_weight: Weight for the deterministic score (default 0.7).

        Returns:
            Blended and clamped score.
        """
        llm_weight = 1.0 - deterministic_weight
        blended = (
            self.clamp_score(deterministic_score) * deterministic_weight
            + self.clamp_score(llm_score) * llm_weight
        )
        return self.clamp_score(blended)
