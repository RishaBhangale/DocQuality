"""
Deterministic Rule Engine.

Merges the rule-based approach of the Compliance POC (registry of evaluation
functions based on domain/type) with the Banking POC's robust deterministic
field extraction and foundational metrics (Completeness, Consistency, etc.).

Provides a unified RULE_REGISTRY that executes the appropriate rules.
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Callable

from core.models.schemas import IssueSchema

logger = logging.getLogger(__name__)

# ─── Unified Rule Engine (Banking Foundational + Compliance Domain) ─────────

class RuleEngine:
    """
    Deterministic rule engine for document quality metrics.
    """

    # Common field format patterns
    FORMAT_PATTERNS: dict[str, str] = {
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "phone": r"^[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]*$",
        "date": r"\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}",
        "currency_amount": r"^[\$€£¥]?\s?\d{1,3}(,\d{3})*(\.\d{2})?$",
        "postal_code": r"^\d{5}(-\d{4})?$|^[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}$",
        "url": r"^https?://[^\s]+$",
    }

    def extract_basic_fields_from_text(self, text: str) -> dict[str, Any]:
        """
        Deterministic extraction of basic metadata fields using regex.
        Restored to support legacy Banking POC orchestration steps.
        """
        fields = {}
        
        # 1. Date Extraction
        date_pattern = self.FORMAT_PATTERNS["date"]
        dates = re.findall(date_pattern, text)
        if dates:
            fields["document_date"] = dates[0]
            # Try to find a later date if multiple exist (like 'last updated')
            parsed_dates = [self._parse_date(d) for d in dates]
            valid_dates = [d for d in parsed_dates if d]
            if valid_dates:
                fields["document_date_parsed"] = max(valid_dates).isoformat()

        # 2. Amount Extraction
        amount_pattern = r'[\$€£¥]\s?\d{1,3}(?:[,\s]\d{3})*(?:\.\d{2})?'
        amounts = re.findall(amount_pattern, text)
        if amounts:
            fields["primary_amount"] = amounts[0]
            
        # 3. ID/Reference Extraction
        id_patterns = [
            r'(?i)ref(?:erence)?\s*[:\-\#]\s*([A-Z0-9\-\/]{4,})',
            r'(?i)id\s*[:\-\#]\s*([A-Z0-9\-\/]{4,})',
            r'(?i)doc(?:ument)?\s*num(?:ber)?\s*[:\-\#]\s*([A-Z0-9\-\/]{4,})'
        ]
        for p in id_patterns:
            matches = re.findall(p, text)
            if matches:
                fields["document_id"] = matches[0]
                break

        # 4. Entity Extraction (Simple)
        entity_patterns = [
            r'(?i)prepared\s+for\s+([A-Z][A-Za-z\s\.]{2,30})',
            r'(?i)issued\s+to\s+([A-Z][A-Za-z\s\.]{2,30})',
            r'(?i)client\s*:\s*([A-Z][A-Za-z\s\.]{2,30})'
        ]
        for p in entity_patterns:
            matches = re.findall(p, text)
            if matches:
                fields["target_entity"] = matches[0].strip()
                break

        return fields

    def calculate_completeness(self, fields: dict, raw_text: str = "") -> tuple[float, list[IssueSchema]]:
        """Wrapper for evaluate_completeness free function."""
        return evaluate_completeness(fields, raw_text)

    def calculate_validity(self, fields: dict, raw_text: str = "") -> tuple[float, list[IssueSchema]]:
        """Wrapper for evaluate_validity free function."""
        return evaluate_validity(fields, raw_text)

    def calculate_consistency(self, fields: dict, raw_text: str = "") -> tuple[float, list[IssueSchema]]:
        """Wrapper for evaluate_consistency free function."""
        return evaluate_consistency(fields, raw_text)

    def calculate_accuracy(self, fields: dict, raw_text: str = "") -> tuple[float, list[IssueSchema]]:
        """Wrapper for evaluate_accuracy free function."""
        return evaluate_accuracy(fields, raw_text)

    def calculate_timeliness(self, fields: dict, raw_text: str = "") -> tuple[float, list[IssueSchema]]:
        """Wrapper for evaluate_timeliness free function."""
        return evaluate_timeliness(fields, raw_text)

    def calculate_uniqueness(self, fields: dict, raw_text: str = "") -> tuple[float, list[IssueSchema]]:
        """Wrapper for evaluate_uniqueness free function."""
        return evaluate_uniqueness(fields, raw_text)

    def _parse_date(self, date_str: str) -> datetime | None:
        """Attempt to parse a date string in common formats."""
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

    def generate_deterministic_recommendations(
        self,
        issues: list[IssueSchema],
        metric_scores: dict[str, float],
        max_items: int = 10,
    ) -> list[str]:
        """Generate objective, deterministic recommendations from issues/scores."""
        recs: list[str] = []

        # Score-driven high-level actions
        for metric, score in (metric_scores or {}).items():
            try:
                s = float(score)
            except Exception:
                continue
            if s < 75:
                if metric == "completeness":
                    recs.append("Add missing required fields and ensure key identifiers/dates are captured.")
                elif metric == "validity":
                    recs.append("Standardize formats for dates, amounts, and IDs.")
                elif metric == "consistency":
                    recs.append("Resolve internal inconsistencies (conflicting dates, mismatched identifiers).")
                elif metric == "accuracy":
                    recs.append("Verify extracted values against the document text.")
                elif metric == "timeliness":
                    recs.append("Update expired/outdated dates.")
                elif metric == "uniqueness":
                    recs.append("Remove duplicate entries and consolidate repeated values.")

        # Issue-driven targeted actions
        for issue in issues or []:
            it = (getattr(issue, "issue_type", "") or "").lower()
            fn = getattr(issue, "field_name", "this field") or "this field"
            if "missing" in it:
                recs.append(f"Populate the missing required field: {fn}.")
            elif "invalid" in it or "format" in it:
                recs.append(f"Correct the format of {fn}.")
            elif "inconsistent" in it:
                recs.append(f"Reconcile inconsistent values affecting {fn}.")
            elif "expired" in it or "outdated" in it:
                recs.append(f"Review and update time-sensitive information for {fn}.")
            elif "duplicate" in it:
                recs.append(f"Remove duplicate information related to {fn}.")

        # De-dupe while preserving order
        seen: set[str] = set()
        uniq: list[str] = []
        for r in recs:
            r = (r or "").strip()
            if not r:
                continue
            if r in seen:
                continue
            seen.add(r)
            uniq.append(r)
            if len(uniq) >= max_items:
                break

        return uniq


# ─── Free-Function Rules for Registry (Compliance Style) ───────────────────

def evaluate_completeness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check whether the document contains expected structural elements (Core/Compliance)."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 5

    if len(raw_text.strip()) > 200:
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Document Body", issue_type="Insufficient Content", description="Document is too short.", severity="critical"))

    headings = re.findall(r'(?m)^(?:\d+[\.\)]\s+|#{1,3}\s+|[A-Z][A-Z\s]{3,}:)', raw_text)
    if len(headings) >= 2:
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Document Structure", issue_type="Missing Headings", description="Lacks clear section structure.", severity="warning"))

    date_pattern = r'\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
    if re.search(date_pattern, raw_text, re.IGNORECASE):
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Document Metadata", issue_type="No Date Found", description="No recognizable date found.", severity="warning"))

    owner_patterns = [r'(?i)author', r'(?i)owner', r'(?i)prepared\s+by', r'(?i)approved\s+by', r'(?i)responsible']
    if any(re.search(p, raw_text) for p in owner_patterns):
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Document Ownership", issue_type="No Author", description="No author/owner identified.", severity="warning"))

    scope_patterns = [r'(?i)scope', r'(?i)purpose', r'(?i)objective', r'(?i)introduction', r'(?i)overview']
    if any(re.search(p, raw_text) for p in scope_patterns):
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Document Scope", issue_type="Missing Scope", description="No scope statement found.", severity="warning"))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues

def evaluate_validity(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Verify that dates, references, and identifiers conform to expected formats."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 3

    date_matches = re.findall(r'\b(\d{4}[-/]\d{2}[-/]\d{2})\b', raw_text)
    if date_matches:
        valid_dates = 0
        for d in date_matches:
            try:
                datetime.strptime(d.replace('/', '-'), '%Y-%m-%d')
                valid_dates += 1
            except ValueError:
                pass
        if valid_dates > 0:
            checks_passed += 1
        else:
            issues.append(IssueSchema(field_name="Date Formats", issue_type="Invalid Date Format", description="Dates found but could not be parsed.", severity="warning"))
    else:
        checks_passed += 0.5

    version_pattern = r'(?i)(?:version|v|rev)\s*[:\.]?\s*\d+[\.\d]*'
    if re.search(version_pattern, raw_text):
        checks_passed += 1
    else:
        checks_passed += 0.5

    placeholder_patterns = [r'\[TBD\]', r'\bTODO\b', r'\bXXX\b', r'\bFIXME\b', r'\[INSERT\b']
    placeholders_found = sum(1 for p in placeholder_patterns if re.search(p, raw_text, re.IGNORECASE))
    if placeholders_found == 0:
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Content Placeholders", issue_type="Unresolved Placeholders", description=f"Found {placeholders_found} placeholder(s).", severity="critical"))

    score = (checks_passed / total_checks) * 100
    return round(min(score, 100), 1), issues

def evaluate_consistency(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check coherence across sections."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 3

    text_lower = raw_text.lower()
    term_pairs = [("data subject", "user"), ("controller", "processor"), ("shall", "must")]
    inconsistencies = 0
    for term_a, term_b in term_pairs:
        if text_lower.count(term_a) > 3 and text_lower.count(term_b) > 3:
            inconsistencies += 1

    if inconsistencies == 0:
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Terminology", issue_type="Inconsistent Terminology", description=f"Detected {inconsistencies} potential inconsistency(ies).", severity="warning"))

    checks_passed += 1 # Contradiction check stub

    section_nums = re.findall(r'(?m)^(\d+)\.\s', raw_text)
    if section_nums:
        nums = [int(n) for n in section_nums]
        if nums == list(range(nums[0], nums[0] + len(nums))):
            checks_passed += 1
        else:
            issues.append(IssueSchema(field_name="Section Numbering", issue_type="Non-Sequential Sections", description="Section numbering is not sequential.", severity="warning"))
    else:
        checks_passed += 1

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues

def evaluate_accuracy(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Evaluate whether numeric values and factual references appear correct."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 3

    percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', raw_text)
    if percentages:
        invalid_pct = [p for p in percentages if float(p) > 100]
        if not invalid_pct:
            checks_passed += 1
        else:
            issues.append(IssueSchema(field_name="Numeric Values", issue_type="Invalid Percentage", description="Found percentage > 100%.", severity="warning"))
    else:
        checks_passed += 1

    known_frameworks = ["iso 27001", "nist", "gdpr", "eu ai act", "ccpa", "soc 2", "pci dss"]
    text_lower = raw_text.lower()
    if [f for f in known_frameworks if f in text_lower] or len(raw_text) < 1000:
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Framework References", issue_type="No Recognized Frameworks", description="No compliance frameworks referenced.", severity="warning"))

    years = re.findall(r'\b(20\d{2})\b', raw_text)
    current_year = datetime.now().year
    future_years = [y for y in years if int(y) > current_year + 1]
    if not future_years:
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Date Accuracy", issue_type="Future Dates", description="Document references years far in the future.", severity="warning"))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues

def evaluate_timeliness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Assess whether the document has been reviewed recently."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 2
    current_year = datetime.now().year

    years = re.findall(r'\b(20\d{2})\b', raw_text)
    if years:
        most_recent = max(int(y) for y in years)
        age = current_year - most_recent
        if age <= 1:
            checks_passed += 1
        elif age <= 3:
            checks_passed += 0.5
            issues.append(IssueSchema(field_name="Document Currency", issue_type="Aging Document", description="Document may need review.", severity="warning"))
        else:
            issues.append(IssueSchema(field_name="Document Currency", issue_type="Outdated Document", description="Document appears outdated.", severity="critical"))
    else:
        issues.append(IssueSchema(field_name="Document Currency", issue_type="No Year", description="No year references found.", severity="warning"))

    review_patterns = [r'(?i)review\s*date', r'(?i)effective\s*date', r'(?i)last\s*updated']
    if any(re.search(p, raw_text) for p in review_patterns):
        checks_passed += 1
    else:
        issues.append(IssueSchema(field_name="Review Schedule", issue_type="No Review Date", description="No review date found.", severity="warning"))

    score = (checks_passed / total_checks) * 100
    return round(min(score, 100), 1), issues

def evaluate_uniqueness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Detect duplicate or near-duplicate sections within the document."""
    issues: list[IssueSchema] = []
    paragraphs = [p.strip() for p in raw_text.split('\n\n') if len(p.strip()) > 50]
    if len(paragraphs) < 2:
        return 100.0, issues

    counter = Counter(paragraphs)
    duplicates = {text[:80]: count for text, count in counter.items() if count > 1}

    if duplicates:
        issues.append(IssueSchema(field_name="Content Duplication", issue_type="Duplicate Paragraphs", description="Found repeating paragraphs.", severity="warning"))
        score = (len(set(paragraphs)) / len(paragraphs)) * 100
    else:
        score = 100.0

    return round(score, 1), issues


