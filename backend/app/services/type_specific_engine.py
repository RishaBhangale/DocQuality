"""
Document-Type-Specific Metric Engine.

Provides specialized quality metrics that activate based on the detected
document type. Each document type has its own set of metrics that supplement
the core metrics computed by the main rule engine.

Supported document types:
- Contract: clause completeness, signature presence, metadata, risk clauses
- Invoice: field completeness, OCR confidence, amount consistency
- JSON: schema compliance, type validation, cross-field consistency, drift rate
- Social Media: language consistency, offensive rate, spam detection
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# --- Result Container ---

class TypeSpecificResult:
    """Container for a single type-specific metric result."""

    def __init__(
        self,
        name: str,
        score: float,
        description: str,
        status: str,
        details: str,
        document_type: str,
    ):
        self.name = name
        self.score = max(0.0, min(100.0, round(score, 1)))
        self.description = description
        self.status = status
        self.details = details
        self.document_type = document_type

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": self.score,
            "description": self.description,
            "status": self.status,
            "details": self.details,
            "document_type": self.document_type,
        }


def _determine_status(score: float) -> str:
    """Determine metric status from score."""
    if score >= 90:
        return "good"
    elif score >= 70:
        return "warning"
    else:
        return "critical"


# =============================================================================
# Main Entry Point
# =============================================================================

def evaluate_type_specific(
    document_type: str,
    fields: dict[str, Any],
    text: str,
    file_path: str = "",
    raw_json: Any = None,
) -> list[TypeSpecificResult]:
    """
    Run type-specific metrics for a given document type.

    Args:
        document_type: Detected document type (e.g., "contract", "invoice").
        fields: Structured fields extracted by the LLM.
        text: Normalized document text.
        file_path: Path to the original file (for OCR confidence).
        raw_json: Parsed JSON data (for JSON-specific metrics).

    Returns:
        List of TypeSpecificResult objects.
    """
    doc_type = document_type.lower().strip()
    logger.info("Running type-specific metrics for document type: %s", doc_type)

    if doc_type == "contract":
        return _evaluate_contract(fields, text)
    elif doc_type == "invoice":
        return _evaluate_invoice(fields, text, file_path)
    elif doc_type in ("json", "json_document", "json_data"):
        return _evaluate_json(fields, text, raw_json)
    elif doc_type in ("social_media", "social media", "tweet", "post", "social media post"):
        return _evaluate_social_media(fields, text)
    elif doc_type in ("tabular", "csv", "table", "dataset", "spreadsheet"):
        return _evaluate_tabular(fields, text)
    elif doc_type in ("markup", "xml", "html", "htm", "webpage"):
        return _evaluate_markup(fields, text)
    elif doc_type in ("email", "eml", "mail", "message"):
        return _evaluate_email(fields, text)
    else:
        # General Document — fallback for any unmatched type
        logger.info("Using general document metrics for type: %s", doc_type)
        return _evaluate_general(fields, text)


# =============================================================================
# CONTRACT METRICS
# =============================================================================

def _evaluate_contract(fields: dict, text: str) -> list[TypeSpecificResult]:
    """Run all contract-specific metrics."""
    results = []
    results.append(_contract_clause_completeness(text))
    results.append(_contract_signature_presence(fields, text))
    results.append(_contract_metadata_completeness(fields))
    results.append(_contract_risk_clause_detection(text))
    return results


def _contract_clause_completeness(text: str) -> TypeSpecificResult:
    """Check for presence of standard contract clauses."""
    standard_clauses = {
        "termination": [r"terminat\w+", r"cancel\w+\s+(?:of\s+)?(?:this\s+)?(?:agreement|contract)"],
        "liability": [r"liabilit\w+", r"liable\b"],
        "indemnity": [r"indemnif\w+", r"indemnit\w+", r"hold\s+harmless"],
        "confidentiality": [r"confidential\w+", r"non-disclosure", r"NDA", r"proprietary\s+information"],
        "governing_law": [r"governing\s+law", r"jurisdiction", r"governed\s+by"],
        "dispute_resolution": [r"dispute\s+resolution", r"arbitrat\w+", r"mediat\w+"],
        "force_majeure": [r"force\s+majeure", r"act\s+of\s+god"],
        "payment_terms": [r"payment\s+term", r"payment\s+schedul", r"compensat\w+"],
        "intellectual_property": [r"intellectual\s+property", r"\bIP\b\s+rights", r"copyright"],
        "warranty": [r"warrant\w+", r"guarantee"],
    }

    text_lower = text.lower()
    found_clauses = []
    missing_clauses = []

    for clause_name, patterns in standard_clauses.items():
        found = any(re.search(p, text_lower) for p in patterns)
        if found:
            found_clauses.append(clause_name)
        else:
            missing_clauses.append(clause_name)

    total = len(standard_clauses)
    score = (len(found_clauses) / total) * 100

    details = f"Found {len(found_clauses)}/{total} standard clauses."
    if missing_clauses:
        details += f" Missing: {', '.join(c.replace('_', ' ').title() for c in missing_clauses[:5])}"

    return TypeSpecificResult(
        name="Clause Completeness",
        score=score,
        description="Checks for presence of standard contract clauses",
        status=_determine_status(score),
        details=details,
        document_type="contract",
    )


def _contract_signature_presence(fields: dict, text: str) -> TypeSpecificResult:
    """Detect signature blocks and signing indicators."""
    text_lower = text.lower()
    indicators = {
        "signature_block": bool(re.search(r"sign(?:ed|ature)\s*(?:by|:)", text_lower)),
        "witness": bool(re.search(r"witness(?:ed|es)?(?:\s+by)?", text_lower)),
        "date_of_signing": bool(re.search(r"(?:date|signed)\s*(?:of|on)?\s*(?:signing|execution)", text_lower)),
        "authorized_signatory": bool(re.search(r"authoriz\w+\s+sign", text_lower)),
        "party_signatures": bool(fields.get("signatures") or re.search(r"(?:party\s+[ab]|first\s+party|second\s+party)\s*:?\s*_+", text_lower)),
    }

    found = sum(1 for v in indicators.values() if v)
    total = len(indicators)
    score = (found / total) * 100

    found_items = [k.replace("_", " ").title() for k, v in indicators.items() if v]
    details = f"Found {found}/{total} signature indicators."
    if found_items:
        details += f" Present: {', '.join(found_items)}"

    return TypeSpecificResult(
        name="Signature Presence",
        score=score,
        description="Detects signature blocks and signing indicators",
        status=_determine_status(score),
        details=details,
        document_type="contract",
    )


def _contract_metadata_completeness(fields: dict) -> TypeSpecificResult:
    """Check for contract metadata fields."""
    metadata_fields = {
        "contract_number": ["contract_number", "contract_id", "agreement_number", "reference_number"],
        "effective_date": ["effective_date", "start_date", "commencement_date"],
        "expiration_date": ["expiration_date", "end_date", "termination_date"],
        "party_a": ["party_a", "first_party", "client", "company"],
        "party_b": ["party_b", "second_party", "vendor", "contractor", "service_provider"],
        "jurisdiction": ["jurisdiction", "governing_law", "applicable_law"],
        "contract_value": ["contract_value", "total_amount", "consideration", "fee"],
    }

    found = 0
    missing = []
    for meta_name, aliases in metadata_fields.items():
        if any(fields.get(alias) for alias in aliases):
            found += 1
        else:
            missing.append(meta_name)

    total = len(metadata_fields)
    score = (found / total) * 100

    details = f"Found {found}/{total} metadata fields."
    if missing:
        details += f" Missing: {', '.join(m.replace('_', ' ').title() for m in missing[:4])}"

    return TypeSpecificResult(
        name="Metadata Completeness",
        score=score,
        description="Checks for essential contract metadata",
        status=_determine_status(score),
        details=details,
        document_type="contract",
    )


def _contract_risk_clause_detection(text: str) -> TypeSpecificResult:
    """Flag potentially risky contract clauses."""
    text_lower = text.lower()
    risk_patterns = {
        "Auto-Renewal": [r"auto(?:-|\s+)?renew", r"automatic(?:ally)?\s+renew"],
        "Unlimited Liability": [r"unlimited\s+liabilit", r"no\s+(?:cap|limit)\s+(?:on\s+)?liabilit"],
        "Non-Compete": [r"non-compet\w+", r"restrictive\s+covenant", r"competition\s+restriction"],
        "Penalty Clause": [r"penalty\s+clause", r"liquidated\s+damages", r"penalt(?:y|ies)\s+for"],
        "Unilateral Termination": [r"sole\s+discretion\s+to\s+terminat", r"unilateral(?:ly)?\s+terminat"],
        "Automatic Assignment": [r"assign\w*\s+without\s+(?:prior\s+)?consent"],
        "Indemnify All": [r"indemnif\w+\s+(?:against\s+)?all\s+(?:claims|losses|damages)"],
    }

    risks_found = []
    for risk_name, patterns in risk_patterns.items():
        if any(re.search(p, text_lower) for p in patterns):
            risks_found.append(risk_name)

    # Higher score = fewer risks (better quality)
    risk_count = len(risks_found)
    if risk_count == 0:
        score = 100
        details = "No risky clauses detected."
    elif risk_count <= 2:
        score = 70
        details = f"{risk_count} risk(s) flagged: {', '.join(risks_found)}"
    else:
        score = max(40, 100 - risk_count * 15)
        details = f"{risk_count} risk(s) flagged: {', '.join(risks_found)}"

    return TypeSpecificResult(
        name="Risk Clause Detection",
        score=score,
        description="Flags potentially risky contract clauses",
        status=_determine_status(score),
        details=details,
        document_type="contract",
    )


# =============================================================================
# INVOICE METRICS
# =============================================================================

def _evaluate_invoice(fields: dict, text: str, file_path: str) -> list[TypeSpecificResult]:
    """Run all invoice-specific metrics."""
    results = []
    results.append(_invoice_field_completeness(fields))
    results.append(_invoice_ocr_confidence(file_path))
    results.append(_invoice_amount_consistency(fields))
    return results


def _invoice_field_completeness(fields: dict) -> TypeSpecificResult:
    """Check for invoice-specific required fields beyond core completeness."""
    invoice_fields = {
        "invoice_number": ["invoice_number", "invoice_no", "inv_number", "bill_number"],
        "invoice_date": ["invoice_date", "bill_date", "date_of_invoice"],
        "due_date": ["due_date", "payment_due", "date_due"],
        "vendor_name": ["vendor_name", "supplier", "seller", "biller", "company_name"],
        "customer_name": ["customer_name", "buyer", "bill_to", "client_name"],
        "line_items": ["line_items", "items", "products", "services"],
        "subtotal": ["subtotal", "sub_total", "net_amount"],
        "tax": ["tax", "tax_amount", "gst", "vat", "sales_tax"],
        "total_amount": ["total_amount", "total", "grand_total", "amount_due"],
        "payment_terms": ["payment_terms", "terms", "payment_method"],
        "currency": ["currency", "currency_code"],
        "billing_address": ["billing_address", "bill_to_address", "customer_address"],
    }

    found = 0
    missing = []
    for field_name, aliases in invoice_fields.items():
        if any(fields.get(alias) for alias in aliases):
            found += 1
        else:
            missing.append(field_name)

    total = len(invoice_fields)
    score = (found / total) * 100

    details = f"Found {found}/{total} invoice fields."
    if missing:
        details += f" Missing: {', '.join(m.replace('_', ' ').title() for m in missing[:5])}"

    return TypeSpecificResult(
        name="Field Completeness",
        score=score,
        description="Checks for invoice-specific required fields",
        status=_determine_status(score),
        details=details,
        document_type="invoice",
    )


def _invoice_ocr_confidence(file_path: str) -> TypeSpecificResult:
    """Assess OCR confidence for image-based invoices."""
    ext = Path(file_path).suffix.lower() if file_path else ""

    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        try:
            from PIL import Image
            import pytesseract

            img = Image.open(file_path)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confidences = [int(c) for c in data.get("conf", []) if int(c) > 0]

            if confidences:
                avg_conf = sum(confidences) / len(confidences)
                score = min(avg_conf, 100)
                details = f"Average OCR confidence: {avg_conf:.1f}% across {len(confidences)} text blocks"
            else:
                score = 0
                details = "No text detected by OCR"

        except Exception as e:
            score = 50
            details = f"OCR analysis failed: {str(e)}"
    elif ext in (".pdf", ".docx"):
        score = 100
        details = "Native text document — no OCR needed (100% confidence)"
    else:
        score = 100
        details = "Non-image document — OCR not applicable"

    return TypeSpecificResult(
        name="OCR Confidence",
        score=score,
        description="Assesses text extraction confidence for image-based documents",
        status=_determine_status(score),
        details=details,
        document_type="invoice",
    )


def _invoice_amount_consistency(fields: dict) -> TypeSpecificResult:
    """Verify arithmetic consistency: subtotal + tax = total, line items sum = subtotal."""
    checks_done = 0
    checks_passed = 0
    issues = []

    def _parse_amount(val: Any) -> Optional[float]:
        if val is None:
            return None
        clean = re.sub(r"[,$€£¥₹\s]", "", str(val))
        try:
            return float(clean)
        except ValueError:
            return None

    # Check 1: subtotal + tax = total
    subtotal = _parse_amount(fields.get("subtotal") or fields.get("sub_total"))
    tax = _parse_amount(fields.get("tax") or fields.get("tax_amount") or fields.get("gst"))
    total = _parse_amount(fields.get("total_amount") or fields.get("total") or fields.get("grand_total"))

    if subtotal is not None and total is not None:
        checks_done += 1
        tax_val = tax if tax is not None else 0
        expected_total = subtotal + tax_val
        if abs(expected_total - total) < 0.01:
            checks_passed += 1
        else:
            issues.append(f"subtotal ({subtotal}) + tax ({tax_val}) != total ({total})")

    # Check 2: line items sum = subtotal (or total)
    line_items = fields.get("line_items") or fields.get("items")
    if isinstance(line_items, list) and len(line_items) > 0:
        checks_done += 1
        items_sum = 0
        for item in line_items:
            if isinstance(item, dict):
                amt = _parse_amount(
                    item.get("amount") or item.get("total") or item.get("line_total")
                )
                if amt is not None:
                    items_sum += amt

        compare_to = subtotal if subtotal is not None else total
        if compare_to is not None and items_sum > 0:
            if abs(items_sum - compare_to) < 0.01:
                checks_passed += 1
            else:
                issues.append(f"Line items sum ({items_sum}) != expected ({compare_to})")
        elif items_sum > 0:
            checks_passed += 1  # Can't compare but items exist

    # Check 3: quantity × unit price = line total (for each line item)
    if isinstance(line_items, list):
        for item in line_items:
            if not isinstance(item, dict):
                continue
            qty = _parse_amount(item.get("quantity") or item.get("qty"))
            unit_price = _parse_amount(item.get("unit_price") or item.get("price") or item.get("rate"))
            line_total = _parse_amount(item.get("amount") or item.get("total") or item.get("line_total"))

            if qty is not None and unit_price is not None and line_total is not None:
                checks_done += 1
                expected = qty * unit_price
                if abs(expected - line_total) < 0.01:
                    checks_passed += 1
                else:
                    issues.append(f"qty ({qty}) × price ({unit_price}) != line total ({line_total})")

    if checks_done == 0:
        score = 100
        details = "No amount fields found to validate"
    else:
        score = (checks_passed / checks_done) * 100
        details = f"Passed {checks_passed}/{checks_done} arithmetic checks."
        if issues:
            details += f" Issues: {'; '.join(issues[:3])}"

    return TypeSpecificResult(
        name="Amount Consistency",
        score=score,
        description="Verifies arithmetic consistency of invoice amounts",
        status=_determine_status(score),
        details=details,
        document_type="invoice",
    )


# =============================================================================
# JSON METRICS
# =============================================================================

def _evaluate_json(fields: dict, text: str, raw_json: Any) -> list[TypeSpecificResult]:
    """Run all JSON-specific metrics."""
    results = []
    results.append(_json_schema_compliance(raw_json))
    results.append(_json_type_validation(raw_json))
    results.append(_json_cross_field_consistency(raw_json))
    results.append(_json_schema_drift_rate(raw_json))
    return results


def _json_schema_compliance(data: Any) -> TypeSpecificResult:
    """Check structural consistency of JSON data."""
    if data is None:
        return TypeSpecificResult(
            name="Schema Compliance",
            score=0, description="Validates JSON structural consistency",
            status="critical", details="No JSON data provided",
            document_type="json",
        )

    issues = []
    total_checks = 0
    passed = 0

    if isinstance(data, list) and len(data) > 1:
        # Check that all objects in array have consistent keys
        first_keys = set()
        if isinstance(data[0], dict):
            first_keys = set(data[0].keys())

        for i, item in enumerate(data[1:], start=1):
            if isinstance(item, dict):
                total_checks += 1
                item_keys = set(item.keys())
                if item_keys == first_keys:
                    passed += 1
                else:
                    missing = first_keys - item_keys
                    extra = item_keys - first_keys
                    if missing:
                        issues.append(f"Item [{i}] missing keys: {', '.join(list(missing)[:3])}")
                    if extra:
                        issues.append(f"Item [{i}] has extra keys: {', '.join(list(extra)[:3])}")
                    # Partial credit if most keys match
                    overlap = len(first_keys & item_keys) / max(len(first_keys | item_keys), 1)
                    passed += overlap

    elif isinstance(data, dict):
        # Single object — check for null/empty required-looking values
        total_checks = len(data)
        for key, value in data.items():
            if value is not None and str(value).strip() != "":
                passed += 1
            else:
                issues.append(f"Field '{key}' is empty or null")

    if total_checks == 0:
        score = 100
        details = "JSON structure is valid"
    else:
        score = (passed / total_checks) * 100
        details = f"Passed {passed:.0f}/{total_checks} schema checks."
        if issues:
            details += f" Issues: {'; '.join(issues[:3])}"

    return TypeSpecificResult(
        name="Schema Compliance",
        score=score,
        description="Validates JSON structural consistency",
        status=_determine_status(score),
        details=details,
        document_type="json",
    )


def _json_type_validation(data: Any) -> TypeSpecificResult:
    """Check that JSON values match expected types."""
    if data is None:
        return TypeSpecificResult(
            name="Type Validation", score=0,
            description="Validates data type correctness",
            status="critical", details="No JSON data provided",
            document_type="json",
        )

    issues = []
    total_checks = 0
    passed = 0

    def _check_types(obj: Any, path: str = ""):
        nonlocal total_checks, passed
        if isinstance(obj, dict):
            for key, value in obj.items():
                field_path = f"{path}.{key}" if path else key
                total_checks += 1

                # Check for type inconsistencies
                if value is None:
                    passed += 1  # null is valid
                elif isinstance(value, (dict, list)):
                    _check_types(value, field_path)
                    passed += 1
                else:
                    # Check for strings that should be numbers
                    if isinstance(value, str):
                        str_val = value.strip()
                        if str_val and re.match(r"^-?\d+\.?\d*$", str_val):
                            # Looks like a number stored as string
                            issues.append(f"'{field_path}': numeric value stored as string ('{str_val}')")
                            passed += 0.5
                        elif str_val.lower() in ("true", "false"):
                            issues.append(f"'{field_path}': boolean stored as string ('{str_val}')")
                            passed += 0.5
                        else:
                            passed += 1
                    else:
                        passed += 1

        elif isinstance(obj, list):
            if len(obj) > 1:
                # Check type consistency within arrays
                types_seen = set()
                for i, item in enumerate(obj):
                    types_seen.add(type(item).__name__)
                    if isinstance(item, (dict, list)):
                        _check_types(item, f"{path}[{i}]")

                total_checks += 1
                if len(types_seen) <= 1:
                    passed += 1
                else:
                    issues.append(f"'{path}': mixed types in array ({', '.join(types_seen)})")
                    passed += 0.5

    _check_types(data)

    if total_checks == 0:
        score = 100
        details = "No type issues detected"
    else:
        score = (passed / total_checks) * 100
        details = f"Validated {total_checks} fields."
        if issues:
            details += f" Issues: {'; '.join(issues[:3])}"
        else:
            details += " All types correct."

    return TypeSpecificResult(
        name="Type Validation",
        score=score,
        description="Validates that values match expected data types",
        status=_determine_status(score),
        details=details,
        document_type="json",
    )


def _json_cross_field_consistency(data: Any) -> TypeSpecificResult:
    """Check logical relationships between JSON fields."""
    if not isinstance(data, dict):
        if isinstance(data, list) and data and isinstance(data[0], dict):
            data = data[0]  # Check first object
        else:
            return TypeSpecificResult(
                name="Cross-Field Consistency", score=100,
                description="Validates logical field relationships",
                status="good", details="Not applicable for this structure",
                document_type="json",
            )

    checks = 0
    passed = 0
    issues = []

    # Check date ordering
    date_pairs = [
        ("start_date", "end_date"), ("created_at", "updated_at"),
        ("start", "end"), ("from", "to"),
        ("created", "modified"), ("begin_date", "end_date"),
    ]
    for start_key, end_key in date_pairs:
        start_val = data.get(start_key)
        end_val = data.get(end_key)
        if start_val and end_val:
            checks += 1
            if str(start_val) <= str(end_val):
                passed += 1
            else:
                issues.append(f"'{start_key}' ({start_val}) > '{end_key}' ({end_val})")

    # Check total vs components
    total_keys = [k for k in data.keys() if "total" in k.lower()]
    for total_key in total_keys:
        total_val = data.get(total_key)
        try:
            total_num = float(re.sub(r"[,$]", "", str(total_val)))
        except (ValueError, TypeError):
            continue
        # Look for component fields
        component_sum = 0
        components_found = 0
        for k, v in data.items():
            if k != total_key and any(word in k.lower() for word in ["amount", "price", "cost", "value", "subtotal"]):
                try:
                    component_sum += float(re.sub(r"[,$]", "", str(v)))
                    components_found += 1
                except (ValueError, TypeError):
                    continue
        if components_found >= 2:
            checks += 1
            if abs(component_sum - total_num) < 0.01:
                passed += 1
            else:
                issues.append(f"Components sum ({component_sum}) != {total_key} ({total_num})")

    if checks == 0:
        score = 100
        details = "No cross-field relationships to validate"
    else:
        score = (passed / checks) * 100
        details = f"Passed {passed}/{checks} consistency checks."
        if issues:
            details += f" Issues: {'; '.join(issues[:3])}"

    return TypeSpecificResult(
        name="Cross-Field Consistency",
        score=score,
        description="Validates logical relationships between fields",
        status=_determine_status(score),
        details=details,
        document_type="json",
    )


def _json_schema_drift_rate(data: Any) -> TypeSpecificResult:
    """
    Detect schema drift by checking for structural anomalies.
    Without a reference schema, we infer expected structure from the data itself.
    """
    if data is None:
        return TypeSpecificResult(
            name="Schema Drift Rate", score=0,
            description="Detects structural drift in JSON data",
            status="critical", details="No JSON data provided",
            document_type="json",
        )

    issues = []

    if isinstance(data, list) and len(data) > 1:
        # Use first item as reference schema
        if isinstance(data[0], dict):
            ref_keys = set(data[0].keys())
            ref_types = {k: type(v).__name__ for k, v in data[0].items()}
            drift_count = 0
            total_items = len(data) - 1

            for i, item in enumerate(data[1:], start=1):
                if not isinstance(item, dict):
                    drift_count += 1
                    issues.append(f"Item [{i}] is not an object")
                    continue

                item_keys = set(item.keys())
                # Key drift
                if item_keys != ref_keys:
                    drift_count += 1
                    diff = ref_keys.symmetric_difference(item_keys)
                    issues.append(f"Item [{i}] key drift: {', '.join(list(diff)[:3])}")
                else:
                    # Type drift
                    for k in ref_keys:
                        if k in item and type(item[k]).__name__ != ref_types.get(k):
                            drift_count += 0.5
                            issues.append(f"Item [{i}].{k}: type changed from {ref_types[k]} to {type(item[k]).__name__}")
                            break

            if total_items == 0:
                score = 100
            else:
                drift_rate = drift_count / total_items
                score = max(0, 100 - drift_rate * 100)

            details = f"Checked {total_items} items against reference schema."
            if issues:
                details += f" Drift detected: {'; '.join(issues[:3])}"
            else:
                details += " No drift detected."
        else:
            score = 100
            details = "Array of primitives — no schema drift applicable"
    elif isinstance(data, dict):
        # Single object — check for null density and naming consistency
        total_fields = len(data)
        null_count = sum(1 for v in data.values() if v is None or str(v).strip() == "")
        if total_fields > 0:
            null_rate = null_count / total_fields
            score = max(0, 100 - null_rate * 100)
            details = f"{null_count}/{total_fields} fields are empty/null."
        else:
            score = 100
            details = "Empty object"
    else:
        score = 100
        details = "Primitive value — no drift applicable"

    return TypeSpecificResult(
        name="Schema Drift Rate",
        score=score,
        description="Detects structural drift in JSON data",
        status=_determine_status(score),
        details=details,
        document_type="json",
    )


# =============================================================================
# SOCIAL MEDIA METRICS
# =============================================================================

def _evaluate_social_media(fields: dict, text: str) -> list[TypeSpecificResult]:
    """Run all social media-specific metrics."""
    results = []
    results.append(_social_language_consistency(text))
    results.append(_social_offensive_rate(text))
    results.append(_social_spam_detection(text))
    return results


def _social_language_consistency(text: str) -> TypeSpecificResult:
    """Check for consistent language use, slang ratio, mixed languages."""
    words = re.findall(r"\b[a-zA-Z]+\b", text)
    if not words:
        return TypeSpecificResult(
            name="Language Consistency", score=100,
            description="Checks for consistent language use",
            status="good", details="No text to analyze",
            document_type="social_media",
        )

    issues = []
    total_words = len(words)
    penalties = 0

    # --- Language detection using langdetect (from app 1.py) ---
    try:
        from langdetect import detect
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            lang_ok = 0
            for line in lines:
                try:
                    if detect(line) == "en":
                        lang_ok += 1
                except Exception:
                    pass
            lang_ratio = lang_ok / max(len(lines), 1)
            if lang_ratio < 0.5:
                penalties += 30
                issues.append(f"Mixed language content: only {lang_ratio:.0%} English")
            elif lang_ratio < 0.8:
                penalties += 15
                issues.append(f"Some non-English content: {lang_ratio:.0%} English")
    except ImportError:
        logger.debug("langdetect not available, skipping language detection")

    # --- Check slang/abbreviation ratio ---
    slang_patterns = [
        r"\b(lol|lmao|brb|tbh|imo|imho|smh|fwiw|rofl|omg|wtf|idk|ngl)\b",
        r"\b(u|ur|r|b4|2day|2moro|2nite|gr8|m8|h8|w8|l8r)\b",
        r"\b(gonna|wanna|gotta|kinda|sorta|dunno|lemme)\b",
    ]
    slang_count = 0
    for pattern in slang_patterns:
        slang_count += len(re.findall(pattern, text.lower()))

    slang_ratio = slang_count / max(total_words, 1)

    # --- Check ALL CAPS ratio ---
    all_caps_words = [w for w in words if w.isupper() and len(w) > 1]
    caps_ratio = len(all_caps_words) / max(total_words, 1)

    # --- Check emoji density ---
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+", flags=re.UNICODE
    )
    emoji_count = len(emoji_pattern.findall(text))

    # --- Score: lower slang + lower caps = better consistency ---
    if slang_ratio > 0.3:
        penalties += 30
        issues.append(f"High slang ratio: {slang_ratio:.0%}")
    elif slang_ratio > 0.15:
        penalties += 15
        issues.append(f"Moderate slang ratio: {slang_ratio:.0%}")

    if caps_ratio > 0.3:
        penalties += 20
        issues.append(f"Excessive ALL CAPS: {caps_ratio:.0%} of words")
    elif caps_ratio > 0.15:
        penalties += 10

    score = max(0, 100 - penalties)
    details = f"Analyzed {total_words} words. Slang ratio: {slang_ratio:.0%}, CAPS ratio: {caps_ratio:.0%}, Emojis: {emoji_count}."
    if issues:
        details += f" {'; '.join(issues)}"

    return TypeSpecificResult(
        name="Language Consistency",
        score=score,
        description="Measures language consistency and formality",
        status=_determine_status(score),
        details=details,
        document_type="social_media",
    )


def _social_offensive_rate(text: str) -> TypeSpecificResult:
    """Detect offensive/toxic content using keyword patterns."""
    text_lower = text.lower()

    # Offensive keyword categories (production system would use ML)
    offensive_categories = {
        "profanity": [
            r"\b(damn|hell|crap|suck|stupid|idiot|dumb|moron|loser)\b",
            r"\b(shut\s+up|piss\s+off)\b",
        ],
        "hate_speech": [
            r"\b(hate\s+(?:you|them|all)|go\s+die|kill\s+yourself)\b",
            r"\b(worthless|pathetic|disgusting)\s+(?:people|person|human)",
        ],
        "threats": [
            r"\b((?:i(?:'ll|m going to|will))\s+(?:kill|hurt|destroy|find)\s+(?:you|them))\b",
            r"\b(watch\s+your\s+back|you(?:'ll|will)\s+(?:pay|regret))\b",
        ],
        "discriminatory": [
            r"\b(go\s+back\s+to|you\s+people|your\s+kind)\b",
        ],
    }

    found_categories = {}
    total_matches = 0
    for category, patterns in offensive_categories.items():
        matches = 0
        for pattern in patterns:
            matches += len(re.findall(pattern, text_lower))
        if matches > 0:
            found_categories[category] = matches
            total_matches += matches

    # Score: higher = cleaner
    words = text.split()
    word_count = max(len(words), 1)
    offensive_ratio = total_matches / word_count

    if total_matches == 0:
        score = 100
        details = "No offensive content detected."
    elif offensive_ratio < 0.02:
        score = 80
        details = f"Minor concerns: {total_matches} flagged term(s) in {', '.join(found_categories.keys())}"
    elif offensive_ratio < 0.05:
        score = 50
        details = f"Moderate concerns: {total_matches} flagged in {', '.join(found_categories.keys())}"
    else:
        score = max(10, 100 - total_matches * 20)
        details = f"Significant concerns: {total_matches} flagged in {', '.join(found_categories.keys())}"

    return TypeSpecificResult(
        name="Offensive Rate",
        score=score,
        description="Detects offensive or toxic content",
        status=_determine_status(score),
        details=details,
        document_type="social_media",
    )


def _social_spam_detection(text: str) -> TypeSpecificResult:
    """Flag spam indicators: excessive links, hashtags, promotional patterns."""
    words = text.split()
    word_count = max(len(words), 1)
    issues = []
    penalties = 0

    # Check URL density
    urls = re.findall(r"https?://\S+", text)
    url_ratio = len(urls) / word_count
    if url_ratio > 0.1:
        penalties += 30
        issues.append(f"High URL density: {len(urls)} links")
    elif url_ratio > 0.05:
        penalties += 15
        issues.append(f"Moderate URL density: {len(urls)} links")

    # Check hashtag density
    hashtags = re.findall(r"#\w+", text)
    if len(hashtags) > 10:
        penalties += 25
        issues.append(f"Excessive hashtags: {len(hashtags)}")
    elif len(hashtags) > 5:
        penalties += 10

    # Check promotional patterns
    promo_patterns = [
        r"\b(buy\s+now|limited\s+(?:time|offer)|act\s+now|click\s+(?:here|below))\b",
        r"\b(free\s+(?:gift|trial|offer)|discount\s+code|promo\s+code|coupon)\b",
        r"\b(subscribe|follow\s+(?:us|me)|retweet|share\s+this)\b",
        r"\b(earn\s+money|make\s+\$?\d+|work\s+from\s+home|passive\s+income)\b",
        r"\b(DM\s+(?:me|us)|link\s+in\s+bio|check\s+out)\b",
    ]
    promo_count = 0
    for pattern in promo_patterns:
        promo_count += len(re.findall(pattern, text.lower()))
    if promo_count >= 3:
        penalties += 30
        issues.append(f"Promotional language: {promo_count} indicators")
    elif promo_count >= 1:
        penalties += 10

    # Check for repetitive content
    sentences = [s.strip().lower() for s in re.split(r"[.!?\n]", text) if s.strip()]
    if sentences:
        unique_ratio = len(set(sentences)) / len(sentences)
        if unique_ratio < 0.5:
            penalties += 20
            issues.append(f"Repetitive content: {unique_ratio:.0%} unique sentences")

    # ALL CAPS check (already in language consistency but spam indicator too)
    caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
    if caps_ratio > 0.5:
        penalties += 15
        issues.append(f"Excessive capitals: {caps_ratio:.0%}")

    score = max(0, 100 - penalties)
    if not issues:
        details = "No spam indicators detected."
    else:
        details = f"Spam score: {100 - score}. " + "; ".join(issues)

    return TypeSpecificResult(
        name="Spam Detection",
        score=score,
        description="Flags spam indicators in social media content",
        status=_determine_status(score),
        details=details,
        document_type="social_media",
    )


# =============================================================================
# TABULAR DATA METRICS (CSV, datasets)
# =============================================================================

def _evaluate_tabular(fields: dict, text: str) -> list[TypeSpecificResult]:
    """Run all tabular-data-specific metrics."""
    results = []
    results.append(_tabular_row_completeness(text))
    results.append(_tabular_column_type_consistency(text))
    results.append(_tabular_header_quality(text))
    results.append(_tabular_null_empty_ratio(text))
    return results


def _tabular_row_completeness(text: str) -> TypeSpecificResult:
    """Check percentage of rows with no empty cells."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        return TypeSpecificResult(
            name="Row Completeness", score=50,
            description="Percentage of rows with no empty cells",
            status="critical", details="Insufficient rows to analyze",
            document_type="tabular",
        )

    # Detect delimiter
    first_line = lines[0]
    delimiter = ","
    for d in ["\t", "|", ";"]:
        if first_line.count(d) > first_line.count(delimiter):
            delimiter = d

    data_rows = lines[1:]  # skip header
    complete = 0
    for row in data_rows:
        cells = row.split(delimiter)
        if all(c.strip() for c in cells):
            complete += 1

    ratio = complete / max(len(data_rows), 1)
    score = ratio * 100
    return TypeSpecificResult(
        name="Row Completeness",
        score=score,
        description="Percentage of rows with no empty cells",
        status=_determine_status(score),
        details=f"{complete}/{len(data_rows)} rows are fully complete ({ratio:.0%}).",
        document_type="tabular",
    )


