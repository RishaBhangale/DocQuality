"""
AI Insight Engine.

Generates deterministic issue → impact → recommendation insights
based on type-specific metric results. Works entirely without LLM
as a local fallback for the executive summary and recommendations.

Inspired by the standalone Streamlit app's insight logic, expanded
to cover all metrics across all document types.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class InsightEntry:
    """Single insight with issue, impact, and recommendation."""

    def __init__(self, issue: str, impact: str, recommendation: str, severity: str = "warning"):
        self.issue = issue
        self.impact = impact
        self.recommendation = recommendation
        self.severity = severity

    def to_dict(self) -> dict:
        return {
            "issue": self.issue,
            "impact": self.impact,
            "recommendation": self.recommendation,
            "severity": self.severity,
        }


def generate_insights(
    document_type: str,
    core_metrics: dict[str, float],
    type_specific_metrics: list[dict[str, Any]] | None = None,
    issues_count: int = 0,
) -> dict[str, Any]:
    """
    Generate deterministic AI insights from metric scores.

    Args:
        document_type: Detected document type.
        core_metrics: Dict of core metric name → score.
        type_specific_metrics: List of type-specific metric dicts.
        issues_count: Total number of issues detected.

    Returns:
        Dict with 'insights' (list), 'executive_summary' (str),
        'risk_summary' (str), and 'recommendations' (list[str]).
    """
    insights: list[InsightEntry] = []

    # --- Core metric insights ---
    _core_insights(core_metrics, insights)

    # --- Type-specific insights ---
    if type_specific_metrics:
        ts_dict = {m["name"]: m["score"] for m in type_specific_metrics}
        doc_type = document_type.lower().strip()

        if doc_type == "contract":
            _contract_insights(ts_dict, insights)
        elif doc_type == "invoice":
            _invoice_insights(ts_dict, insights)
        elif doc_type in ("json", "json_document", "json_data"):
            _json_insights(ts_dict, insights)
        elif doc_type in ("social_media", "social media", "tweet", "post"):
            _social_media_insights(ts_dict, insights)

    # Build outputs
    recommendations = [i.recommendation for i in insights]
    risk_summary = _build_risk_summary(insights, issues_count)
    executive_summary = _build_executive_summary(
        document_type, core_metrics, insights, issues_count
    )

    return {
        "insights": [i.to_dict() for i in insights],
        "executive_summary": executive_summary,
        "risk_summary": risk_summary,
        "recommendations": recommendations,
    }


# =============================================================================
# Core Metric Insights
# =============================================================================

def _core_insights(metrics: dict[str, float], out: list[InsightEntry]) -> None:
    """Generate insights from core quality metrics."""

    completeness = metrics.get("completeness", 100)
    if completeness < 70:
        out.append(InsightEntry(
            issue="Significant number of required fields are missing.",
            impact="Downstream systems may fail or produce incorrect results due to missing data.",
            recommendation="Review extraction pipeline and ensure all required fields are captured.",
            severity="critical",
        ))
    elif completeness < 90:
        out.append(InsightEntry(
            issue="Some required fields are missing from the document.",
            impact="Data completeness may affect reporting accuracy.",
            recommendation="Verify that all expected fields are present before processing.",
        ))

    validity = metrics.get("validity", 100)
    if validity < 70:
        out.append(InsightEntry(
            issue="Multiple field values do not conform to expected formats.",
            impact="Invalid data formats can cause processing errors and data corruption.",
            recommendation="Implement format validation rules during data ingestion.",
            severity="critical",
        ))
    elif validity < 90:
        out.append(InsightEntry(
            issue="Some fields have minor format inconsistencies.",
            impact="May cause parsing issues in downstream systems.",
            recommendation="Standardize date, phone, and email formats across the pipeline.",
        ))

    consistency = metrics.get("consistency", 100)
    if consistency < 70:
        out.append(InsightEntry(
            issue="Logical inconsistencies detected between related fields.",
            impact="Cross-field relationships are broken, compromising data integrity.",
            recommendation="Add cross-field validation rules to catch arithmetic and logical errors.",
            severity="critical",
        ))

    accuracy = metrics.get("accuracy", 100)
    if accuracy < 70:
        out.append(InsightEntry(
            issue="Extracted values could not be verified against source text.",
            impact="Unverifiable data reduces confidence in extracted information.",
            recommendation="Review extraction accuracy and consider re-processing with improved methods.",
            severity="critical",
        ))

    timeliness = metrics.get("timeliness", 100)
    if timeliness < 70:
        out.append(InsightEntry(
            issue="Document contains expired or outdated date information.",
            impact="Stale data may lead to compliance violations or incorrect decisions.",
            recommendation="Update expired dates and establish a document refresh cadence.",
        ))

    uniqueness = metrics.get("uniqueness", 100)
    if uniqueness < 90:
        out.append(InsightEntry(
            issue="Duplicate entries detected in document data.",
            impact="Duplicate records may distort reporting and analytics results.",
            recommendation="Apply deduplication checks during data ingestion.",
        ))


# =============================================================================
# Contract-Specific Insights
# =============================================================================

def _contract_insights(ts: dict[str, float], out: list[InsightEntry]) -> None:
    sig = ts.get("Signature Presence", 100)
    if sig < 50:
        out.append(InsightEntry(
            issue="Contract signature is missing or incomplete.",
            impact="Contract may not be legally enforceable without proper signatures.",
            recommendation="Ensure all parties have signed the document with authorized signatories.",
            severity="critical",
        ))

    clause = ts.get("Clause Completeness", 100)
    if clause < 70:
        out.append(InsightEntry(
            issue="Several standard contract clauses are missing.",
            impact="Missing clauses may leave parties unprotected in disputes.",
            recommendation="Add standard clauses: termination, liability, confidentiality, governing law.",
            severity="critical",
        ))

    risk = ts.get("Risk Clause Detection", 100)
    if risk < 70:
        out.append(InsightEntry(
            issue="Multiple risky clauses detected (e.g., auto-renewal, unlimited liability).",
            impact="Risky terms may expose the organization to financial or legal liability.",
            recommendation="Review flagged clauses with legal counsel before execution.",
            severity="critical",
        ))

    meta = ts.get("Metadata Completeness", 100)
    if meta < 80:
        out.append(InsightEntry(
            issue="Contract metadata is incomplete (missing dates, parties, or reference numbers).",
            impact="Incomplete metadata reduces contract traceability and searchability.",
            recommendation="Ensure contract number, effective/expiration dates, and party names are present.",
        ))


# =============================================================================
# Invoice-Specific Insights
# =============================================================================

def _invoice_insights(ts: dict[str, float], out: list[InsightEntry]) -> None:
    amount = ts.get("Amount Consistency", 100)
    if amount < 100:
        out.append(InsightEntry(
            issue="Invoice subtotal and tax do not match the total amount.",
            impact="Financial discrepancies may lead to payment errors or audit findings.",
            recommendation="Validate invoice arithmetic (subtotal + tax = total) during ingestion.",
            severity="critical",
        ))

    ocr = ts.get("OCR Confidence", 100)
    if ocr < 80:
        out.append(InsightEntry(
            issue="OCR text extraction confidence is low.",
            impact="Extracted text may contain errors affecting all downstream quality checks.",
            recommendation="Use higher-quality scans or consider manual verification for critical fields.",
        ))

    field = ts.get("Field Completeness", 100)
    if field < 80:
        out.append(InsightEntry(
            issue="Key invoice fields are missing (e.g., invoice number, due date, payment terms).",
            impact="Incomplete invoices cannot be processed for payment.",
            recommendation="Ensure all mandatory invoice fields are captured before submission.",
        ))


# =============================================================================
# JSON-Specific Insights
# =============================================================================

def _json_insights(ts: dict[str, float], out: list[InsightEntry]) -> None:
    type_val = ts.get("Type Validation", 100)
    if type_val < 100:
        out.append(InsightEntry(
            issue="Data type mismatches detected (e.g., numbers stored as strings).",
            impact="Financial analytics may produce incorrect totals due to type coercion.",
            recommendation="Convert numeric fields to proper data types before analytics.",
        ))

    schema = ts.get("Schema Compliance", 100)
    if schema < 90:
        out.append(InsightEntry(
            issue="JSON records do not conform to a consistent schema.",
            impact="Inconsistent structure may cause data pipeline failures.",
            recommendation="Enforce schema validation during data ingestion.",
            severity="critical",
        ))

    drift = ts.get("Schema Drift Rate", 100)
    if drift < 80:
        out.append(InsightEntry(
            issue="Schema drift detected — records have inconsistent key structures.",
            impact="Structural drift can break downstream data consumers.",
            recommendation="Monitor schema changes and version your data contracts.",
        ))

    cross = ts.get("Cross-Field Consistency", 100)
    if cross < 90:
        out.append(InsightEntry(
            issue="Logical inconsistencies between JSON fields detected.",
            impact="Cross-field errors may produce incorrect aggregations.",
            recommendation="Add cross-field validation rules to your data pipeline.",
        ))


# =============================================================================
# Social Media-Specific Insights
# =============================================================================

def _social_media_insights(ts: dict[str, float], out: list[InsightEntry]) -> None:
    offensive = ts.get("Offensive Rate", 100)
    if offensive < 80:
        out.append(InsightEntry(
            issue="Offensive or toxic content detected in the data.",
            impact="Unfiltered offensive content may cause brand damage or compliance issues.",
            recommendation="Implement content moderation filters before public-facing use.",
            severity="critical",
        ))

    spam = ts.get("Spam Detection", 100)
    if spam < 80:
        out.append(InsightEntry(
            issue="Spam indicators detected (excessive links, promotional language).",
            impact="Spam data can skew analytics and degrade data quality.",
            recommendation="Apply spam filters and remove promotional content from datasets.",
        ))

    lang = ts.get("Language Consistency", 100)
    if lang < 80:
        out.append(InsightEntry(
            issue="Inconsistent language use detected (high slang or mixed-language content).",
            impact="Language inconsistency may affect NLP processing and sentiment analysis.",
            recommendation="Normalize text and filter by target language before analysis.",
        ))


# =============================================================================
# Summary Builders
# =============================================================================

def _build_risk_summary(insights: list[InsightEntry], issues_count: int) -> str:
    """Build a human-readable risk summary."""
    critical = sum(1 for i in insights if i.severity == "critical")
    warnings = sum(1 for i in insights if i.severity == "warning")

    if critical == 0 and warnings == 0:
        return "No significant quality risks detected. Document meets quality standards."

    parts = []
    if critical > 0:
        parts.append(f"{critical} critical risk(s)")
    if warnings > 0:
        parts.append(f"{warnings} warning(s)")

    risk_level = "HIGH" if critical >= 2 else "MODERATE" if critical >= 1 else "LOW"
    return (
        f"Risk Level: {risk_level}. "
        f"Detected {' and '.join(parts)} across {issues_count} total issue(s). "
        f"Review recommendations before proceeding."
    )


def _build_executive_summary(
    document_type: str,
    core_metrics: dict[str, float],
    insights: list[InsightEntry],
    issues_count: int,
) -> str:
    """Build an executive summary from metrics and insights."""
    avg_score = sum(core_metrics.values()) / max(len(core_metrics), 1)

    if avg_score >= 90 and len(insights) == 0:
        return (
            f"The {document_type} document demonstrates excellent data quality "
            f"with an average core metric score of {avg_score:.0f}%. "
            f"No significant issues detected."
        )

    summary = (
        f"Quality analysis of {document_type} document completed. "
        f"Average core metric score: {avg_score:.0f}%. "
    )

    if issues_count > 0:
        summary += f"{issues_count} issue(s) were identified. "

    if insights:
        top_issues = [i.issue for i in insights[:3]]
        summary += "Key findings: " + " ".join(top_issues)

    return summary