# ── Domain-Specific Compliance Rules ────────────────────────────────────────

def evaluate_isms_doc_control(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    checks_passed = 0
    control_elements = {
        "version": [r'(?i)version', r'(?i)revision'],
        "owner": [r'(?i)document\s*owner', r'(?i)authored?\s*by'],
        "classification": [r'(?i)classification', r'(?i)confidential'],
        "approval": [r'(?i)approved?\s*by', r'(?i)sign[\-\s]?off'],
        "review_date": [r'(?i)review\s*date', r'(?i)next\s*review'],
    }
    for element, patterns in control_elements.items():
        if any(re.search(p, raw_text) for p in patterns):
            checks_passed += 1
        else:
            issues.append(IssueSchema(field_name=f"Document Control — {element.title()}", issue_type=f"Missing {element.title()}", description=f"Missing {element}.", severity="warning"))
    return round((checks_passed / len(control_elements)) * 100, 1), issues

def evaluate_annex_a_coverage(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    annex_categories = {"A.5": "organizational", "A.6": "people", "A.7": "physical", "A.8": "technological"}
    found = sum(1 for ref, desc in annex_categories.items() if ref.lower() in raw_text.lower() or desc in raw_text.lower())
    if found < len(annex_categories):
        issues.append(IssueSchema(field_name="Annex A Coverage", issue_type="Incomplete Coverage", description=f"Only {found}/{len(annex_categories)} categories referenced.", severity="warning"))
    return round((found / len(annex_categories)) * 100, 1), issues

def evaluate_ropa_completeness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    ropa_fields = {
        "purpose": [r'(?i)purpose', r'(?i)processing\s*activit'],
        "basis": [r'(?i)lawful\s*basis', r'(?i)consent'],
        "data_cat": [r'(?i)categor(?:y|ies)\s*of\s*data'],
        "recipients": [r'(?i)recipient', r'(?i)third\s*part'],
        "retention": [r'(?i)retention', r'(?i)storage'],
        "transfers": [r'(?i)transfer', r'(?i)cross[\-\s]border'],
    }
    found = sum(1 for _, patterns in ropa_fields.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(ropa_fields):
        issues.append(IssueSchema(field_name="RoPA Fields", issue_type="Missing RoPA Field", description="Some mandatory RoPA fields are missing.", severity="warning"))
    return round((found / len(ropa_fields)) * 100, 1), issues

def evaluate_dsar_procedure(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    dsar_elements = {
        "workflow": [r'(?i)data\s*subject\s*(?:access\s*)?request', r'(?i)DSAR'],
        "timelines": [r'(?i)\d+\s*(?:day|business\s*day)'],
        "channels": [r'(?i)email', r'(?i)contact', r'(?i)privacy@'],
    }
    found = sum(1 for _, patterns in dsar_elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(dsar_elements):
         issues.append(IssueSchema(field_name="DSAR Procedures", issue_type="Missing DSAR Element", description="DSAR procedures lack completeness.", severity="warning"))
    return round((found / len(dsar_elements)) * 100, 1), issues

def evaluate_ai_risk_assessment(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    risk_elements = {"id": [r'(?i)risk\s*scenario'], "likelihood": [r'(?i)likelihood'], "impact": [r'(?i)impact'], "mitigation": [r'(?i)mitigat']}
    found = sum(1 for _, patterns in risk_elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(risk_elements):
         issues.append(IssueSchema(field_name="AI Risk Assessment", issue_type="Missing Element", description="AI risk assessment lacks some required dimensions.", severity="warning"))
    return round((found / len(risk_elements)) * 100, 1), issues

def evaluate_ai_governance_clarity(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    gov_elements = {"roles": [r'(?i)role'], "lifecycle": [r'(?i)lifecycle'], "oversight": [r'(?i)oversight'], "doc": [r'(?i)audit\s*trail']}
    found = sum(1 for _, patterns in gov_elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(gov_elements):
         issues.append(IssueSchema(field_name="AI Governance", issue_type="Missing Governance element", description="Governance docs lack clarity in some areas.", severity="warning"))
    return round((found / len(gov_elements)) * 100, 1), issues

def evaluate_fairness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    elements = {"bias": [r'(?i)bias'], "parity": [r'(?i)parity'], "discrimination": [r'(?i)discriminat'], "fairness": [r'(?i)fairness']}
    found = sum(1 for _, patterns in elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(elements):
         issues.append(IssueSchema(field_name="Fairness", issue_type="Missing Fairness Metric", description="Bias mitigation or fairness criteria missing.", severity="warning"))
    return round((found / len(elements)) * 100, 1), issues

def evaluate_transparency(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    elements = {"explainability": [r'(?i)explainab'], "architecture": [r'(?i)architect'], "training": [r'(?i)training\s*data'], "intended_use": [r'(?i)intended\s*use']}
    found = sum(1 for _, patterns in elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(elements):
         issues.append(IssueSchema(field_name="Transparency", issue_type="Missing Transparency Detail", description="Model architecture or explainability details missing.", severity="warning"))
    return round((found / len(elements)) * 100, 1), issues

def evaluate_accountability(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    elements = {"hitl": [r'(?i)human-in-the-loop', r'(?i)HITL'], "oversight": [r'(?i)oversight'], "audit": [r'(?i)audit\s*trail'], "fallback": [r'(?i)fallback']}
    found = sum(1 for _, patterns in elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(elements):
         issues.append(IssueSchema(field_name="Accountability", issue_type="Missing Accountability Control", description="Human oversight or audit mechanisms missing.", severity="warning"))
    return round((found / len(elements)) * 100, 1), issues

def evaluate_privacy(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    elements = {"pii": [r'(?i)PII', r'(?i)personally\s*identifiable'], "anonymization": [r'(?i)anonymiz'], "encryption": [r'(?i)encrypt'], "pipeline": [r'(?i)data\s*pipeline']}
    found = sum(1 for _, patterns in elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(elements):
         issues.append(IssueSchema(field_name="Privacy (AI)", issue_type="Missing Privacy Control", description="Data anonymization or PII handling details missing.", severity="warning"))
    return round((found / len(elements)) * 100, 1), issues

def evaluate_robustness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    elements = {"adversarial": [r'(?i)adversarial'], "stress": [r'(?i)stress-test'], "resilience": [r'(?i)resilien']}
    found = sum(1 for _, patterns in elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(elements):
         issues.append(IssueSchema(field_name="Robustness", issue_type="Missing Robustness Metric", description="Adversarial testing or resilience metrics missing.", severity="warning"))
    return round((found / len(elements)) * 100, 1), issues

def evaluate_regulatory(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    elements = {"nist": [r'(?i)NIST'], "eu_ai": [r'(?i)EU\s*AI\s*Act'], "gdpr": [r'(?i)GDPR'], "iso": [r'(?i)ISO']}
    found = sum(1 for _, patterns in elements.items() if any(re.search(p, raw_text) for p in patterns))
    if found < len(elements):
         issues.append(IssueSchema(field_name="Regulatory Alignment", issue_type="Missing Framework Ref", description="Adherence to major AI/Privacy frameworks not mentioned.", severity="warning"))
    return round((found / len(elements)) * 100, 1), issues

# ─── Rule Registry ──────────────────────────────────────────────────────────

RuleFn = Callable[[dict[str, Any], str], tuple[float, list[IssueSchema]]]

RULE_REGISTRY: dict[str, RuleFn] = {
    "evaluate_completeness": evaluate_completeness,
    "evaluate_validity": evaluate_validity,
    "evaluate_consistency": evaluate_consistency,
    "evaluate_accuracy": evaluate_accuracy,
    "evaluate_timeliness": evaluate_timeliness,
    "evaluate_uniqueness": evaluate_uniqueness,
    "evaluate_isms_doc_control": evaluate_isms_doc_control,
    "evaluate_annex_a_coverage": evaluate_annex_a_coverage,
    "evaluate_ropa_completeness": evaluate_ropa_completeness,
    "evaluate_dsar_procedure": evaluate_dsar_procedure,
    "evaluate_ai_risk_assessment": evaluate_ai_risk_assessment,
    "evaluate_ai_governance_clarity": evaluate_ai_governance_clarity,
    "evaluate_fairness": evaluate_fairness,
    "evaluate_transparency": evaluate_transparency,
    "evaluate_accountability": evaluate_accountability,
    "evaluate_privacy": evaluate_privacy,
    "evaluate_robustness": evaluate_robustness,
    "evaluate_regulatory": evaluate_regulatory,
}

def execute_rule(rule_fn_name: str, fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Execute a rule function by name from the registry."""
    fn = RULE_REGISTRY.get(rule_fn_name)
    if fn is None:
        logger.error("Unknown rule function: %s", rule_fn_name)
        return 0.0, [IssueSchema(
            field_name="System",
            issue_type="Configuration Error",
            description=f"Rule function '{rule_fn_name}' not found in RULE_REGISTRY.",
            severity="critical",
        )]
    return fn(fields, raw_text)