def _tabular_column_type_consistency(text: str) -> TypeSpecificResult:
    """Check if columns have consistent types."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 3:
        return TypeSpecificResult(
            name="Column Type Consistency", score=50,
            description="Checks type consistency across columns",
            status="critical", details="Insufficient data to analyze",
            document_type="tabular",
        )

    first_line = lines[0]
    delimiter = ","
    for d in ["\t", "|", ";"]:
        if first_line.count(d) > first_line.count(delimiter):
            delimiter = d

    header = first_line.split(delimiter)
    num_cols = len(header)
    data_rows = [l.split(delimiter) for l in lines[1:]]

    consistent_cols = 0
    for col_idx in range(min(num_cols, 50)):  # cap at 50 cols
        col_vals = [r[col_idx].strip() for r in data_rows if col_idx < len(r) and r[col_idx].strip()]
        if not col_vals:
            continue

        # Infer dominant type
        num_count = sum(1 for v in col_vals if _is_numeric(v))
        date_count = sum(1 for v in col_vals if _is_date_like(v))
        total = len(col_vals)

        if num_count / total > 0.8 or date_count / total > 0.8 or (total - num_count - date_count) / total > 0.8:
            consistent_cols += 1

    score = (consistent_cols / max(num_cols, 1)) * 100
    return TypeSpecificResult(
        name="Column Type Consistency",
        score=score,
        description="Checks if column values have consistent types",
        status=_determine_status(score),
        details=f"{consistent_cols}/{num_cols} columns have consistent types.",
        document_type="tabular",
    )


def _tabular_header_quality(text: str) -> TypeSpecificResult:
    """Evaluate header row quality."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if not lines:
        return TypeSpecificResult(
            name="Header Quality", score=0,
            description="Evaluates quality of column headers",
            status="critical", details="No data found",
            document_type="tabular",
        )

    first_line = lines[0]
    delimiter = ","
    for d in ["\t", "|", ";"]:
        if first_line.count(d) > first_line.count(delimiter):
            delimiter = d

    headers = [h.strip() for h in first_line.split(delimiter)]
    penalties = 0
    issues = []

    # Check for empty headers
    empty = sum(1 for h in headers if not h)
    if empty:
        penalties += 30
        issues.append(f"{empty} empty header(s)")

    # Check for duplicate headers
    seen = set()
    dupes = 0
    for h in headers:
        if h.lower() in seen:
            dupes += 1
        seen.add(h.lower())
    if dupes:
        penalties += 20
        issues.append(f"{dupes} duplicate header(s)")

    # Check for purely numeric headers (likely not real headers)
    numeric_headers = sum(1 for h in headers if h and _is_numeric(h))
    if numeric_headers > len(headers) * 0.5:
        penalties += 25
        issues.append(f"{numeric_headers} numeric headers (may not be real headers)")

    # Check header naming (very short or very long)
    bad_len = sum(1 for h in headers if h and (len(h) < 2 or len(h) > 50))
    if bad_len:
        penalties += 10
        issues.append(f"{bad_len} header(s) with unusual length")

    score = max(0, 100 - penalties)
    details = f"Analyzed {len(headers)} headers."
    if issues:
        details += " " + "; ".join(issues)
    else:
        details += " All headers look good."

    return TypeSpecificResult(
        name="Header Quality",
        score=score,
        description="Evaluates column header quality",
        status=_determine_status(score),
        details=details,
        document_type="tabular",
    )


