"""
Scoring Engine.

Applies weighted scoring to metric results, normalizes scores,
and determines overall quality status. 

Merges the logic from both workspaces, including Banking's domain-adaptive weights
and S_Bank composite calculation.
"""

import logging
from typing import Any

from core.config import settings

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

    # ─── Config-Driven Scoring (Compliance Style) ─────────────────────────

    def apply_weighted_scoring_from_definitions(
        self,
        scores: dict[str, float],
        metrics: list[Any], # list[MetricDefinition]
    ) -> float:
        """
        Compute the weighted overall score from individual metric scores
        using MetricDefinition objects.
        """
        total_score = 0.0
        total_weight = 0.0

        for metric_def in metrics:
            score = scores.get(metric_def.id, 0.0)
            clamped = self.clamp_score(score)

            if metric_def.category == "core":
                weight = metric_def.weight
            else:
                weight = 0.05

            total_score += clamped * weight
            total_weight += weight

        if total_weight > 0:
            overall = total_score / total_weight
        else:
            overall = 0.0

        return self.clamp_score(overall)

    def calculate_overall_score(self, scores: dict[str, float]) -> float:
        """
        Compute a simple average of scores for backwards compatibility with Banking POC.
        """
        if not scores:
            return 0.0
        return self.clamp_score(sum(scores.values()) / len(scores))

    def apply_weighted_scoring(self, scores: dict[str, float], metrics: list[Any]) -> float:
        """Alias for apply_weighted_scoring_from_definitions for backwards compatibility."""
        return self.apply_weighted_scoring_from_definitions(scores, metrics)

    # ─── Domain-Adaptive Scoring (Banking Style) ───────────────────────────

    def apply_weighted_scoring_for_domain(
        self,
        metrics_dict: dict[str, float],
        weights_dict: dict[str, float] = None,
    ) -> float:
        """
        Compute the weighted overall score using an explicit weight dictionary.
        """
        if weights_dict is None:
            # Fallback to simple average if no weights provided
            if not metrics_dict: return 0.0
            return self.clamp_score(sum(metrics_dict.values()) / len(metrics_dict))

        total_score = 0.0
        total_weight = 0.0

        for metric_name, weight in weights_dict.items():
            score = metrics_dict.get(metric_name, 0.0)
            clamped = self.clamp_score(score)
            total_score += clamped * weight
            total_weight += weight

        if total_weight > 0 and abs(total_weight - 1.0) > 0.001:
            total_score = total_score / total_weight

        return self.clamp_score(total_score)

    def compute_composite_score(
        self,
        domain_metrics: list[dict],
        domain_weights: dict[str, float],
    ) -> float | None:
        """
        Compute a domain-specific composite score (like S_Bank).
        """
        if not domain_metrics:
            return None

        total_score = 0.0
        total_weight = 0.0

        for metric in domain_metrics:
            name = metric.get("name", "")
            score = float(metric.get("score", 0))
            w = domain_weights.get(name, 0.0) if domain_weights else 0.0
            if w > 0:
                total_score += score * w
                total_weight += w

        if total_weight > 0:
            composite = round(total_score / total_weight, 1)
        else:
            composite = round(
                sum(float(m.get("score", 0)) for m in domain_metrics) / len(domain_metrics), 1
            )

        return self.clamp_score(composite)

    # ─── Utilities ─────────────────────────────────────────────────────────

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

        critical = sum(1 for i in issues if getattr(i, "severity", "") == "critical" or (isinstance(i, dict) and i.get("severity") == "critical"))
        moderate = sum(1 for i in issues if getattr(i, "severity", "") == "warning" or (isinstance(i, dict) and i.get("severity") == "warning"))

        parts = []
        if critical > 0:
            parts.append(f"{critical} critical")
        if moderate > 0:
            parts.append(f"{moderate} moderate")

        if parts:
            return f"{' and '.join(parts)} issue(s) detected"

        return f"{issues_count} issue(s) requiring review"
