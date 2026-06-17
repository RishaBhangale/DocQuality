"""
Unified LLM Service.

Provides a single interface for LLM-based document analysis across all workspaces.
Supports both the "Single-Shot Extraction" pattern (Compliance) and the 
"Multi-Agent Job Pipeline" pattern (Banking).
"""

import json
import logging
import re
import time
from typing import Any, List, Optional, Tuple, Dict

import requests

from core.config import settings

logger = logging.getLogger(__name__)


# ─── Prompts (Unified) ───────────────────────────────────────────────────────

# 1. Compliance Semantic Classification
CLASSIFICATION_PROMPT = """Analyze the following document and classify it into exactly ONE of these semantic types:
{type_list}

Document excerpt:
---
{document_text}
---

Return ONLY a JSON object:
{{
  "semantic_type": "<type>"
}}"""

# 2. Banking Domain Detection
GET_BANKING_DOMAIN_PROMPT = """Analyze the FULL DOCUMENT below. Conceptually evaluate its purpose, meaning, and function to determine which of the following banking categories it belongs to.
Classify it even if explicit acronyms (like KYC, LCR, M&A) are missing, based purely on what the document is doing (e.g. tracking short term assets = Treasury).

ALLOWED DOMAINS (CHOOSE EXACTLY ONE, OR null):
1. "Customer Onboarding (KYC/AML)"
2. "Loan & Credit Documentation"
3. "Treasury & Liquidity Reports"
4. "Regulatory & Compliance Filings"
5. "Investment Banking & M&A"
6. "Fraud & Investigation Records"

If the document definitively does not fit any of the 6 categories, output null. NEVER invent a new category.

FILENAME: {filename}

FULL DOCUMENT:
---
{document_text}
---

Return valid JSON:
{{
    "banking_domain": "<matched category string exactly as above, or null>"
}}"""

# 3. Extraction Prompt (Compliance Style)
def build_extraction_prompt(document_text: str, semantic_type: str, metrics: list, reference_context: list[str] | None = None) -> str:
    metric_lines = []
    for m in metrics:
        standards_info = ""
        if hasattr(m, 'linked_standards') and m.linked_standards:
            refs = [f"{ls.standard_id} {ls.clause}" for ls in m.linked_standards]
            standards_info = f" [References: {', '.join(refs)}]"
        metric_lines.append(f"- {m.id}: {m.description}{standards_info}")

    metrics_block = "\n".join(metric_lines)
    score_keys = ", ".join([f'"{m.id}": <0-100>' for m in metrics])
    reasoning_keys = ", ".join([f'"{m.id}": "<reasoning>"' for m in metrics])

    kb_section = ""
    if reference_context:
        kb_text = "\n\n".join(reference_context[:5])
        kb_section = f"""\n\nREFERENCE STANDARDS (Organization's Knowledge Base):
The following excerpts are from the organization's approved reference documents.
Use these as ground truth when evaluating quality and compliance alignment.
Compare the document being evaluated against these standards and penalize deviations.
---
{kb_text}
---"""

    return f"""You are a Document Quality and Compliance Auditor specializing in financial and banking documents. Analyze the following document text and return a structured JSON response.

The document has been classified as: **{semantic_type}**

INSTRUCTIONS:
1. Extract all structural elements, fields, policies, or mechanisms related to quality and compliance.
2. Evaluate each quality metric below on a scale of 0-100 with strict reasoning. Be critical.
3. Provide an executive summary, risk summary, and actionable recommendations.{f"{chr(10)}4. Use the REFERENCE STANDARDS section below as ground truth for evaluation." if reference_context else ""}

SCORING DO / DON'T (applies to ALL metrics):
- DO base scores only on evidence present in the text and extracted fields.
- DO treat missing required information as a score reduction.
- DO penalize contradictions or draft indicators.
- DO use the full 0-100 range. Avoid clustering all metrics in 70-90.
- DON'T give a high score with vague reasoning — reasoning must reference specific evidence.

QUALITY METRICS TO EVALUATE:
{metrics_block}
{kb_section}
DOCUMENT TEXT:
---
{document_text}
---

RESPOND WITH ONLY VALID JSON in this exact format (no markdown, no extra text):
{{
  "document_type": "<detected document type (e.g. Basel III Disclosure, Contract, etc.)>",
  "semantic_type": "{semantic_type}",
  "fields": {{
    "<field_name>": "<extracted_value>",
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

# 4. Strict Quality Validation (Banking Style)
STRICT_QUALITY_PROMPT = """You are a strict document quality evaluation engine.

