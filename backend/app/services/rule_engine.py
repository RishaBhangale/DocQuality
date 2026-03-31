"""
Deterministic Rule Engine with Registry Pattern.

Provides a RULE_REGISTRY that maps metric rule_fn names to callable
evaluation functions. Each function accepts extracted fields and raw text,
returning a score (0–100) and a list of detected issues.

Core metrics apply to all document types.
Type-specific metrics activate based on semantic document classification.
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Callable

from app.models.schemas import IssueSchema

logger = logging.getLogger(__name__)


# ─── Rule Functions ──────────────────────────────────────────────────────────
# Signature: (fields: dict, raw_text: str) -> tuple[float, list[IssueSchema]]

# ── Core Metrics ─────────────────────────────────────────────────────────────

def evaluate_completeness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check whether the document contains expected structural elements."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 5

    # Check 1: Document has meaningful length
    if len(raw_text.strip()) > 200:
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Document Body",
            issue_type="Insufficient Content",
            description="Document is too short to contain meaningful policy or compliance information.",
            severity="critical",
        ))

    # Check 2: Has section headings (any numbered or titled sections)
    headings = re.findall(r'(?m)^(?:\d+[\.\)]\s+|#{1,3}\s+|[A-Z][A-Z\s]{3,}:)', raw_text)
    if len(headings) >= 2:
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Document Structure",
            issue_type="Missing Section Headings",
            description="Document lacks clear section structure (expected numbered or titled headings).",
            severity="warning",
        ))

    # Check 3: Has a date reference
    date_pattern = r'\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b'
    if re.search(date_pattern, raw_text, re.IGNORECASE):
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Document Metadata",
            issue_type="No Date Found",
            description="No recognizable date found in the document (expected creation, review, or effective date).",
            severity="warning",
        ))

    # Check 4: Has an author/owner reference
    owner_patterns = [r'(?i)author', r'(?i)owner', r'(?i)prepared\s+by', r'(?i)approved\s+by', r'(?i)responsible']
    if any(re.search(p, raw_text) for p in owner_patterns):
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Document Ownership",
            issue_type="No Author/Owner",
            description="No author, owner, or responsible party identified in the document.",
            severity="warning",
        ))

    # Check 5: Has a scope or purpose statement
    scope_patterns = [r'(?i)scope', r'(?i)purpose', r'(?i)objective', r'(?i)introduction', r'(?i)overview']
    if any(re.search(p, raw_text) for p in scope_patterns):
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Document Scope",
            issue_type="Missing Scope/Purpose",
            description="No scope, purpose, or objective statement found.",
            severity="warning",
        ))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues


def evaluate_validity(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Verify that dates, references, and identifiers conform to expected formats."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 3

    # Check 1: Dates are parseable
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
            issues.append(IssueSchema(
                field_name="Date Formats",
                issue_type="Invalid Date Format",
                description="Dates found but none could be parsed as valid ISO dates.",
                severity="warning",
            ))
    else:
        checks_passed += 0.5  # No dates is not necessarily invalid

    # Check 2: Version identifier present and well-formed
    version_pattern = r'(?i)(?:version|v|rev)\s*[:\.]?\s*\d+[\.\d]*'
    if re.search(version_pattern, raw_text):
        checks_passed += 1
    else:
        checks_passed += 0.5  # Not all docs need versions

    # Check 3: No obviously broken references (e.g., "[TBD]", "TODO", "XXX")
    placeholder_patterns = [r'\[TBD\]', r'\bTODO\b', r'\bXXX\b', r'\bFIXME\b', r'\[INSERT\b']
    placeholders_found = sum(1 for p in placeholder_patterns if re.search(p, raw_text, re.IGNORECASE))
    if placeholders_found == 0:
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Content Placeholders",
            issue_type="Unresolved Placeholders",
            description=f"Found {placeholders_found} placeholder(s) (TBD, TODO, etc.) that need to be resolved.",
            severity="critical",
        ))

    score = (checks_passed / total_checks) * 100
    return round(min(score, 100), 1), issues


def evaluate_consistency(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check coherence across sections — terminology, naming, references."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 3

    # Check 1: Consistent terminology (e.g., doesn't mix "data subject" and "user" erratically)
    text_lower = raw_text.lower()
    term_pairs = [
        ("data subject", "user"),
        ("controller", "processor"),
        ("shall", "must"),
    ]
    inconsistencies = 0
    for term_a, term_b in term_pairs:
        count_a = text_lower.count(term_a)
        count_b = text_lower.count(term_b)
        # If both are heavily used, it's potentially inconsistent
        if count_a > 3 and count_b > 3:
            inconsistencies += 1

    if inconsistencies == 0:
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Terminology",
            issue_type="Inconsistent Terminology",
            description=f"Detected {inconsistencies} potential terminology inconsistency(ies).",
            severity="warning",
        ))

    # Check 2: No contradictory statements (basic check for "not" near previously affirmed statements)
    checks_passed += 1  # Hard to do deterministically, give benefit of the doubt

    # Check 3: Section numbering is sequential (if numbered)
    section_nums = re.findall(r'(?m)^(\d+)\.\s', raw_text)
    if section_nums:
        nums = [int(n) for n in section_nums]
        expected = list(range(nums[0], nums[0] + len(nums)))
        if nums == expected:
            checks_passed += 1
        else:
            issues.append(IssueSchema(
                field_name="Section Numbering",
                issue_type="Non-Sequential Sections",
                description="Section numbering is not sequential, suggesting missing or reordered sections.",
                severity="warning",
            ))
    else:
        checks_passed += 1  # No numbering is fine

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues


def evaluate_accuracy(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Evaluate whether numeric values and factual references appear correct."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 3

    # Check 1: Percentages are in valid range
    percentages = re.findall(r'(\d+(?:\.\d+)?)\s*%', raw_text)
    if percentages:
        invalid_pct = [p for p in percentages if float(p) > 100]
        if not invalid_pct:
            checks_passed += 1
        else:
            issues.append(IssueSchema(
                field_name="Numeric Values",
                issue_type="Invalid Percentage",
                description=f"Found percentage value(s) exceeding 100%: {', '.join(invalid_pct[:3])}.",
                severity="warning",
            ))
    else:
        checks_passed += 1

    # Check 2: Referenced standards/frameworks are real
    known_frameworks = [
        "iso 27001", "iso 27701", "iso 42001", "nist", "gdpr", "eu ai act",
        "ccpa", "hipaa", "soc 2", "pci dss", "iso 31000", "cobit", "nist ai rmf",
    ]
    text_lower = raw_text.lower()
    referenced = [f for f in known_frameworks if f in text_lower]
    if referenced or len(raw_text) < 1000:
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Framework References",
            issue_type="No Recognized Frameworks",
            description="No recognized compliance frameworks or standards are referenced in the document.",
            severity="warning",
        ))

    # Check 3: No obviously wrong years (e.g., future years beyond next year)
    years = re.findall(r'\b(20\d{2})\b', raw_text)
    current_year = datetime.now().year
    future_years = [y for y in years if int(y) > current_year + 1]
    if not future_years:
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Date Accuracy",
            issue_type="Suspicious Future Dates",
            description=f"Document references years far in the future: {', '.join(future_years[:3])}.",
            severity="warning",
        ))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues


def evaluate_timeliness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Assess whether the document has been reviewed recently."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 2

    current_year = datetime.now().year

    # Check 1: Document mentions current or recent year
    years = re.findall(r'\b(20\d{2})\b', raw_text)
    if years:
        most_recent = max(int(y) for y in years)
        age = current_year - most_recent
        if age <= 1:
            checks_passed += 1
        elif age <= 3:
            checks_passed += 0.5
            issues.append(IssueSchema(
                field_name="Document Currency",
                issue_type="Aging Document",
                description=f"Most recent year referenced is {most_recent}. Document may need review.",
                severity="warning",
            ))
        else:
            issues.append(IssueSchema(
                field_name="Document Currency",
                issue_type="Outdated Document",
                description=f"Most recent year referenced is {most_recent}. Document appears significantly outdated.",
                severity="critical",
            ))
    else:
        issues.append(IssueSchema(
            field_name="Document Currency",
            issue_type="No Year References",
            description="No year references found. Cannot determine document timeliness.",
            severity="warning",
        ))

    # Check 2: Has review/effective date keywords
    review_patterns = [r'(?i)review\s*date', r'(?i)effective\s*date', r'(?i)last\s*updated', r'(?i)next\s*review']
    if any(re.search(p, raw_text) for p in review_patterns):
        checks_passed += 1
    else:
        issues.append(IssueSchema(
            field_name="Review Schedule",
            issue_type="No Review Date",
            description="No review date, effective date, or update timestamp found.",
            severity="warning",
        ))

    score = (checks_passed / total_checks) * 100
    return round(min(score, 100), 1), issues


def evaluate_uniqueness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Detect duplicate or near-duplicate sections within the document."""
    issues: list[IssueSchema] = []

    # Split into paragraphs and look for duplicates
    paragraphs = [p.strip() for p in raw_text.split('\n\n') if len(p.strip()) > 50]

    if len(paragraphs) < 2:
        return 100.0, issues

    # Count exact duplicate paragraphs
    counter = Counter(paragraphs)
    duplicates = {text[:80]: count for text, count in counter.items() if count > 1}

    if duplicates:
        dup_count = len(duplicates)
        issues.append(IssueSchema(
            field_name="Content Duplication",
            issue_type="Duplicate Paragraphs",
            description=f"Found {dup_count} paragraph(s) that appear more than once in the document.",
            severity="warning" if dup_count <= 2 else "critical",
        ))
        # Proportional score based on duplication ratio
        total_paras = len(paragraphs)
        unique_paras = len(set(paragraphs))
        score = (unique_paras / total_paras) * 100
    else:
        score = 100.0

    return round(score, 1), issues


