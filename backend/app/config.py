"""
Application configuration module.

Loads environment variables and provides centralized configuration
for all application components, including ISO standards catalog
and data-driven metric definitions.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


# ─── ISO Standards Catalog ───────────────────────────────────────────────────


@dataclass(frozen=True)
class StandardRef:
    """Reference to a specific ISO standard."""
    id: str
    name: str
    version: str
    description: str


@dataclass(frozen=True)
class LinkedStandardRef:
    """Links a metric to a specific ISO control/clause."""
    standard_id: str
    control_id: str
    clause: str
    description: str


STANDARDS_CATALOG: dict[str, StandardRef] = {
    "ISO_27001": StandardRef(
        id="ISO_27001",
        name="ISO/IEC 27001:2022",
        version="2022",
        description="Information Security Management System (ISMS) — documented information, "
                    "document control, Annex A controls, Statement of Applicability, risk treatment.",
    ),
    "ISO_27701": StandardRef(
        id="ISO_27701",
        name="ISO/IEC 27701:2019",
        version="2019",
        description="Privacy Information Management — RoPA, DPIA, DSAR procedures, "
                    "privacy policies, data subject rights.",
    ),
    "ISO_42001": StandardRef(
        id="ISO_42001",
        name="ISO/IEC 42001:2023",
        version="2023",
        description="AI Management System (AIMS) — AI policy, AI risk/impact assessments, "
                    "AI lifecycle processes, governance and accountability.",
    ),
}


# ─── Semantic Document Types ─────────────────────────────────────────────────

SEMANTIC_TYPES = [
    "isms_policy",
    "privacy_policy",
    "ropa_record",
    "dpia",
    "ai_policy",
    "ai_risk_assessment",
    "contract",
    "invoice",
    "general",
]

DOC_TYPE_TO_STANDARDS: dict[str, list[str]] = {
    "isms_policy":        ["ISO_27001"],
    "privacy_policy":     ["ISO_27701", "ISO_27001"],
    "ropa_record":        ["ISO_27701"],
    "dpia":               ["ISO_27701"],
    "ai_policy":          ["ISO_42001"],
    "ai_risk_assessment": ["ISO_42001"],
    "contract":           ["ISO_27001", "ISO_27701"],
    "invoice":            ["ISO_27001"],
    "general":            [],
}


# ─── Metric Definitions ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class MetricDefinition:
    """Data-driven definition of a quality metric."""
    id: str
    name: str
    category: Literal["core", "type_specific"]
    doc_types: list[str]         # semantic types where this metric is active
    linked_standards: list[LinkedStandardRef]
    rule_fn: str                 # name of the function in rule_engine RULE_REGISTRY
    weight: float = 1.0
    description: str = ""


# --- Core Metrics (apply to ALL document types) ---

CORE_METRICS: list[MetricDefinition] = [
    MetricDefinition(
        id="completeness",
        name="Completeness",
        category="core",
        doc_types=SEMANTIC_TYPES,
        linked_standards=[],
        rule_fn="evaluate_completeness",
        weight=0.20,
        description="Checks whether the document contains all expected sections, fields, and structural elements.",
    ),
    MetricDefinition(
        id="validity",
        name="Validity",
        category="core",
        doc_types=SEMANTIC_TYPES,
        linked_standards=[],
        rule_fn="evaluate_validity",
        weight=0.15,
        description="Verifies that dates, references, and identifiers conform to expected formats.",
    ),
    MetricDefinition(
        id="consistency",
        name="Consistency",
        category="core",
        doc_types=SEMANTIC_TYPES,
        linked_standards=[],
        rule_fn="evaluate_consistency",
        weight=0.15,
        description="Checks coherence across sections — summaries match body, terminology is uniform.",
    ),
    MetricDefinition(
        id="accuracy",
        name="Accuracy",
        category="core",
        doc_types=SEMANTIC_TYPES,
        linked_standards=[],
        rule_fn="evaluate_accuracy",
        weight=0.20,
        description="Evaluates whether numeric values, calculations, and factual references are correct.",
    ),
    MetricDefinition(
        id="timeliness",
        name="Timeliness",
        category="core",
        doc_types=SEMANTIC_TYPES,
        linked_standards=[],
        rule_fn="evaluate_timeliness",
        weight=0.15,
        description="Assesses whether the document has been reviewed recently and carries current dates.",
    ),
    MetricDefinition(
        id="uniqueness",
        name="Uniqueness",
        category="core",
        doc_types=SEMANTIC_TYPES,
        linked_standards=[],
        rule_fn="evaluate_uniqueness",
        weight=0.15,
        description="Detects duplicate or near-duplicate sections, paragraphs, or entries within the document.",
    ),
]


# --- Type-Specific Metrics ---

TYPE_SPECIFIC_METRICS: list[MetricDefinition] = [
    # ── ISMS / ISO 27001 ──
    MetricDefinition(
        id="isms_doc_control",
        name="ISMS Document Control",
        category="type_specific",
        doc_types=["isms_policy"],
        linked_standards=[
            LinkedStandardRef("ISO_27001", "7.5", "Clause 7.5",
                              "Documented information is controlled and current (version, approval, retention)."),
        ],
        rule_fn="evaluate_isms_doc_control",
        weight=1.0,
        description="Checks for document versioning, ownership, classification, approval, and review dates.",
    ),
    MetricDefinition(
        id="annex_a_coverage",
        name="Annex A Control Coverage",
        category="type_specific",
        doc_types=["isms_policy"],
        linked_standards=[
            LinkedStandardRef("ISO_27001", "A.5-A.8", "Annex A",
                              "Statement of Applicability covers organizational, people, physical, and technological controls."),
        ],
        rule_fn="evaluate_annex_a_coverage",
        weight=1.0,
        description="Scans for references to Annex A control categories across the Statement of Applicability.",
    ),

    # ── Privacy / ISO 27701 ──
    MetricDefinition(
        id="ropa_completeness",
        name="RoPA Completeness",
        category="type_specific",
        doc_types=["ropa_record", "privacy_policy"],
        linked_standards=[
            LinkedStandardRef("ISO_27701", "A.7.2.8", "Clause A.7.2.8",
                              "Records of processing activities are complete (purposes, lawful basis, categories, recipients, retention, transfers)."),
        ],
        rule_fn="evaluate_ropa_completeness",
        weight=1.0,
        description="Checks that mandatory RoPA fields are present: processing purposes, lawful basis, data categories, recipients, retention periods, and transfers.",
    ),
    MetricDefinition(
        id="dsar_procedure",
        name="DSAR Procedure Clarity",
        category="type_specific",
        doc_types=["privacy_policy", "dpia"],
        linked_standards=[
            LinkedStandardRef("ISO_27701", "A.7.3", "Clause A.7.3",
                              "Data subject access request procedures with timelines, channels, and escalation."),
        ],
        rule_fn="evaluate_dsar_procedure",
        weight=1.0,
        description="Verifies presence of DSAR workflow, response timelines, contact channels, and escalation paths.",
    ),

    # ── AI Governance / ISO 42001 ──
    MetricDefinition(
        id="ai_risk_assessment",
        name="AI Risk Assessment Documentation",
        category="type_specific",
        doc_types=["ai_risk_assessment", "ai_policy"],
        linked_standards=[
            LinkedStandardRef("ISO_42001", "6.1.2", "Clause 6.1.2",
                              "AI risks and impacts are assessed and documented with likelihood, impact, and mitigation."),
        ],
        rule_fn="evaluate_ai_risk_assessment",
        weight=1.0,
        description="Checks for structured risk entries with scenario, likelihood, impact, mitigation, and residual risk.",
    ),
    MetricDefinition(
        id="ai_governance_clarity",
        name="AI Governance & Accountability",
        category="type_specific",
        doc_types=["ai_risk_assessment", "ai_policy"],
        linked_standards=[
            LinkedStandardRef("ISO_42001", "5.1", "Clause 5.1",
                              "AI governance roles, lifecycle processes, and responsibilities are described."),
            LinkedStandardRef("ISO_42001", "A.5.3", "Annex A.5.3",
                              "AI system impact assessment processes are in place."),
        ],
        rule_fn="evaluate_ai_governance_clarity",
        weight=1.0,
        description="Checks that roles, lifecycle processes, human oversight, and accountability mechanisms are clearly defined.",
    ),

    # ── Legacy AI-specific metrics (now type-specific for AI docs) ──
    MetricDefinition(
        id="fairness",
        name="Fairness",
        category="type_specific",
        doc_types=["ai_policy", "ai_risk_assessment"],
        linked_standards=[
            LinkedStandardRef("ISO_42001", "A.8.4", "Annex A.8.4",
                              "Bias mitigation and demographic parity measures."),
        ],
        rule_fn="evaluate_fairness",
        weight=1.0,
        description="Evaluates bias mitigation strategies, demographic parity, and anti-discrimination policies.",
    ),
    MetricDefinition(
        id="transparency",
        name="Transparency",
        category="type_specific",
        doc_types=["ai_policy", "ai_risk_assessment"],
        linked_standards=[
            LinkedStandardRef("ISO_42001", "A.6.2", "Annex A.6.2",
                              "Model explainability and documentation of architecture."),
        ],
        rule_fn="evaluate_transparency",
        weight=1.0,
        description="Checks documentation of model architecture, training data, intended use, and explainability.",
    ),
    MetricDefinition(
        id="accountability",
        name="Accountability",
        category="type_specific",
        doc_types=["ai_policy", "ai_risk_assessment"],
        linked_standards=[
            LinkedStandardRef("ISO_42001", "5.1", "Clause 5.1",
                              "Human-in-the-loop, oversight, and fallback mechanisms."),
        ],
        rule_fn="evaluate_accountability",
        weight=1.0,
        description="Checks for human-in-the-loop, oversight, audit trails, and fallback procedures.",
    ),
    MetricDefinition(
        id="privacy_ai",
        name="Privacy (AI)",
        category="type_specific",
        doc_types=["ai_policy", "ai_risk_assessment"],
        linked_standards=[
            LinkedStandardRef("ISO_27701", "A.7.4", "Clause A.7.4",
                              "PII handling, anonymization, and encryption in AI systems."),
        ],
        rule_fn="evaluate_privacy",
        weight=1.0,
        description="Ensures PII handling, data anonymization, and encryption are addressed for AI data pipelines.",
    ),
    MetricDefinition(
        id="robustness",
        name="Robustness",
        category="type_specific",
        doc_types=["ai_policy", "ai_risk_assessment"],
        linked_standards=[
            LinkedStandardRef("ISO_42001", "A.7.3", "Annex A.7.3",
                              "Performance under stress-tests and adversarial conditions."),
        ],
        rule_fn="evaluate_robustness",
        weight=1.0,
        description="Assesses adversarial testing, stress-test metrics, and resilience documentation.",
    ),
    MetricDefinition(
        id="regulatory",
        name="Regulatory Alignment",
        category="type_specific",
        doc_types=["ai_policy", "ai_risk_assessment", "isms_policy", "privacy_policy"],
        linked_standards=[],
        rule_fn="evaluate_regulatory",
        weight=1.0,
        description="Identifies adherence to recognized frameworks (NIST AI RMF, EU AI Act, GDPR, ISO).",
    ),
]

# Combined list for lookups
ALL_METRIC_DEFINITIONS: list[MetricDefinition] = CORE_METRICS + TYPE_SPECIFIC_METRICS


def get_metrics_for_type(semantic_type: str) -> list[MetricDefinition]:
    """Return all applicable metrics for a given semantic document type."""
    return [m for m in ALL_METRIC_DEFINITIONS if semantic_type in m.doc_types]


def get_core_metrics() -> list[MetricDefinition]:
    """Return only core metrics."""
    return [m for m in ALL_METRIC_DEFINITIONS if m.category == "core"]


def get_type_specific_metrics(semantic_type: str) -> list[MetricDefinition]:
    """Return type-specific metrics for a given semantic document type."""
    return [m for m in ALL_METRIC_DEFINITIONS
            if m.category == "type_specific" and semantic_type in m.doc_types]


# ─── Application Settings ────────────────────────────────────────────────────


class Settings:
    """Centralized application settings loaded from environment variables."""

    # Azure Foundry LLM Configuration
    FOUNDRY_API_KEY: str = os.getenv("FOUNDRY_API_KEY", "")
    FOUNDRY_ENDPOINT: str = os.getenv("FOUNDRY_ENDPOINT", "")
    FOUNDRY_MODEL: str = os.getenv("FOUNDRY_MODEL", "")
    FOUNDRY_API_VERSION: str = os.getenv("FOUNDRY_API_VERSION", "")

    # Database Configuration
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./document_quality.db")

    # Application Configuration
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", "5"))
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # LLM Configuration
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    LLM_TEMPERATURE: float = 0.0

    # Supported file types
    SUPPORTED_FILE_TYPES: list[str] = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]

    # Generic scoring weights (compliance mode)
    METRIC_WEIGHTS: dict[str, float] = {
        "completeness": 0.25,
        "validity": 0.20,
        "consistency": 0.20,
        "accuracy": 0.20,
        "timeliness": 0.10,
        "uniqueness": 0.05,
    }

    # ── Banking Domain Config ─────────────────────────────────────────────────

    # Domain-adaptive scoring weights — override METRIC_WEIGHTS when banking domain detected
    DOMAIN_SCORING_WEIGHTS: dict[str, dict[str, float]] = {
        "Customer Onboarding (KYC/AML)": {
            "completeness": 0.30, "validity": 0.30, "accuracy": 0.20,
            "consistency": 0.10, "timeliness": 0.05, "uniqueness": 0.05,
        },
        "Loan & Credit Documentation": {
            "completeness": 0.25, "validity": 0.35, "consistency": 0.25,
            "accuracy": 0.10, "timeliness": 0.03, "uniqueness": 0.02,
        },
        "Treasury & Liquidity Reports": {
            "accuracy": 0.35, "consistency": 0.30, "completeness": 0.20,
            "validity": 0.10, "timeliness": 0.04, "uniqueness": 0.01,
        },
        "Regulatory & Compliance Filings": {
            "completeness": 0.30, "accuracy": 0.25, "validity": 0.25,
            "consistency": 0.15, "timeliness": 0.04, "uniqueness": 0.01,
        },
        "Investment Banking & M&A": {
            "accuracy": 0.35, "completeness": 0.25, "consistency": 0.25,
            "validity": 0.10, "timeliness": 0.04, "uniqueness": 0.01,
        },
        "Fraud & Investigation Records": {
            "completeness": 0.35, "accuracy": 0.30, "consistency": 0.20,
            "validity": 0.10, "timeliness": 0.04, "uniqueness": 0.01,
        },
    }

    # Banking metric weights for S_Bank composite score (per domain)
    BANKING_METRIC_WEIGHTS: dict[str, dict[str, float]] = {
        "Customer Onboarding (KYC/AML)": {
            "Beneficial Ownership Transparency Index (BOTI)": 0.20,
            "Identity Evidence Strength Score (IESS)": 0.15,
            "Sanctions/PEP Screening Evidence Coverage (SPEC)": 0.15,
            "CDD/EDD Trigger Justification Quality (CEDJ)": 0.15,
            "Source-of-Funds Traceability (SOFT)": 0.15,
            "Address Verification Strength (AVS)": 0.10,
            "Risk Rating Explainability (RRE)": 0.10,
        },
        "Loan & Credit Documentation": {
            "Collateral Perfection Index (CPI)": 0.20,
            "Covenant Compliance Transparency Score (CCTS)": 0.15,
            "Rate Index & Fallback Correctness (RIFC)": 0.15,
            "Execution & Authority Completeness (EAC)": 0.15,
            "Repayment Schedule Integrity (RSI)": 0.15,
            "Borrower/Guarantor Identification Consistency (BGIC)": 0.10,
            "Collateral Valuation Recency (CVR)": 0.10,
        },
        "Treasury & Liquidity Reports": {
            "HQLA Eligibility Confidence (HEC)": 0.18,
            "Inter-System Reconciliation Ratio (ISRR)": 0.16,
            "Cut-off Time & Timestamp Alignment (CTTA)": 0.14,
            "Stress Scenario Coverage (SSC)": 0.14,
            "Inflow/Outflow Classification Completeness (IOCC)": 0.14,
            "Limit Breach Disclosure Quality (LBDQ)": 0.12,
            "Source System Coverage (SSCOV)": 0.12,
        },
        "Regulatory & Compliance Filings": {
            "Regulatory Mapping Precision (RMP)": 0.20,
            "BCBS 239 Data Lineage Integrity (DLI)": 0.20,
            "Regulatory Change Coverage (RCC)": 0.15,
            "Disclosure Completeness Score (DCS)": 0.15,
            "Governance Sign-off Completeness (GSC)": 0.10,
            "Control Mapping Coverage (CMC)": 0.10,
            "Recordkeeping & Classification Policy Coverage (RCPC)": 0.10,
        },
        "Investment Banking & M&A": {
            "QoE Normalization Transparency": 0.20,
            "Fairness Opinion Sensitivity Index (FOSI)": 0.15,
            "Assumption Transparency Score (ATS)": 0.15,
            "Sensitivity Analysis Coverage (SAC)": 0.15,
            "Comparable Set Justification (CSJ)": 0.12,
            "Conflict & Independence Disclosure Completeness (CIDC)": 0.12,
            "Data Room Traceability (DRT)": 0.11,
        },
        "Fraud & Investigation Records": {
            "SAR Narrative Actionability Density (SNAD)": 0.20,
            "Whistleblower Credibility Weight (WCW)": 0.14,
            "Timeline Coherence Score (TCS)": 0.14,
            "Evidence Chain-of-Custody Completeness (ECCC)": 0.14,
            "Transaction Detail Completeness (TDC)": 0.14,
            "Disposition & Escalation Traceability (DETR)": 0.12,
            "Regulatory Notification Completeness (RNC)": 0.12,
        },
    }

    # Regulatory pass thresholds per metric code
    BANKING_REGULATORY_THRESHOLDS: dict[str, dict] = {
        "boti":  {"threshold": 95, "label": "FATF Rec. 10",           "description": "Regulatory pass ≥ 95"},
        "iess":  {"threshold": 80, "label": "AML5D Art. 13",          "description": "Identity evidence pass ≥ 80"},
        "spec":  {"threshold": 85, "label": "FATF / Sanctions controls","description": "Sanctions/PEP evidence pass ≥ 85"},
        "cedj":  {"threshold": 80, "label": "CDD/EDD governance",     "description": "CDD/EDD rationale pass ≥ 80"},
        "soft":  {"threshold": 80, "label": "Source-of-funds controls","description": "SoF traceability pass ≥ 80"},
        "avs":   {"threshold": 75, "label": "Address verification std.","description": "Address verification pass ≥ 75"},
        "rre":   {"threshold": 80, "label": "Risk governance",         "description": "Risk explainability pass ≥ 80"},
        "cpi":   {"threshold": 100,"label": "OCC Safety & Soundness",  "description": "Regulatory pass = 100"},
        "ccts":  {"threshold": 75, "label": "IFRS 9 / CECL",          "description": "Covenant transparency pass ≥ 75"},
        "rifc":  {"threshold": 85, "label": "Benchmark reform standards","description": "Rate fallback correctness pass ≥ 85"},
        "eac":   {"threshold": 85, "label": "Execution authority policy","description": "Execution completeness pass ≥ 85"},
        "rsi":   {"threshold": 80, "label": "Loan servicing standards","description": "Repayment schedule integrity pass ≥ 80"},
        "bgic":  {"threshold": 85, "label": "Borrower ID controls",   "description": "Borrower/guarantor consistency pass ≥ 85"},
        "cvr":   {"threshold": 80, "label": "Collateral valuation policy","description": "Collateral valuation recency pass ≥ 80"},
        "hec":   {"threshold": 85, "label": "12 CFR §329.20",         "description": "HQLA eligibility pass ≥ 85"},
        "isrr":  {"threshold": 98, "label": "BCBS 239 Principle 3",   "description": "Reconciliation pass ≥ 98"},
        "ctta":  {"threshold": 85, "label": "Liquidity reporting timing","description": "Cut-off/timestamp alignment pass ≥ 85"},
        "ssc":   {"threshold": 80, "label": "Liquidity stress testing","description": "Stress scenario coverage pass ≥ 80"},
        "iocc":  {"threshold": 80, "label": "LCR/NSFR taxonomy",      "description": "Inflow/outflow classification pass ≥ 80"},
        "lbdq":  {"threshold": 80, "label": "Limit breach governance","description": "Limit breach disclosure pass ≥ 80"},
        "sscov": {"threshold": 85, "label": "Source system controls", "description": "Source system coverage pass ≥ 85"},
        "rmp":   {"threshold": 90, "label": "EBA RTS compliance",     "description": "Reg. mapping pass ≥ 90"},
        "dli":   {"threshold": 80, "label": "BCBS 239 Principle 3",   "description": "Data lineage pass ≥ 80"},
        "rcc":   {"threshold": 80, "label": "Change control std.",     "description": "Regulatory change coverage pass ≥ 80"},
        "dcs":   {"threshold": 85, "label": "Pillar 3 disclosures",   "description": "Disclosure completeness pass ≥ 85"},
        "gsc":   {"threshold": 90, "label": "Governance attestation",  "description": "Governance sign-off pass ≥ 90"},
        "cmc":   {"threshold": 80, "label": "Control mapping std.",    "description": "Control mapping pass ≥ 80"},
        "rcpc":  {"threshold": 80, "label": "Recordkeeping policy",   "description": "Recordkeeping & classification pass ≥ 80"},
        "qoe":   {"threshold": 75, "label": "AICPA QoE standards",    "description": "QoE transparency pass ≥ 75"},
        "fosi":  {"threshold": 65, "label": "Delaware fiduciary",     "description": "Fairness opinion pass ≥ 65"},
        "ats":   {"threshold": 80, "label": "Valuation governance",    "description": "Assumption transparency pass ≥ 80"},
        "sac":   {"threshold": 80, "label": "Sensitivity standards",  "description": "Sensitivity analysis coverage pass ≥ 80"},
        "csj":   {"threshold": 75, "label": "Comparable methodology", "description": "Comparable-set justification pass ≥ 75"},
        "cidc":  {"threshold": 85, "label": "Conflict disclosure rules","description": "Conflict/independence disclosure pass ≥ 85"},
        "drt":   {"threshold": 80, "label": "Diligence traceability", "description": "Data room traceability pass ≥ 80"},
        "snad":  {"threshold": 83, "label": "31 CFR §1020.320",       "description": "SAR completeness pass ≥ 83"},
        "wcw":   {"threshold": 60, "label": "Internal ethics std.",   "description": "Credibility weight pass ≥ 60"},
        "tcs":   {"threshold": 80, "label": "Investigation standards","description": "Timeline coherence pass ≥ 80"},
        "eccc":  {"threshold": 85, "label": "Evidence handling policy","description": "Chain-of-custody completeness pass ≥ 85"},
        "tdc":   {"threshold": 80, "label": "Case documentation standard","description": "Transaction detail completeness pass ≥ 80"},
        "detr":  {"threshold": 80, "label": "Escalation governance",  "description": "Disposition traceability pass ≥ 80"},
        "rnc":   {"threshold": 85, "label": "Regulatory notification rule","description": "Regulatory notification completeness pass ≥ 85"},
    }

    # Dependency block rules — metric thresholds that trigger a Legal Hold flag
    DEPENDENCY_BLOCK_RULES: dict[str, list[dict]] = {
        "Customer Onboarding (KYC/AML)": [
            {"metric_code": "boti", "threshold": 50,
             "message": "Beneficial Ownership incomplete — onboarding pack flagged Legally Invalid"},
        ],
        "Loan & Credit Documentation": [
            {"metric_code": "cpi", "threshold": 80,
             "message": "Collateral unperfected — loan documents flagged Legally Invalid"},
        ],
        "Treasury & Liquidity Reports": [
            {"metric_code": "isrr", "threshold": 85,
             "message": "System reconciliation failed — treasury report flagged for mandatory review"},
        ],
        "Regulatory & Compliance Filings": [
            {"metric_code": "rmp", "threshold": 60,
             "message": "Regulatory mapping insufficient — filing flagged for immediate remediation"},
            {"metric_code": "dcs", "threshold": 50,
             "message": "Material disclosures missing — filing flagged for mandatory remediation"},
            {"metric_code": "gsc", "threshold": 50,
             "message": "Governance sign-off missing — filing flagged as not approved for submission"},
        ],
        "Fraud & Investigation Records": [
            {"metric_code": "snad", "threshold": 50,
             "message": "SAR narrative incomplete — report cannot be filed to FinCEN/NCA"},
        ],
    }

    # Chunking configuration for large document processing
    LLM_CHUNK_SIZE: int = int(os.getenv("LLM_CHUNK_SIZE", "6000"))
    LLM_CHUNK_OVERLAP: int = int(os.getenv("LLM_CHUNK_OVERLAP", "500"))
    LLM_MAX_CHUNKS: int = int(os.getenv("LLM_MAX_CHUNKS", "5"))

    # Upload directory
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate critical configuration. Returns list of warnings."""
        warnings = []
        if not cls.FOUNDRY_API_KEY or cls.FOUNDRY_API_KEY == "your-api-key-here":
            warnings.append("FOUNDRY_API_KEY is not configured. LLM features will be unavailable.")
        if not cls.FOUNDRY_ENDPOINT or "your-foundry-endpoint" in cls.FOUNDRY_ENDPOINT:
            warnings.append("FOUNDRY_ENDPOINT is not configured. LLM features will be unavailable.")
        return warnings


settings = Settings()
