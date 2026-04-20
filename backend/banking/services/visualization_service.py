"""
Visualization Service.

Generates Plotly chart data for the frontend. Provides structured
chart configurations that the React frontend can render using Recharts,
or that the Dash dashboard can render directly.
"""

import logging
from typing import Any

from banking.models.schemas import MetricResult, IssueSchema

logger = logging.getLogger(__name__)


class VisualizationService:
    """
    Service for generating chart data for document quality visualization.

    Produces structured data for gauge, radar, bar, and pie charts.
    """

    # Color scheme matching the frontend theme
    COLORS = {
        "good": "#16A34A",
        "warning": "#EAB308",
        "critical": "#DC2626",
        "primary": "#1E3A8A",
        "background": "#F9FAFB",
        "text": "#111827",
    }

    STATUS_COLORS = {
        "good": "#16A34A",
        "warning": "#EAB308",
        "critical": "#DC2626",
    }

    def generate_gauge_data(self, overall_score: float, status: str) -> dict[str, Any]:
        """
        Generate gauge chart data for overall score.

        Args:
            overall_score: The overall quality score (0–100).
            status: Quality status ('good', 'warning', 'critical').

        Returns:
            Gauge chart configuration dictionary.
        """
        return {
            "type": "gauge",
            "value": overall_score,
            "max": 100,
            "color": self.STATUS_COLORS.get(status, self.COLORS["primary"]),
            "thresholds": [
                {"value": 70, "color": self.COLORS["critical"], "label": "Critical"},
                {"value": 90, "color": self.COLORS["warning"], "label": "Moderate"},
                {"value": 100, "color": self.COLORS["good"], "label": "Good"},
            ],
        }

    def generate_radar_data(self, metrics: list[MetricResult]) -> dict[str, Any]:
        """
        Generate radar chart data for metric comparison.

        Args:
            metrics: List of metric results.

        Returns:
            Radar chart configuration dictionary.
        """
        return {
            "type": "radar",
            "labels": [m.name for m in metrics],
            "datasets": [
                {
                    "label": "Score",
                    "data": [m.score for m in metrics],
                    "backgroundColor": "rgba(30, 58, 138, 0.2)",
                    "borderColor": self.COLORS["primary"],
                    "borderWidth": 2,
                },
            ],
            "max": 100,
        }

    def generate_bar_data(self, metrics: list[MetricResult]) -> dict[str, Any]:
        """
        Generate bar chart data for metric breakdown.

        Args:
            metrics: List of metric results.

        Returns:
            Bar chart configuration dictionary.
        """
        return {
            "type": "bar",
            "data": [
                {
                    "name": m.name,
                    "score": m.score,
                    "weight": m.weight,
                    "status": m.status,
                    "color": self.STATUS_COLORS.get(m.status, self.COLORS["primary"]),
                }
                for m in metrics
            ],
        }

    def generate_severity_distribution(self, issues: list[IssueSchema]) -> dict[str, Any]:
        """
        Generate pie/donut chart data for issue severity distribution.

        Args:
            issues: List of detected issues.

        Returns:
            Pie chart configuration dictionary.
        """
        severity_counts = {"critical": 0, "warning": 0, "good": 0}
        for issue in issues:
            severity = issue.severity.lower()
            if severity in severity_counts:
                severity_counts[severity] += 1

        return {
            "type": "pie",
            "data": [
                {
                    "name": "Critical",
                    "value": severity_counts["critical"],
                    "color": self.COLORS["critical"],
                },
                {
                    "name": "Warning",
                    "value": severity_counts["warning"],
                    "color": self.COLORS["warning"],
                },
                {
                    "name": "Minor",
                    "value": severity_counts["good"],
                    "color": self.COLORS["good"],
                },
            ],
            "total": len(issues),
        }

    def generate_full_visualization_data(
        self,
        overall_score: float,
        status: str,
        metrics: list[MetricResult],
        issues: list[IssueSchema],
    ) -> dict[str, Any]:
        """
        Generate complete visualization data package for the frontend.

        Args:
            overall_score: Overall quality score.
            status: Overall quality status.
            metrics: List of metric results.
            issues: List of detected issues.

        Returns:
            Complete visualization data dictionary.
        """
        return {
            "gauge": self.generate_gauge_data(overall_score, status),
            "radar": self.generate_radar_data(metrics),
            "bar": self.generate_bar_data(metrics),
            "severity_distribution": self.generate_severity_distribution(issues),
        }
