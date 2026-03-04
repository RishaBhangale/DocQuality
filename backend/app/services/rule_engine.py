"""
Deterministic Rule Engine.

Performs reproducible, deterministic quality evaluation on structured
document fields. Each metric is calculated independently with detected issues.

The LLM does NOT decide the final score — this engine does.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from app.models.schemas import IssueSchema

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Deterministic rule engine for document quality metrics.

    Each method accepts structured fields and returns a numeric score (0–100)
    along with a list of detected issues.
    """

    # Common required fields by document type
    REQUIRED_FIELDS_MAP: dict[str, list[str]] = {
        "invoice": [
            "invoice_number", "invoice_date", "due_date", "vendor_name",
            "customer_name", "total_amount", "line_items", "currency",
            "billing_address",
        ],
        "contract": [
            "contract_number", "effective_date", "expiration_date",
            "party_a", "party_b", "terms", "signatures",
        ],
        "report": [
            "title", "author", "date", "summary", "sections",
        ],
        "form": [
            "form_id", "date", "name", "signature",
        ],
        "letter": [
            "sender", "recipient", "date", "subject", "body",
        ],
    }

    # Default required fields when document type is unknown
    DEFAULT_REQUIRED_FIELDS: list[str] = [
        "date", "name", "title", "reference_number",
    ]

    # Common field format patterns
    FORMAT_PATTERNS: dict[str, str] = {
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "phone": r"^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]*$",
        "date": r"\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}",
        "currency_amount": r"^[\$€£¥]?\s?\d{1,3}(,\d{3})*(\.\d{2})?$",
        "postal_code": r"^\d{5}(-\d{4})?$|^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$",
        "url": r"^https?://[^\s]+$",
    }

    def calculate_completeness(
        self, fields: dict[str, Any], document_type: str = "unknown"
    ) -> tuple[float, list[IssueSchema]]:
        """
        Calculate completeness score based on presence of required fields.

        Completeness = filled_required / total_required * 100

        Args:
            fields: Extracted structured fields.
            document_type: Detected document type.

        Returns:
            Tuple of (score, list of issues).
        """
        issues: list[IssueSchema] = []
        doc_type = document_type.lower().strip()
        required_fields = self.REQUIRED_FIELDS_MAP.get(
            doc_type, self.DEFAULT_REQUIRED_FIELDS
        )

        if not required_fields:
            return 100.0, issues

        total_required = len(required_fields)
        filled_count = 0

        for field in required_fields:
            # Check if field exists and has a non-empty value
            value = fields.get(field)
            if value is not None and str(value).strip():
                filled_count += 1
            else:
                issues.append(IssueSchema(
                    field_name=field.replace("_", " ").title(),
                    issue_type="Missing Field",
                    description=f"Required field '{field.replace('_', ' ').title()}' not detected in document",
                    severity="critical" if field in self._get_critical_fields(doc_type) else "warning",
                ))

        score = (filled_count / total_required) * 100 if total_required > 0 else 100.0
        logger.info(
            "Completeness: %d/%d fields filled (%.1f%%)",
            filled_count, total_required, score
        )
        return round(score, 1), issues

    def calculate_validity(
        self, fields: dict[str, Any]
    ) -> tuple[float, list[IssueSchema]]:
        """
        Calculate validity score based on format compliance.

        Checks field values against expected format patterns.

        Args:
            fields: Extracted structured fields.

        Returns:
            Tuple of (score, list of issues).
        """
        issues: list[IssueSchema] = []
        if not fields:
            return 100.0, issues

        total_checks = 0
        passed_checks = 0

        for field_name, value in fields.items():
            if value is None or str(value).strip() == "":
                continue

            str_value = str(value).strip()
            field_lower = field_name.lower()

            # Determine which format check to apply
            if "email" in field_lower:
                total_checks += 1
                if re.match(self.FORMAT_PATTERNS["email"], str_value):
                    passed_checks += 1
                else:
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Invalid Format",
                        description=f"Value '{str_value[:50]}' does not match expected email format",
                        severity="warning",
                    ))

            elif "phone" in field_lower or "tel" in field_lower:
                total_checks += 1
                if re.match(self.FORMAT_PATTERNS["phone"], str_value):
                    passed_checks += 1
                else:
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Invalid Format",
                        description=f"Value '{str_value[:50]}' does not match expected phone format",
                        severity="warning",
                    ))

            elif "date" in field_lower:
                total_checks += 1
                if re.search(self.FORMAT_PATTERNS["date"], str_value):
                    passed_checks += 1
                else:
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Invalid Format",
                        description=f"Value '{str_value[:50]}' does not match expected date format",
                        severity="warning",
                    ))

            elif any(kw in field_lower for kw in ["amount", "total", "price", "cost", "fee"]):
                total_checks += 1
                # Check if it looks like a number
                clean_val = re.sub(r"[,$€£¥\s]", "", str_value)
                try:
                    float(clean_val)
                    passed_checks += 1
                except ValueError:
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Invalid Format",
                        description=f"Value '{str_value[:50]}' is not a valid numeric amount",
                        severity="critical",
                    ))

            elif "url" in field_lower or "website" in field_lower:
                total_checks += 1
                if re.match(self.FORMAT_PATTERNS["url"], str_value):
                    passed_checks += 1
                else:
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Invalid Format",
                        description=f"Value '{str_value[:50]}' does not match expected URL format",
                        severity="warning",
                    ))

        if total_checks == 0:
            return 100.0, issues

        score = (passed_checks / total_checks) * 100
        logger.info("Validity: %d/%d checks passed (%.1f%%)", passed_checks, total_checks, score)
        return round(score, 1), issues

    def calculate_consistency(
        self, fields: dict[str, Any]
    ) -> tuple[float, list[IssueSchema]]:
        """
        Calculate consistency score based on logical relationships between fields.

        Example checks:
        - Line items should sum to total amount
        - Date logical ordering (start before end)
        - Cross-field agreement

        Args:
            fields: Extracted structured fields.

        Returns:
            Tuple of (score, list of issues).
        """
        issues: list[IssueSchema] = []
        if not fields:
            return 100.0, issues

        consistency_checks = 0
        passed_checks = 0

        # Check 1: Line items sum vs total amount
        line_items = fields.get("line_items")
        total_amount = fields.get("total_amount")

        if line_items and total_amount:
            consistency_checks += 1
            try:
                if isinstance(line_items, list):
                    items_sum = sum(
                        float(re.sub(r"[,$€£¥\s]", "", str(item.get("amount", item.get("total", 0)))))
                        for item in line_items
                        if isinstance(item, dict)
                    )
                    total_val = float(re.sub(r"[,$€£¥\s]", "", str(total_amount)))
                    if abs(items_sum - total_val) < 0.01:
                        passed_checks += 1
                    else:
                        issues.append(IssueSchema(
                            field_name="Total Amount",
                            issue_type="Inconsistent Value",
                            description=f"Line items sum ({items_sum:.2f}) does not match total amount ({total_val:.2f})",
                            severity="critical",
                        ))
            except (ValueError, TypeError) as e:
                logger.debug("Could not check line items consistency: %s", str(e))

        # Check 2: Date ordering (start/invoice date before due/end date)
        date_pairs = [
            ("invoice_date", "due_date"),
            ("start_date", "end_date"),
            ("effective_date", "expiration_date"),
            ("created_date", "modified_date"),
        ]

        for start_field, end_field in date_pairs:
            start_val = fields.get(start_field)
            end_val = fields.get(end_field)

            if start_val and end_val:
                consistency_checks += 1
                start_date = self._parse_date(str(start_val))
                end_date = self._parse_date(str(end_val))

                if start_date and end_date:
                    if start_date <= end_date:
                        passed_checks += 1
                    else:
                        issues.append(IssueSchema(
                            field_name=end_field.replace("_", " ").title(),
                            issue_type="Logical Inconsistency",
                            description=f"'{end_field.replace('_', ' ').title()}' ({end_val}) is before '{start_field.replace('_', ' ').title()}' ({start_val})",
                            severity="critical",
                        ))
                else:
                    passed_checks += 1  # Can't parse dates, assume ok

        # Check 3: Name consistency (vendor/sender name appears in address)
        name_address_pairs = [
            ("vendor_name", "vendor_address"),
            ("customer_name", "billing_address"),
            ("sender", "sender_address"),
        ]

        for name_field, addr_field in name_address_pairs:
            name_val = fields.get(name_field)
            addr_val = fields.get(addr_field)
            if name_val and addr_val:
                consistency_checks += 1
                passed_checks += 1  # Soft check - don't penalize if name not in address

        if consistency_checks == 0:
            return 100.0, issues

        score = (passed_checks / consistency_checks) * 100
        logger.info("Consistency: %d/%d checks passed (%.1f%%)", passed_checks, consistency_checks, score)
        return round(score, 1), issues

    def calculate_timeliness(
        self, fields: dict[str, Any]
    ) -> tuple[float, list[IssueSchema]]:
        """
        Calculate timeliness score based on data recency.

        Checks if dates are within reasonable ranges and not expired.

        Args:
            fields: Extracted structured fields.

        Returns:
            Tuple of (score, list of issues).
        """
        issues: list[IssueSchema] = []
        if not fields:
            return 100.0, issues

        time_checks = 0
        passed_checks = 0
        now = datetime.now()

        date_fields = [
            key for key in fields.keys()
            if "date" in key.lower() or "expir" in key.lower() or "valid" in key.lower()
        ]

        for field_name in date_fields:
            value = fields.get(field_name)
            if not value:
                continue

            parsed_date = self._parse_date(str(value))
            if not parsed_date:
                continue

            time_checks += 1
            field_lower = field_name.lower()

            # Check for expired dates
            if any(kw in field_lower for kw in ["expir", "valid_until", "due_date"]):
                if parsed_date < now:
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Expired Date",
                        description=f"Date '{value}' has already passed",
                        severity="critical",
                    ))
                else:
                    passed_checks += 1

            # Check if document date is unreasonably old (>2 years)
            elif any(kw in field_lower for kw in ["invoice_date", "created", "issue_date"]):
                age = now - parsed_date
                if age > timedelta(days=730):
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Outdated Data",
                        description=f"Date '{value}' is more than 2 years old",
                        severity="warning",
                    ))
                else:
                    passed_checks += 1

            # Check for future dates that shouldn't be in the future
            elif any(kw in field_lower for kw in ["invoice_date", "created", "signed"]):
                if parsed_date > now + timedelta(days=1):
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Future Date",
                        description=f"Date '{value}' is in the future which may indicate an error",
                        severity="warning",
                    ))
                else:
                    passed_checks += 1
            else:
                passed_checks += 1

        if time_checks == 0:
            return 100.0, issues

        score = (passed_checks / time_checks) * 100
        logger.info("Timeliness: %d/%d checks passed (%.1f%%)", passed_checks, time_checks, score)
        return round(score, 1), issues

    def calculate_uniqueness(
        self, fields: dict[str, Any]
    ) -> tuple[float, list[IssueSchema]]:
        """
        Calculate uniqueness score based on duplicate detection.

        Checks for redundant data entries within the document.

        Args:
            fields: Extracted structured fields.

        Returns:
            Tuple of (score, list of issues).
        """
        issues: list[IssueSchema] = []
        if not fields:
            return 100.0, issues

        # Check for duplicate values across fields
        value_map: dict[str, list[str]] = {}
        for field_name, value in fields.items():
            if value is None:
                continue
            str_val = str(value).strip().lower()
            if len(str_val) > 3:  # Skip very short values
                if str_val not in value_map:
                    value_map[str_val] = []
                value_map[str_val].append(field_name)

        duplicates = {val: names for val, names in value_map.items() if len(names) > 1}

        # Check for duplicate line items
        line_items = fields.get("line_items")
        duplicate_items = 0
        if isinstance(line_items, list) and len(line_items) > 1:
            seen = set()
            for item in line_items:
                item_str = str(item).strip().lower()
                if item_str in seen:
                    duplicate_items += 1
                seen.add(item_str)

            if duplicate_items > 0:
                issues.append(IssueSchema(
                    field_name="Line Items",
                    issue_type="Duplicate Entry",
                    description=f"{duplicate_items} duplicate line item(s) detected",
                    severity="warning",
                ))

        for val, field_names in duplicates.items():
            # Skip expected duplicates (same value in related fields is normal)
            if len(field_names) == 2 and any(
                "name" in f.lower() for f in field_names
            ):
                continue
            issues.append(IssueSchema(
                field_name=", ".join(f.replace("_", " ").title() for f in field_names),
                issue_type="Duplicate Value",
                description=f"Same value '{val[:50]}' found in multiple fields",
                severity="warning",
            ))

        total_fields = max(len(fields), 1)
        duplicate_count = len(duplicates) + duplicate_items
        score = max(0, 100 - (duplicate_count / total_fields * 100))

        logger.info("Uniqueness: %d duplicates in %d fields (%.1f%%)", duplicate_count, total_fields, score)
        return round(min(score, 100), 1), issues

    def calculate_accuracy(
        self, fields: dict[str, Any], document_text: str = ""
    ) -> tuple[float, list[IssueSchema]]:
        """
        Calculate accuracy score based on data correctness validation.

        Performs cross-reference checks between extracted fields and source text,
        and validates plausibility of values.

        Args:
            fields: Extracted structured fields.
            document_text: Original document text for cross-reference.

        Returns:
            Tuple of (score, list of issues).
        """
        issues: list[IssueSchema] = []
        if not fields:
            return 100.0, issues

        accuracy_checks = 0
        passed_checks = 0

        for field_name, value in fields.items():
            if value is None or str(value).strip() == "":
                continue

            str_value = str(value).strip()
            field_lower = field_name.lower()

            # Check 1: If we have source text, verify extracted values appear in it
            if document_text and len(str_value) > 2:
                accuracy_checks += 1
                # Fuzzy presence check
                if str_value.lower() in document_text.lower():
                    passed_checks += 1
                elif any(
                    word.lower() in document_text.lower()
                    for word in str_value.split()
                    if len(word) > 3
                ):
                    passed_checks += 0.8  # Partial match
                else:
                    issues.append(IssueSchema(
                        field_name=field_name.replace("_", " ").title(),
                        issue_type="Unverifiable Value",
                        description=f"Extracted value '{str_value[:50]}' could not be verified in source text",
                        severity="warning",
                    ))

            # Check 2: Plausibility checks for numeric fields
            if any(kw in field_lower for kw in ["amount", "total", "price", "cost"]):
                accuracy_checks += 1
                try:
                    num_val = float(re.sub(r"[,$€£¥\s]", "", str_value))
                    if num_val < 0:
                        issues.append(IssueSchema(
                            field_name=field_name.replace("_", " ").title(),
                            issue_type="Implausible Value",
                            description=f"Negative amount ({num_val}) detected",
                            severity="warning",
                        ))
                    elif num_val > 1_000_000_000:
                        issues.append(IssueSchema(
                            field_name=field_name.replace("_", " ").title(),
                            issue_type="Implausible Value",
                            description=f"Unusually large amount ({num_val:,.2f}) detected",
                            severity="warning",
                        ))
                    else:
                        passed_checks += 1
                except ValueError:
                    pass  # Already caught in validity

        if accuracy_checks == 0:
            return 100.0, issues

        score = (passed_checks / accuracy_checks) * 100
        logger.info("Accuracy: %.1f/%d checks passed (%.1f%%)", passed_checks, accuracy_checks, score)
        return round(min(score, 100), 1), issues

    def _get_critical_fields(self, document_type: str) -> set[str]:
        """Get fields considered critical for a given document type."""
        critical_map: dict[str, set[str]] = {
            "invoice": {"invoice_number", "total_amount", "vendor_name", "invoice_date"},
            "contract": {"contract_number", "party_a", "party_b", "effective_date"},
            "report": {"title", "date"},
            "form": {"form_id", "name"},
            "letter": {"sender", "recipient", "date"},
        }
        return critical_map.get(document_type.lower(), {"date", "name"})

    def _parse_date(self, date_str: str) -> datetime | None:
        """
        Attempt to parse a date string in common formats.

        Args:
            date_str: String representation of a date.

        Returns:
            Parsed datetime or None if parsing fails.
        """
        formats = [
            "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y",
            "%Y/%m/%d", "%d-%m-%Y", "%m-%d-%Y",
            "%B %d, %Y", "%b %d, %Y", "%d %B %Y",
            "%d %b %Y", "%Y.%m.%d", "%d.%m.%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        return None
