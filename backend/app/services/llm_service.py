"""
Azure Foundry LLM Service.

Handles all interactions with the Azure Foundry (OpenAI-compatible) API
for structured document extraction and semantic reasoning.
"""

import json
import logging
import time
from typing import Optional

import requests

from app.config import settings
from app.models.schemas import LLMExtractionResponse

logger = logging.getLogger(__name__)


# Structured extraction prompt template
EXTRACTION_PROMPT = """You are a document quality analysis AI. Analyze the following document text and return a structured JSON response.

INSTRUCTIONS:
1. Identify the document type (e.g., invoice, contract, report, form, letter, etc.)
2. Extract all structured fields you can find (dates, names, amounts, IDs, addresses, etc.)
3. Evaluate each quality metric on a scale of 0-100 with reasoning
4. Provide an executive summary, risk summary, and actionable recommendations

QUALITY METRICS TO EVALUATE:
- completeness: Are all expected/required fields present for this document type?
- accuracy: Are the extracted values correct, plausible, and well-formed?
- consistency: Are field values logically consistent with each other?
- validity: Do values conform to expected formats and standards?
- timeliness: Are dates and time-sensitive data current and reasonable?
- uniqueness: Are there duplicate entries or redundant data?

DOCUMENT TEXT:
---
{document_text}
---

RESPOND WITH ONLY VALID JSON in this exact format (no markdown, no extra text):
{{
  "document_type": "<detected document type>",
  "fields": {{
    "<field_name>": "<extracted_value>",
    ...
  }},
  "semantic_evaluation": {{
    "completeness": <0-100>,
    "accuracy": <0-100>,
    "consistency": <0-100>,
    "validity": <0-100>,
    "timeliness": <0-100>,
    "uniqueness": <0-100>
  }},
  "metric_reasoning": {{
    "completeness": "<reasoning>",
    "accuracy": "<reasoning>",
    "consistency": "<reasoning>",
    "validity": "<reasoning>",
    "timeliness": "<reasoning>",
    "uniqueness": "<reasoning>"
  }},
  "executive_summary": "<2-3 sentence quality summary>",
  "risk_summary": "<identified risks and concerns>",
  "recommendations": [
    "<recommendation 1>",
    "<recommendation 2>",
    ...
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
            # Default to Azure OpenAI pattern (most common for Azure deployments)
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
            # Azure OpenAI Service: {endpoint}/openai/deployments/{model}/chat/completions?api-version={version}
            url = (
                f"{self.endpoint}/openai/deployments/{self.model}"
                f"/chat/completions?api-version={self.api_version}"
            )
        elif self._endpoint_type == "openai_direct":
            # Direct OpenAI API
            url = f"{self.endpoint}/v1/chat/completions"
        else:
            # Azure AI Foundry serverless (MaaS): {endpoint}/chat/completions
            url = f"{self.endpoint}/chat/completions"

        logger.debug("Built LLM URL: %s", url)
        return url

    def _build_headers(self) -> dict[str, str]:
        """Build request headers based on detected endpoint type."""
        if self._endpoint_type == "azure_openai":
            # Azure OpenAI Service uses api-key header
            return {
                "Content-Type": "application/json",
                "api-key": self.api_key,
            }
        elif self._endpoint_type == "openai_direct":
            # Direct OpenAI uses Bearer token
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
        else:
            # Azure AI Foundry serverless uses either api-key OR Bearer token
            # Try api-key first (works for most Azure Foundry deployments)
            return {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "api-key": self.api_key,
            }

    def _build_payload(self, document_text: str) -> dict:
        """
        Build the request payload for the LLM.

        Args:
            document_text: Extracted document text content.

        Returns:
            Request payload dictionary.
        """
        prompt = EXTRACTION_PROMPT.format(document_text=document_text[:8000])
        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a document quality analysis assistant. "
                        "Always respond with valid JSON only. No markdown formatting."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": 4000,
            "response_format": {"type": "json_object"},
        }
        return payload

    def _parse_response(self, raw_response: str) -> LLMExtractionResponse:
        """
        Parse and validate the LLM JSON response.

        Args:
            raw_response: Raw text response from the LLM.

        Returns:
            Validated LLMExtractionResponse object.

        Raises:
            ValueError: If the response is not valid JSON or fails schema validation.
        """
        # Strip potential markdown code block markers
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("LLM returned invalid JSON: %s", str(e))
            raise ValueError(f"LLM response is not valid JSON: {str(e)}")

        try:
            return LLMExtractionResponse(**data)
        except Exception as e:
            logger.error("LLM response failed schema validation: %s", str(e))
            raise ValueError(f"LLM response failed schema validation: {str(e)}")

    def extract_and_evaluate(self, document_text: str) -> tuple[LLMExtractionResponse, str]:
        """
        Send document text to the LLM for structured extraction and evaluation.

        Implements retry logic for malformed responses and timeout protection.

        Args:
            document_text: Normalized document text.

        Returns:
            Tuple of (validated LLMExtractionResponse, raw response string).

        Raises:
            RuntimeError: If all retries are exhausted or the LLM is unavailable.
        """
        if not self.is_configured:
            raise RuntimeError(
                "Azure Foundry LLM is not configured. "
                "Set FOUNDRY_API_KEY and FOUNDRY_ENDPOINT in the .env file."
            )

        url = self._build_url()
        headers = self._build_headers()
        payload = self._build_payload(document_text)

        logger.info(
            "LLM request config: endpoint_type=%s, url=%s, model=%s",
            self._endpoint_type, url, self.model
        )

        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    "LLM request attempt %d/%d for %d chars of text",
                    attempt, self.max_retries, len(document_text)
                )
                start_time = time.time()

                response = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )

                elapsed = time.time() - start_time
                logger.info("LLM response received in %.2fs (status: %d)", elapsed, response.status_code)

                if response.status_code == 401:
                    error_msg = (
                        f"LLM API authentication failed (HTTP 401). "
                        f"Check FOUNDRY_API_KEY in .env. "
                        f"Endpoint type: {self._endpoint_type}. Response: {response.text[:300]}"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)  # Don't retry auth failures

                if response.status_code == 404:
                    error_msg = (
                        f"LLM API endpoint not found (HTTP 404). "
                        f"Check FOUNDRY_ENDPOINT and FOUNDRY_MODEL in .env. "
                        f"URL attempted: {url}. Response: {response.text[:300]}"
                    )
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)  # Don't retry 404s

                if response.status_code != 200:
                    error_msg = f"LLM API error (HTTP {response.status_code}): {response.text[:500]}"
                    logger.error(error_msg)
                    last_error = error_msg
                    continue

                response_data = response.json()
                raw_content = response_data["choices"][0]["message"]["content"]

                logger.debug("LLM raw response: %s", raw_content[:500])

                parsed = self._parse_response(raw_content)
                return parsed, raw_content

            except requests.Timeout:
                last_error = f"LLM request timed out after {self.timeout}s (attempt {attempt})"
                logger.warning(last_error)

            except requests.RequestException as e:
                last_error = f"LLM request failed (attempt {attempt}): {str(e)}"
                logger.error(last_error)

            except ValueError as e:
                last_error = f"LLM response parsing failed (attempt {attempt}): {str(e)}"
                logger.warning(last_error)

            # Brief delay before retry
            if attempt < self.max_retries:
                time.sleep(1)

        raise RuntimeError(
            f"LLM extraction failed after {self.max_retries} attempts. Last error: {last_error}"
        )

    def get_fallback_response(self, document_text: str) -> LLMExtractionResponse:
        """
        Generate a minimal fallback response when the LLM is unavailable.

        This allows the system to still function with deterministic-only evaluation.

        Args:
            document_text: Extracted document text.

        Returns:
            Minimal LLMExtractionResponse with empty semantic scores.
        """
        logger.warning("Using fallback LLM response (LLM unavailable)")
        return LLMExtractionResponse(
            document_type="unknown",
            fields={},
            executive_summary="LLM analysis was unavailable. Scores are based on deterministic checks only.",
            risk_summary="Unable to perform AI-assisted risk assessment.",
            recommendations=[
                "Configure Azure Foundry LLM credentials for full analysis.",
                "Review document manually for completeness.",
            ],
        )
