"""PDF report generation for compliance evaluations."""

from __future__ import annotations

from io import BytesIO
import re

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Spacer,
        Paragraph,
        Table,
        TableStyle,
        PageBreak,
    )

    REPORTLAB_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    REPORTLAB_IMPORT_ERROR = exc

from compliance.models.schemas import EvaluationResponse, IssueSchema, MetricResult


class ReportService:
    """Builds a PDF report from a compliance evaluation."""

    def build_evaluation_report(self, evaluation: EvaluationResponse) -> BytesIO:
        if REPORTLAB_IMPORT_ERROR is not None:
            raise RuntimeError(
                "PDF report generation requires the 'reportlab' package. Install backend requirements first."
            ) from REPORTLAB_IMPORT_ERROR

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="Document Quality Report",
            author="DocQuality System",
        )

        styles = self._build_styles()
        story = self._build_story(evaluation, styles)
        doc.build(story)
        buffer.seek(0)
        return buffer

    def build_report_filename(self, filename: str) -> str:
        stem = re.sub(r"\.[^.]+$", "", filename or "document-quality")
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "document-quality"
        return f"{stem}-report.pdf"

    def _build_styles(self) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle(
                "Title",
                parent=base["Heading1"],
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#0F172A"),
                spaceAfter=10,
            ),
            "subtitle": ParagraphStyle(
                "Subtitle",
                parent=base["BodyText"],
                fontSize=10,
                leading=13,
                textColor=colors.HexColor("#475569"),
                spaceAfter=8,
            ),
            "h2": ParagraphStyle(
                "Heading2",
                parent=base["Heading2"],
                fontSize=12,
                leading=16,
                textColor=colors.HexColor("#0F172A"),
                spaceAfter=6,
            ),
            "body": ParagraphStyle(
                "Body",
                parent=base["BodyText"],
                fontSize=9.5,
                leading=13,
                textColor=colors.HexColor("#334155"),
                spaceAfter=4,
            ),
            "muted": ParagraphStyle(
                "Muted",
                parent=base["BodyText"],
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#64748B"),
                spaceAfter=2,
            ),
        }

    def _build_story(self, evaluation: EvaluationResponse, styles: dict[str, ParagraphStyle]) -> list:
        story: list = []

        story.append(Paragraph("Document Quality Report", styles["title"]))
        story.append(Paragraph("Compliance evaluation summary", styles["subtitle"]))

        meta_rows = [
            ["File", self._safe_text(evaluation.filename, "N/A")],
            ["Document type", self._safe_text(evaluation.document_type, "N/A")],
            ["Evaluation ID", self._safe_text(evaluation.evaluation_id, "N/A")],
            ["Review date", self._format_date(evaluation.created_at)],
        ]
        meta_table = Table(meta_rows, colWidths=[35 * mm, 135 * mm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 8))

        story.append(Paragraph("Executive Summary", styles["h2"]))
        story.append(Paragraph(self._safe_text(evaluation.executive_summary, "No executive summary available."), styles["body"]))

        story.append(Paragraph("Risk Assessment", styles["h2"]))
        story.append(Paragraph(self._safe_text(evaluation.risk_summary, "No risk summary available."), styles["body"]))

        if evaluation.recommendations:
            story.append(Paragraph("Recommendations", styles["h2"]))
            for rec in evaluation.recommendations:
                story.append(Paragraph(f"- {self._safe_text(rec, '')}", styles["body"]))

        story.append(PageBreak())

        story.append(Paragraph("Quality Metrics", styles["h2"]))
        story.append(self._metrics_table(evaluation.metrics, styles))

        if evaluation.issues:
            story.append(Spacer(1, 10))
            story.append(Paragraph("Issues", styles["h2"]))
            story.append(self._issues_table(evaluation.issues, styles))

        return story

    def _metrics_table(self, metrics: list[MetricResult], styles: dict[str, ParagraphStyle]) -> Table:
        rows = [["Metric", "Score", "Status", "Description"]]
        for metric in metrics:
            rows.append([
                self._safe_text(metric.name, ""),
                f"{metric.score:.1f}",
                self._safe_text(metric.status, ""),
                self._safe_text(metric.description, ""),
            ])
        table = Table(rows, colWidths=[40 * mm, 20 * mm, 25 * mm, 85 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    def _issues_table(self, issues: list[IssueSchema], styles: dict[str, ParagraphStyle]) -> Table:
        rows = [["Issue", "Severity", "Description"]]
        for issue in issues:
            rows.append([
                self._safe_text(issue.issue_type, ""),
                self._safe_text(issue.severity, ""),
                self._safe_text(issue.description, ""),
            ])
        table = Table(rows, colWidths=[40 * mm, 25 * mm, 105 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        return table

    def _safe_text(self, value: str | None, fallback: str) -> str:
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback

    def _format_date(self, value) -> str:
        if not value:
            return "N/A"
        try:
            return value.strftime("%b %d, %Y")
        except Exception:
            return "N/A"