You will be given:
1) FULL DOCUMENT TEXT (may be a chunk of the full document)
2) A DETERMINISTIC EVALUATION OUTPUT (scores + issues + extracted fields)

STRICT EVALUATION GUIDELINES (MANDATORY):
- This is document QUALITY evaluation only (not interpretation, not creativity).
- Do NOT make assumptions. Only use evidence from the text and deterministic output.
- Validate the deterministic scores and issues. You MAY refine scores, but keep changes justified.

OUTPUT FORMAT (STRICT):
- Respond with ONLY valid JSON.
- ONLY these top-level keys are allowed:
    - document_integrity_score
    - document_type
    - banking_domain
    - executive_summary
    - risk_assessment
    - recommendations
    - issues_observations
    - important_constraints

DOCUMENT INTEGRITY SCORE SECTION:
- document_integrity_score must contain:
    - overall_score (0-100)
    - metrics: object with exact keys for each metric evaluated.
    - each metric value must be an object with: score (0-100), deterministic_score (0-100), reasoning (string)

DETERMINISTIC OUTPUT (JSON):
---
{deterministic_output_json}
---
{reference_context}
DOCUMENT TEXT:
---
{document_text}
---
"""

# 5. Consolidation (Banking Style)
CONSOLIDATE_RECS_ISSUES_PROMPT = """You are a strict consolidation engine.

You will be given deterministic and LLM outputs (recommendations + issues).

TASK:
- Merge deterministic + LLM recommendations into ONE final list.
- Merge deterministic + LLM issues into ONE final list.
- Remove redundancy and merge overlapping items.
- Prioritize high-impact items.

STRICT RULES:
- Do NOT add new recommendations/issues.
- Do NOT change meaning.
- Output must be valid JSON and ONLY the keys:
    - recommendations
    - issues_observations

INPUTS:
DETERMINISTIC OUTPUT (JSON):
---
{deterministic_output_json}
---

LLM OUTPUT (JSON):
---
{llm_output_json}
---

RESPOND WITH ONLY VALID JSON:
{{
    "recommendations": ["..."],
    "issues_observations": [
        {{
            "field_name": "...",
            "issue_type": "...",
            "description": "...",
            "severity": "critical|warning|good",
            "metric_dimension": "..." 
        }}
    ]
}}"""

# 6. Domain Specialist Prompts (Banking)
DOMAIN_SPECIALIST_PROMPTS: dict[str, str] = {
    "Customer Onboarding (KYC/AML)": """You are a KYC/AML compliance specialist. Evaluate this document against FATF Recommendations.
Deterministic baselines: {deterministic_baselines}
Text: {document_text}
Fields: {fields_summary}""",
    "Loan & Credit Documentation": """You are a credit risk specialist. Evaluate against OCC guidelines.
Deterministic baselines: {deterministic_baselines}
Text: {document_text}
Fields: {fields_summary}""",
    "Treasury & Liquidity Reports": """You are a treasury risk specialist. Evaluate against Basel III LCR/NSFR requirements.
Deterministic baselines: {deterministic_baselines}
Text: {document_text}
Fields: {fields_summary}""",
    "Regulatory & Compliance Filings": """You are a regulatory reporting specialist. Evaluate against Pillar 3 disclosure requirements.
Deterministic baselines: {deterministic_baselines}
Text: {document_text}
Fields: {fields_summary}""",
    "Investment Banking & M&A": """You are an M&A specialist. Evaluate against fairness opinion guidelines.
