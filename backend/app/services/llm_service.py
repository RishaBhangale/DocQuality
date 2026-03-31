"""
Azure Foundry LLM Service.

Handles all interactions with the Azure Foundry (OpenAI-compatible) API
for structured document extraction, semantic classification, and
dynamic metric evaluation.
"""

import json
import logging
import re
import time
from typing import Optional

import requests

from app.config import (
    settings,
    MetricDefinition,
    SEMANTIC_TYPES,
    get_metrics_for_type,
)
from app.models.schemas import LLMExtractionResponse

logger = logging.getLogger(__name__)


# ─── Classification Prompt ───────────────────────────────────────────────────

CLASSIFICATION_PROMPT = """You are a document classification expert. Read the following document text and classify it into EXACTLY ONE of these semantic types:

{type_list}

INSTRUCTIONS:
- Read the document carefully and choose the BEST matching type.
- If the document doesn't closely match any specific type, use "general".
- Respond with ONLY valid JSON: {{"semantic_type": "<one of the types above>"}}

DOCUMENT TEXT (first 3000 chars):
---
{document_text}
---

RESPOND WITH ONLY VALID JSON:"""


# ─── Dynamic Extraction Prompt Builder ───────────────────────────────────────

def build_extraction_prompt(
    document_text: str,
    semantic_type: str,
    metrics: list[MetricDefinition],
) -> str:
    """Build a dynamic LLM prompt based on the detected semantic type and active metrics."""

    # Build the metrics section dynamically
    metric_lines = []
    for m in metrics:
        standards_info = ""
        if m.linked_standards:
            refs = [f"{ls.standard_id} {ls.clause}" for ls in m.linked_standards]
            standards_info = f" [References: {', '.join(refs)}]"
        metric_lines.append(f"- {m.id}: {m.description}{standards_info}")

    metrics_block = "\n".join(metric_lines)

    # Build the expected JSON keys for semantic_scores
    score_keys = ", ".join([f'"{m.id}": <0-100>' for m in metrics])
    reasoning_keys = ", ".join([f'"{m.id}": "<reasoning>"' for m in metrics])

    return f"""You are a Document Quality and Compliance Auditor. Analyze the following document text and return a structured JSON response.

The document has been classified as: **{semantic_type}**

INSTRUCTIONS:
1. Extract all structural elements, policies, or mechanisms related to quality and compliance.
2. Evaluate each quality metric below on a scale of 0-100 with strict reasoning. Be critical.
3. Provide an executive summary, risk summary, and actionable recommendations.

QUALITY METRICS TO EVALUATE:
{metrics_block}

DOCUMENT TEXT:
---
{document_text}
---

RESPOND WITH ONLY VALID JSON in this exact format (no markdown, no extra text):
{{
  "document_type": "<detected document type>",
  "semantic_type": "{semantic_type}",
  "fields": {{
    "<policy_or_mechanism_name>": "<extracted_value>",
    ...
  }},
  "semantic_scores": {{
    {score_keys}
  }},
  "metric_reasoning": {{
    {reasoning_keys}
  }},
  "executive_summary": "<2-3 sentence quality summary>",
  "risk_summary": "<identified risks and concerns>",
  "recommendations": [
    "<recommendation 1>",
    "<recommendation 2>"
  ]
}}"""