def _tabular_null_empty_ratio(text: str) -> TypeSpecificResult:
    """Calculate ratio of null/empty cells."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    if len(lines) < 2:
        return TypeSpecificResult(
            name="Null/Empty Ratio", score=50,
            description="Checks for null or empty cells",
            status="critical", details="Insufficient data",
            document_type="tabular",
        )

    first_line = lines[0]
    delimiter = ","
    for d in ["\t", "|", ";"]:
        if first_line.count(d) > first_line.count(delimiter):
            delimiter = d

    data_rows = lines[1:]
    total_cells = 0
    empty_cells = 0
    null_keywords = {"null", "none", "na", "n/a", "nan", "", "nil", "undefined", "-"}

    for row in data_rows:
        cells = row.split(delimiter)
        for cell in cells:
            total_cells += 1
            if cell.strip().lower() in null_keywords:
                empty_cells += 1

    empty_ratio = empty_cells / max(total_cells, 1)
    score = max(0, (1 - empty_ratio) * 100)

    return TypeSpecificResult(
        name="Null/Empty Ratio",
        score=score,
        description="Measures percentage of non-null cells",
        status=_determine_status(score),
        details=f"{empty_cells}/{total_cells} cells are null/empty ({empty_ratio:.1%}).",
        document_type="tabular",
    )


def _is_numeric(val: str) -> bool:
    """Check if a string looks numeric."""
    try:
        float(val.replace(",", "").replace("$", "").replace("₹", ""))
        return True
    except (ValueError, AttributeError):
        return False


def _is_date_like(val: str) -> bool:
    """Check if a string looks like a date."""
    date_patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\d{2}/\d{2}/\d{4}",
        r"\d{2}-\d{2}-\d{4}",
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)",
    ]
    return any(re.search(p, val, re.IGNORECASE) for p in date_patterns)


# =============================================================================
# STRUCTURED MARKUP METRICS (XML, HTML)
# =============================================================================

def _evaluate_markup(fields: dict, text: str) -> list[TypeSpecificResult]:
    """Run all markup-specific metrics."""
    results = []
    
    # Evaluate base tag validity first
    tag_validity = _markup_tag_validity(text)
    results.append(tag_validity)
    
    # If the markup is fundamentally broken (score < 60), 
    # it makes no sense to evaluate nesting and attributes, 
    # as the regex will just falsely pass because it can't find any well-formed tags.
    if tag_validity.score < 60:
        results.append(TypeSpecificResult(
            name="Nesting Depth",
            score=tag_validity.score,
            description="Checks for excessive tag nesting",
            status=_determine_status(tag_validity.score),
            details="Nesting evaluation compromised due to severely malformed or missing tags.",
            document_type="markup",
        ))
        results.append(TypeSpecificResult(
            name="Attribute Completeness",
            score=tag_validity.score,
            description="Checks for required attributes on elements",
            status=_determine_status(tag_validity.score),
            details="Attribute evaluation compromised due to severely malformed or missing tags.",
            document_type="markup",
        ))
        results.append(TypeSpecificResult(
            name="Encoding Consistency",
            score=tag_validity.score,
            description="Checks for consistent character encoding",
            status=_determine_status(tag_validity.score),
            details="Encoding consistency assumed poor due to malformed or missing tags.",
            document_type="markup",
        ))
        return results

    # Otherwise, structural integrity is good enough to proceed with deeper metrics
    results.append(_markup_nesting_depth(text))
    results.append(_markup_attribute_completeness(text))
    results.append(_markup_encoding_consistency(text))
    return results


def _markup_tag_validity(text: str) -> TypeSpecificResult:
    """Check for well-formed tag structure."""
    # Find all tags
    open_tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)\b[^/>]*(?<!/)>", text)
    close_tags = re.findall(r"</([a-zA-Z][a-zA-Z0-9]*)>", text)
    self_closing = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*/\s*>", text)

    if not open_tags and not self_closing:
        return TypeSpecificResult(
            name="Tag Validity", score=50,
            description="Checks for well-formed tag structure",
            status="critical", details="No markup tags found in document",
            document_type="markup",
        )

    issues = []
    # Compare open vs close tag counts
    open_counts: dict[str, int] = {}
    close_counts: dict[str, int] = {}
    void_elements = {"br", "hr", "img", "input", "meta", "link", "area", "base",
                     "col", "embed", "source", "track", "wbr"}

    for t in open_tags:
        tl = t.lower()
        if tl not in void_elements:
            open_counts[tl] = open_counts.get(tl, 0) + 1
    for t in close_tags:
        tl = t.lower()
        close_counts[tl] = close_counts.get(tl, 0) + 1

    mismatches = 0
    for tag, count in open_counts.items():
        close_count = close_counts.get(tag, 0)
        if count != close_count:
            mismatches += abs(count - close_count)
            if abs(count - close_count) > 0:
                issues.append(f"<{tag}>: {count} open, {close_count} close")

    total_tags = sum(open_counts.values()) + len(self_closing)
    mismatch_ratio = mismatches / max(total_tags, 1)
    score = max(0, (1 - mismatch_ratio) * 100)

    details = f"Found {total_tags} tags, {len(self_closing)} self-closing."
    if issues:
        details += " Mismatches: " + "; ".join(issues[:5])
    else:
        details += " All tags properly matched."

    return TypeSpecificResult(
        name="Tag Validity",
        score=score,
        description="Checks for well-formed tag structure",
        status=_determine_status(score),
        details=details,
        document_type="markup",
    )


def _markup_nesting_depth(text: str) -> TypeSpecificResult:
    """Check nesting depth of markup."""
    max_depth = 0
    current_depth = 0
    void_elements = {"br", "hr", "img", "input", "meta", "link", "area", "base",
                     "col", "embed", "source", "track", "wbr"}

    for match in re.finditer(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*(/?)\s*>", text):
        is_closing = match.group(1) == "/"
        tag = match.group(2).lower()
        is_self_closing = match.group(3) == "/"

        if tag in void_elements or is_self_closing:
            continue
        if is_closing:
            current_depth = max(0, current_depth - 1)
        else:
            current_depth += 1
            max_depth = max(max_depth, current_depth)

    penalties = 0
    if max_depth > 15:
        penalties = 40
    elif max_depth > 10:
        penalties = 20
    elif max_depth > 7:
        penalties = 10

    score = max(0, 100 - penalties)
    return TypeSpecificResult(
        name="Nesting Depth",
        score=score,
        description="Checks for excessive tag nesting",
        status=_determine_status(score),
        details=f"Maximum nesting depth: {max_depth} levels.",
        document_type="markup",
    )


def _markup_attribute_completeness(text: str) -> TypeSpecificResult:
    """Check for required attributes on common elements."""
    checks = {
        "img": {"alt": r'<img\b[^>]*\balt\s*='},
        "a": {"href": r'<a\b[^>]*\bhref\s*='},
        "input": {"type": r'<input\b[^>]*\btype\s*='},
        "form": {"action": r'<form\b[^>]*\baction\s*='},
    }

    total_checks = 0
    passed = 0
    issues = []

    for tag, attrs in checks.items():
        tag_pattern = re.compile(f"<{tag}\\b", re.IGNORECASE)
        tag_count = len(tag_pattern.findall(text))
        if tag_count == 0:
            continue
        for attr_name, attr_pattern in attrs.items():
            total_checks += tag_count
            attr_count = len(re.findall(attr_pattern, text, re.IGNORECASE))
            passed += min(attr_count, tag_count)
            missing = tag_count - min(attr_count, tag_count)
            if missing > 0:
                issues.append(f"{missing} <{tag}> missing '{attr_name}'")

    if total_checks == 0:
        return TypeSpecificResult(
            name="Attribute Completeness", score=100,
            description="Checks for required attributes on elements",
            status="good", details="No elements requiring mandatory attributes found.",
            document_type="markup",
        )

    score = (passed / total_checks) * 100
    details = f"Checked {total_checks} attribute requirements, {passed} passed."
    if issues:
        details += " " + "; ".join(issues[:5])

    return TypeSpecificResult(
        name="Attribute Completeness",
        score=score,
        description="Checks for required attributes on elements",
        status=_determine_status(score),
        details=details,
        document_type="markup",
    )


def _markup_encoding_consistency(text: str) -> TypeSpecificResult:
    """Check for encoding issues in markup."""
    penalties = 0
    issues = []

    # Check for mixed encoding declarations
    charset_decls = re.findall(r'charset\s*=\s*["\']?([a-zA-Z0-9_-]+)', text, re.IGNORECASE)
    if len(set(c.lower() for c in charset_decls)) > 1:
        penalties += 30
        issues.append(f"Mixed charset declarations: {', '.join(set(charset_decls))}")

    # Check for common encoding artifacts
    encoding_artifacts = [
        (r'Ã¢|Ã©|Ã¼|Â©|Â®|Ã±', "UTF-8 mojibake detected"),
        (r'&#\d{4,6};', "Excessive numeric entities"),
        (r'&amp;amp;|&amp;lt;|&amp;gt;', "Double-escaped entities"),
    ]
    for pattern, msg in encoding_artifacts:
        if re.search(pattern, text):
            penalties += 15
            issues.append(msg)

    score = max(0, 100 - penalties)
    details = "Encoding analysis complete."
    if issues:
        details += " " + "; ".join(issues)
    else:
        details = "No encoding issues detected."

    return TypeSpecificResult(
        name="Encoding Consistency",
        score=score,
        description="Checks for consistent character encoding",
        status=_determine_status(score),
        details=details,
        document_type="markup",
    )


# =============================================================================
# EMAIL METRICS (EML)
# =============================================================================

def _evaluate_email(fields: dict, text: str) -> list[TypeSpecificResult]:
    """Run all email-specific metrics."""
    results = []
    results.append(_email_header_completeness(text))
    results.append(_email_recipient_validation(text))
    results.append(_email_body_quality(text))
    results.append(_email_attachment_check(text))
    return results


def _email_header_completeness(text: str) -> TypeSpecificResult:
    """Check for required email headers."""
    required = {
        "From": r"^From:\s*.+",
        "To": r"^To:\s*.+",
        "Subject": r"^Subject:\s*.+",
        "Date": r"^Date:\s*.+",
    }
    optional = {
        "Message-ID": r"^Message-ID:\s*.+",
        "MIME-Version": r"^MIME-Version:\s*.+",
        "Content-Type": r"^Content-Type:\s*.+",
    }

    found_required = 0
    found_optional = 0
    missing = []

    for name, pattern in required.items():
        if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
            found_required += 1
        else:
            missing.append(name)

    for name, pattern in optional.items():
        if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
            found_optional += 1

    score = (found_required / len(required)) * 80 + (found_optional / len(optional)) * 20
    details = f"Found {found_required}/{len(required)} required headers, {found_optional}/{len(optional)} optional."
    if missing:
        details += f" Missing: {', '.join(missing)}"

    return TypeSpecificResult(
        name="Header Completeness",
        score=score,
        description="Checks for essential email headers",
        status=_determine_status(score),
        details=details,
        document_type="email",
    )


def _email_recipient_validation(text: str) -> TypeSpecificResult:
    """Validate email addresses in headers."""
    email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

    # Extract emails from To, From, Cc, Bcc headers
    header_lines = []
    for header in ["From", "To", "Cc", "Bcc"]:
        match = re.search(rf"^{header}:\s*(.+?)(?=\n\S|\n\n|\Z)", text, re.MULTILINE | re.IGNORECASE | re.DOTALL)
        if match:
            header_lines.append(match.group(1))

    all_text = " ".join(header_lines)
    emails = email_pattern.findall(all_text)

    if not emails:
        return TypeSpecificResult(
            name="Recipient Validation", score=50,
            description="Validates email addresses in headers",
            status="critical", details="No email addresses found in headers",
            document_type="email",
        )

    # Validate each email
    valid = 0
    issues = []
    for email in emails:
        domain = email.split("@")[1] if "@" in email else ""
        if "." in domain and len(domain) > 3:
            valid += 1
        else:
            issues.append(f"Invalid: {email}")

    score = (valid / len(emails)) * 100
    details = f"Found {len(emails)} email addresses, {valid} valid."
    if issues:
        details += " " + "; ".join(issues[:3])

    return TypeSpecificResult(
        name="Recipient Validation",
        score=score,
        description="Validates email addresses in headers",
        status=_determine_status(score),
        details=details,
        document_type="email",
    )


def _email_body_quality(text: str) -> TypeSpecificResult:
    """Evaluate email body content quality."""
    # Split header from body (blank line separator)
    parts = re.split(r"\n\n", text, maxsplit=1)
    body = parts[1] if len(parts) > 1 else parts[0]

    # Strip HTML if present
    clean_body = re.sub(r"<[^>]+>", " ", body)
    clean_body = re.sub(r"\s+", " ", clean_body).strip()

    penalties = 0
    issues = []

    word_count = len(clean_body.split())
    if word_count < 5:
        penalties += 40
        issues.append(f"Very short body ({word_count} words)")
    elif word_count < 20:
        penalties += 15
        issues.append(f"Short body ({word_count} words)")

    # Check if body is mostly HTML/base64
    if len(body) > 100:
        text_ratio = len(clean_body) / max(len(body), 1)
        if text_ratio < 0.3:
            penalties += 20
            issues.append(f"Low text-to-markup ratio ({text_ratio:.0%})")

    # Check for signatures/disclaimers ratio
    disclaimer_patterns = [r"confidential", r"disclaimer", r"do not reply", r"unsubscribe"]
    disclaimer_count = sum(1 for p in disclaimer_patterns if re.search(p, body, re.IGNORECASE))
    if disclaimer_count > 2 and word_count < 50:
        penalties += 10
        issues.append("Body is mostly disclaimers")

    score = max(0, 100 - penalties)
    details = f"Body: {word_count} words."
    if issues:
        details += " " + "; ".join(issues)
    else:
        details += " Good content quality."

    return TypeSpecificResult(
        name="Body Quality",
        score=score,
        description="Evaluates email body content quality",
        status=_determine_status(score),
        details=details,
        document_type="email",
    )


def _email_attachment_check(text: str) -> TypeSpecificResult:
    """Check for attachment references vs actual attachments."""
    # Check for attachment indicators
    attachment_refs = re.findall(
        r"\b(?:attach(?:ed|ment|ing)?|enclosed|find\s+attached|PFA|please\s+find)\b",
        text, re.IGNORECASE
    )
    has_content_disposition = bool(re.search(r"Content-Disposition:\s*attachment", text, re.IGNORECASE))
    has_multipart = bool(re.search(r"Content-Type:\s*multipart", text, re.IGNORECASE))

    if not attachment_refs:
        return TypeSpecificResult(
            name="Attachment Check", score=100,
            description="Checks attachment references vs actual attachments",
            status="good",
            details="No attachment references found — no issues.",
            document_type="email",
        )

    if has_content_disposition or has_multipart:
        return TypeSpecificResult(
            name="Attachment Check", score=100,
            description="Checks attachment references vs actual attachments",
            status="good",
            details=f"Found {len(attachment_refs)} attachment reference(s) with attachment content present.",
            document_type="email",
        )
    else:
        return TypeSpecificResult(
            name="Attachment Check", score=40,
            description="Checks attachment references vs actual attachments",
            status="critical",
            details=f"Found {len(attachment_refs)} attachment reference(s) but no actual attachment detected.",
            document_type="email",
        )


# =============================================================================
# GENERAL DOCUMENT METRICS (fallback for all unmatched types)
# =============================================================================

def _evaluate_general(fields: dict, text: str) -> list[TypeSpecificResult]:
    """Run general document metrics (fallback)."""
    results = []
    results.append(_general_structure_quality(text))
    results.append(_general_readability(text))
    results.append(_general_section_completeness(text))
    results.append(_general_keyword_density(text))
    return results


def _general_structure_quality(text: str) -> TypeSpecificResult:
    """Evaluate structural diversity of the document."""
    penalties = 0
    features = []

    # Check for headings / section markers
    headings = re.findall(r"(?:^|\n)(?:#{1,6}\s|[A-Z][A-Z\s]{3,}:?\s*$|(?:\d+\.)+\s)", text, re.MULTILINE)
    if headings:
        features.append(f"{len(headings)} heading(s)")
    else:
        penalties += 15

    # Check for paragraphs (blocks of text separated by blank lines)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) > 1:
        features.append(f"{len(paragraphs)} paragraph(s)")
    else:
        penalties += 10

    # Check for lists
    list_items = re.findall(r"^[\s]*[-*•]\s+\S|^[\s]*\d+[.)]\s+\S", text, re.MULTILINE)
    if list_items:
        features.append(f"{len(list_items)} list item(s)")

    # Check for tables or key-value patterns
    kv_patterns = re.findall(r"^\s*[\w\s]+:\s+\S", text, re.MULTILINE)
    if len(kv_patterns) > 3:
        features.append(f"{len(kv_patterns)} key-value pair(s)")

    word_count = len(text.split())
    if word_count < 20:
        penalties += 25

    score = max(0, 100 - penalties)
    if features:
        details = "Structural elements found: " + ", ".join(features) + f". Total {word_count} words."
    else:
        details = f"Minimal structure detected. {word_count} words, no clear sections/headings."

    return TypeSpecificResult(
        name="Structure Quality",
        score=score,
        description="Evaluates structural diversity and organization",
        status=_determine_status(score),
        details=details,
        document_type="general",
    )


def _general_readability(text: str) -> TypeSpecificResult:
    """Calculate a simple readability score."""
    sentences = re.split(r"[.!?]+\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = text.split()

    if len(words) < 10:
        return TypeSpecificResult(
            name="Readability Score", score=50,
            description="Measures text readability",
            status="critical", details="Insufficient text for readability analysis",
            document_type="general",
        )

    # Simple metrics
    avg_sentence_len = len(words) / max(len(sentences), 1)
    syllable_count = sum(_count_syllables(w) for w in words)
    avg_syllables = syllable_count / max(len(words), 1)

    # Simplified Flesch Reading Ease
    flesch = max(0, min(100, 206.835 - 1.015 * avg_sentence_len - 84.6 * avg_syllables))

    # Map to 0-100 quality score (higher flesch = more readable = better)
    score = min(100, flesch)

    if score >= 60:
        level = "Easy to read"
    elif score >= 30:
        level = "Moderately readable"
    else:
        level = "Difficult to read"

    return TypeSpecificResult(
        name="Readability Score",
        score=score,
        description="Measures text readability (Flesch Reading Ease)",
        status=_determine_status(score),
        details=f"Flesch score: {flesch:.0f} ({level}). Avg sentence: {avg_sentence_len:.0f} words, avg syllables: {avg_syllables:.1f}.",
        document_type="general",
    )


def _count_syllables(word: str) -> int:
    """Rough syllable count for English words."""
    word = word.lower().strip(".,;:!?\"'()[]{}")
    if len(word) <= 2:
        return 1
    vowels = "aeiouy"
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _general_section_completeness(text: str) -> TypeSpecificResult:
    """Detect whether doc has intro, body, conclusion-like sections."""
    sections_found = []
    text_lower = text.lower()

    # Intro indicators
    intro_patterns = [r"\bintroduction\b", r"\boverview\b", r"\bpurpose\b", r"\babstract\b",
                      r"\bsummary\b", r"\bbackground\b", r"\bdear\s+\w+"]
    if any(re.search(p, text_lower) for p in intro_patterns):
        sections_found.append("Introduction/Overview")

    # Body indicators (headings, numbered sections)
    body_indicators = re.findall(r"(?:^|\n)(?:\d+\.\s+|#{2,}\s|[A-Z][a-z]+\s+[A-Z])", text)
    if len(body_indicators) >= 2:
        sections_found.append("Body sections")

    # Conclusion indicators
    conclusion_patterns = [r"\bconclusion\b", r"\brecommendation\b", r"\bnext\s+steps\b",
                           r"\baction\s+items\b", r"\bsincerely\b", r"\bregards\b", r"\bthanks\b"]
    if any(re.search(p, text_lower) for p in conclusion_patterns):
        sections_found.append("Conclusion/Closing")

    score = min(100, len(sections_found) * 33.3)
    if not sections_found:
        score = 50
        details = "No recognizable document sections detected."
    else:
        details = f"Found {len(sections_found)} section type(s): {', '.join(sections_found)}."

    return TypeSpecificResult(
        name="Section Completeness",
        score=score,
        description="Detects intro, body, and conclusion sections",
        status=_determine_status(score),
        details=details,
        document_type="general",
    )


def _general_keyword_density(text: str) -> TypeSpecificResult:
    """Flag unusually repetitive text."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    if len(words) < 20:
        return TypeSpecificResult(
            name="Keyword Density", score=100,
            description="Checks for unusual keyword repetition",
            status="good", details="Too few words to analyze density",
            document_type="general",
        )

    # Count word frequencies
    freq: dict[str, int] = {}
    stop_words = {"the", "and", "for", "are", "but", "not", "you", "all",
                  "can", "had", "her", "was", "one", "our", "out", "has",
                  "his", "how", "its", "may", "new", "now", "old", "see",
                  "way", "who", "did", "get", "let", "say", "she", "too",
                  "use", "this", "that", "with", "have", "from", "will",
                  "been", "each", "make", "like", "than", "them", "then",
                  "what", "when", "some", "into"}
    for w in words:
        if w not in stop_words:
            freq[w] = freq.get(w, 0) + 1

    if not freq:
        return TypeSpecificResult(
            name="Keyword Density", score=100,
            description="Checks for unusual keyword repetition",
            status="good", details="No significant keywords found",
            document_type="general",
        )

    total_content_words = sum(freq.values())
    max_freq = max(freq.values())
    top_word = max(freq, key=freq.get)  # type: ignore
    top_density = max_freq / total_content_words

    penalties = 0
    issues = []
    if top_density > 0.15:
        penalties += 30
        issues.append(f"'{top_word}' appears {max_freq} times ({top_density:.0%} density)")
    elif top_density > 0.08:
        penalties += 15
        issues.append(f"'{top_word}' appears {max_freq} times ({top_density:.0%} density)")

    # Check for overall vocabulary diversity
    unique_ratio = len(freq) / max(total_content_words, 1)
    if unique_ratio < 0.3:
        penalties += 15
        issues.append(f"Low vocabulary diversity ({unique_ratio:.0%} unique words)")

    score = max(0, 100 - penalties)
    details = f"Analyzed {total_content_words} content words, {len(freq)} unique."
    if issues:
        details += " " + "; ".join(issues)
    else:
        details += " Good vocabulary diversity."

    return TypeSpecificResult(
        name="Keyword Density",
        score=score,
        description="Checks for unusual keyword repetition",
        status=_determine_status(score),
        details=details,
        document_type="general",
    )
