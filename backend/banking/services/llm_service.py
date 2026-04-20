"""
Azure Foundry LLM Service.

Handles all interactions with the Azure Foundry (OpenAI-compatible) API
for structured document extraction and semantic reasoning.
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests

from banking.config import settings
from banking.models.schemas import (
    IntegrityMetricDetail,
    IssueSchema,
    LLMConsolidationResponse,
    LLMExtractionResponse,
    LLMStrictQualityResponse,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Chunk:
    text: str
    start: int
    end: int


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[_Chunk]:
    """Split text into overlapping character chunks.

    Character-based chunking avoids tokenizers and keeps behavior predictable.
    """
    if not text:
        return []
    if chunk_size <= 0:
        return [_Chunk(text=text, start=0, end=len(text))]
    overlap = max(0, min(overlap, chunk_size - 1))

    chunks: list[_Chunk] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(_Chunk(text=text[start:end], start=start, end=end))
        if end >= n:
            break
        start = end - overlap
    return chunks


def _select_representative_chunks(text: str, *, chunk_size: int, overlap: int, max_chunks: int) -> list[_Chunk]:
    """Pick representative chunks that cover the full document.

    Strategy:
    - Always include the beginning, middle, and end of the document.
    - Add chunks that contain evidence-heavy markers (annexes, revision history,
      approvals/sign-off, dates/versions, key regulatory terms).
    - If still too many, downsample; if too few, add evenly spaced chunks.
    """
    if not text:
        return []

    max_chunks = max(1, int(max_chunks))
    all_chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if len(all_chunks) <= max_chunks:
        return all_chunks

    chosen_idxs: set[int] = {0, len(all_chunks) // 2, len(all_chunks) - 1}

    # NOTE: keep these keywords generic (avoid hard-coded domain/document names).
    keywords = (
        "annex",
        "appendix",
        "schedule",
        "table",
        "figure",
        "approved",
        "approval",
        "signed",
        "signature",
        "attestation",
        "revision history",
        "change log",
        "effective date",
        "version",
        "supersed",
        "regulatory",
        "compliance",
        "audit",
    )
    keyword_re = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    for i, ch in enumerate(all_chunks):
        if keyword_re.search(ch.text):
            chosen_idxs.add(i)

    idx_list = sorted(chosen_idxs)

    if len(idx_list) > max_chunks:
        step = max(1, len(idx_list) // max_chunks)
        idx_list = idx_list[::step][:max_chunks]

    if len(idx_list) < max_chunks:
        stride = max(1, len(all_chunks) // max_chunks)
        for i in range(0, len(all_chunks), stride):
            idx_list.append(i)
            if len(set(idx_list)) >= max_chunks:
                break
        idx_list = sorted(set(idx_list))[:max_chunks]

    return [all_chunks[i] for i in idx_list]


# Structured extraction prompt template
EXTRACTION_PROMPT = """You are a document quality analysis AI specializing in financial and banking documents. Analyze the following document text and return a structured JSON response.

INSTRUCTIONS:
1. Identify the specific document type strictly based on the text (e.g., "Basel III Pillar 3 Disclosure", "ISDA Master Agreement"). Do NOT use generic words like "report" or "document" if a formal title or regulatory name is present.
2. Extract all structured fields you can find (dates, names, amounts, IDs, addresses, etc.)
3. Evaluate each quality metric on a scale of 0-100 with reasoning
4. Provide an executive summary, risk summary, and actionable recommendations

SCORING DO / DON'T (applies to ALL metrics):
- DO base scores only on evidence present in the text and extracted fields.
- DO treat missing required information as a score reduction (especially for completeness/validity).
- DO penalize contradictions, draft indicators, truncated endings, or ambiguous statements under consistency/validity.
- DO use the full 0-100 range. Avoid clustering all metrics in 70-90.
- DON'T invent citations, sections, numbers, or approvals that are not explicitly present.
- DON'T assume "industry standard" content exists if it's not in the document.
- DON'T give a high score with vague reasoning — reasoning must reference specific evidence (short phrases).
5. BANKING INTELLIGENCE (CONDITIONAL): If the document is a banking-specific record, you MUST also provide
    a "domain_evaluation" object. Determine whether it belongs to one of these banking domains:
    - "Customer Onboarding (KYC/AML)"
    - "Loan & Credit Documentation"
    - "Treasury & Liquidity Reports"
    - "Regulatory & Compliance Filings"
    - "Investment Banking & M&A"
    - "Fraud & Investigation Records"
   If a banking domain is detected, provide scores (0-100) and reasoning for each relevant metric:
    - KYC/AML: boti, iess, spec (Sanctions/PEP Screening Evidence Coverage), cedj (CDD/EDD Trigger Justification Quality), soft (Source-of-Funds Traceability), avs (Address Verification Strength), rre (Risk Rating Explainability)
    - Loan & Credit: cpi, ccts, rifc (Rate Index & Fallback Correctness), eac (Execution & Authority Completeness), rsi (Repayment Schedule Integrity), bgic (Borrower/Guarantor Identification Consistency), cvr (Collateral Valuation Recency)
    - Treasury: hec, isrr, ctta (Cut-off Time & Timestamp Alignment), ssc (Stress Scenario Coverage), iocc (Inflow/Outflow Classification Completeness), lbdq (Limit Breach Disclosure Quality), sscov (Source System Coverage)
    - Regulatory: rmp (Regulatory Mapping Precision), dli (BCBS 239 Data Lineage Integrity), rcc (Regulatory Change Coverage), dcs (Disclosure Completeness Score), gsc (Governance Sign-off Completeness), cmc (Control Mapping Coverage), rcpc (Recordkeeping & Classification Policy Coverage)
    - Investment Banking: qoe, fosi, ats (Assumption Transparency Score), sac (Sensitivity Analysis Coverage), csj (Comparable Set Justification), cidc (Conflict & Independence Disclosure Completeness), drt (Data Room Traceability)
    - Fraud: snad, wcw, tcs (Timeline Coherence Score), eccc (Evidence Chain-of-Custody Completeness), tdc (Transaction Detail Completeness), detr (Disposition & Escalation Traceability), rnc (Regulatory Notification Completeness)

QUALITY METRICS TO EVALUATE:
- completeness: Are all expected/required fields present for this document type?
- accuracy: Are the extracted values correct, plausible, and well-formed?
- consistency: Are field values logically consistent with each other?
- validity: Do values conform to expected formats and standards?
- timeliness: Are dates and time-sensitive data current and reasonable?
- uniqueness: Are there duplicate entries or redundant data?

RECOMMENDATION RULES:
- Generate actionable recommendations ONLY for actual issues found.
- Generate 1 recommendation for every major negative issue (score < 100).
- If the document is perfect, return 0 or 1 general improvement recommendation. Do NOT force multiple recommendations.
- Merge overlapping actions into one clearer recommendation.
- Each recommendation must target a clear deficiency area (governance, mapping, etc.).

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
  ],
  "domain_evaluation": {{
    "banking_domain": "<one of the six domain names above, or null if not a banking document>",
    "<metric_code>": {{
      "score": <0-100>,
      "reasoning": "<brief reasoning for this domain metric score>"
    }},
    ...
  }}
}}

IMPORTANT: If the document is NOT a banking document, set domain_evaluation.banking_domain to null and omit other domain metric keys."""


# --- Deterministic-first strict quality evaluation prompts ---

STRICT_QUALITY_PROMPT = """You are a strict document quality evaluation engine.

You will be given:
1) FULL DOCUMENT TEXT (may be a chunk of the full document)
2) A DETERMINISTIC EVALUATION OUTPUT (scores + issues + extracted fields)

STRICT EVALUATION GUIDELINES (MANDATORY):
- This is document QUALITY evaluation only (not interpretation, not creativity).
- Do NOT make assumptions. Only use evidence from:
    (a) the provided document text, and
    (b) the deterministic output.
- Validate the deterministic scores and issues.
- If you disagree, challenge with specific evidence phrases (short quotes).
- You MAY refine scores, but keep changes justified and consistent.
- Keep executive summary and risk assessment concise and professional.

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
    - metrics: object with exactly these keys:
        completeness, accuracy, consistency, validity, timeliness, uniqueness
    - each metric value must be an object with:
        score (0-100), deterministic_score (0-100), reasoning (string)

