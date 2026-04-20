"""
Domain Validator for Knowledge Base uploads.

Uses a lightweight LLM classification call to verify that an uploaded
reference document belongs to the correct workspace domain.
Falls back to keyword-based validation when LLM is unavailable.
"""

import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of domain validation."""
    is_valid: bool
    reason: str
    confidence: float


# ── Domain keyword sets for fallback validation ──────────────────────────────

COMPLIANCE_KEYWORDS = {
    "ai governance", "artificial intelligence", "machine learning", "iso 42001",
    "iso 27001", "iso 27701", "nist ai rmf", "eu ai act", "gdpr", "data protection",
    "privacy", "compliance", "risk assessment", "isms", "information security",
    "data subject", "fairness", "transparency", "accountability", "bias",
    "model governance", "audit", "regulatory", "ethical ai", "responsible ai",
    "explainability", "human oversight", "ropa", "dsar", "annex a",
    "ccpa", "hipaa", "soc 2", "pci dss", "cobit", "nist",
}

BANKING_KEYWORDS = {
    "banking", "financial", "bank", "kyc", "aml", "anti-money laundering",
    "know your customer", "loan", "credit", "treasury", "liquidity",
    "basel", "pillar", "regulatory filing", "capital adequacy",
    "investment banking", "m&a", "merger", "acquisition", "fraud",
    "sar", "suspicious activity", "collateral", "covenant",
    "nsfr", "lcr", "hqla", "rwa", "risk-weighted",
    "interest rate", "deposit", "mortgage", "securitization",
    "fatf", "pep", "sanctions", "due diligence", "cdd", "edd",
    "bcbs", "disclosure", "prudential", "solvency",
}


def _keyword_validate(text: str, workspace: str) -> ValidationResult:
    """
    Fallback keyword-based domain validation.

    Counts domain-relevant keywords and checks if the document
    has sufficient domain relevance.
    """
    text_lower = text.lower()

    if workspace == "compliance":
        target_keywords = COMPLIANCE_KEYWORDS
        other_keywords = BANKING_KEYWORDS
        domain_name = "AI Governance & Compliance"
    else:
        target_keywords = BANKING_KEYWORDS
        other_keywords = COMPLIANCE_KEYWORDS
        domain_name = "Banking & Financial Services"

    target_hits = sum(1 for kw in target_keywords if kw in text_lower)
    other_hits = sum(1 for kw in other_keywords if kw in text_lower)

    # Minimum threshold: at least 3 domain keywords
    if target_hits < 3:
        return ValidationResult(
            is_valid=False,
            reason=f"Document does not appear to be related to {domain_name}. "
                   f"Only {target_hits} domain-relevant keyword(s) found (minimum: 3).",
            confidence=0.3,
        )

    # If the "other" domain has significantly more hits, reject
    if other_hits > target_hits * 1.5 and other_hits > 5:
        return ValidationResult(
            is_valid=False,
            reason=f"Document appears more relevant to a different domain. "
                   f"Found {other_hits} keywords from another domain vs {target_hits} for {domain_name}.",
            confidence=0.5,
        )

    confidence = min(1.0, target_hits / 10.0)
    return ValidationResult(
        is_valid=True,
        reason=f"Document validated for {domain_name} ({target_hits} relevant keywords found).",
        confidence=round(confidence, 2),
    )


# ── LLM-based validation ────────────────────────────────────────────────────

DOMAIN_VALIDATION_PROMPT = """You are a document domain classifier. Determine whether the following document belongs to the specified domain.

TARGET DOMAIN: {domain_description}

ACCEPTED TOPICS for this domain:
{accepted_topics}

REJECTED TOPICS (these belong to a DIFFERENT domain):
{rejected_topics}

DOCUMENT TEXT (first 3000 chars):
---
{document_text}
---

INSTRUCTIONS:
- Analyze the document's content, terminology, and purpose.
- Determine if it genuinely belongs to the target domain.
- Be strict: generic business documents that don't specifically relate to the domain should be REJECTED.
- A document can reference multiple domains but must PRIMARILY be about the target domain.

