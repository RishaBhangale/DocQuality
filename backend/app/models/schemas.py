"""
Pydantic schemas for request/response validation.

Defines strict validation schemas for all API interactions
and internal data structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


# --- Issue Schema ---

class IssueSchema(BaseModel):
    """Schema for a single detected issue."""

    field_name: str = Field(..., description="Name of the field with the issue")
    issue_type: str = Field(..., description="Category of the issue")
    description: str = Field(..., description="Human-readable description of the issue")
    severity: str = Field(..., description="Severity level: critical, warning, or good")
    regulation_reference: Optional[str] = Field(
        default=None,
        description="Specific regulation article violated (e.g., 'FATF Rec. 10', 'CRR3 Art. 124')",
    )
    metric_dimension: Optional[str] = Field(
        default=None,
        description="Which quality dimension this issue belongs to (generic or banking metric name)",
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"critical", "warning", "good"}
        if v.lower() not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v.lower()


# --- Metric Result Schema ---

class MetricResult(BaseModel):
    """Schema for a single quality metric evaluation result."""

    name: str = Field(..., description="Metric name")
    score: float = Field(..., ge=0, le=100, description="Metric score (0–100)")
    description: str = Field(..., description="What this metric measures")
    status_message: str = Field(..., description="Human-readable status message")
    status: str = Field(..., description="Status: good, warning, or critical")
    weight: float = Field(0.0, description="Weight applied in overall scoring")
    reasoning: str = Field("", description="LLM reasoning for this metric")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"good", "warning", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v.lower()


# --- LLM Extraction Response Schema ---

class SemanticEvaluation(BaseModel):
    """Semantic metric scores suggested by the LLM."""

    completeness: float = Field(0, ge=0, le=100)
    accuracy: float = Field(0, ge=0, le=100)
    consistency: float = Field(0, ge=0, le=100)
    validity: float = Field(0, ge=0, le=100)
    timeliness: float = Field(0, ge=0, le=100)
    uniqueness: float = Field(0, ge=0, le=100)


class LLMExtractionResponse(BaseModel):
    """Schema for the structured JSON response from the LLM."""

    document_type: str = Field("", description="Detected document type")
    fields: dict = Field(default_factory=dict, description="Extracted structured fields")
    semantic_evaluation: SemanticEvaluation = Field(
        default_factory=SemanticEvaluation,
        description="LLM-suggested metric scores"
    )
    metric_reasoning: dict[str, str] = Field(
        default_factory=dict,
        description="LLM reasoning per metric"
    )
    executive_summary: str = Field("", description="Executive summary of document quality")
    risk_summary: str = Field("", description="Risk assessment summary")
    recommendations: list[str] = Field(
        default_factory=list,
        description="Improvement recommendations"
    )
    # Optional banking domain evaluation — populated when the LLM detects a banking document
    domain_evaluation: Optional[dict] = Field(
        default=None,
        description=(
            "Banking-domain metric scores (0-100) and reasoning keyed by short metric code "
            "(e.g., 'boti', 'cpi', 'hec'). Provided only for banking documents."
        ),
    )


# --- Strict LLM Quality Evaluation (Deterministic-first pipeline) ---

class IntegrityMetricDetail(BaseModel):
    """Per-metric refined score + reasoning (strict LLM output)."""

    score: float = Field(..., ge=0, le=100)
    reasoning: str = Field("", description="Evidence-based reasoning tied to document + deterministic output")
    deterministic_score: Optional[float] = Field(
        default=None, ge=0, le=100, description="Deterministic baseline score for this metric"
    )


class DocumentIntegrityScoreSection(BaseModel):
    """Strict 'Document Integrity Score' section returned by the LLM."""

    overall_score: float = Field(..., ge=0, le=100)
    metrics: dict[str, IntegrityMetricDetail] = Field(default_factory=dict)


class LLMStrictQualityResponse(BaseModel):
    """Strict-format LLM output used to validate/challenge/refine deterministic scoring."""

    document_integrity_score: DocumentIntegrityScoreSection
    document_type: str = Field("", description="Detected document type")
    banking_domain: Optional[str] = Field(
        default=None,
        description="Detected banking domain (optional; one of the configured domain names)",
    )
    executive_summary: str = Field("", description="Concise quality summary")
    risk_assessment: str = Field("", description="Concise risk assessment")
    recommendations: list[str] = Field(default_factory=list)
    issues_observations: list[IssueSchema] = Field(default_factory=list)
    important_constraints: list[str] = Field(
        default_factory=list,
        description="Explicit constraints/guardrails the evaluator relied on",
    )


class LLMConsolidationResponse(BaseModel):
    """Final consolidation output for recommendations + issues (single-tab UI)."""

    recommendations: list[str] = Field(default_factory=list)
    issues_observations: list[IssueSchema] = Field(default_factory=list)


# --- Banking Domain Schemas ---

class BankingMetric(BaseModel):
    """A single banking-domain-specific quality metric."""

    name: str = Field(..., description="Metric name (e.g., 'Collateral Perfection Index (CPI)')")
    metric_code: str = Field("", description="Short code for the metric (e.g., 'cpi')")
    score: int = Field(..., ge=0, le=100, description="Blended metric score (0–100)")
    description: str = Field(..., description="What this metric measures")
    calculation_logic: str = Field(..., description="Formula and logic used for calculation")
    risk_impact: str = Field(..., description="Why a low score is dangerous for the bank")
    reasoning: str = Field("", description="Deterministic reasoning trace for this score")
    # Regulatory threshold intelligence
    regulatory_pass_threshold: Optional[int] = Field(
        default=None,
        description="Score needed to pass regulatory standard (e.g., 95 for BOTI)",
    )
    regulatory_reference: str = Field(
        "", description="Regulation this threshold derives from (e.g., 'FATF Rec. 10')"
    )
    passes_regulatory_threshold: bool = Field(
        True, description="Whether the score meets the regulatory pass threshold"
    )
    # Confidence — how aligned are deterministic and LLM scores
    confidence: float = Field(
        1.0, ge=0.0, le=1.0,
        description="AI confidence score (0–1). Low = high disagreement between rule engine and LLM.",
    )
    deterministic_score: int = Field(0, description="Raw deterministic (rule-engine) score before blending")
    llm_score: Optional[int] = Field(None, description="LLM semantic score before blending")


# --- Job / Async Processing Schemas ---

class JobResponse(BaseModel):
    """Returned immediately after submitting a document for evaluation."""

    job_id: str
    filename: str
    status: str = "queued"
    message: str = "Document queued for evaluation"


class JobStatus(BaseModel):
    """Polling response for a background evaluation job."""

    job_id: str
    filename: str
    status: str  # queued | processing | completed | failed
    progress_message: str = ""
    evaluation_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime


# --- Evaluation List Schemas ---

class EvaluationListItem(BaseModel):
    """Compact row for the evaluation history list."""

    evaluation_id: str
    filename: str
    document_type: Optional[str] = None
    overall_score: Optional[float] = None
    overall_status: Optional[str] = None
    banking_domain: Optional[str] = None
    banking_overall_score: Optional[float] = None
    legal_hold: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


# --- API Response Schemas ---

class EvaluationResponse(BaseModel):
    """Full evaluation response returned to the client."""

    evaluation_id: str
    filename: str
    document_type: str
    overall_score: float
    overall_status: str
    metrics: list[MetricResult]
    issues: list[IssueSchema]
    executive_summary: str
    risk_summary: str
    recommendations: list[str]
    created_at: datetime
    # Banking domain intelligence — populated only when a banking document is detected
    banking_domain: Optional[str] = Field(
        default=None,
        description="Detected banking domain (e.g., 'Customer Onboarding (KYC/AML)')",
    )
    banking_metrics: List[BankingMetric] = Field(
        default_factory=list,
        description="Domain-specific banking quality metrics",
    )
    banking_overall_score: Optional[float] = Field(
        default=None,
        description="S_Bank composite score (0–100) — weighted sum of banking dimension scores",
    )
    # Legal hold — triggered when critical banking metrics fail dependency block rules
    legal_hold: bool = Field(
        default=False,
        description="True when a critical regulatory threshold failure invalidates the document",
    )
    legal_hold_reason: str = Field(
        default="",
        description="Explanation of why the legal hold was triggered",
    )
    # Remediation plan from the remediation agent
    remediation_plan: List[dict] = Field(
        default_factory=list,
        description="Specific, actionable remediation steps from the AI remediation agent",
    )

    class Config:
        from_attributes = True


class EvaluationSummary(BaseModel):
    """Lightweight evaluation summary for listing."""

    evaluation_id: str
    filename: str
    overall_score: float
    overall_status: str
    created_at: datetime


class UploadResponse(BaseModel):
    """Response returned after starting an evaluation."""

    evaluation_id: str
    filename: str
    status: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    llm_configured: bool
    llm_endpoint_type: str = "unknown"
    llm_model: str = "not_set"
    llm_endpoint_set: bool = False
    llm_key_set: bool = False