RECOMMENDATIONS RULES:
- Recommendations must be distinct and actionable.
- Do not repeat the same action with different wording.
- Prioritize high-impact fixes based ONLY on issues found.
- If the document is high quality with no major issues, return 0 or 1 general improvement.
- Provide 1 recommendation per substantive issue identified. Do NOT force a high number.

ISSUES & OBSERVATIONS RULES:
- issues_observations must be a list of objects with:
    field_name, issue_type, description, severity, metric_dimension (optional)
- severity must be one of: critical, warning, good
- Do not invent issues without evidence.

IMPORTANT CONSTRAINTS RULES:
- important_constraints must be a list of concise guardrails/constraints you followed.
- Include 2 to 6 items.
- Each item must be evidence-anchored and quality-evaluation specific.

DOCUMENT TYPE RULES:
- document_type must be a specific, best-fit label derived from the document's actual title or content.
- DO NOT use generic types like "report", "file", or "document" if the text contains a specific title (e.g. "Basel III Pillar 3 Disclosure", "Liquidity Coverage Ratio", "Credit Agreement").
- If completely unclear, only then fallback to: invoice, contract, letter, form, unknown.

BANKING DOMAIN ROUTING (CRITICAL SYSTEM GUARDRAIL):
Classify the document conceptually into one of the below categories IF it belongs to banking documents, regardless of whether specific keywords are present. Just use your understanding of the document's purpose:
1. "Customer Onboarding (KYC/AML)"
2. "Loan & Credit Documentation"
3. "Treasury & Liquidity Reports"
4. "Regulatory & Compliance Filings"
5. "Investment Banking & M&A"
6. "Fraud & Investigation Records"

- Set banking_domain to null ONLY if it definitively does not fit any category.
- NEVER invent a new category name.

DETERMINISTIC OUTPUT (JSON):
---
{deterministic_output_json}
---

DOCUMENT TEXT:
---
{document_text}
---
"""


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

OUTPUT LIMITS:
- recommendations: Dynamic based on number of critical/warning issues found. Do NOT force a specific number. 
- issues_observations: up to 30 items

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
{
    "recommendations": ["..."],
    "issues_observations": [
        {
            "field_name": "...",
            "issue_type": "...",
            "description": "...",
            "severity": "critical|warning|good",
            "metric_dimension": "..." 
        }
    ]
}
"""


def _limit_str(s: str, max_len: int) -> str:
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


# ─── Agent 1: Dual Full-Document Classification ───────────────────────────────

GET_DOCUMENT_TYPE_PROMPT = """Analyze the FULL DOCUMENT below and determine its specific document type.
Return ONLY a valid JSON object with the key "document_type". 
Do NOT use generic types like "report" or "file" if a title or specific nature is evident.

FILENAME: {filename}

FULL DOCUMENT:
---
{document_text}
---

Return valid JSON:
{{
    "document_type": "<specific document type label>"
}}"""

GET_BANKING_DOMAIN_PROMPT = """Analyze the FULL DOCUMENT below. Conceptually evaluate its purpose, meaning, and function to determine which of the follow banking categories it belongs to.
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


# ─── Agent 3: Domain specialist prompts per banking domain ────────────────────
DOMAIN_SPECIALIST_PROMPTS: dict[str, str] = {
    "Customer Onboarding (KYC/AML)": """You are a KYC/AML compliance specialist. Evaluate this document against FATF Recommendations, the EU 5th Anti-Money Laundering Directive (AML5D), and PEP/sanctions screening requirements.

Deterministic (rule-engine) baselines for these metrics (0-100):
{deterministic_baselines}

DOCUMENT:
---
{document_text}
---

Extracted fields already found: {fields_summary}

RULES:
- Return integers 0-100.
- Provide up to 3 short evidence snippets (exact phrases/quotes from the document) per metric.
- If your score materially differs from the deterministic baseline, explain why in reasoning.

