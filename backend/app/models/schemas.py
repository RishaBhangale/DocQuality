"""
Pydantic schemas for request/response validation.

Defines strict validation schemas for all API interactions
and internal data structures. Supports dynamic metrics and
ISO standard references.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --- Issue Schema ---

class IssueSchema(BaseModel):
    """Schema for a single detected issue."""

    field_name: str = Field(..., description="Name of the field with the issue")
    issue_type: str = Field(..., description="Category of the issue")
    description: str = Field(..., description="Human-readable description of the issue")
    severity: str = Field(..., description="Severity level: critical, warning, or good")
    metric_name: Optional[str] = Field(None, description="The metric name this issue relates to")

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        allowed = {"critical", "warning", "good"}
        if v.lower() not in allowed:
            raise ValueError(f"Severity must be one of {allowed}")
        return v.lower()


# --- Linked Standard Reference (for API responses) ---

class LinkedStandardResponse(BaseModel):
    """ISO standard reference returned in API responses."""
    standard_id: str
    control_id: str
    clause: str
    description: str


# --- Metric Result Schema ---

class MetricResult(BaseModel):
    """Schema for a single quality metric evaluation result."""

    id: str = Field("", description="Metric definition ID")
    name: str = Field(..., description="Metric name")
    category: str = Field("core", description="core or type_specific")
    score: float = Field(..., ge=0, le=100, description="Metric score (0–100)")
    description: str = Field(..., description="What this metric measures")
    status_message: str = Field(..., description="Human-readable status message")
    status: str = Field(..., description="Status: good, warning, or critical")
    weight: float = Field(0.0, description="Weight applied in overall scoring")
    reasoning: str = Field("", description="LLM reasoning for this metric")
    linked_standards: list[LinkedStandardResponse] = Field(
        default_factory=list,
        description="ISO standards linked to this metric"
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"good", "warning", "critical"}
        if v.lower() not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v.lower()


# --- LLM Extraction Response Schema ---

class LLMExtractionResponse(BaseModel):
    """Schema for the structured JSON response from the LLM."""

    document_type: str = Field("", description="Detected document type")
    semantic_type: str = Field("general", description="Classified semantic type")
    fields: dict = Field(default_factory=dict, description="Extracted structured fields")
    semantic_scores: dict[str, float] = Field(
        default_factory=dict,
        description="LLM-suggested metric scores (dynamic keys)"
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
    semantic_type: str = "general"
    overall_score: float
    overall_status: str
    core_metrics: list[MetricResult] = Field(default_factory=list)
    type_specific_metrics: list[MetricResult] = Field(default_factory=list)
    primary_type_metrics: list[MetricResult] = Field(default_factory=list)
    metrics: list[MetricResult]  # all metrics combined (backward compat)
    issues: list[IssueSchema]
    executive_summary: str
    risk_summary: str
    recommendations: list[str]
    # Phase 2 pipeline fields
    pipeline_status: dict = Field(
        default_factory=lambda: {
            "ingest": "success", "extract": "success",
            "normalize": "success", "evaluate": "success",
        },
        description="Pipeline stage statuses",
    )
    corrections_count: int = Field(0, description="Number of correction proposals generated")
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
