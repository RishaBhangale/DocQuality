"""Professional PDF report generation for document quality evaluations."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        KeepTogether,
        LongTable,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover
    REPORTLAB_IMPORT_ERROR = exc

from banking.models.schemas import BankingMetric, EvaluationResponse, IssueSchema, MetricResult
from banking.config import settings


class ReportService:
    """Builds polished PDF reports from evaluation results."""

    _DEFAULT_FONTS = {
        "regular": "Helvetica",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
    }

    _PALETTE = {
        # Hex palette (converted to ReportLab colors lazily) so the module can
        # be imported even when reportlab is not installed.
        "ink": "#0A2540",
        "muted": "#64748B",
        "body": "#334155",
        "surface": "#F8FAFC",
        "border": "#CBD5E1",
        "grid": "#E2E8F0",
        "header": "#0F172A",
        "danger": "#DC2626",
        "warning": "#D97706",
        "good": "#15803D",
    }

    def _c(self, key: str):
        return colors.HexColor(self._PALETTE[key])

    def build_evaluation_report(self, evaluation: EvaluationResponse) -> BytesIO:
        """Generate a professional PDF report for a completed evaluation."""
        if REPORTLAB_IMPORT_ERROR is not None:
            raise RuntimeError(
                "PDF report generation requires the 'reportlab' package. Install backend requirements first."
            ) from REPORTLAB_IMPORT_ERROR

        # Best-effort: use a modern UI font (Segoe UI on Windows, or Inter if provided).
        # Falls back to built-in Helvetica when unavailable.
        self._register_fonts()

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=16 * mm,
            rightMargin=16 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
            title="Document Quality Assessment Report",
            author="DocQuality System",
        )

        styles = self._build_styles()
        story = self._build_story(evaluation, styles)
        doc.build(story, onFirstPage=self._draw_page, onLaterPages=self._draw_page)
        buffer.seek(0)
        return buffer

    def build_report_filename(self, filename: str) -> str:
        """Create a safe report filename for Content-Disposition."""
        stem = re.sub(r"\.[^.]+$", "", filename or "document-quality")
        stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-") or "document-quality"
        return f"{stem}-professional-report.pdf"

    def _status_from_score(self, score: int) -> str:
        # Mirrors frontend getStatusFromScore
        return "good" if score >= 90 else "warning" if score >= 70 else "critical"

    def _status_label(self, status: str) -> str:
        # Mirrors frontend getOverallStatusLabel
        norm = (status or "").strip().lower()
        return {"good": "Good Quality", "warning": "Moderate Quality", "critical": "Critical Quality"}.get(norm, "N/A")

    def _has_banking_domain(self, evaluation: EvaluationResponse) -> bool:
        return bool(
            evaluation.banking_domain
            and evaluation.banking_domain.strip().lower() not in ["none", "null", "unknown", "not applicable", "n/a", ""]
            and evaluation.banking_overall_score is not None
        )

    def _font_names(self) -> dict[str, str]:
        return getattr(self, "_registered_fonts", self._DEFAULT_FONTS)

    def _register_fonts(self) -> None:
        """Best-effort font registration.

        Prefers Inter (if provided via font dir), then Segoe UI on Windows.
        Falls back to built-in Helvetica.
        """

        if getattr(self, "_fonts_registered", False):
            return

        fonts: dict[str, str] = dict(self._DEFAULT_FONTS)

        def try_register(path: Path, name: str) -> bool:
            if not path.exists() or not path.is_file():
                return False
            try:
                pdfmetrics.registerFont(TTFont(name, str(path)))
                return True
            except Exception:
                return False

        font_dirs: list[Path] = []
        env_dir = os.getenv("DOCQUALITY_PDF_FONT_DIR")
        if env_dir:
            font_dirs.append(Path(env_dir))
        font_dirs.append(Path(__file__).resolve().parents[1] / "assets" / "fonts")

        def find_first_existing(filename: str) -> Path | None:
            for base_dir in font_dirs:
                candidate = base_dir / filename
                if candidate.exists():
                    return candidate
            return None

        # 1) Inter (if font files are provided alongside the backend)
        inter_regular = find_first_existing("Inter-Regular.ttf")
        inter_bold = find_first_existing("Inter-Bold.ttf")
        inter_italic = find_first_existing("Inter-Italic.ttf")

        if inter_regular and inter_bold:
            reg_ok = try_register(inter_regular, "DocQualityInter")
            bold_ok = try_register(inter_bold, "DocQualityInter-Bold")
            ital_ok = bool(inter_italic and try_register(inter_italic, "DocQualityInter-Italic"))
            if reg_ok and bold_ok:
                fonts["regular"] = "DocQualityInter"
                fonts["bold"] = "DocQualityInter-Bold"
                fonts["italic"] = "DocQualityInter-Italic" if ital_ok else fonts["italic"]

        # 2) Segoe UI (common on Windows)
        if fonts == self._DEFAULT_FONTS and os.name == "nt":
            win_fonts = Path(os.environ.get("WINDIR", r"C:\\Windows")) / "Fonts"
            segoe_regular = win_fonts / "segoeui.ttf"
            segoe_bold = win_fonts / "segoeuib.ttf"
            segoe_italic = win_fonts / "segoeuii.ttf"
            reg_ok = try_register(segoe_regular, "DocQualitySegoe")
            bold_ok = try_register(segoe_bold, "DocQualitySegoe-Bold")
            ital_ok = try_register(segoe_italic, "DocQualitySegoe-Italic")
            if reg_ok and bold_ok:
                fonts["regular"] = "DocQualitySegoe"
                fonts["bold"] = "DocQualitySegoe-Bold"
                if ital_ok:
                    fonts["italic"] = "DocQualitySegoe-Italic"

        self._registered_fonts = fonts
        self._fonts_registered = True

    def _build_styles(self) -> dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()
        fonts = self._font_names()
        return {
            "cover_title": ParagraphStyle(
                "CoverTitle",
                parent=base["Heading1"],
                fontName=fonts["bold"],
                fontSize=25,
                leading=30,
                textColor=self._c("ink"),
                spaceAfter=10,
                alignment=TA_CENTER,
            ),
            "cover_subtitle": ParagraphStyle(
                "CoverSubtitle",
                parent=base["Normal"],
                fontName=fonts["regular"],
                fontSize=13,
                leading=17,
                textColor=colors.HexColor("#475569"),
                spaceAfter=12,
                alignment=TA_CENTER,
            ),
            "cover_caption": ParagraphStyle(
                "CoverCaption",
                parent=base["Normal"],
                fontName=fonts["regular"],
                fontSize=9,
                leading=12,
                textColor=self._c("muted"),
                spaceAfter=22,
                alignment=TA_CENTER,
            ),
            "h1": ParagraphStyle(
                "Heading1",
                parent=base["Heading1"],
                fontName=fonts["bold"],
                fontSize=18,
                leading=22,
                textColor=self._c("ink"),
                spaceAfter=10,
                spaceBefore=12,
            ),
            "h2": ParagraphStyle(
                "Heading2",
                parent=base["Heading2"],
                fontName=fonts["bold"],
                fontSize=13,
                leading=17,
                textColor=colors.HexColor("#0369A1"),
                spaceAfter=7,
                spaceBefore=8,
            ),
            "body": ParagraphStyle(
                "Body",
                parent=base["BodyText"],
                fontName=fonts["regular"],
                fontSize=9.6,
                leading=13.2,
                textColor=self._c("body"),
                alignment=TA_LEFT,
                spaceAfter=5,
            ),
            "body_bold": ParagraphStyle(
                "BodyBold",
                parent=base["BodyText"],
                fontName=fonts["bold"],
                fontSize=9.5,
                leading=13,
                textColor=colors.HexColor("#1E293B"),
            ),
            "muted": ParagraphStyle(
                "Muted",
                parent=base["BodyText"],
                fontName=fonts["regular"],
                fontSize=8.5,
                leading=11,
                textColor=self._c("muted"),
            ),
            "table_header": ParagraphStyle(
                "TableHeader",
                parent=base["BodyText"],
                fontName=fonts["bold"],
                fontSize=8.8,
                leading=11,
                textColor=colors.HexColor("#FFFFFF"),
                alignment=TA_LEFT,
            ),
            "table_cell": ParagraphStyle(
                "TableCell",
                parent=base["BodyText"],
                fontName=fonts["regular"],
                fontSize=8.3,
                leading=10.8,
                textColor=colors.HexColor("#1E293B"),
            ),
            "metric_large": ParagraphStyle(
                "MetricLarge",
                parent=base["BodyText"],
                fontName=fonts["bold"],
                fontSize=20,
                leading=24,
                textColor=self._c("ink"),
                alignment=TA_CENTER,
            ),
            "metric_label": ParagraphStyle(
                "MetricLabel",
                parent=base["BodyText"],
                fontName=fonts["regular"],
                fontSize=8.5,
                leading=10,
                textColor=self._c("muted"),
                alignment=TA_CENTER,
            ),
            "section_note": ParagraphStyle(
                "SectionNote",
                parent=base["BodyText"],
                fontName=fonts["italic"],
                fontSize=8.8,
                leading=12,
                textColor=colors.HexColor("#475569"),
                spaceAfter=7,
            ),
        }

    def _build_story(self, evaluation: EvaluationResponse, styles: dict[str, ParagraphStyle]) -> list:
        story: list = []
        has_banking_domain = self._has_banking_domain(evaluation)

        document_integrity_score = int(round(float(evaluation.overall_score or 0)))
        domain_specific_score = (
            int(round(float(evaluation.banking_overall_score)))
            if has_banking_domain and evaluation.banking_overall_score is not None
            else None
        )
        overall_quality_score = (
            int(round((document_integrity_score + int(domain_specific_score)) / 2))
            if domain_specific_score is not None
            else document_integrity_score
        )
        overall_quality_status = self._status_from_score(overall_quality_score)
        document_integrity_status = (evaluation.overall_status or overall_quality_status).strip().lower()
        domain_specific_status = self._status_from_score(int(domain_specific_score)) if domain_specific_score is not None else None

        issue_counts = Counter((issue.severity or "").lower() for issue in evaluation.issues)
        critical_count = issue_counts.get("critical", 0)
        moderate_count = issue_counts.get("warning", 0)

        top_issue_dimensions = self._top_issue_dimensions(evaluation.issues)

        # Cover page
        story.append(Spacer(1, 34 * mm))
        story.append(Paragraph("Document Quality Overview", styles["cover_title"]))
        story.append(
            Paragraph(
                "Two-dimensional quality evaluation for comprehensive document validation",
                styles["cover_subtitle"],
            )
        )
        story.append(
            Paragraph(
                "Generated for quality assurance, audit-readiness, and remediation planning workflows.",
                styles["cover_caption"],
            )
        )

        cover_rows = [
            [Paragraph("<b>File Name</b>", styles["body"]), Paragraph(self._safe_text(evaluation.filename, "N/A"), styles["body"])],
            [Paragraph("<b>Document Type</b>", styles["body"]), Paragraph(self._safe_text(evaluation.document_type, "N/A"), styles["body"])],
            [Paragraph("<b>Evaluation ID</b>", styles["body"]), Paragraph(self._safe_text(evaluation.evaluation_id, "N/A"), styles["body"])],
            [Paragraph("<b>Review Date</b>", styles["body"]), Paragraph(evaluation.created_at.strftime("%d %b %Y") if evaluation.created_at else "N/A", styles["body"])],
        ]
        cover_table = Table(cover_rows, colWidths=[48 * mm, 124 * mm], hAlign="LEFT")
        cover_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self._c("surface")),
                    ("BOX", (0, 0), (-1, -1), 1, self._c("border")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, self._c("grid")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(cover_table)
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Key results and findings begin on the next page.", styles["muted"]))
        story.append(PageBreak())

        # 1. Executive overview
        story.append(Paragraph("1. Executive Overview", styles["h1"]))
        story.append(
            Paragraph(
                "This section summarizes key outcomes, risk posture, and issue concentration from the completed evaluation.",
                styles["section_note"],
            )
        )

        # Mirrors UI: overall score is composite of Integrity + Domain (when domain is present)
        status_short = {"good": "GOOD", "warning": "MODERATE", "critical": "CRITICAL"}.get(overall_quality_status, "N/A")
        kpi_data = [
            [
                Paragraph(f"{overall_quality_score}/100", styles["metric_large"]),
                Paragraph(self._safe_text(status_short, "N/A"), styles["metric_large"]),
                Paragraph(str(len(evaluation.issues)), styles["metric_large"]),
            ],
            [
                Paragraph("OVERALL SCORE", styles["metric_label"]),
                Paragraph("QUALITY STATUS", styles["metric_label"]),
                Paragraph("ISSUES FLAGGED", styles["metric_label"]),
            ],
        ]
        kpi_widths = [57 * mm, 57 * mm, 57 * mm]
        # Add Integrity and (optional) Domain score blocks
        kpi_data[0].append(Paragraph(f"{document_integrity_score}/100", styles["metric_large"]))
        kpi_data[1].append(Paragraph("INTEGRITY SCORE", styles["metric_label"]))
        kpi_widths = [43 * mm, 43 * mm, 43 * mm, 43 * mm]
        if has_banking_domain:
            kpi_data[0].append(
                Paragraph(
                    f"{int(domain_specific_score)}/100" if domain_specific_score is not None else "N/A",
                    styles["metric_large"],
                )
            )
            kpi_data[1].append(Paragraph("DOMAIN SCORE", styles["metric_label"]))
            kpi_widths = [34.5 * mm, 34.5 * mm, 34.5 * mm, 34.5 * mm, 34.5 * mm]

        kpi_table = Table(kpi_data, colWidths=kpi_widths, hAlign="LEFT")
        kpi_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), self._c("surface")),
                    ("BOX", (0, 0), (-1, -1), 1, self._c("border")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, 0), 14),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                    ("TOPPADDING", (0, 1), (-1, 1), 0),
                    ("BOTTOMPADDING", (0, 1), (-1, 1), 14),
                ]
            )
        )
        story.append(kpi_table)

        story.append(Spacer(1, 6 * mm))
        severity_rows = [
            [
                Paragraph("Critical", styles["table_header"]),
                Paragraph("Moderate", styles["table_header"]),
            ],
            [
                Paragraph(str(critical_count), styles["table_cell"]),
                Paragraph(str(moderate_count), styles["table_cell"]),
            ],
        ]
        severity_table = Table(severity_rows, colWidths=[86 * mm, 86 * mm], hAlign="LEFT")
        severity_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), self._c("header")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("BOX", (0, 0), (-1, -1), 1, self._c("border")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, self._c("grid")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(severity_table)

        if top_issue_dimensions:
            dims = " · ".join(f"{d['label']} ({d['count']})" for d in top_issue_dimensions)
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(f"Most affected: {self._safe_text(dims, 'N/A')}", styles["muted"]))

        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("Executive Summary", styles["h2"]))
        story.append(Paragraph(self._safe_text(evaluation.executive_summary, "No executive summary available."), styles["body"]))

        story.append(Paragraph("Risk Assessment", styles["h2"]))
        story.append(Paragraph(self._safe_text(evaluation.risk_summary, "No risk summary available."), styles["body"]))

        if evaluation.legal_hold:
            story.append(Spacer(1, 3 * mm))
            legal_hold = Table(
                [[
                    Paragraph("<b>LEGAL HOLD</b>", styles["body_bold"]),
                    Paragraph(
                        self._safe_text(
                            evaluation.legal_hold_reason,
                            "A critical rule threshold failure triggered a legal hold.",
                        ),
                        styles["body"],
                    ),
                ]],
                colWidths=[35 * mm, 137 * mm],
            )
            legal_hold.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#EF4444")),
                        ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#991B1B")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(legal_hold)

        story.append(PageBreak())

        # 2. Metrics
        story.append(Paragraph("2. Quality Dimensions", styles["h1"]))
        story.append(
            Paragraph(
                "Core metrics are evaluated for every document. Domain-specific metrics are included only for domain-classified documents.",
                styles["section_note"],
            )
        )

        story.append(Paragraph("2.1 Core Quality Metrics", styles["h2"]))
        story.append(self._metrics_table(evaluation.metrics, styles))

        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph("2.2 Banking Domain Metrics", styles["h2"]))
        if has_banking_domain:
            story.append(Paragraph(f"Detected domain: <b>{self._safe_text(evaluation.banking_domain, 'N/A')}</b>", styles["body"]))
            if evaluation.banking_metrics:
                story.append(self._banking_metrics_table(evaluation.banking_metrics, styles))
            else:
                story.append(
                    Paragraph(
                        "A domain classification was detected, but no domain-specific metrics were produced for this evaluation.",
                        styles["body"],
                    )
                )
        else:
            story.append(Paragraph("No domain-specific evaluation was applicable for this document.", styles["body"]))

        story.append(PageBreak())

        # 3. Findings
        story.append(Paragraph("3. Issues & Observations", styles["h1"]))
        story.append(
            Paragraph(
                "This section captures all flagged issues (as shown in the application).",
                styles["section_note"],
            )
        )
        story.append(self._issues_table(evaluation.issues, styles))

        # 4. Action plan
        story.append(Spacer(1, 7 * mm))
        story.append(Paragraph("4. Action Plan", styles["h1"]))

        story.append(Paragraph("4.1 Remediation Steps", styles["h2"]))
        if evaluation.remediation_plan:
            story.extend(self._remediation_plan(evaluation.remediation_plan, styles))
        else:
            story.append(Paragraph("No remediation plan items were generated.", styles["body"]))

        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("4.2 Recommendations", styles["h2"]))
        if evaluation.recommendations:
            story.extend(self._recommendations(evaluation.recommendations, styles))
        else:
            story.append(Paragraph("No recommendations were generated.", styles["body"]))

        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(f"Report Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}", styles["muted"]))
        story.append(Paragraph("END OF REPORT", styles["metric_label"]))

        return story

    def _metrics_table(self, metrics: list[MetricResult], styles: dict[str, ParagraphStyle]) -> LongTable:
        rows = [[
            Paragraph("Metric", styles["table_header"]),
            Paragraph("Description", styles["table_header"]),
            Paragraph("Score", styles["table_header"]),
            Paragraph("Weight", styles["table_header"]),
            Paragraph("Status", styles["table_header"]),
            Paragraph("Reasoning", styles["table_header"]),
        ]]
        if not metrics:
            rows.append([
                Paragraph("None", styles["table_cell"]),
                Paragraph("-", styles["table_cell"]),
                Paragraph("-", styles["table_cell"]),
                Paragraph("-", styles["table_cell"]),
                Paragraph("-", styles["table_cell"]),
                Paragraph("No core metrics were produced for this evaluation.", styles["table_cell"]),
            ])
        else:
            for metric in metrics:
                rows.append([
                    Paragraph(self._safe_text(metric.name, "N/A"), styles["table_cell"]),
                    Paragraph(self._safe_text(metric.description, "N/A"), styles["table_cell"]),
                    Paragraph(str(round(metric.score)), styles["table_cell"]),
                    Paragraph(f"{metric.weight:.2f}", styles["table_cell"]),
                    Paragraph(self._safe_text(metric.status.title(), "N/A"), styles["table_cell"]),
                    Paragraph(self._safe_text(metric.reasoning or metric.status_message, "N/A"), styles["table_cell"]),
                ])
        table = LongTable(rows, colWidths=[30 * mm, 46 * mm, 13 * mm, 13 * mm, 18 * mm, 52 * mm], repeatRows=1)
        table.setStyle(self._prof_table_style())
        return table

    def _banking_metrics_table(self, metrics: list[BankingMetric], styles: dict[str, ParagraphStyle]) -> LongTable:
        rows = [[
            Paragraph("Metric", styles["table_header"]),
            Paragraph("Score", styles["table_header"]),
            Paragraph("Regulatory Threshold", styles["table_header"]),
            Paragraph("Status", styles["table_header"]),
            Paragraph("Reasoning", styles["table_header"]),
        ]]
        for metric in metrics:
            code = (metric.metric_code or "").strip().lower()
            thr_cfg = settings.BANKING_REGULATORY_THRESHOLDS.get(code) if code else None
            thr_val = metric.regulatory_pass_threshold if metric.regulatory_pass_threshold is not None else (thr_cfg or {}).get("threshold")
            thr_label = (thr_cfg or {}).get("label") or (metric.regulatory_reference or "")
            thr_desc = (thr_cfg or {}).get("description")
            if thr_val is None:
                threshold_text = "N/A"
            else:
                comparator = "=" if int(thr_val) == 100 else "≥"
                threshold_text = f"Reg. Pass {comparator} {int(thr_val)}"
                if thr_label:
                    threshold_text += f" | {self._safe_text(thr_label, '')}"
                elif thr_desc:
                    threshold_text += f" | {self._safe_text(thr_desc, '')}"

            status = "Pass" if metric.passes_regulatory_threshold else "Below Threshold"
            reasoning = self._safe_text(metric.reasoning, "")
            if not reasoning:
                reasoning = self._safe_text(metric.risk_impact, "N/A")
            confidence_text = f"AI Confidence: {round(metric.confidence * 100)}%" if metric.confidence is not None else ""
            if confidence_text:
                reasoning = f"{reasoning}<br/>{confidence_text}"

            rows.append([
                Paragraph(self._safe_text(metric.name, "N/A"), styles["table_cell"]),
                Paragraph(f"{int(round(metric.score))}/100", styles["table_cell"]),
                Paragraph(self._safe_text(threshold_text, "N/A"), styles["table_cell"]),
                Paragraph(self._safe_text(status, "N/A"), styles["table_cell"]),
                Paragraph(reasoning, styles["table_cell"]),
            ])
        table = LongTable(rows, colWidths=[48 * mm, 16 * mm, 48 * mm, 22 * mm, 38 * mm], repeatRows=1)
        table.setStyle(self._prof_table_style())
        return table

    def _issues_table(self, issues: list[IssueSchema], styles: dict[str, ParagraphStyle]) -> LongTable:
        rows = [[
            Paragraph("Field", styles["table_header"]),
            Paragraph("Issue Type", styles["table_header"]),
            Paragraph("Description", styles["table_header"]),
            Paragraph("Regulation", styles["table_header"]),
            Paragraph("Severity", styles["table_header"]),
        ]]
        if not issues:
            rows.append([
                Paragraph("-", styles["table_cell"]),
                Paragraph("-", styles["table_cell"]),
                Paragraph("No issues were flagged during this evaluation.", styles["table_cell"]),
                Paragraph("—", styles["table_cell"]),
                Paragraph("—", styles["table_cell"]),
            ])
        else:
            for issue in issues:
                sev = (issue.severity or "").strip().lower()
                sev_label = "Critical" if sev == "critical" else "Moderate" if sev == "warning" else sev.title() if sev else "N/A"
                rows.append([
                    Paragraph(self._safe_text(issue.field_name, "N/A"), styles["table_cell"]),
                    Paragraph(self._safe_text(issue.issue_type, "N/A"), styles["table_cell"]),
                    Paragraph(self._safe_text(issue.description, "N/A"), styles["table_cell"]),
                    Paragraph(self._safe_text(issue.regulation_reference, "—"), styles["table_cell"]),
                    Paragraph(self._safe_text(sev_label, "N/A"), styles["table_cell"]),
                ])
        table = LongTable(rows, colWidths=[52 * mm, 26 * mm, 60 * mm, 22 * mm, 20 * mm], repeatRows=1)
        table.setStyle(self._prof_table_style())
        return table

    def _top_issue_dimensions(self, issues: list[IssueSchema]) -> list[dict[str, int | str]]:
        allowed = {"completeness", "accuracy", "consistency", "validity", "timeliness", "uniqueness"}
        counts: dict[str, int] = {}
        for issue in issues:
            dim = (issue.metric_dimension or "").strip().lower()
            if not dim or dim not in allowed:
                continue
            counts[dim] = counts.get(dim, 0) + 1
        ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:2]

    def _remediation_plan(self, remediation_plan: list[dict], styles: dict[str, ParagraphStyle]) -> list:
        story: list = []
        for index, item in enumerate(remediation_plan, start=1):
            details = [
                f"<b>Action {index}:</b> {self._safe_text(item.get('action'), 'No action provided.')}",
                f"<b>Priority:</b> {self._safe_text(item.get('priority'), 'N/A')}",
            ]
            if item.get("regulation"):
                details.append(f"<b>Regulation:</b> {self._safe_text(item.get('regulation'), 'N/A')}")
            if item.get("deadline"):
                details.append(f"<b>Deadline:</b> {self._safe_text(item.get('deadline'), 'N/A')}")
            if item.get("responsible_party"):
                details.append(f"<b>Owner:</b> {self._safe_text(item.get('responsible_party'), 'N/A')}")

            box = Table([[Paragraph("<br/>".join(details), styles["body"])]] , colWidths=[172 * mm])
            box.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#CBD5E1")),
                        ("LEFTPADDING", (0, 0), (-1, -1), 12),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                        ("TOPPADDING", (0, 0), (-1, -1), 10),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ]
                )
            )
            story.append(KeepTogether([box, Spacer(1, 4 * mm)]))
        return story

    def _recommendations(self, recommendations: list[str], styles: dict[str, ParagraphStyle]) -> list:
        story = []
        for item in recommendations:
            story.append(Paragraph(f"&#8226; {self._safe_text(item, '')}", styles["body"]))
        return story

    def _prof_table_style(self) -> TableStyle:
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), self._c("header")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#FFFFFF")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0.5, self._c("border")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, self._c("grid")),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]
        )

    def _safe_text(self, value, fallback: str) -> str:
        if value is None:
            cleaned = ""
        elif isinstance(value, str):
            cleaned = value.strip()
        elif isinstance(value, (list, tuple)):
            cleaned = ", ".join(str(item).strip() for item in value if str(item).strip())
        elif isinstance(value, dict):
            cleaned = json.dumps(value, ensure_ascii=True)
        else:
            cleaned = str(value).strip()

        return str(cleaned).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") or fallback

    def _draw_page(self, canvas, doc) -> None:
        canvas.saveState()
        width, height = A4
        fonts = self._font_names()

        canvas.setStrokeColor(self._c("ink"))
        canvas.setLineWidth(1)
        canvas.line(doc.leftMargin, height - 12 * mm, width - doc.rightMargin, height - 12 * mm)

        canvas.setFont(fonts["bold"], 9.8)
        canvas.setFillColor(self._c("ink"))
        canvas.drawString(doc.leftMargin, height - 9 * mm, "Document Quality Overview")

        canvas.setFont(fonts["regular"], 8)
        canvas.setFillColor(self._c("muted"))
        canvas.drawRightString(width - doc.rightMargin, height - 9 * mm, "Confidential")

        canvas.setStrokeColor(self._c("grid"))
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 15 * mm, width - doc.rightMargin, 15 * mm)

        # Match product naming
        canvas.setFillColor(self._c("muted"))
        canvas.drawString(doc.leftMargin, 10 * mm, "Generated by Document Quality Intelligence")
        canvas.drawRightString(width - doc.rightMargin, 10 * mm, f"Page {canvas.getPageNumber()}")

        canvas.restoreState()