Score these seven metrics (0-100 each). Return valid JSON:
{{
  "boti": {{
    "score": <0-100>,
        "reasoning": "<cite specific FATF Rec 10 / AML5D Art 13 requirements met or missing>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
  "iess": {{
    "score": <0-100>,
        "reasoning": "<cite biometric/documentary evidence quality and AML5D Art 13(1) compliance>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
    "spec": {
        "score": <0-100>,
                "reasoning": "<cite sanctions/PEP evidence coverage: screening date, source lists, result, reviewer sign-off>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "cedj": {
        "score": <0-100>,
                "reasoning": "<cite quality of CDD/EDD trigger rationale (PEP/adverse media/high-risk jurisdiction)>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "soft": {
        "score": <0-100>,
                "reasoning": "<cite source-of-funds traceability to supporting artifacts>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "avs": {
        "score": <0-100>,
                "reasoning": "<cite proof-of-address presence, recency, and match quality>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "rre": {
        "score": <0-100>,
                "reasoning": "<cite risk score explainability and named driver coverage>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
  "specialist_notes": "<any additional compliance concerns>"
}}""",

    "Loan & Credit Documentation": """You are a credit risk and loan documentation specialist. Evaluate this document against OCC safety-and-soundness guidelines, UCC Article 9 (collateral perfection), IFRS 9/CECL provisions, and standard covenant packages.

Deterministic (rule-engine) baselines for these metrics (0-100):
{deterministic_baselines}

DOCUMENT:
---
{document_text}
---

Extracted fields already found: {fields_summary}

RULES:
- Return integers 0-100.
- Provide up to 3 short evidence snippets (exact phrases/quotes from the document) per metric.
- If your score materially differs from the deterministic baseline, explain why in reasoning.

Score these seven metrics (0-100 each). Return valid JSON:
{{
  "cpi": {{
    "score": <0-100>,
        "reasoning": "<cite UCC filing status, collateral description completeness, and OCC S&S compliance>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
  "ccts": {{
    "score": <0-100>,
        "reasoning": "<cite presence/absence of financial covenants and IFRS 9/CECL compliance>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
    "rifc": {
        "score": <0-100>,
                "reasoning": "<cite benchmark index correctness, fallback language, and any LIBOR-only risk>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "eac": {
        "score": <0-100>,
                "reasoning": "<cite execution signatures, authority evidence, and board resolution completeness>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "rsi": {
        "score": <0-100>,
                "reasoning": "<cite repayment schedule completeness and consistency of dates/tenor/frequency>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "bgic": {
        "score": <0-100>,
                "reasoning": "<cite borrower/guarantor identity consistency across referenced sections>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "cvr": {
        "score": <0-100>,
                "reasoning": "<cite collateral appraisal recency and policy-window compliance>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
  "specialist_notes": "<any additional credit risk concerns>"
}}""",

    "Treasury & Liquidity Reports": """You are a treasury and liquidity risk specialist. Evaluate this report against Basel III LCR/NSFR requirements, BCBS 238, and 12 CFR Part 329 (LCR rule).

Deterministic (rule-engine) baselines for these metrics (0-100):
{deterministic_baselines}

DOCUMENT:
---
{document_text}
---

Extracted fields already found: {fields_summary}

RULES:
- Return integers 0-100.
- Provide up to 3 short evidence snippets (exact phrases/quotes from the document) per metric.
- If your score materially differs from the deterministic baseline, explain why in reasoning.

Score these seven metrics (0-100 each). Return valid JSON:
{{
  "hec": {{
    "score": <0-100>,
        "reasoning": "<cite HQLA Level 1/2 eligibility criteria per 12 CFR §329.20 and Basel III paras 49-54>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
  "isrr": {{
    "score": <0-100>,
        "reasoning": "<cite cross-system reconciliation evidence vs BCBS 239 Principle 3>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
    "ctta": {
        "score": <0-100>,
                "reasoning": "<cite cut-off and timestamp alignment between report and source systems>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "ssc": {
        "score": <0-100>,
                "reasoning": "<cite stress scenario definitions, assumptions, and documented outcomes>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "iocc": {
        "score": <0-100>,
                "reasoning": "<cite inflow/outflow classification category completeness>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "lbdq": {
        "score": <0-100>,
                "reasoning": "<cite quality of limit breach actions, approvals, and escalation records>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "sscov": {
        "score": <0-100>,
                "reasoning": "<cite coverage of GL/core banking/treasury source-system references>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
  "specialist_notes": "<any additional liquidity risk concerns>"
}}""",

    "Regulatory & Compliance Filings": """You are a regulatory reporting specialist. Evaluate this document against EBA Reporting Technical Standards (ITS), BCBS 239 data governance principles, and Pillar 3 disclosure requirements.

Deterministic (rule-engine) baselines for these metrics (0-100):
{deterministic_baselines}

EVALUATION RULES (DO / DON'T):
- DO be framework-aware: if the document is clearly a PCI-DSS / control framework / internal policy, score disclosure completeness based on that framework’s expected sections (scope, roles, control requirements, evidence, review cycle), not Pillar 3 capital/RWA topics.
- DO score strictly when key evidence is missing (e.g., no approvals, no version/effective date, no mapping table).
- DO cite concrete evidence snippets (e.g., "Requirement 12.1", "Approved by", "Effective date").
- DON'T assume the presence of mapping tables, sign-off pages, lineage traces, or quantitative disclosures if they are not present.
- DON'T treat generic words like "data governance" as a regulatory citation for RMP — RMP requires explicit regulation/taxonomy references.

DOCUMENT:
---
{document_text}
---

Extracted fields already found: {fields_summary}

SCORING RUBRIC (use consistently):
- 90–100: Explicit, complete, audit-ready evidence throughout.
- 70–89: Mostly present but some gaps or limited evidence.
- 40–69: Partial coverage; major sections missing or only generic statements.
- 0–39: Essentially absent; only vague mentions or unrelated content.

Score these metrics (0-100 each). Return valid JSON (integers only). Include up to 3 short evidence snippets per metric:
{{
  "rmp": {{
    "score": <0-100>,
                "reasoning": "<evidence of explicit regulation/taxonomy citations (EBA RTS/ITS, CRR/CRD, BCBS 239, Pillar 3, ICAAP/ILAAP). Mention what is cited and what's missing.>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
  "dli": {{
    "score": <0-100>,
                "reasoning": "<evidence of source systems, system-of-record, audit trail, automated lineage, controls over manual adjustments; cite any BCBS 239 alignment if present>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
    "rcc": {
        "score": <0-100>,
                                "reasoning": "<evidence of versioning, revision history, effective dates, change log, superseded rules; flag obsolete references if present>",
                                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "dcs": {
        "score": <0-100>,
                                "reasoning": "<framework-aware completeness: Pillar 3 topics if applicable; otherwise policy/framework sections (scope, roles, requirements, evidence, exceptions, review cycle). Note missing mandatory sections.>",
                                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "gsc": {
        "score": <0-100>,
                                "reasoning": "<evidence of approvals/signatures, accountable roles (CISO/CRO/etc), dates; penalize draft markers; note what's missing>",
                                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "cmc": {
        "score": <0-100>,
                                "reasoning": "<evidence of mapping between requirements and internal controls, owners, testing, and evidence artifacts (tables/matrices preferred)>",
                                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "rcpc": {
        "score": <0-100>,
                                "reasoning": "<evidence of retention periods, classification labels, archival/storage, disposal/destruction, and legal hold/e-discovery>",
                                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
  "specialist_notes": "<any additional regulatory concerns>"
}}""",

    "Investment Banking & M&A": """You are an investment banking and M&A documentation specialist. Evaluate against AICPA Quality of Earnings standards, Delaware fiduciary duty requirements, and FINRA fairness opinion guidelines.

Deterministic (rule-engine) baselines for these metrics (0-100):
{deterministic_baselines}

DOCUMENT:
---
{document_text}
---

Extracted fields already found: {fields_summary}

RULES:
- Return integers 0-100.
- Provide up to 3 short evidence snippets (exact phrases/quotes from the document) per metric.
- If your score materially differs from the deterministic baseline, explain why in reasoning.

Score these seven metrics (0-100 each). Return valid JSON:
{{
  "qoe": {{
    "score": <0-100>,
        "reasoning": "<cite EBITDA normalization adjustments present, AICPA SAS standards>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
  "fosi": {{
    "score": <0-100>,
        "reasoning": "<cite sensitivity analysis completeness and Delaware fiduciary standard>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
    "ats": {
        "score": <0-100>,
                "reasoning": "<cite assumption transparency with sources and rationale>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "sac": {
        "score": <0-100>,
                "reasoning": "<cite sensitivity coverage for WACC, growth, and multiples>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "csj": {
        "score": <0-100>,
                "reasoning": "<cite comparable inclusion/exclusion criteria and justification quality>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "cidc": {
        "score": <0-100>,
                "reasoning": "<cite independence, fee, and conflict disclosure completeness>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "drt": {
        "score": <0-100>,
                "reasoning": "<cite data-room traceability to source exhibits/documents>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
  "specialist_notes": "<any additional M&A due diligence concerns>"
}}""",

    "Fraud & Investigation Records": """You are a financial crime investigation specialist. Evaluate against FinCEN SAR filing requirements (31 CFR §1020.320), FATF Guidance on SARs, and internal investigation best practices.

Deterministic (rule-engine) baselines for these metrics (0-100):
{deterministic_baselines}

DOCUMENT:
---
{document_text}
---

Extracted fields already found: {fields_summary}

RULES:
- Return integers 0-100.
- Provide up to 3 short evidence snippets (exact phrases/quotes from the document) per metric.
- If your score materially differs from the deterministic baseline, explain why in reasoning.

Score these seven metrics (0-100 each). Return valid JSON:
{{
  "snad": {{
    "score": <0-100>,
        "reasoning": "<cite 5W+H completeness per 31 CFR §1020.320: who/what/when/where/how/why elements>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
  "wcw": {{
    "score": <0-100>,
        "reasoning": "<cite corroboration quality, specificity, and internal credibility indicators>",
        "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
  }},
    "tcs": {
        "score": <0-100>,
                "reasoning": "<cite chronological coherence and presence of clear time markers>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "eccc": {
        "score": <0-100>,
                "reasoning": "<cite chain-of-custody metadata completeness: IDs, collection dates, handlers>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "tdc": {
        "score": <0-100>,
                "reasoning": "<cite transaction detail completeness: amount/date/sender/receiver/channel>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "detr": {
        "score": <0-100>,
                "reasoning": "<cite disposition and escalation traceability: decision/approver/rationale>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
    "rnc": {
        "score": <0-100>,
                "reasoning": "<cite regulatory notification timing and reference completeness>",
                "evidence": ["<snippet1>", "<snippet2>", "<snippet3>"]
    },
  "specialist_notes": "<any additional investigation quality concerns>"
}}""",
}


# ─── Agent 4: Challenge / confidence validation prompt ────────────────────────
CHALLENGE_PROMPT = """You are a quality control reviewer. Examine these metric scores for consistency and flag discrepancies.

Document type: {doc_type}
Deterministic scores (rule-based): {det_scores}
LLM extraction scores: {llm_scores}
Domain specialist scores (if available): {domain_scores}

Identify any metrics where deterministic and LLM scores diverge by more than 20 points. For those, provide your confidence assessment.

Return ONLY valid JSON:
{{
  "confidence": {{
    "<metric_name>": <0.0-1.0>,
    ...
  }},
  "flags": [
    "<description of any significant score discrepancy>"
  ],
  "overall_confidence": <0.0-1.0>
}}"""


# ─── Agent 5: Remediation guidance prompt ────────────────────────────────────
REMEDIATION_PROMPT = """You are a banking compliance remediation specialist. Based on the document issues and low-scoring metrics below, generate specific, actionable remediation steps.

Document type: {doc_type}
Banking domain: {banking_domain}

Issues identified:
{issues_summary}

Low-scoring metrics (score < 75):
{low_metrics_summary}

Generate remediation steps dynamically based ONLY on the actual issues and low-scoring metrics present.
Provide exactly 1 remediation step per critical/warning issue or low-scoring metric. If 0 issues/low-metrics exist, return an empty list []. Each step must:
- Directly address at least one listed issue or low-scoring metric.
- Name a SPECIFIC action (not a vague suggestion).
- Reference a relevant regulation/standard (prefer those already mentioned in issues; otherwise choose a conservative, broadly applicable standard).
- Include a realistic timeline.
- Assign a responsible party.

Return ONLY valid JSON:
{{
  "remediation_steps": [
    {{
      "priority": <1-6>,
      "action": "<specific action to take>",
      "regulation": "<regulation or standard this addresses>",
      "deadline": "<recommended timeline e.g. 5 business days>",
      "responsible_party": "<who should action this>"
    }}
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

    @staticmethod
    def _safe_parse_json(text: str) -> dict | list:
        """Safely parse JSON from LLM output, handling markdown and decode errors."""
        import json
        if not text:
            return {}
        cleaned = text.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to parse JSON: {e} (first 200 chars: {text[:200]})")
            return {}



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
        # Do not truncate here; chunking is handled at a higher level.
        prompt = EXTRACTION_PROMPT.format(document_text=document_text)
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

    # ── Internal shared LLM caller ─────────────────────────────────────────

    def _call_llm(
        self,
        user_prompt: str,
        system_prompt: str = "You are a helpful assistant. Respond with valid JSON only.",
        max_tokens: int = 2000,
    ) -> tuple[str, str]:
        """
        Low-level LLM call used by all agents.

        Args:
            user_prompt: The user turn prompt.
            system_prompt: The system turn instructions.
            max_tokens: Maximum completion tokens.

        Returns:
            Tuple of (content_string, raw_response_string).

        Raises:
            RuntimeError: On HTTP errors or exhausted retries.
        """
        if not self.is_configured:
            raise RuntimeError("Azure Foundry LLM is not configured.")

        url = self._build_url()
        headers = self._build_headers()
        payload: dict = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_completion_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        # Non-Azure-OpenAI endpoints need model in payload
        if self._endpoint_type != "azure_openai":
            payload["model"] = self.model

        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                if response.status_code in (401, 404):
                    raise RuntimeError(
                        f"LLM API error HTTP {response.status_code}: {response.text[:300]}"
                    )
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                    if attempt < self.max_retries:
                        time.sleep(1)
                    continue
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return content, json.dumps(data)
            except requests.Timeout:
                last_error = f"Timeout after {self.timeout}s (attempt {attempt})"
            except requests.RequestException as e:
                last_error = f"Request error (attempt {attempt}): {e}"
            except RuntimeError:
                raise
            if attempt < self.max_retries:
                time.sleep(1)

        raise RuntimeError(f"LLM call failed after {self.max_retries} attempts. {last_error}")

    @staticmethod
    def _clean_recommendation_text(text: str) -> str:
        """Normalize recommendation text while preserving original intent."""
        if not isinstance(text, str):
            return ""
        cleaned = text.strip()
        cleaned = re.sub(r"^\s*(?:[-*•]|\d+[\.)])\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _recommendation_key(text: str) -> str:
        """Build a strict de-duplication key for recommendation text."""
        cleaned = AzureFoundryLLMService._clean_recommendation_text(text)
        lowered = cleaned.lower()
        lowered = re.sub(r"[^a-z0-9\s]", "", lowered)
        lowered = re.sub(r"\s+", " ", lowered).strip()
        return lowered

    @staticmethod
    def _recommendation_token_set(text: str) -> set[str]:
        """Tokenize recommendation text for near-duplicate detection."""
        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "into", "your",
            "are", "was", "were", "have", "has", "had", "should", "must", "can",
            "include", "including", "ensure", "provide", "add", "update", "document",
            "policy", "process", "controls", "control", "requirements", "requirement",
        }
        key = AzureFoundryLLMService._recommendation_key(text)
        return {
            token
            for token in key.split()
            if len(token) >= 4 and token not in stopwords
        }

    @classmethod
    def _is_near_duplicate_recommendation(cls, candidate: str, existing: str) -> bool:
        """Detect near-duplicate recommendations without forcing a fixed count."""
        c_key = cls._recommendation_key(candidate)
        e_key = cls._recommendation_key(existing)

        if not c_key or not e_key:
            return False
        if c_key == e_key:
            return True
        if (len(c_key) >= 35 and c_key in e_key) or (len(e_key) >= 35 and e_key in c_key):
            return True

        c_tokens = cls._recommendation_token_set(candidate)
        e_tokens = cls._recommendation_token_set(existing)
        if not c_tokens or not e_tokens:
            return False

        intersection = len(c_tokens & e_tokens)
        union = len(c_tokens | e_tokens)
        jaccard = (intersection / union) if union else 0.0

        return intersection >= 4 and jaccard >= 0.55

    @classmethod
    def _merge_recommendations(cls, base: list[str], incoming: list[str]) -> list[str]:
        """Merge recommendations dynamically with strict + near-duplicate suppression."""
        merged: list[str] = []

        for rec in [*(base or []), *(incoming or [])]:
            cleaned = cls._clean_recommendation_text(rec)
            if not cleaned:
                continue

            if any(cls._is_near_duplicate_recommendation(cleaned, existing) for existing in merged):
                continue
            merged.append(cleaned)

        return merged

    # ── Chunking helpers ───────────────────────────────────────────────────

    # Chunking strategy: select representative excerpts across the document to
    # avoid hard truncation while keeping cost bounded.

    # ── Agent 1: Classification ────────────────────────────────────────────

    def classify_document(
        self,
        text: str,
        *,
        filename: str = "",
        strict_executive_summary: str = "",
        strict_risk_assessment: str = "",
    ) -> dict:
        """
        Agent 1 — Fast document classification based on Dual Full-Document approach.
        Instead of a single prompt, makes two sequential calls to the LLM providing the FULL text:
        1. Determine specific document type.
        2. Determine banking domain category conceptually without hardcoded keywords.
        Returns a dict with keys: document_type, banking_domain, confidence.
        """
        try:
            if not text or not isinstance(text, str):
                logger.warning("Invalid text for classification")
                return {"document_type": "unknown", "banking_domain": None, "confidence": 0}
            
            # Use full text bounded gently to avoid huge unhandled context bloat, but essentially "full document"
            full_text = text.strip()[:80000]

            # 1. Ask for Document Type
            type_prompt = GET_DOCUMENT_TYPE_PROMPT.format(
                filename=(filename or "").strip(),
                document_text=full_text,
            )
            doc_type_content, _ = self._call_llm(type_prompt, max_tokens=150)
            
            doc_type = "unknown"
            if doc_type_content:
                cleaned_type = doc_type_content.strip().strip("```json").strip("```").strip()
                try:
                    type_data = AzureFoundryLLMService._safe_parse_json(cleaned_type)
                    doc_type = str(type_data.get("document_type", "unknown")).strip()
                except Exception as e:
                    logger.warning("Failed to parse document_type JSON: %s", e)

            # 2. Ask for Banking Domain
            domain_prompt = GET_BANKING_DOMAIN_PROMPT.format(
                filename=(filename or "").strip(),
                document_text=full_text,
            )
            domain_content, _ = self._call_llm(domain_prompt, max_tokens=150)
            
            domain = None
            if domain_content:
                cleaned_domain = domain_content.strip().strip("```json").strip("```").strip()
                try:
                    domain_data = AzureFoundryLLMService._safe_parse_json(cleaned_domain)
                    ext_domain = domain_data.get("banking_domain")
                    if ext_domain and str(ext_domain).lower() not in ["null", "none", ""]:
                        domain = str(ext_domain).strip()
                except Exception as e:
                    logger.warning("Failed to parse banking_domain JSON: %s", e)

            return {
                "document_type": doc_type if doc_type else "unknown",
                "banking_domain": domain,
                "confidence": 95 if (domain and doc_type != "unknown") else 75
            }
        except Exception as e:
            logger.warning("Classification agent failed: %s", e)
            return {"document_type": "unknown", "banking_domain": None, "confidence": 0}

    # ── Agent 2: Chunked extraction (replaces _build_payload direct call) ──

    def _extract_single_prompt(
        self, text: str, pre_classified_type: str = ""
    ) -> tuple["LLMExtractionResponse", str]:
        """
        Run the full EXTRACTION_PROMPT on a single text segment.
        """
        prompt = EXTRACTION_PROMPT.format(document_text=text)
        system = (
            "You are a document quality analysis assistant. "
            "Always respond with valid JSON only. No markdown formatting."
        )
        content, raw = self._call_llm(prompt, system_prompt=system, max_tokens=4000)
        parsed = self._parse_response(content)
        parsed.recommendations = self._merge_recommendations(parsed.recommendations or [], [])
        return parsed, raw

    def _merge_llm_extractions(
        self, parts: list["LLMExtractionResponse"]
    ) -> "LLMExtractionResponse":
        """Merge per-chunk LLMExtractionResponse objects into one response."""
        merged = LLMExtractionResponse()

        # Document type: pick the most frequent non-empty value.
        doc_types: dict[str, int] = {}
        for p in parts:
            if p.document_type:
                doc_types[p.document_type] = doc_types.get(p.document_type, 0) + 1
        merged.document_type = max(doc_types, key=doc_types.get) if doc_types else ""

        # Fields: union, prefer first seen non-empty.
        fields: dict = {}
        for p in parts:
            for k, v in (p.fields or {}).items():
                if k not in fields and v not in (None, "", [], {}):
                    fields[k] = v
        merged.fields = fields

        # Semantic evaluation: length-weighted average.
        # If a chunk doesn't provide it, treat as 0 contribution.
        total_w = 0.0
        sums = {"completeness": 0.0, "accuracy": 0.0, "consistency": 0.0, "validity": 0.0, "timeliness": 0.0, "uniqueness": 0.0}
        for p in parts:
            w = float(len(json.dumps(p.fields or {})) + 1)
            total_w += w
            sem = p.semantic_evaluation
            if sem:
                sums["completeness"] += w * float(sem.completeness or 0)
                sums["accuracy"] += w * float(sem.accuracy or 0)
                sums["consistency"] += w * float(sem.consistency or 0)
                sums["validity"] += w * float(sem.validity or 0)
                sums["timeliness"] += w * float(sem.timeliness or 0)
                sums["uniqueness"] += w * float(sem.uniqueness or 0)
        if total_w <= 0:
            total_w = 1.0
        merged.semantic_evaluation.completeness = round(sums["completeness"] / total_w, 2)
        merged.semantic_evaluation.accuracy = round(sums["accuracy"] / total_w, 2)
        merged.semantic_evaluation.consistency = round(sums["consistency"] / total_w, 2)
        merged.semantic_evaluation.validity = round(sums["validity"] / total_w, 2)
        merged.semantic_evaluation.timeliness = round(sums["timeliness"] / total_w, 2)
        merged.semantic_evaluation.uniqueness = round(sums["uniqueness"] / total_w, 2)

        # Metric reasoning: keep the longest (usually most detailed) per metric.
        metric_reasoning: dict[str, str] = {}
        for p in parts:
            for k, v in (p.metric_reasoning or {}).items():
                if not isinstance(v, str):
                    continue
                v = v.strip()
                if not v:
                    continue
                if k not in metric_reasoning or len(v) > len(metric_reasoning[k]):
                    metric_reasoning[k] = v
        merged.metric_reasoning = metric_reasoning

        # Executive/risk summaries: prefer the most detailed.
        merged.executive_summary = max((p.executive_summary or "" for p in parts), key=len, default="")
        merged.risk_summary = max((p.risk_summary or "" for p in parts), key=len, default="")

        # Recommendations: dedupe across chunks.
        recs: list[str] = []
        for p in parts:
            recs = self._merge_recommendations(recs, p.recommendations or [])
        merged.recommendations = recs

        # Domain evaluation: merge banking_domain by majority, then per-metric keep max score and the most detailed reasoning.
        domain_eval_parts = [p.domain_evaluation for p in parts if getattr(p, "domain_evaluation", None)]
        if domain_eval_parts:
            banking_domains: dict[str, int] = {}
            for de in domain_eval_parts:
                bd = (de or {}).get("banking_domain")
                if bd:
                    banking_domains[str(bd)] = banking_domains.get(str(bd), 0) + 1
            merged_domain: dict = {"banking_domain": max(banking_domains, key=banking_domains.get) if banking_domains else None}
            metric_map: dict[str, dict] = {}
            for de in domain_eval_parts:
                if not isinstance(de, dict):
                    continue
                for code, val in de.items():
                    if code == "banking_domain" or val is None:
                        continue
                    if isinstance(val, dict):
                        score = val.get("score")
                        reasoning = val.get("reasoning")
                    else:
                        score = val
                        reasoning = ""
                    try:
                        score_f = float(score)
                    except Exception:
                        continue
                    prev = metric_map.get(code)
                    if not prev or score_f > float(prev.get("score", -1)):
                        metric_map[code] = {"score": score_f, "reasoning": reasoning or ""}
                    elif prev and isinstance(reasoning, str) and len(reasoning) > len(str(prev.get("reasoning", ""))):
                        prev["reasoning"] = reasoning
            merged_domain.update(metric_map)
            merged.domain_evaluation = merged_domain

        return merged

    def extract_and_evaluate(
        self, document_text: str, pre_classified_type: str = ""
    ) -> tuple["LLMExtractionResponse", str]:
        """
        Agent 2 — Full-document extraction and semantic evaluation.

        Full-document coverage strategy:
        - Split the document into overlapping chunks.
        - Run extraction on every chunk (map).
        - Merge extracted fields, semantic scores, reasoning, recommendations, and
          banking domain evaluation into one response (reduce).

        Args:
            document_text: Normalized document text (any length).
            pre_classified_type: Optional hint from Agent 1.

        Returns:
            Tuple of (LLMExtractionResponse, raw JSON).
        """
        if not self.is_configured:
            raise RuntimeError(
                "Azure Foundry LLM is not configured. "
                "Set FOUNDRY_API_KEY and FOUNDRY_ENDPOINT in the .env file."
            )

        chunk_size = max(1000, int(getattr(settings, "LLM_CHUNK_SIZE", 6000)))
        overlap = max(0, int(getattr(settings, "LLM_CHUNK_OVERLAP", 500)))

        text = document_text or ""
        chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            return self._extract_single_prompt(text, pre_classified_type)

        # If the document is small enough, keep a single call.
        if len(chunks) == 1:
            return self._extract_single_prompt(text, pre_classified_type)

        part_responses: list[LLMExtractionResponse] = []
        raw_parts: list[str] = []
        for idx, ch in enumerate(chunks, start=1):
            logger.info(
                "LLM extraction chunk %d/%d (chars %d-%d)",
                idx,
                len(chunks),
                ch.start,
                ch.end,
            )
            parsed, raw = self._extract_single_prompt(ch.text, pre_classified_type)
            part_responses.append(parsed)
            raw_parts.append(raw)

        merged = self._merge_llm_extractions(part_responses)
        merged_raw = json.dumps({"chunks": raw_parts})
        return merged, merged_raw

    # ── Deterministic-first strict quality evaluation ─────────────────────

    @staticmethod
    def _clean_issue_key(issue: IssueSchema) -> str:
        parts = [
            (issue.field_name or "").strip().lower(),
            (issue.issue_type or "").strip().lower(),
            re.sub(r"\s+", " ", (issue.description or "").strip().lower()),
            (issue.metric_dimension or "").strip().lower(),
        ]
        joined = "|".join(parts)
        joined = re.sub(r"[^a-z0-9\|\s]", "", joined)
        return re.sub(r"\s+", " ", joined).strip()

    @classmethod
    def _merge_issues(cls, base: list[IssueSchema], incoming: list[IssueSchema]) -> list[IssueSchema]:
        merged: list[IssueSchema] = []
        seen: set[str] = set()
        for it in [*(base or []), *(incoming or [])]:
            if not it:
                continue
            try:
                issue = it if isinstance(it, IssueSchema) else IssueSchema(**dict(it))
            except Exception:
                continue
            key = cls._clean_issue_key(issue)
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(issue)
        return merged

    def _parse_strict_quality_response(self, raw_response: str) -> LLMStrictQualityResponse:
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        data = AzureFoundryLLMService._safe_parse_json(cleaned)
        return LLMStrictQualityResponse(**data)

    @staticmethod
    def _normalize_strict_quality_response(
        parsed: LLMStrictQualityResponse,
        deterministic_output: dict,
    ) -> LLMStrictQualityResponse:
        """Backfill missing strict sections and metric objects from deterministic output."""
        det = deterministic_output or {}
        det_metrics = det.get("metrics", {}) or {}

        # Ensure the six core metrics always exist with deterministic baselines.
        required_metrics = (
            "completeness",
            "accuracy",
            "consistency",
            "validity",
            "timeliness",
            "uniqueness",
        )
        metric_map = parsed.document_integrity_score.metrics or {}

        for metric_name in required_metrics:
            detail = metric_map.get(metric_name)
            try:
                metric_dict = det_metrics.get(metric_name, {}) or {}
                score_val = metric_dict.get("score", 0) or 0
                det_score = float(score_val) if score_val is not None else 0.0
            except (ValueError, TypeError):
                det_score = 0.0

            if detail is None:
                metric_map[metric_name] = IntegrityMetricDetail(
                    score=det_score,
                    deterministic_score=det_score,
                    reasoning="",
                )
                continue

            if detail.deterministic_score is None:
                detail.deterministic_score = round(max(0.0, min(100.0, det_score)), 1)

        # Ensure overall score exists and is bounded.
        if parsed.document_integrity_score.overall_score is None:
            try:
                parsed.document_integrity_score.overall_score = float(det.get("overall_score", 0) or 0)
            except Exception:
                parsed.document_integrity_score.overall_score = 0.0
        parsed.document_integrity_score.overall_score = round(
            max(0.0, min(100.0, float(parsed.document_integrity_score.overall_score))), 1
        )

        # Fill key narrative fields logically when omitted.
        if not (parsed.document_type or "").strip():
            parsed.document_type = str(det.get("document_type", "unknown") or "unknown")

        if not (parsed.important_constraints or []):
            parsed.important_constraints = [
                "Scores are evidence-based and grounded in document text plus deterministic output.",
                "No assumption is made for missing sections or controls.",
                "Deterministic logic is not overridden without explicit justification.",
            ]

        parsed.document_integrity_score.metrics = metric_map
        return parsed

    def _parse_consolidation_response(self, raw_response: str) -> LLMConsolidationResponse:
        if not raw_response or not isinstance(raw_response, str):
            logger.warning("Invalid consolidation response: not a string or empty")
            return LLMConsolidationResponse()
        
        cleaned = raw_response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        if not cleaned:
            logger.warning("Empty consolidation response after stripping markers")
            return LLMConsolidationResponse()
        
        try:
            data = AzureFoundryLLMService._safe_parse_json(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse consolidation JSON: %s (first 200 chars: %s)", e, cleaned[:200])
            return LLMConsolidationResponse()
        
        try:
            return LLMConsolidationResponse(**data)
        except Exception as e:
            logger.error("Failed to validate consolidation response schema: %s", e)
            return LLMConsolidationResponse()

    def evaluate_quality_strict(
        self,
        document_text: str,
        deterministic_output: dict,
    ) -> tuple[LLMStrictQualityResponse, str]:
        """Strict LLM second-layer evaluation: validate/challenge/refine deterministic results."""
        det_json = json.dumps(deterministic_output or {}, indent=2, default=str)

        # Deterministic-only fallback
        if not self.is_configured:
            metrics = {}
            det_metrics = (deterministic_output or {}).get("metrics", {})
            for k in ("completeness", "accuracy", "consistency", "validity", "timeliness", "uniqueness"):
                try:
                    metric_obj = det_metrics.get(k, {}) or {}
                    score_val = metric_obj.get("score", 0)
                    d = float(score_val) if score_val is not None else 0.0
                except (ValueError, TypeError) as e:
                    logger.warning("Failed to convert metric %s to float: %s, defaulting to 0", k, e)
                    d = 0.0
                metrics[k] = {"score": d, "deterministic_score": d, "reasoning": ""}
            try:
                overall_score_val = (deterministic_output or {}).get("overall_score", 0) or 0
                overall = float(overall_score_val) if overall_score_val is not None else 0.0
            except (ValueError, TypeError) as e:
                logger.warning("Failed to convert overall_score to float: %s, defaulting to 0", e)
                overall = 0.0
            fallback = LLMStrictQualityResponse(
                document_integrity_score={"overall_score": overall, "metrics": metrics},
                document_type=str((deterministic_output or {}).get("document_type", "unknown") or "unknown"),
                executive_summary="LLM analysis was unavailable. Results are based on deterministic checks only.",
                risk_assessment="Unable to perform second-layer AI validation. Review deterministically detected issues.",
                recommendations=(deterministic_output or {}).get("recommendations", []) or [],
                issues_observations=(deterministic_output or {}).get("issues", []) or [],
            )
            return fallback, ""

        chunk_size = max(1000, int(getattr(settings, "LLM_CHUNK_SIZE", 6000)))
        overlap = max(0, int(getattr(settings, "LLM_CHUNK_OVERLAP", 500)))
        chunks = _chunk_text(document_text or "", chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            chunks = [_Chunk(text=document_text or "", start=0, end=len(document_text or ""))]

        parts: list[LLMStrictQualityResponse] = []
        raw_parts: list[str] = []
        for idx, ch in enumerate(chunks, start=1):
            logger.info("LLM strict quality chunk %d/%d (chars %d-%d)", idx, len(chunks), ch.start, ch.end)
            prompt = STRICT_QUALITY_PROMPT.format(
                deterministic_output_json=det_json,
                document_text=(ch.text or ""),
            )
            content, raw = self._call_llm(
                prompt,
                system_prompt=(
                    "You are a strict evaluator. Return valid JSON only. "
                    "Do not output markdown or extra keys."
                ),
                max_tokens=2500,
            )
            parsed = self._parse_strict_quality_response(content)
            parsed = self._normalize_strict_quality_response(parsed, deterministic_output)
            parts.append(parsed)
            raw_parts.append(raw)

        # Merge parts
        merged_doc_type_counts: dict[str, int] = {}
        merged_domain_counts: dict[str, int] = {}
        for p in parts:
            dt = (p.document_type or "").strip()
            if dt:
                merged_doc_type_counts[dt] = merged_doc_type_counts.get(dt, 0) + 1
            
            dm = (getattr(p, "banking_domain", None) or "").strip()
            if dm and dm.lower() not in {"null", "none"}:
                merged_domain_counts[dm] = merged_domain_counts.get(dm, 0) + 1
                
        merged_doc_type = max(merged_doc_type_counts, key=merged_doc_type_counts.get) if merged_doc_type_counts else ""
        merged_banking_domain = max(merged_domain_counts, key=merged_domain_counts.get) if merged_domain_counts else None

        merged_exec = max((p.executive_summary or "" for p in parts), key=len, default="")
        merged_risk = max((p.risk_assessment or "" for p in parts), key=len, default="")

        recs: list[str] = []
        for p in parts:
            recs = self._merge_recommendations(recs, p.recommendations or [])

        issues: list[IssueSchema] = []
        for p in parts:
            issues = self._merge_issues(issues, p.issues_observations or [])

        # Merge metric scores by averaging across chunks; keep the longest reasoning.
        det_metrics = (deterministic_output or {}).get("metrics", {})
        metric_names = ("completeness", "accuracy", "consistency", "validity", "timeliness", "uniqueness")
        merged_metrics: dict[str, dict] = {}
        for mn in metric_names:
            scores: list[float] = []
            best_reason = ""
            for p in parts:
                md = (p.document_integrity_score.metrics or {}).get(mn)
                if md is None:
                    continue
                try:
                    if md.score is not None:
                        scores.append(float(md.score))
                except (ValueError, TypeError):
                    logger.debug("Failed to parse metric score: %s", md.score)
                r = (md.reasoning or "").strip()
                if len(r) > len(best_reason):
                    best_reason = r
            try:
                det_score = float((det_metrics.get(mn, {}) or {}).get("score", 0))
            except Exception:
                det_score = 0.0
            avg = sum(scores) / len(scores) if scores else det_score
            merged_metrics[mn] = {
                "score": round(max(0.0, min(100.0, avg)), 1),
                "deterministic_score": round(max(0.0, min(100.0, det_score)), 1),
                "reasoning": best_reason,
            }

        overall = round(sum(m["score"] for m in merged_metrics.values()) / 6.0, 1) if merged_metrics else 0.0
        merged = LLMStrictQualityResponse(
            document_integrity_score={"overall_score": overall, "metrics": merged_metrics},
            document_type=merged_doc_type,
            banking_domain=merged_banking_domain,
            executive_summary=merged_exec,
            risk_assessment=merged_risk,
            recommendations=recs,
            issues_observations=issues,
            important_constraints=(parts[0].important_constraints if parts else []),
        )
        return merged, json.dumps({"chunks": raw_parts})

    def consolidate_recommendations_and_issues(
        self,
        deterministic_output: dict,
        llm_output: dict,
    ) -> tuple[LLMConsolidationResponse, str]:
        """Final consolidation pass for recommendations + issues into a single-tab set."""
        def _coerce_issue_list(value: object) -> list[IssueSchema]:
            items = value if isinstance(value, list) else []
            coerced: list[IssueSchema] = []
            for it in items:
                if not it:
                    continue
                try:
                    issue = it if isinstance(it, IssueSchema) else IssueSchema(**dict(it))
                except Exception:
                    continue
                coerced.append(issue)
            return coerced

        det_recs = (deterministic_output or {}).get("recommendations", []) or []
        llm_recs = (llm_output or {}).get("recommendations", []) or []

        det_issues_raw = (
            (deterministic_output or {}).get("issues_observations")
            or (deterministic_output or {}).get("issues")
            or []
        )
        llm_issues_raw = (
            (llm_output or {}).get("issues_observations")
            or (llm_output or {}).get("issues")
            or []
        )

        det_issues = _coerce_issue_list(det_issues_raw)
        llm_issues = _coerce_issue_list(llm_issues_raw)

        def _consolidate_locally() -> LLMConsolidationResponse:
            recs = self._merge_recommendations(det_recs, llm_recs)
            issues = self._merge_issues(det_issues, llm_issues)
            severity_rank = {"critical": 0, "warning": 1, "good": 2}
            issues_sorted = sorted(
                issues,
                key=lambda i: (
                    severity_rank.get((i.severity or "").lower(), 99),
                    (i.metric_dimension or "").lower(),
                    (i.field_name or "").lower(),
                    (i.issue_type or "").lower(),
                ),
            )
            return LLMConsolidationResponse(
                recommendations=recs[:12],
                issues_observations=issues_sorted[:30],
            )

        # Deterministic fallback: merge + dedupe locally
        if not self.is_configured:
            return _consolidate_locally(), ""

        # Build minimal prompt payloads (avoid sending extracted_fields / other context)
        def _issue_for_prompt(issue: IssueSchema) -> dict:
            return {
                "field_name": _limit_str(issue.field_name or "", 80),
                "issue_type": _limit_str(issue.issue_type or "", 50),
                "description": _limit_str(issue.description or "", 400),
                "severity": (issue.severity or "warning").lower(),
                "metric_dimension": _limit_str(issue.metric_dimension or "", 80),
            }

        det_payload = {
            "recommendations": [
                _limit_str(str(r), 240) for r in det_recs if isinstance(r, str) and r.strip()
            ][:20],
            "issues_observations": [_issue_for_prompt(i) for i in det_issues][:50],
        }
        llm_payload = {
            "recommendations": [
                _limit_str(str(r), 240) for r in llm_recs if isinstance(r, str) and r.strip()
            ][:20],
            "issues_observations": [_issue_for_prompt(i) for i in llm_issues][:50],
        }

        det_json = json.dumps(det_payload, indent=2, default=str)
        llm_json = json.dumps(llm_payload, indent=2, default=str)

        # NOTE: This prompt contains literal JSON braces; avoid str.format().
        prompt = (
            CONSOLIDATE_RECS_ISSUES_PROMPT
            .replace("{deterministic_output_json}", det_json)
            .replace("{llm_output_json}", llm_json)
        )
        try:
            content, raw = self._call_llm(
                prompt,
                system_prompt="You are a strict consolidation engine. Return valid JSON only.",
                max_tokens=2000,
            )
        except Exception as exc:
            logger.warning("Consolidation LLM call failed; falling back to local merge: %s", exc)
            return _consolidate_locally(), ""

        try:
            parsed = self._parse_consolidation_response(content)
            parsed.recommendations = (parsed.recommendations or [])[:12]
            parsed.issues_observations = (parsed.issues_observations or [])[:30]
            return parsed, raw
        except Exception as exc:
            logger.warning("Consolidation response parse failed; falling back to local merge: %s", exc)
            return _consolidate_locally(), raw

    # ── Agent 3: Domain Specialist ─────────────────────────────────────────

    def evaluate_domain_specialist(
        self,
        text: str,
        domain: str,
        fields: dict,
        deterministic_baselines: Optional[dict[str, float]] = None,
    ) -> dict:
        """
        Agent 3 — Deep domain-specific evaluation with regulatory citations.

        Uses a domain-specific prompt that references the actual regulations
        (FATF Rec 10, AML5D, UCC Article 9, 12 CFR §329.20, etc.).

        Args:
            text: Full document text. This method processes the full document by
                running the specialist prompt across every chunk and merging results.
            domain: Detected banking domain string.
            fields: Already-extracted fields dict from Agent 2.

        Returns:
            Dict with metric_code keys and {score, reasoning} values.
        """
        prompt_template = DOMAIN_SPECIALIST_PROMPTS.get(domain)
        if not prompt_template:
            logger.warning("No specialist prompt for domain: %s", domain)
            return {}

        # Keep the specialist prompt compact: include only the first ~20 non-empty fields.
        limited_items: list[tuple[str, object]] = []
        for k, v in (fields or {}).items():
            if v is None or v == "" or v == [] or v == {}:
                continue
            limited_items.append((k, v))
            if len(limited_items) >= 20:
                break

        fields_summary = json.dumps(dict(limited_items), indent=2, default=str)
        baselines_summary = json.dumps(deterministic_baselines or {}, indent=2, default=str)

        # Run the specialist prompt across ALL chunks to ensure full-document coverage.
        chunk_size = max(1000, int(getattr(settings, "LLM_CHUNK_SIZE", 6000)))
        overlap = max(0, int(getattr(settings, "LLM_CHUNK_OVERLAP", 500)))
        chunks = _chunk_text(text or "", chunk_size=chunk_size, overlap=overlap)

        # If small enough, do a single specialist call with the full text.
        if len(chunks) <= 1:
            chunks = [_Chunk(text=text or "", start=0, end=len(text or ""))]

        merged: dict = {}
        specialist_notes: list[str] = []

        for idx, ch in enumerate(chunks, start=1):
            chunk_label = f"[Chunk {idx}/{len(chunks)} | chars {ch.start}-{ch.end}]\n"
            # NOTE: Domain specialist prompt templates include literal JSON blocks.
            # Using str.format() would treat JSON braces as placeholders and can
            # raise KeyError (e.g., on "score"). Do targeted replacement instead.
            prompt = (
                prompt_template
                .replace("{document_text}", chunk_label + (ch.text or ""))
                .replace("{fields_summary}", fields_summary)
                .replace("{deterministic_baselines}", baselines_summary)
            )
            try:
                content, _ = self._call_llm(
                    prompt,
                    system_prompt="You are a banking compliance specialist. Return valid JSON only.",
                    max_tokens=1500,
                )
                cleaned = content.strip().strip("```json").strip("```").strip()
                data = AzureFoundryLLMService._safe_parse_json(cleaned)
            except Exception as e:
                logger.warning("Domain specialist chunk %d/%d failed for %s: %s", idx, len(chunks), domain, e)
                continue

            if not isinstance(data, dict):
                continue

            # Merge per-metric: choose the highest score seen; keep the most detailed reasoning.
            for k, v in data.items():
                if k == "specialist_notes":
                    if isinstance(v, str) and v.strip():
                        specialist_notes.append(v.strip())
                    continue

                # Normalise shapes: either {"score":...,"reasoning":...} or raw score.
                if isinstance(v, dict):
                    score = v.get("score")
                    reasoning = v.get("reasoning", "")
                    evidence = v.get("evidence")
                else:
                    score = v
                    reasoning = ""
                    evidence = None

                try:
                    score_f = float(score)
                except Exception:
                    continue

                prev = merged.get(k)
                if not isinstance(prev, dict):
                    prev_score = None
                    prev_reasoning = ""
                    prev_evidence: list[str] = []
                else:
                    prev_score = prev.get("score")
                    prev_reasoning = prev.get("reasoning", "") or ""
                    prev_evidence = prev.get("evidence") if isinstance(prev.get("evidence"), list) else []

                new_evidence: list[str] = []
                if isinstance(evidence, list):
                    for item in evidence:
                        s = str(item).strip()
                        if not s:
                            continue
                        new_evidence.append(s[:120])

                merged_evidence: list[str] = []
                seen_ev: set[str] = set()
                for ev in (prev_evidence + new_evidence):
                    if ev in seen_ev:
                        continue
                    seen_ev.add(ev)
                    merged_evidence.append(ev)
                    if len(merged_evidence) >= 3:
                        break

                if prev_score is None or score_f > float(prev_score):
                    merged[k] = {
                        "score": int(round(score_f)),
                        "reasoning": (reasoning or "").strip(),
                        "evidence": merged_evidence,
                    }
                else:
                    # Keep longer reasoning when scores tie or are lower.
                    if isinstance(reasoning, str) and len(reasoning.strip()) > len(prev_reasoning):
                        merged[k] = {
                            "score": int(round(float(prev_score))),
                            "reasoning": reasoning.strip(),
                            "evidence": merged_evidence,
                        }
                    else:
                        # Preserve prior score/reasoning but still merge evidence.
                        merged[k] = {
                            "score": int(round(float(prev_score))),
                            "reasoning": prev_reasoning,
                            "evidence": merged_evidence,
                        }

        if specialist_notes:
            # De-dupe while preserving order.
            seen: set[str] = set()
            uniq = []
            for n in specialist_notes:
                if n in seen:
                    continue
                seen.add(n)
                uniq.append(n)
            merged["specialist_notes"] = "\n".join(uniq)[:2000]

        return merged

    # ── Agent 4: Challenge & Confidence Validation ─────────────────────────

    def challenge_and_validate(
        self,
        doc_type: str,
        det_scores: dict,
        llm_scores: dict,
        domain_scores: dict | None = None,
    ) -> dict:
        """
        Agent 4 — Lightweight score validation and confidence scoring.

        For metrics where |det - llm| ≤ 20, confidence is computed
        deterministically without an LLM call. Only when high discrepancies
        exist does it invoke the LLM for a challenge review.

        Returns:
            Dict with keys: confidence (dict metric→float), flags (list), overall_confidence (float).
        """
        DISCREPANCY_THRESHOLD = 20
        confidence: dict[str, float] = {}
        high_discrepancy_pairs: list[tuple[str, float, float]] = []

        all_metrics = set(det_scores) | set(llm_scores)
        for metric in all_metrics:
            d = det_scores.get(metric, 0) or 0
            l = llm_scores.get(metric, 0) or 0
            delta = abs(d - l)
            conf = max(0.0, 1.0 - delta / 100.0)
            confidence[metric] = round(conf, 2)
            if delta > DISCREPANCY_THRESHOLD:
                high_discrepancy_pairs.append((metric, d, l))

        flags: list[str] = []
        overall_confidence = round(
            sum(confidence.values()) / len(confidence) if confidence else 1.0, 2
        )

        # Only call LLM if there are high-discrepancy metrics (saves latency + cost)
        if high_discrepancy_pairs and self.is_configured:
            try:
                prompt = CHALLENGE_PROMPT.format(
                    doc_type=doc_type,
                    det_scores=json.dumps(det_scores),
                    llm_scores=json.dumps(llm_scores),
                    domain_scores=json.dumps(domain_scores or {}),
                )
                content, _ = self._call_llm(prompt, max_tokens=800)
                cleaned = content.strip().strip("```json").strip("```").strip()
                data = AzureFoundryLLMService._safe_parse_json(cleaned)
                # Override confidence for challenged metrics
                for metric, conf_val in (data.get("confidence") or {}).items():
                    confidence[metric] = float(conf_val)
                flags = data.get("flags", [])
                overall_confidence = float(data.get("overall_confidence", overall_confidence))
            except Exception as e:
                logger.warning("Challenge agent LLM call failed: %s", e)
                for metric, d, l in high_discrepancy_pairs:
                    flags.append(f"{metric}: deterministic={d} vs LLM={l} (delta={abs(d - l)})")

        return {
            "confidence": confidence,
            "flags": flags,
            "overall_confidence": overall_confidence,
        }

    # ── Agent 5: Remediation Plan ──────────────────────────────────────────

    def generate_remediation(
        self,
        doc_type: str,
        banking_domain: Optional[str],
        issues: list,
        low_metrics: list,
    ) -> list[dict]:
        """
        Agent 5 — Generate specific, regulation-aware remediation steps.

        Args:
            doc_type: Document type string.
            banking_domain: Detected banking domain, or None.
            issues: List of IssueSchema dicts (or objects with field_name, description, severity).
            low_metrics: List of dicts with keys name and score (score < 75).

        Returns:
            List of remediation step dicts with keys: priority, action, regulation, deadline, responsible_party.
        """
        if not self.is_configured:
            return []

        def _fmt_issue(issue: object | dict) -> str:
            if isinstance(issue, dict):
                return f"  [{issue.get('severity','?')}] {issue.get('field_name','?')}: {issue.get('description','?')}"
            return f"  [{getattr(issue,'severity','?')}] {getattr(issue,'field_name','?')}: {getattr(issue,'description','?')}"

        issues_summary = "\n".join(_fmt_issue(i) for i in (issues or [])[:10]) or "None identified"
        low_metrics_summary = "\n".join(
            f"  {m.get('name','?')}: {m.get('score','?')}/100" for m in (low_metrics or [])[:8]
        ) or "None"

        prompt = REMEDIATION_PROMPT.format(
            doc_type=doc_type,
            banking_domain=banking_domain or "N/A",
            issues_summary=issues_summary,
            low_metrics_summary=low_metrics_summary,
        )
        try:
            content, _ = self._call_llm(
                prompt,
                system_prompt="You are a banking compliance remediation specialist. Return valid JSON only.",
                max_tokens=1500,
            )
            cleaned = content.strip().strip("```json").strip("```").strip()
            if not cleaned:
                logger.warning("Empty remediation response after cleaning")
                return []
            try:
                data = AzureFoundryLLMService._safe_parse_json(cleaned)
            except json.JSONDecodeError as e:
                logger.warning("Failed to parse remediation JSON: %s", e)
                return []

            steps = data.get("remediation_steps", [])
            if not isinstance(steps, list):
                logger.warning("Remediation steps not a list: %s", type(steps))
                return []

            normalized: list[dict] = []
            for item in steps:
                if not isinstance(item, dict):
                    continue

                pr_raw = item.get("priority")
                try:
                    pr = int(pr_raw) if pr_raw is not None else 0
                except (ValueError, TypeError):
                    pr = 0

                action = str(item.get("action", "")).strip()
                if not action:  # Skip empty actions early
                    continue
                
                normalized.append(
                    {
                        "priority": pr,
                        "action": action,
                        "regulation": str(item.get("regulation", "")).strip(),
                        "deadline": str(item.get("deadline", "")).strip(),
                        "responsible_party": str(item.get("responsible_party", "")).strip(),
                    }
                )

            # Sort by priority and action name
            normalized.sort(key=lambda s: (s.get("priority") or 0, s.get("action")))

            # Ensure priorities are 1..N sequential for display.
            for idx, step in enumerate(normalized, start=1):
                step["priority"] = idx

            return normalized[:6]
        except Exception as e:
            logger.warning("Remediation agent failed: %s", e)
            return []



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
            data = AzureFoundryLLMService._safe_parse_json(cleaned)
        except json.JSONDecodeError as e:
            logger.error("LLM returned invalid JSON: %s", str(e))
            raise ValueError(f"LLM response is not valid JSON: {str(e)}")

        try:
            return LLMExtractionResponse(**data)
        except Exception as e:
            logger.error("LLM response failed schema validation: %s", str(e))
            raise ValueError(f"LLM response failed schema validation: {str(e)}")

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
