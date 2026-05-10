"""
Visualization Service.

Generates structured data for the frontend to render using Recharts.
Aligned with the React components in the frontend.
"""

import logging
from typing import Any

from core.models.schemas import MetricResult, IssueSchema

logger = logging.getLogger(__name__)


class VisualizationService:
    """
    Service for generating chart data for document quality visualization.
    Produces structured data compatible with Recharts components.
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
        """Generate gauge chart data."""
        return {
            "score": overall_score,
            "status": status,
            "color": self.STATUS_COLORS.get(status, self.COLORS["primary"]),
        }

    def generate_radar_data(self, metrics: list[MetricResult]) -> list[dict[str, Any]]:
        """Generate data for MetricRadarChart (array of { name, score })."""
        return [
            {
                "name": m.name,
                "score": m.score
            }
            for m in metrics
        ]

    def generate_bar_data(self, metrics: list[MetricResult]) -> list[dict[str, Any]]:
        """Generate data for MetricBarChart (array of { name, score, status })."""
        return [
            {
                "name": m.name,
                "score": m.score,
                "status": m.status
            }
            for m in metrics
        ]

    def generate_pie_data(self, issues: list[IssueSchema]) -> list[dict[str, Any]]:
        """
        Generate data for SeverityPieChart.
        Actually, the frontend component calculates counts from the raw issues list.
        So we just pass the issues through, or a simplified version.
        """
        return [
            {
                "severity": issue.severity,
                "issueType": issue.issue_type,
                "description": issue.description
            }
            for issue in issues
        ]

    def generate_full_visualization_data(
        self,
        overall_score: float,
        status: str,
        metrics: list[MetricResult],
        issues: list[IssueSchema],
    ) -> dict[str, Any]:
        """
        Generate complete visualization data package for the frontend.
        Matches keys expected by WorkspaceApp.tsx.
        """
        return {
            "radarData": self.generate_radar_data(metrics),
            "barData": self.generate_bar_data(metrics),
            "pieData": self.generate_pie_data(issues),
            "gaugeData": self.generate_gauge_data(overall_score, status),
        }