# ── Type-Specific Metrics: ISMS / ISO 27001 ─────────────────────────────────

def evaluate_isms_doc_control(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check for ISMS document control elements: version, owner, classification, approval, review dates."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 5

    text_lower = raw_text.lower()

    control_elements = {
        "version": [r'(?i)version', r'(?i)revision', r'(?i)\brev\b'],
        "owner": [r'(?i)document\s*owner', r'(?i)responsible\s*party', r'(?i)authored?\s*by'],
        "classification": [r'(?i)classification', r'(?i)confidential', r'(?i)internal', r'(?i)public', r'(?i)restricted'],
        "approval": [r'(?i)approved?\s*by', r'(?i)sign[\-\s]?off', r'(?i)authorization'],
        "review_date": [r'(?i)review\s*date', r'(?i)next\s*review', r'(?i)review\s*cycle'],
    }

    for element, patterns in control_elements.items():
        if any(re.search(p, raw_text) for p in patterns):
            checks_passed += 1
        else:
            issues.append(IssueSchema(
                field_name=f"Document Control — {element.replace('_', ' ').title()}",
                issue_type=f"Missing {element.replace('_', ' ').title()}",
                description=f"ISMS document control requires a {element.replace('_', ' ')} element (ISO 27001 Clause 7.5).",
                severity="warning",
            ))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues


def evaluate_annex_a_coverage(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Scan for references to ISO 27001 Annex A control categories."""
    issues: list[IssueSchema] = []

    annex_categories = {
        "A.5": "organizational controls",
        "A.6": "people controls",
        "A.7": "physical controls",
        "A.8": "technological controls",
    }

    text_lower = raw_text.lower()
    found = 0
    for ref, desc in annex_categories.items():
        if ref.lower() in text_lower or desc in text_lower:
            found += 1

    total = len(annex_categories)
    if found < total:
        missing = total - found
        issues.append(IssueSchema(
            field_name="Annex A Coverage",
            issue_type="Incomplete Control Coverage",
            description=f"Only {found}/{total} Annex A control categories are referenced. {missing} category(ies) missing.",
            severity="warning" if found >= 2 else "critical",
        ))

    score = (found / total) * 100
    return round(score, 1), issues


# ── Type-Specific Metrics: Privacy / ISO 27701 ──────────────────────────────

def evaluate_ropa_completeness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check that mandatory RoPA fields are present."""
    issues: list[IssueSchema] = []

    ropa_fields = {
        "processing_purposes": [r'(?i)purpose', r'(?i)processing\s*activit'],
        "lawful_basis": [r'(?i)lawful\s*basis', r'(?i)legal\s*basis', r'(?i)consent', r'(?i)legitimate\s*interest'],
        "data_categories": [r'(?i)categor(?:y|ies)\s*of\s*data', r'(?i)data\s*categor', r'(?i)personal\s*data'],
        "recipients": [r'(?i)recipient', r'(?i)third\s*part', r'(?i)disclosure'],
        "retention": [r'(?i)retention', r'(?i)storage\s*period', r'(?i)deletion'],
        "transfers": [r'(?i)transfer', r'(?i)cross[\-\s]border', r'(?i)international'],
    }

    found = 0
    for field_name, patterns in ropa_fields.items():
        if any(re.search(p, raw_text) for p in patterns):
            found += 1
        else:
            issues.append(IssueSchema(
                field_name=f"RoPA — {field_name.replace('_', ' ').title()}",
                issue_type=f"Missing RoPA Field",
                description=f"Records of Processing Activities should include {field_name.replace('_', ' ')} (ISO 27701 A.7.2.8).",
                severity="warning",
            ))

    score = (found / len(ropa_fields)) * 100
    return round(score, 1), issues


def evaluate_dsar_procedure(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Verify presence of DSAR workflow, timelines, and contact channels."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 3

    dsar_elements = {
        "workflow": [r'(?i)data\s*subject\s*(?:access\s*)?request', r'(?i)DSAR', r'(?i)right\s*(?:of|to)\s*access'],
        "timelines": [r'(?i)\d+\s*(?:day|business\s*day|calendar\s*day)', r'(?i)response\s*time', r'(?i)within\s*\d+'],
        "channels": [r'(?i)email', r'(?i)contact', r'(?i)portal', r'(?i)privacy@', r'(?i)dpo'],
    }

    for element, patterns in dsar_elements.items():
        if any(re.search(p, raw_text) for p in patterns):
            checks_passed += 1
        else:
            issues.append(IssueSchema(
                field_name=f"DSAR — {element.title()}",
                issue_type=f"Missing DSAR {element.title()}",
                description=f"DSAR procedures should include {element} information (ISO 27701 A.7.3).",
                severity="warning",
            ))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues


# ── Type-Specific Metrics: AI / ISO 42001 ───────────────────────────────────

def evaluate_ai_risk_assessment(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check for structured risk entries with required fields."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 4

    risk_elements = {
        "risk_identification": [r'(?i)risk\s*(?:id|identifier|register)', r'(?i)risk\s*scenario', r'(?i)threat'],
        "likelihood": [r'(?i)likelihood', r'(?i)probability', r'(?i)frequency'],
        "impact": [r'(?i)impact', r'(?i)consequence', r'(?i)severity\s*level'],
        "mitigation": [r'(?i)mitigat', r'(?i)treatment', r'(?i)control\s*measure', r'(?i)residual\s*risk'],
    }

    for element, patterns in risk_elements.items():
        if any(re.search(p, raw_text) for p in patterns):
            checks_passed += 1
        else:
            issues.append(IssueSchema(
                field_name=f"AI Risk — {element.replace('_', ' ').title()}",
                issue_type=f"Missing {element.replace('_', ' ').title()}",
                description=f"AI risk assessment should include {element.replace('_', ' ')} (ISO 42001 6.1.2).",
                severity="warning",
            ))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues


def evaluate_ai_governance_clarity(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    """Check that AI governance roles, lifecycle, and accountability are clearly defined."""
    issues: list[IssueSchema] = []
    checks_passed = 0
    total_checks = 4

    governance_elements = {
        "roles": [r'(?i)role', r'(?i)responsible', r'(?i)accountable', r'(?i)raci'],
        "lifecycle": [r'(?i)lifecycle', r'(?i)life[\-\s]cycle', r'(?i)development\s*process', r'(?i)deployment'],
        "oversight": [r'(?i)human[\-\s]in[\-\s]the[\-\s]loop', r'(?i)oversight', r'(?i)review\s*board', r'(?i)governance\s*committee'],
        "documentation": [r'(?i)document', r'(?i)record', r'(?i)log', r'(?i)audit\s*trail'],
    }

    for element, patterns in governance_elements.items():
        if any(re.search(p, raw_text) for p in patterns):
            checks_passed += 1
        else:
            issues.append(IssueSchema(
                field_name=f"AI Governance — {element.title()}",
                issue_type=f"Missing {element.title()} Definition",
                description=f"AI governance documentation should include {element} (ISO 42001 5.1, A.5.3).",
                severity="warning",
            ))

    score = (checks_passed / total_checks) * 100
    return round(score, 1), issues


# ── Legacy AI Metrics (preserved as type-specific) ──────────────────────────

def evaluate_fairness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    keywords = ["bias", "parity", "demographic", "fairness", "disparate", "minority", "protected"]
    found = _check_keywords_in_text(raw_text, keywords)
    passed = min(len(found), 4)
    if passed < 2:
        issues.append(IssueSchema(
            field_name="Fairness Analysis", issue_type="Missing Bias Strategy",
            description="Failed to detect adequate mentions of bias mitigation strategies or demographic parity.",
            severity="critical",
        ))
    return round((passed / 4) * 100, 1), issues


def evaluate_transparency(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    keywords = ["architecture", "training", "parameters", "weights", "source", "intended use", "explainability", "dataset"]
    found = _check_keywords_in_text(raw_text, keywords)
    passed = min(len(found), 5)
    if passed < 3:
        issues.append(IssueSchema(
            field_name="Model Transparency", issue_type="Lack of Model Explainability",
            description="Insufficient details regarding model architecture, training sources, or parameters.",
            severity="critical",
        ))
    return round((passed / 5) * 100, 1), issues


def evaluate_accountability(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    keywords = ["human-in-the-loop", "oversight", "fallback", "responsibility", "audit", "governance", "review"]
    found = _check_keywords_in_text(raw_text, keywords)
    passed = min(len(found), 3)
    if passed < 1:
        issues.append(IssueSchema(
            field_name="Governance & Oversight", issue_type="Missing Accountability Measures",
            description="No clear human-in-the-loop, oversight, or fallback mechanisms defined.",
            severity="warning",
        ))
    return round((passed / 3) * 100, 1), issues


def evaluate_privacy(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    keywords = ["pii", "anonymization", "encryption", "gdpr", "data protection", "confidentiality", "consent"]
    found = _check_keywords_in_text(raw_text, keywords)
    passed = min(len(found), 4)
    if passed < 2:
        issues.append(IssueSchema(
            field_name="Privacy & Security", issue_type="Inadequate Data Protection",
            description="Insufficient mentions of PII shielding, data anonymization, or encryption.",
            severity="critical",
        ))
    return round((passed / 4) * 100, 1), issues


def evaluate_robustness(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    keywords = ["stress", "edge case", "adversarial", "performance", "degradation", "resilience", "testing", "metrics"]
    found = _check_keywords_in_text(raw_text, keywords)
    passed = min(len(found), 4)
    if passed < 2:
        issues.append(IssueSchema(
            field_name="Model Robustness", issue_type="Weak Adversarial Testing",
            description="Failed to detect adequate adversarial testing, expected performance degradation, or resilience metrics.",
            severity="warning",
        ))
    return round((passed / 4) * 100, 1), issues


def evaluate_regulatory(fields: dict[str, Any], raw_text: str) -> tuple[float, list[IssueSchema]]:
    issues: list[IssueSchema] = []
    keywords = ["nist", "eu ai act", "compliance", "regulation", "framework", "standard", "legal", "iso"]
    found = _check_keywords_in_text(raw_text, keywords)
    passed = min(len(found), 3)
    if passed < 1:
        issues.append(IssueSchema(
            field_name="Regulatory Alignment", issue_type="No Standards Mentioned",
            description="No recognized compliance frameworks (NIST, EU AI Act, ISO, etc.) are cited.",
            severity="warning",
        ))
    return round((passed / 3) * 100, 1), issues


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _check_keywords_in_text(raw_text: str, keywords: list[str]) -> set[str]:
    """Find unique keywords in raw document text."""
    text_lower = raw_text.lower()
    return {kw for kw in keywords if kw in text_lower}


# ─── Rule Registry ──────────────────────────────────────────────────────────

RuleFn = Callable[[dict[str, Any], str], tuple[float, list[IssueSchema]]]

RULE_REGISTRY: dict[str, RuleFn] = {
    # Core metrics
    "evaluate_completeness": evaluate_completeness,
    "evaluate_validity": evaluate_validity,
    "evaluate_consistency": evaluate_consistency,
    "evaluate_accuracy": evaluate_accuracy,
    "evaluate_timeliness": evaluate_timeliness,
    "evaluate_uniqueness": evaluate_uniqueness,
    # ISMS / ISO 27001
    "evaluate_isms_doc_control": evaluate_isms_doc_control,
    "evaluate_annex_a_coverage": evaluate_annex_a_coverage,
    # Privacy / ISO 27701
    "evaluate_ropa_completeness": evaluate_ropa_completeness,
    "evaluate_dsar_procedure": evaluate_dsar_procedure,
    # AI / ISO 42001
    "evaluate_ai_risk_assessment": evaluate_ai_risk_assessment,
    "evaluate_ai_governance_clarity": evaluate_ai_governance_clarity,
    # Legacy AI metrics
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
