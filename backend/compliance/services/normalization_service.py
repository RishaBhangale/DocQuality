"""
Normalization Service — Phase 2.

Per semantic_type, applies a normalization schema to transform
extracted text + LLM-extracted fields into structured, validated data.
Produces the Gold layer (DocumentNormalized).
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from compliance.models.db_models import DocumentExtracted, DocumentNormalized, IngestionEvent

logger = logging.getLogger(__name__)


# ── Normalization schemas per semantic type ──────────────────────

NORMALIZATION_SCHEMAS: dict[str, dict[str, Any]] = {
    "isms_policy": {
        "required_fields": [
            "title", "version", "owner", "classification",
            "effective_date", "review_date",
        ],
        "optional_fields": [
            "approval_authority", "scope", "objectives",
            "risk_methodology", "annex_a_controls", "sections",
        ],
        "date_fields": ["effective_date", "review_date"],
    },
    "privacy_policy": {
        "required_fields": [
            "organization_name", "dpo_contact", "data_categories",
            "lawful_bases", "retention_periods",
        ],
        "optional_fields": [
            "dpia_reference", "international_transfers",
            "security_measures", "dsar_procedure",
        ],
        "date_fields": ["effective_date", "last_updated"],
    },
    "ropa_record": {
        "required_fields": [
            "processing_activity", "data_subjects", "data_categories",
            "purpose", "lawful_basis", "retention_period",
        ],
        "optional_fields": [
            "recipients", "third_country_transfers", "safeguards",
            "technical_measures",
        ],
        "date_fields": [],
    },
    "ai_risk_assessment": {
        "required_fields": [
            "model_name", "model_architecture", "intended_use",
            "risk_entries",
        ],
        "optional_fields": [
            "training_data_description", "fairness_metrics",
            "explainability_method", "human_oversight",
            "robustness_results", "governance_structure",
        ],
        "date_fields": ["assessment_date"],
    },
    "ai_policy": {
        "required_fields": [
            "title", "scope", "ai_principles", "governance_roles",
        ],
        "optional_fields": [
            "lifecycle_stages", "risk_framework",
            "monitoring_procedures", "compliance_references",
        ],
        "date_fields": ["effective_date", "review_date"],
    },
    "general": {
        "required_fields": ["title"],
        "optional_fields": ["author", "date", "sections"],
        "date_fields": ["date"],
    },
}


class NormalizationService:
    """
    Transforms extracted data into structured, validated fields
    per document semantic type.
    """

    # Common date patterns for normalization
    DATE_PATTERNS = [
        r"\d{4}-\d{2}-\d{2}",           # 2025-01-15
        r"\d{2}/\d{2}/\d{4}",           # 01/15/2025
        r"\d{2}\.\d{2}\.\d{4}",         # 15.01.2025
        r"[A-Z][a-z]+ \d{1,2},? \d{4}",  # January 15, 2025
    ]

    def normalize(
        self,
        extracted: DocumentExtracted,
        llm_fields: dict[str, Any],
        db: Session,
    ) -> DocumentNormalized:
        """
        Normalize extracted data into structured fields.

        Args:
            extracted: Silver layer record with raw text and semantic type.
            llm_fields: Fields extracted by the LLM during evaluation.
            db: Database session.

        Returns:
            DocumentNormalized record (Gold layer).
        """
        semantic_type = extracted.semantic_type or "general"
        schema = NORMALIZATION_SCHEMAS.get(semantic_type, NORMALIZATION_SCHEMAS["general"])

        logger.info(
            "Normalizing document (type=%s) with %d required fields",
            semantic_type, len(schema["required_fields"]),
        )

        structured = {}
        validation_errors = []

        # ── Required fields ──────────────────────────────────────
        for field in schema["required_fields"]:
            value = llm_fields.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                validation_errors.append({
                    "field": field,
                    "error": "missing_required",
                    "message": f"Required field '{field}' is missing or empty.",
                })
                structured[field] = None
            else:
                structured[field] = self._clean_value(field, value, schema)

        # ── Optional fields ──────────────────────────────────────
        for field in schema.get("optional_fields", []):
            value = llm_fields.get(field)
            if value is not None:
                structured[field] = self._clean_value(field, value, schema)

        # ── Date validation ──────────────────────────────────────
        for date_field in schema.get("date_fields", []):
            raw_date = structured.get(date_field)
            if raw_date and isinstance(raw_date, str):
                parsed = self._parse_date(raw_date)
                if parsed:
                    structured[date_field] = parsed
                else:
                    validation_errors.append({
                        "field": date_field,
                        "error": "invalid_date",
                        "message": f"Could not parse date: '{raw_date}'",
                    })

        # ── Risk entries validation (AI type) ────────────────────
        if semantic_type in ("ai_risk_assessment",) and "risk_entries" in structured:
            risk_errors = self._validate_risk_entries(structured.get("risk_entries", []))
            validation_errors.extend(risk_errors)

        # ── Persist ──────────────────────────────────────────────
        if extracted.normalized:
            normalized = extracted.normalized
            normalized.version += 1
            normalized.structured_fields_json = json.dumps(structured, default=str)
            normalized.validation_errors_json = json.dumps(validation_errors) if validation_errors else None
        else:
            normalized = DocumentNormalized(
                document_extracted_id=extracted.id,
                version=1,
                structured_fields_json=json.dumps(structured, default=str),
                validation_errors_json=json.dumps(validation_errors) if validation_errors else None,
            )
            db.add(normalized)

        logger.info(
            "Normalization complete: %d fields structured, %d validation errors",
            len(structured), len(validation_errors),
        )

        return normalized

    def _clean_value(self, field: str, value: Any, schema: dict) -> Any:
        """Clean and normalize a field value."""
        if isinstance(value, str):
            value = value.strip()
            # Standardize field name casing
            if field in ("title", "organization_name", "model_name"):
                value = value.title() if value == value.lower() else value
        return value

    def _parse_date(self, raw: str) -> Optional[str]:
        """Attempt to parse a date string into ISO format."""
        for pattern in self.DATE_PATTERNS:
            match = re.search(pattern, raw)
            if match:
                try:
                    # Try common formats
                    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d.%m.%Y", "%B %d, %Y", "%B %d %Y"):
                        try:
                            dt = datetime.strptime(match.group(), fmt)
                            return dt.strftime("%Y-%m-%d")
                        except ValueError:
                            continue
                except Exception:
                    pass
        return None

    def _validate_risk_entries(self, entries: Any) -> list[dict]:
        """Validate risk register entries for AI risk assessments."""
        errors = []
        if not isinstance(entries, list):
            errors.append({
                "field": "risk_entries",
                "error": "invalid_type",
                "message": "risk_entries should be a list of risk objects.",
            })
            return errors

        required_risk_fields = {"scenario", "likelihood", "impact", "mitigation"}
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append({
                    "field": f"risk_entries[{i}]",
                    "error": "invalid_type",
                    "message": f"Risk entry {i} is not an object.",
                })
                continue
            missing = required_risk_fields - set(entry.keys())
            if missing:
                errors.append({
                    "field": f"risk_entries[{i}]",
                    "error": "missing_fields",
                    "message": f"Risk entry {i} missing: {', '.join(missing)}",
                })
        return errors