Deterministic baselines: {deterministic_baselines}
Text: {document_text}
Fields: {fields_summary}""",
    "Fraud & Investigation Records": """You are a financial crime specialist. Evaluate against FinCEN SAR requirements.
Deterministic baselines: {deterministic_baselines}
Text: {document_text}
Fields: {fields_summary}""",
}

# 7. Remediation Guidance (Banking)
REMEDIATION_PROMPT = """You are a banking compliance remediation specialist. Generate actionable remediation steps.
Document type: {doc_type}
Banking domain: {banking_domain}
Issues: {issues_summary}
Low metrics: {low_metrics_summary}

Return ONLY valid JSON:
{{
  "remediation_steps": [
    {{
      "priority": <1-6>,
      "action": "<action>",
      "regulation": "<regulation>",
      "deadline": "<timeline>",
      "responsible_party": "<party>"
    }}
  ]
}}"""

# 8. Unified Classification (Banking Style)
GET_DOCUMENT_TYPE_PROMPT = """Analyze the FULL DOCUMENT below and determine its specific document type.
Return ONLY a valid JSON object with the key "document_type". 

FILENAME: {filename}

FULL DOCUMENT:
---
{document_text}
---

Return valid JSON:
{{
    "document_type": "<specific label>"
}}"""


# ─── Service Implementation ──────────────────────────────────────────────────

class BaseLLMService:
    """
    Unified LLM Service capable of both simple Extractions (Compliance) 
    and multi-agent Job pipelines (Banking).
    """

    def __init__(self) -> None:
        self.api_key: str = settings.FOUNDRY_API_KEY
        self.endpoint: str = settings.FOUNDRY_ENDPOINT.rstrip("/")
        self.model: str = settings.FOUNDRY_MODEL
        self.api_version: str = settings.FOUNDRY_API_VERSION
        self.timeout: int = getattr(settings, "LLM_TIMEOUT_SECONDS", 30)
        self.max_retries: int = getattr(settings, "LLM_MAX_RETRIES", 3)
        self.temperature: float = settings.LLM_TEMPERATURE
        self._endpoint_type: str = self._detect_endpoint_type()

        logger.info(
            "LLM Service initialized: configured=%s, endpoint_type=%s, model=%s",
            self.is_configured, self._endpoint_type, self.model
        )

    def _detect_endpoint_type(self) -> str:
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
        return bool(
            self.api_key and self.api_key != "your-api-key-here" and
            self.endpoint and "your-foundry-endpoint" not in self.endpoint
        )

    def _build_url(self) -> str:
        if self._endpoint_type == "azure_openai":
            return f"{self.endpoint}/openai/deployments/{self.model}/chat/completions?api-version={self.api_version}"
        elif self._endpoint_type == "openai_direct":
            return f"{self.endpoint}/v1/chat/completions"
        else:
            return f"{self.endpoint}/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        if self._endpoint_type == "azure_openai":
            return {"Content-Type": "application/json", "api-key": self.api_key}
        elif self._endpoint_type == "openai_direct":
            return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        else:
            return {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}", "api-key": self.api_key}

    # Monitor context: set by orchestrators before LLM calls
    _monitor_workspace: str = "unknown"
    _monitor_eval_id: str | None = None
    _monitor_step: str = ""

    def set_monitor_context(self, workspace: str = "unknown", eval_id: str | None = None, step: str = ""):
        """Set monitoring context for subsequent LLM calls."""
        self._monitor_workspace = workspace
        self._monitor_eval_id = eval_id
        self._monitor_step = step

    def _call_llm(self, prompt: str, system_msg: str = "You are a helpful assistant. Respond with valid JSON only.", max_tokens: int = 4000) -> tuple[dict, str]:
        if not self.is_configured:
            raise RuntimeError("Azure Foundry LLM is not configured.")

        url = self._build_url()
        headers = self._build_headers()
        payload = {
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            "max_completion_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self._endpoint_type != "azure_openai":
            payload["model"] = self.model

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                start_time = time.time()
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info("LLM response in %.2fs (status: %d)", time.time() - start_time, response.status_code)

                # ── Monitor: emit LLM telemetry ──
                try:
                    from core.services.monitor_collector import monitor
                    usage = {}
                    if response.status_code == 200:
                        try:
                            usage = response.json().get("usage", {})
                        except Exception:
                            pass
                    monitor.log_llm_call(
                        workspace=self._monitor_workspace,
                        eval_id=self._monitor_eval_id,
                        step=self._monitor_step,
                        model=self.model,
                        latency_ms=elapsed_ms,
                        tokens_in=usage.get("prompt_tokens", 0),
                        tokens_out=usage.get("completion_tokens", 0),
                        status_code=response.status_code,
                        error=response.text[:300] if response.status_code != 200 else None,
                    )
                except Exception:
                    pass  # Never let monitoring break the pipeline

                if response.status_code in (401, 404):
                    raise RuntimeError(f"LLM Auth/Endpoint error (HTTP {response.status_code})")
                if response.status_code != 200:
                    last_error = f"LLM error: {response.text[:200]}"
                    continue

                raw_content = response.json()["choices"][0]["message"]["content"]
                parsed = self._parse_json_response(raw_content)
                return parsed, raw_content

            except requests.Timeout:
                last_error = f"LLM timed out after {self.timeout}s"
                # ── Monitor: log timeout ──
                try:
                    from core.services.monitor_collector import monitor
                    monitor.log_llm_call(
                        workspace=self._monitor_workspace,
                        eval_id=self._monitor_eval_id,
                        step=self._monitor_step,
                        model=self.model,
                        latency_ms=self.timeout * 1000,
                        status_code=0,
                        error=last_error,
                    )
                except Exception:
                    pass
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                time.sleep(1)

        raise RuntimeError(f"LLM call failed: {last_error}")

    def _parse_json_response(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```json"): cleaned = cleaned[7:]
        if cleaned.startswith("```"): cleaned = cleaned[3:]
        if cleaned.endswith("```"): cleaned = cleaned[:-3]
        
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            # Fallback: find first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(cleaned[start:end+1])
                except: pass
            raise ValueError(f"Response is not valid JSON: {raw[:100]}...")

    def _truncate_text(self, text: str, max_chars: int = 30000) -> str:
        if len(text) <= max_chars:
            return text
        return text[:20000] + "\n\n...[CONTENT TRUNCATED]...\n\n" + text[-10000:]

    # ─── API Methods ─────────────────────────────────────────────────────────

    def classify_semantic_type(self, document_text: str, semantic_types: list[str]) -> str:
        """Classify document into one of the predefined semantic types."""
        if not self.is_configured:
            return "general"
        type_list = "\n".join(f"- {t}" for t in semantic_types)
        prompt = CLASSIFICATION_PROMPT.format(type_list=type_list, document_text=document_text[:3000])
        try:
            data, _ = self._call_llm(prompt, max_tokens=100)
            return data.get("semantic_type", "general")
        except Exception as e:
            logger.warning("Classification failed: %s", e)
            return "general"

    def detect_banking_domain(self, document_text: str, filename: str) -> str | None:
        """Detect banking domain for Banking POC."""
        if not self.is_configured:
            return None
        prompt = GET_BANKING_DOMAIN_PROMPT.format(filename=filename, document_text=document_text[:6000])
        try:
            data, _ = self._call_llm(prompt, max_tokens=200)
            domain = data.get("banking_domain")
            if isinstance(domain, str) and domain.lower() not in ("null", "none", ""):
                return domain
            return None
        except Exception as e:
            logger.warning("Banking domain detection failed: %s", e)
            return None

    def classify_document(
        self,
        document_text: str,
        filename: str,
        strict_executive_summary: str = "",
        strict_risk_assessment: str = "",
    ) -> dict:
        """Unified classification (Banking Style)."""
        full_text = document_text[:30000]
        # 1. Type
        type_prompt = GET_DOCUMENT_TYPE_PROMPT.format(filename=filename, document_text=full_text)
        try:
            type_data, _ = self._call_llm(type_prompt, max_tokens=100)
            doc_type = type_data.get("document_type", "unknown")
        except:
            doc_type = "unknown"
            
        # 2. Domain
        domain = self.detect_banking_domain(document_text, filename)
        
        return {
            "document_type": doc_type,
            "banking_domain": domain,
            "confidence": 0.85 if domain else 0.5
        }

    def extract_and_evaluate(
        self,
        document_text: str,
        semantic_type: str,
        metrics: list[Any],
        reference_context: list[str] | None = None,
    ) -> Any:
        """Single-shot extraction and evaluation (Compliance style)."""
        from core.models.schemas import LLMExtractionResponse
        prompt = build_extraction_prompt(self._truncate_text(document_text), semantic_type, metrics, reference_context)
        parsed, raw = self._call_llm(prompt)
        
        # Schema adaptation: semantic_evaluation vs semantic_scores
        if "semantic_evaluation" in parsed and "semantic_scores" not in parsed:
            parsed["semantic_scores"] = parsed.pop("semantic_evaluation")
            
        try:
            return LLMExtractionResponse(**parsed), raw
        except Exception as e:
            logger.warning("Failed to parse LLMExtractionResponse: %s. Using partial fallback.", e)
            # Create a partial model to avoid AttributeError in orchestrators
            return LLMExtractionResponse(
                document_type=parsed.get("document_type", "Unknown Document"),
                semantic_type=semantic_type,
                fields=parsed.get("fields", {}),
                semantic_scores=parsed.get("semantic_scores", {}),
                metric_reasoning=parsed.get("metric_reasoning", {}),
                executive_summary="LLM extraction was partially successful but failed schema validation.",
                risk_summary="Manual review of extracted fields is recommended.",
                recommendations=["Check for consistency in extracted JSON."]
            ), raw

    def get_fallback_response(self, document_text: str, semantic_type: str) -> Any:
        """Provide a minimal valid response when LLM fails or is disabled."""
        from core.models.schemas import LLMExtractionResponse
        return LLMExtractionResponse(
            document_type="Unknown Document",
            semantic_type=semantic_type,
            fields={},
            semantic_scores={},
            metric_reasoning={},
            executive_summary="LLM evaluation was skipped or failed. Using deterministic fallback.",
            risk_summary="Evaluation limited to rule-based metrics.",
            recommendations=["Enable LLM service for deep semantic analysis."]
        )

    def evaluate_quality_strict(self, document_text: str, deterministic_output: dict, reference_context: list[str] = None) -> tuple[Any, str]:
        """Strict validation against deterministic baseline (Banking Style)."""
        from core.models.schemas import LLMStrictQualityResponse, DocumentIntegrityScoreSection
        kb_section = ""
        if reference_context:
            kb_section = f"\n\nREFERENCE STANDARDS:\n" + "\n".join(reference_context[:3])
            
        prompt = STRICT_QUALITY_PROMPT.format(
            deterministic_output_json=json.dumps(deterministic_output, indent=2, default=str),
            reference_context=kb_section,
            document_text=document_text[:15000]
        )
        data, raw = self._call_llm(prompt)

        def _normalize_issues(raw_issues: Any) -> list[dict]:
            if not raw_issues:
                return []
            if not isinstance(raw_issues, list):
                raw_issues = [raw_issues]

            normalized: list[dict] = []
            for item in raw_issues:
                if isinstance(item, str):
                    normalized.append({
                        "field_name": "general",
                        "issue_type": "observation",
                        "description": item.strip(),
                        "severity": "warning",
                    })
                    continue

                if not isinstance(item, dict):
                    continue

                observation = (item.get("observation") or "").strip()
                description = (item.get("description") or observation).strip()
                normalized.append({
                    "field_name": (item.get("field_name") or "general").strip(),
                    "issue_type": (item.get("issue_type") or "observation").strip(),
                    "description": description or "Observation noted.",
                    "severity": (item.get("severity") or "warning").strip(),
                    "metric_dimension": item.get("metric_dimension"),
                    "regulation_reference": item.get("regulation_reference"),
                })
            return normalized

        if isinstance(data, dict) and "issues_observations" in data:
            data["issues_observations"] = _normalize_issues(data.get("issues_observations"))
        
        # Mapping to match JobResponse expectations
        if "document_integrity_score" in data:
            data["overall_score"] = data["document_integrity_score"].get("overall_score", 0)
        
        try:
            return LLMStrictQualityResponse(**data), raw
        except Exception as e:
            logger.warning("Failed to parse LLMStrictQualityResponse: %s. Using minimal fallback.", e)
            # Minimal fallback to satisfy orchestrator attribute access
            fallback = LLMStrictQualityResponse(
                document_integrity_score=DocumentIntegrityScoreSection(overall_score=0, metrics={}),
                document_type="Unknown",
                executive_summary="Failed to parse LLM validation response.",
                risk_assessment="Validation results unavailable.",
                recommendations=["Review raw LLM output for details."],
                issues_observations=[]
            )
            return fallback, raw

    def evaluate_domain_specialist(self, text: str, domain: str, fields: dict, deterministic_baselines: dict = None) -> dict:
        """Agent 3 — Deep domain-specific evaluation (Banking)."""
        prompt_template = DOMAIN_SPECIALIST_PROMPTS.get(domain)
        if not prompt_template:
            return {}

        prompt = prompt_template.format(
            document_text=text[:10000],
            fields_summary=json.dumps(fields, indent=2, default=str),
            deterministic_baselines=json.dumps(deterministic_baselines or {}, indent=2, default=str)
        )
        try:
            data, _ = self._call_llm(prompt, max_tokens=1500)
            return data
        except Exception as e:
            logger.warning("Specialist evaluation failed: %s", e)
            return {}

    def generate_remediation(self, doc_type: str, banking_domain: str, issues: list, low_metrics: list) -> list[dict]:
        """Agent 5 — Generate remediation steps (Banking)."""
        def _fmt(x):
             if isinstance(x, dict): return x.get('description', '')
             return getattr(x, 'description', '')
             
        issues_summary = "\n".join([f"- {_fmt(i)}" for i in issues[:5]])
        low_metrics_summary = "\n".join([f"- {m.get('name')}" if isinstance(m, dict) else f"- {getattr(m, 'name', '')}" for m in low_metrics])
        
        prompt = REMEDIATION_PROMPT.format(
            doc_type=doc_type,
            banking_domain=banking_domain or "General",
            issues_summary=issues_summary,
            low_metrics_summary=low_metrics_summary
        )
        try:
            data, _ = self._call_llm(prompt, max_tokens=1000)
            return data.get("remediation_steps", [])
        except Exception as e:
            logger.warning("Remediation generation failed: %s", e)
            return []

    def consolidate_issues(self, det_output: dict, llm_output: dict) -> tuple[Any, str]:
        """Merge deterministic and LLM issues (Banking)."""
        from core.models.schemas import LLMConsolidationResponse
        prompt = CONSOLIDATE_RECS_ISSUES_PROMPT.format(
            deterministic_output_json=json.dumps(det_output, indent=2, default=str),
            llm_output_json=json.dumps(llm_output, indent=2, default=str)
        )
        data, raw = self._call_llm(prompt, max_tokens=1500)
        try:
            return LLMConsolidationResponse(**data), raw
        except:
            return data, raw

    def run_strict_quality_validation(self, chunk_text: str, deterministic_json: str) -> tuple[Any, str]:
        """Backwards compatibility for Banking orchestrator."""
        return self.evaluate_quality_strict(chunk_text, json.loads(deterministic_json))

    def consolidate_recommendations_and_issues(self, det_json: str, llm_json: str) -> tuple[Any, str]:
        """Backwards compatibility for Banking orchestrator."""
        return self.consolidate_issues(json.loads(det_json), json.loads(llm_json))