Respond with ONLY valid JSON:
{{
    "is_valid": true/false,
    "reason": "<1-2 sentence explanation>",
    "confidence": <0.0-1.0>
}}"""


def validate_domain(
    document_text: str,
    workspace: str,
    *,
    api_key: Optional[str] = None,
    endpoint: Optional[str] = None,
    model: Optional[str] = None,
    api_version: Optional[str] = None,
) -> ValidationResult:
    """
    Validate that a document belongs to the specified workspace domain.

    Tries LLM classification first, falls back to keyword matching.
    """
    # Try LLM validation if credentials are available
    if api_key and endpoint and model:
        try:
            result = _llm_validate(
                document_text, workspace,
                api_key=api_key,
                endpoint=endpoint,
                model=model,
                api_version=api_version or "2024-12-01-preview",
            )
            if result is not None:
                return result
        except Exception as e:
            logger.warning("LLM domain validation failed, using keyword fallback: %s", e)

    # Fallback to keyword validation
    return _keyword_validate(document_text, workspace)


def _llm_validate(
    document_text: str,
    workspace: str,
    *,
    api_key: str,
    endpoint: str,
    model: str,
    api_version: str,
) -> Optional[ValidationResult]:
    """LLM-based domain validation using existing Azure endpoint."""

    if workspace == "compliance":
        domain_desc = "AI Governance & Compliance Quality"
        accepted = (
            "AI governance, ISO 42001, ISO 27001, ISO 27701, NIST AI RMF, EU AI Act, "
            "GDPR, data protection, privacy policies, ISMS documentation, risk assessment "
            "frameworks, model governance, ethical AI, responsible AI, bias/fairness analysis, "
            "compliance audits, security policies, transparency reports"
        )
        rejected = (
            "Banking operations, financial services, KYC/AML, loan documentation, "
            "treasury reports, Basel regulations, investment banking, fraud investigations, "
            "credit risk, liquidity management"
        )
    else:
        domain_desc = "Banking & Financial Services Quality"
        accepted = (
            "Banking operations, KYC/AML procedures, loan/credit documentation, "
            "treasury & liquidity reports, regulatory & compliance filings (banking-specific), "
            "investment banking & M&A, fraud & investigation records, Basel III/IV, "
            "capital adequacy, risk-weighted assets, FATF recommendations"
        )
        rejected = (
            "AI governance, ISO 42001, machine learning policies, AI ethics, "
            "model transparency, NIST AI RMF, EU AI Act, data subject rights, "
            "ISMS documentation (unless banking-specific)"
        )

    prompt = DOMAIN_VALIDATION_PROMPT.format(
        domain_description=domain_desc,
        accepted_topics=accepted,
        rejected_topics=rejected,
        document_text=document_text[:3000],
    )

    # Build URL (same pattern as existing LLM services)
    ep = endpoint.rstrip("/")
    if ".openai.azure.com" in ep.lower() or ".cognitiveservices.azure.com" in ep.lower():
        url = f"{ep}/openai/deployments/{model}/chat/completions?api-version={api_version}"
        headers = {"Content-Type": "application/json", "api-key": api_key}
    else:
        url = f"{ep}/chat/completions"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    payload = {
        "messages": [
            {"role": "system", "content": "You are a document domain classifier. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "max_completion_tokens": 200,
        "response_format": {"type": "json_object"},
    }

    response = requests.post(url, headers=headers, json=payload, timeout=15)
    if response.status_code != 200:
        logger.warning("Domain validation LLM call failed (HTTP %d)", response.status_code)
        return None

    data = response.json()
    raw = data["choices"][0]["message"]["content"]

    # Clean markdown if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    result = json.loads(cleaned)

    return ValidationResult(
        is_valid=bool(result.get("is_valid", False)),
        reason=str(result.get("reason", "No reason provided")),
        confidence=float(result.get("confidence", 0.5)),
    )
