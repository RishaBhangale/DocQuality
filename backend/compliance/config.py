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
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/compliance/document_quality.db")

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

    # Upload directory
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "compliance", "uploads")

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
