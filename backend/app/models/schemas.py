"""
Pydantic schemas for request/response validation.

Defines strict validation schemas for all API interactions
and internal data structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --- Issue Schema ---

class IssueSchema(BaseModel):
    """Schema for a single detected issue."""

    field_name: str = Field(..., description="Name of the field with the issue")
    issue_type: str = Field(..., description="Category of the issue (e.g., Missing Field, Invalid Format)")
    description: str = Field(..., description="Human-readable description of the issue")
    severity: str = Field(..., description="Severity level: critical, warning, or good")

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


class TypeSpecificMetricResult(BaseModel):
    """Schema for a document-type-specific metric result."""

    name: str = Field(..., description="Metric name")
    score: float = Field(..., ge=0, le=100, description="Metric score (0–100)")
    description: str = Field(..., description="What this metric measures")
    status: str = Field(..., description="Status: good, warning, or critical")
    details: str = Field("", description="Specific findings and details")
    document_type: str = Field(..., description="Document type this metric belongs to")

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


# --- API Response Schemas ---

class EvaluationResponse(BaseModel):
    """Full evaluation response returned to the client."""

    evaluation_id: str
    filename: str
    document_type: str
    overall_score: float
    overall_status: str
    metrics: list[MetricResult]
    type_specific_metrics: list[TypeSpecificMetricResult] = []
    type_specific_score: Optional[float] = None
    issues: list[IssueSchema]
    executive_summary: str
    risk_summary: str
    recommendations: list[str]
    created_at: datetime

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