class AzureFoundryLLMService:
    """
    Service for interacting with Azure Foundry LLM.

    Sends structured extraction prompts, enforces JSON-only responses,
    validates against schema, and handles retries and timeouts.

    Supports two Azure endpoint types (auto-detected from URL):
    - Azure OpenAI Service: *.openai.azure.com
    - Azure AI Foundry serverless (MaaS): *.models.ai.azure.com / *.services.ai.azure.com
    """

    def __init__(self) -> None:
        """Initialize the LLM service with configuration."""
        self.api_key: str = settings.FOUNDRY_API_KEY
        self.endpoint: str = settings.FOUNDRY_ENDPOINT.rstrip("/")
        self.model: str = settings.FOUNDRY_MODEL
        self.api_version: str = settings.FOUNDRY_API_VERSION
        self.timeout: int = settings.LLM_TIMEOUT_SECONDS
        self.max_retries: int = settings.LLM_MAX_RETRIES
        self.temperature: float = settings.LLM_TEMPERATURE
        self._endpoint_type: str = self._detect_endpoint_type()

        logger.info(
            "LLM Service initialized: configured=%s, endpoint_type=%s, model=%s, endpoint=%s",
            self.is_configured, self._endpoint_type, self.model,
            self.endpoint[:40] + "..." if len(self.endpoint) > 40 else self.endpoint
        )

    def _detect_endpoint_type(self) -> str:
        """Auto-detect the Azure endpoint type from the URL."""
        ep = self.endpoint.lower()
        if ".openai.azure.com" in ep or ".cognitiveservices.azure.com" in ep:
            return "azure_openai"
        elif ".models.ai.azure.com" in ep or ".services.ai.azure.com" in ep:
            return "azure_foundry_serverless"
        elif "api.openai.com" in ep:
            return "openai_direct"
        else:
            return "azure_openai"

    @property
    def is_configured(self) -> bool:
        """Check if the LLM service is properly configured."""
        configured = bool(
            self.api_key
            and self.api_key != "your-api-key-here"
            and self.endpoint
            and "your-foundry-endpoint" not in self.endpoint
        )
        if not configured:
            logger.debug(
                "LLM not configured: api_key=%s, endpoint=%s",
                "SET" if self.api_key else "EMPTY",
                "SET" if self.endpoint else "EMPTY",
            )
        return configured

    def _build_url(self) -> str:
        """Build the API URL based on detected endpoint type."""
        if self._endpoint_type == "azure_openai":
            url = (
                f"{self.endpoint}/openai/deployments/{self.model}"
                f"/chat/completions?api-version={self.api_version}"
            )
        elif self._endpoint_type == "openai_direct":
            url = f"{self.endpoint}/v1/chat/completions"
        else:
            url = f"{self.endpoint}/chat/completions"

        logger.debug("Built LLM URL: %s", url)
        return url

    def _build_headers(self) -> dict[str, str]:
        """Build request headers based on detected endpoint type."""
        if self._endpoint_type == "azure_openai":
            return {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
        elif self._endpoint_type == "openai_direct":
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
        else:
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "api-key": self.api_key,
            }

    def _truncate_text(self, text: str, max_chars: int = 30000) -> str:
        """Smart truncation: preserve start and end of large documents."""
        if len(text) <= max_chars:
            return text
        logger.warning(
            "Document too large (%d chars). Truncating middle section to fit LLM window.",
            len(text),
        )
        return (
            text[:20000]
            + "\n\n...[CONTENT TRUNCATED BY SYSTEM TO FIT CONTEXT WINDOW]...\n\n"
            + text[-10000:]
        )

    # ─── Semantic Document Classification ────────────────────────────────

    def classify_semantic_type(self, document_text: str) -> str:
        """
        Classify a document into one of the predefined semantic types.

        Uses a short, cheap LLM call. Falls back to "general" on failure.
        """
        if not self.is_configured:
            logger.warning("LLM not configured. Defaulting semantic_type to 'general'.")
            return "general"

        type_list = "\n".join(f"- {t}" for t in SEMANTIC_TYPES)
        prompt = CLASSIFICATION_PROMPT.format(
            type_list=type_list,
            document_text=document_text[:3000],
        )

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": "You are a document classifier. Respond with valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": 100,
            "response_format": {"type": "json_object"},
        }

        url = self._build_url()
        headers = self._build_headers()

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code != 200:
                logger.warning("Classification LLM call failed (HTTP %d). Using 'general'.", response.status_code)
                return "general"

            data = response.json()
            raw = data["choices"][0]["message"]["content"]
            cleaned = self._clean_json(raw)
            result = json.loads(cleaned)
            semantic_type = result.get("semantic_type", "general")

            if semantic_type not in SEMANTIC_TYPES:
                logger.warning("LLM returned unknown type '%s'. Using 'general'.", semantic_type)
                return "general"

            logger.info("Document classified as: %s", semantic_type)
            return semantic_type

        except Exception as e:
            logger.warning("Classification failed: %s. Using 'general'.", str(e))
            return "general"

    # ─── Main Extraction & Evaluation ────────────────────────────────────

    def extract_and_evaluate(
        self,
        document_text: str,
        semantic_type: str = "general",
        metrics: Optional[list[MetricDefinition]] = None,
    ) -> tuple[LLMExtractionResponse, str]:
        """
        Send document text to the LLM for structured extraction.

        Now accepts semantic_type and active metrics to build a dynamic prompt.
        """
        if not self.is_configured:
            raise RuntimeError(
                "Azure Foundry LLM is not configured. "
                "Set FOUNDRY_API_KEY and FOUNDRY_ENDPOINT in the .env file."
            )

        if metrics is None:
            metrics = get_metrics_for_type(semantic_type)

        truncated_text = self._truncate_text(document_text)
        prompt = build_extraction_prompt(truncated_text, semantic_type, metrics)

        url = self._build_url()
        headers = self._build_headers()
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a document quality and compliance analysis assistant. "
                        "Always respond with valid JSON only. No markdown formatting."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": 4000,
            "response_format": {"type": "json_object"},
        }

        logger.info(
            "LLM extraction: type=%s, metrics=%d, endpoint_type=%s",
            semantic_type, len(metrics), self._endpoint_type,
        )

        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "LLM request attempt %d/%d for %d chars",
                    attempt, self.max_retries, len(document_text),
                )
                start_time = time.time()

                response = requests.post(
                    url, headers=headers, json=payload, timeout=self.timeout,
                )

                elapsed = time.time() - start_time
                logger.info("LLM response in %.2fs (status: %d)", elapsed, response.status_code)

                if response.status_code == 401:
                    error_msg = (
                        f"LLM API auth failed (HTTP 401). "
                        f"Check FOUNDRY_API_KEY. Endpoint type: {self._endpoint_type}."
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                if response.status_code == 404:
                    error_msg = (
                        f"LLM endpoint not found (HTTP 404). "
                        f"Check FOUNDRY_ENDPOINT and FOUNDRY_MODEL. URL: {url}"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

                if response.status_code != 200:
                    last_error = f"LLM API error (HTTP {response.status_code}): {response.text[:500]}"
                    logger.error(last_error)
                    continue

                response_data = response.json()
                raw_content = response_data["choices"][0]["message"]["content"]
                logger.debug("LLM raw response: %s", raw_content[:500])

                parsed = self._parse_response(raw_content)
                return parsed, raw_content

            except requests.Timeout:
                last_error = f"LLM timed out after {self.timeout}s (attempt {attempt})"
                logger.warning(last_error)
            except requests.RequestException as e:
                last_error = f"LLM request failed (attempt {attempt}): {str(e)}"
                logger.error(last_error)
            except ValueError as e:
                last_error = f"LLM parsing failed (attempt {attempt}): {str(e)}"
                logger.warning(last_error)

            if attempt < self.max_retries:
                time.sleep(1)

        raise RuntimeError(
            f"LLM extraction failed after {self.max_retries} attempts. Last error: {last_error}"
        )

    # ─── Response Parsing ────────────────────────────────────────────────

    def _clean_json(self, raw: str) -> str:
        """Strip markdown code block markers from LLM output."""
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _parse_response(self, raw_response: str) -> LLMExtractionResponse:
        """Parse and validate the LLM JSON response with regex fallback."""
        cleaned = self._clean_json(raw_response)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed. Attempting regex recovery: %s", str(e))
            match = re.search(r'\{.*\}', cleaned, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    raise ValueError(f"LLM response not recoverable: {str(e)}")
            else:
                raise ValueError(f"LLM response is not valid JSON: {str(e)}")

        # Migrate old "semantic_evaluation" format to new "semantic_scores" if needed
        if "semantic_evaluation" in data and "semantic_scores" not in data:
            data["semantic_scores"] = data.pop("semantic_evaluation")

        try:
            return LLMExtractionResponse(**data)
        except Exception as e:
            logger.error("LLM response schema validation failed: %s", str(e))
            raise ValueError(f"LLM response schema validation failed: {str(e)}")

    # ─── Fallback ────────────────────────────────────────────────────────

    def get_fallback_response(self, document_text: str, semantic_type: str = "general") -> LLMExtractionResponse:
        """Generate a minimal fallback response when the LLM is unavailable."""
        logger.warning("Using fallback LLM response (LLM unavailable)")
        return LLMExtractionResponse(
            document_type="unknown",
            semantic_type=semantic_type,
            fields={},
            executive_summary="LLM analysis was unavailable. Scores are based on deterministic checks only.",
            risk_summary="Unable to perform AI-assisted risk assessment.",
            recommendations=[
                "Configure Azure Foundry LLM credentials for full analysis.",
                "Review document manually for completeness.",
            ],
        )
