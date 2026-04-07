"""
Banking Rule Engine.

Deterministic calculations for banking-domain-specific quality metrics.
Implements the 70/30 Rule/LLM blending logic for each banking category.

Supported domains:
  - Customer Onboarding (KYC/AML)
  - Loan & Credit Documentation
  - Treasury & Liquidity Reports
  - Regulatory & Compliance Filings
  - Investment Banking & M&A
  - Fraud & Investigation Records
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Banking Rule Engine
# ─────────────────────────────────────────────────────────────────────────────

class BankingRuleEngine:
    """
    Deterministic banking metric evaluator.

        Each calculate_* method returns a 5-tuple:
            - blended_score (0–100) using: S = (D * 0.7) + (L_used * 0.3)
            - reasoning string (deterministic trace)
            - deterministic_score (D)
            - llm_score_raw (optional)
            - llm_score_used (L_used) after guardrail clamping

    The evaluate_domain() dispatcher activates the correct set of metrics
    based on the detected banking domain.
    """

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _blend(
        det_score: float,
        llm_score: Optional[float],
        *,
        max_llm_delta: float = 25.0,
        allow_override: bool = False,
    ) -> tuple[float, float]:
        """Apply 70/30 blending with a guardrail against unjustified LLM overrides.

        Returns:
            (blended_score, llm_score_used)
        """
        det_s = float(det_score)
        if llm_score is None:
            return max(0.0, min(100.0, det_s)), max(0.0, min(100.0, det_s))

        llm_s_raw = float(llm_score)
        llm_s_used = llm_s_raw
        if not allow_override:
            lo = det_s - float(max_llm_delta)
            hi = det_s + float(max_llm_delta)
            llm_s_used = max(lo, min(hi, llm_s_raw))

        blended = (det_s * 0.7) + (llm_s_used * 0.3)
        blended = max(0.0, min(100.0, blended))
        return blended, max(0.0, min(100.0, llm_s_used))

    def _keyword_metric(
        self,
        document_text: str,
        *,
        positive_patterns: list[str],
        llm_score: Optional[float] = None,
        negative_patterns: Optional[list[str]] = None,
        negative_penalty: float = 10.0,
        allow_override: bool = False,
    ) -> tuple[float, int, int, float, float]:
        """Generic deterministic keyword metric helper.

        Returns blended score details and marker counts for reasoning.
        """
        text_lower = (document_text or "").lower()
        positives = sum(1 for p in (positive_patterns or []) if re.search(p, text_lower))
        total = max(len(positive_patterns or []), 1)
        det_score = (positives / total) * 100

        negatives = 0
        if negative_patterns:
            negatives = sum(1 for p in negative_patterns if re.search(p, text_lower))
            det_score = max(0.0, det_score - negatives * float(negative_penalty))

        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)
        return (
            round(blended, 1),
            positives,
            negatives,
            round(det_score, 1),
            round(llm_used, 1),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # KYC / AML Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_boti(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Beneficial Ownership Transparency Index (BOTI).

        BOTI = (NaturalOwners_Identified / RequiredOwners_OrgChart) × 100

        Deterministic logic: counts verified ID evidence markers versus the
        number of beneficial-owner references in the document.
        """
        text_lower = document_text.lower()

        # Evidence of a verified identity document
        id_patterns = [
            r"\bpassport\b",
            r"\bgovernment[\s\-]{0,5}id\b",
            r"\bssn\b",
            r"\bsocial security\b",
            r"\bdriver[\s\-]{0,5}licen[sc]e\b",
            r"\bnational id\b",
            r"\bbiometric\b",
            r"\bverified\b.{0,20}\bowner\b",
        ]
        id_found = sum(1 for p in id_patterns if re.search(p, text_lower))

        # Signals of required beneficial owners in the org/corporate structure
        owner_req_patterns = [
            r"\bbeneficial owner\b",
            r"\bultimate beneficial owner\b",
            r"\b25\s*%\b",
            r"\bcontrolling\s+(?:person|shareholder|interest)\b",
            r"\bownership\s+(?:structure|chart|diagram)\b",
        ]
        owners_required = max(
            sum(1 for p in owner_req_patterns if re.search(p, text_lower)),
            1,
        )

        det_score = min(100.0, (id_found / owners_required) * 100)
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Identified {id_found} natural-owner ID evidence marker(s) against "
            f"{owners_required} required beneficial-owner reference(s). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_iess(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Identity Evidence Strength Score (IESS).

        IESS = Σ(FeatureWeight_i × Confidence_i) for identity security features.

        Features checked: MRZ checksum, hologram, face/biometric match,
        OCR checksum, expiry date, document number.
        """
        text_lower = document_text.lower()

        # Feature name → (regex pattern, weight)
        feature_weights: dict[str, tuple[str, float]] = {
            "mrz_checksum": (r"\bmrz\b|\bmachine readable zone\b|\btd[123]\b", 1.0),
            "hologram": (r"\bhologram\b|\bsecurity feature\b|\blatent image\b", 1.0),
            "face_match": (
                r"\bfacial match\b|\bbiometric match\b|\bface verification\b|\bphoto match\b",
                1.0,
            ),
            "ocr_checksum": (r"\bchecksum\b|\bocr confidence\b|\bverified scan\b", 0.75),
            "expiry": (r"\bexpiry\b|\bexpiration\b|\bvalid until\b|\bdate of expiry\b", 0.75),
            "doc_number": (r"\bdocument number\b|\bpassport number\b|\bid number\b", 0.5),
        }

        max_possible = sum(w for _, w in feature_weights.values())
        achieved = sum(
            w
            for (pattern, w) in feature_weights.values()
            if re.search(pattern, text_lower)
        )

        det_score = (achieved / max_possible) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Identity feature analysis: {achieved:.2f}/{max_possible:.2f} weighted "
            f"feature points detected (MRZ, hologram, biometric, OCR patterns). "
            f"Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_spec(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Sanctions/PEP Screening Evidence Coverage (SPEC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bsanctions? screening\b|\bscreened against\b",
                r"\bpep\b|\bpolitically exposed\b",
                r"\bscreening date\b|\brun date\b",
                r"\bsource list\b|\bofac\b|\beu sanctions\b|\bun sanctions\b",
                r"\bresult\b|\bmatch\b|\bno hit\b",
                r"\breviewer\b|\bsign[-\s]?off\b|\bapproved by\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/6 sanctions/PEP evidence markers (date, lists, result, sign-off). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_cedj(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """CDD/EDD Trigger Justification Quality (CEDJ)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bcdd\b|\bcustomer due diligence\b",
                r"\bedd\b|\benhanced due diligence\b",
                r"\bhigh[-\s]?risk jurisdiction\b|\bsanctioned country\b",
                r"\badverse media\b|\bnegative news\b",
                r"\bjustification\b|\brationale\b|\btrigger\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/5 CDD/EDD trigger and rationale markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_soft(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Source-of-Funds Traceability (SOFT)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bsource of funds\b|\bsource of wealth\b",
                r"\bpayslip\b|\bsalary slip\b",
                r"\bbank statement\b",
                r"\bcontract\b|\bsale agreement\b",
                r"\bevidence\b|\bsupporting document\b|\battachment\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/5 source-of-funds traceability markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_avs(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Address Verification Strength (AVS)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bproof of address\b|\baddress verification\b",
                r"\butility bill\b|\bbank statement\b|\btenancy\b",
                r"\bissued on\b|\bstatement date\b|\brecent\b",
                r"\baddress match\b|\bmatches customer\b|\bverified address\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 address verification strength markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_rre(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Risk Rating Explainability (RRE)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\brisk rating\b|\brisk score\b",
                r"\bjurisdiction\b",
                r"\bproduct\b",
                r"\bchannel\b",
                r"\bownership\s+complexity\b|\bcomplex ownership\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/5 risk-rating explainability driver markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    # ─────────────────────────────────────────────────────────────────────────
    # Loan & Credit Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_cpi(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Collateral Perfection Index (CPI).

        CPI = (Validated Legal Clauses Found / Required Perfection Clauses) × 100

        Checks for 10 standard clauses required to legally perfect a security
        interest under US/international banking law.
        """
        text_lower = document_text.lower()

        required_clauses: dict[str, str] = {
            "granting_clause": r"\bgranting clause\b|\bgrants[^\n]{0,40}security interest\b|\bhereby grants\b",
            "legal_description": r"\blegal description\b|\bproperty description\b",
            "lien_perfection": r"\blien perfection\b|\bperfected lien\b|\bperfect(?:ion|ed)\b",
            "consideration": r"\bgood and valuable consideration\b|\bconsideration of\b|\bfor value received\b",
            "identified_parties": r"\bborrower\b.{0,60}\blender\b|\bsecured party\b|\bdebtor\b.{0,60}\bsecured party\b",
            "execution_date": r"\bexecution date\b|\bdated as of\b|\beffective date\b",
            "governing_law": r"\bgoverning law\b|\blaws of the state\b|\bjurisdiction\b",
            "default_provisions": r"\bevent of default\b|\bdefault\b.{0,40}\bremedies\b",
            "signature": r"\b(?:sign(?:ed|ature)|executed by|authorized signatory)\b",
            "notarization": r"\bnotari[sz]e[d]?\b|\backnowledgment\b|\bnotary public\b",
        }

        found = sum(1 for p in required_clauses.values() if re.search(p, text_lower))
        det_score = (found / len(required_clauses)) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Found {found}/{len(required_clauses)} required legal perfection clauses. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_ccts(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Covenant Compliance Transparency Score (CCTS).

        CCTS = (Traceable Data Points for Ratio / Total Data Points Required) × 100

        Checks presence of 8 standard financial data points required
        for covenant calculations.
        """
        text_lower = document_text.lower()

        required_data: dict[str, str] = {
            "ebitda": r"\bebitda\b|\bearnings before interest[^\n]{0,20}tax\b",
            "total_debt": r"\btotal debt\b|\bdebt level\b|\boutstanding debt\b",
            "net_revenue": r"\bnet revenue\b|\bnet sales\b|\btotal revenue\b",
            "interest_expense": r"\binterest expense\b|\binterest payment\b",
            "leverage_ratio": r"\bleverage ratio\b|\bdebt[\s/\-]{0,5}ebitda\b|\btd[\s/]{0,5}ebitda\b",
            "current_ratio": r"\bcurrent ratio\b|\bcurrent assets[\s/]{0,5}current liabilities\b",
            "coverage_ratio": r"\bdebt service coverage\b|\binterest coverage\b|\bdscr\b",
            "covenant_threshold": r"\bcovenant\b|\bfinancial covenant\b|\bcompliance certificate\b",
        }

        found = sum(1 for p in required_data.values() if re.search(p, text_lower))
        det_score = (found / len(required_data)) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Found {found}/{len(required_data)} required financial data points for "
            f"covenant compliance transparency. Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_rifc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Rate Index & Fallback Correctness (RIFC)."""
        score, hits, negatives, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bsofr\b|\bbase rate\b",
                r"\bfallback\b|\breplacement rate\b",
                r"\bbenchmark transition\b|\brate switch\b",
            ],
            negative_patterns=[r"\blibor\b"],
            negative_penalty=25.0,
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/3 rate-index/fallback markers and {negatives} LIBOR-only flag(s). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_eac(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Execution & Authority Completeness (EAC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bsignature\b|\bsigned by\b",
                r"\bauthorized signatory\b|\bauthorized representative\b",
                r"\bboard resolution\b|\bboard approval\b",
                r"\bexecution date\b|\bdated as of\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 execution and authority markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_rsi(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Repayment Schedule Integrity (RSI)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\brepayment schedule\b|\bamorti[sz]ation\b",
                r"\btenor\b|\bmaturity date\b",
                r"\bpayment frequency\b|\bmonthly\b|\bquarterly\b",
                r"\binstallment\b|\bprincipal and interest\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 repayment schedule integrity markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_bgic(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Borrower/Guarantor Identification Consistency (BGIC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bborrower\b",
                r"\bguarantor\b",
                r"\bcompany registration\b|\bentity id\b|\blei\b",
                r"\bconsistent\b|\bmatches across\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 borrower/guarantor consistency markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_cvr(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Collateral Valuation Recency (CVR)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bappraisal\b|\bvaluation report\b",
                r"\bvaluation date\b|\bassessed on\b",
                r"\bwithin policy\b|\bwithin \d+ (?:days|months)\b|\brecertification\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/3 collateral valuation recency markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    # ─────────────────────────────────────────────────────────────────────────
    # Treasury & Liquidity Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_hec(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        HQLA Eligibility Confidence (HEC).

        HEC = 1 − (Assets with Encumbrance Flags / Total Assets in Buffer)

        Scans asset listings for encumbrance markers relative to HQLA references.
        """
        text_lower = document_text.lower()

        hqla_patterns = [
            r"\bhqla\b",
            r"\bhigh[\s\-]quality liquid asset\b",
            r"\blevel 1\b.{0,20}\basset\b",
            r"\blevel 2[ab]?\b.{0,20}\basset\b",
            r"\bliquidity buffer\b",
            r"\bsovereign bond\b",
            r"\bcentral bank\b.{0,20}\breserve\b",
        ]
        encumbrance_patterns = [
            r"\bpledged\b",
            r"\bencumbered\b",
            r"\brestricted\b",
            r"\bhaircut\b",
            r"\bcollateral posted\b",
            r"\brepurchase agreement\b|\brepo\b",
        ]

        total_hqla = max(
            sum(len(re.findall(p, text_lower)) for p in hqla_patterns), 1
        )
        encumbered = sum(len(re.findall(p, text_lower)) for p in encumbrance_patterns)

        ratio = min(encumbered / total_hqla, 1.0)
        det_score = (1 - ratio) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Detected {encumbered} encumbrance flag(s) vs {total_hqla} HQLA reference(s). "
            f"HEC = 1 − ({encumbered}/{total_hqla}) = {det_score:.0f}. "
            f"Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_isrr(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Inter-System Reconciliation Ratio (ISRR).

        ISRR = (1 − |Doc Balance − System Balance| / System Balance) × 100

        Checks for reconciliation markers and penalises discrepancy flags.
        """
        text_lower = document_text.lower()

        reconciliation_markers = [
            r"\breconcili(?:ation|ed|ing)\b",
            r"\bbalances agree\b|\bno discrepan\w+\b",
            r"\bconfirmed balance\b|\bverified balance\b",
            r"\baudit trail\b",
            r"\bcore banking\b|\bsystem of record\b|\bgeneral ledger\b",
        ]
        discrepancy_markers = [
            r"\bdiscrepan(?:cy|cies)\b",
            r"\bunreconciled\b|\bbreakage\b",
            r"\bmismatch\b",
            r"\bvariance\b.{0,20}\bbalance\b|\bunexplained\b.{0,20}\bdifference\b",
        ]

        reconciled = sum(
            1 for p in reconciliation_markers if re.search(p, text_lower)
        )
        discrepancies = sum(
            1 for p in discrepancy_markers if re.search(p, text_lower)
        )

        base_score = (reconciled / len(reconciliation_markers)) * 100
        det_score = max(0.0, base_score - discrepancies * 15)
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Found {reconciled} reconciliation marker(s) and "
            f"{discrepancies} discrepancy flag(s). "
            f"Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_ctta(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Cut-off Time & Timestamp Alignment (CTTA)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bcut[-\s]?off time\b",
                r"\btimestamp\b|\btime stamp\b",
                r"\bsource system time\b|\bdata as of\b",
                r"\baligned\b|\bmatch(?:es|ed)?\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 cut-off and timestamp alignment markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_ssc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Stress Scenario Coverage (SSC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bstress scenario\b|\bstress test\b",
                r"\bassumption\b|\bmodel assumption\b",
                r"\bresult\b|\boutcome\b|\bimpact\b",
                r"\bbaseline\b|\badverse\b|\bseverely adverse\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 stress-scenario coverage markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_iocc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Inflow/Outflow Classification Completeness (IOCC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\binflow\b|\bcash inflow\b",
                r"\boutflow\b|\bcash outflow\b",
                r"\bcategory\b|\bclassification\b",
                r"\boperational\b|\bwholesale\b|\bsecured funding\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 inflow/outflow classification markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_lbdq(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Limit Breach Disclosure Quality (LBDQ)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\blimit breach\b|\bbreach detected\b",
                r"\baction taken\b|\bmitigation\b|\bremediation\b",
                r"\bapproval\b|\bapproved by\b",
                r"\bescalation\b|\bexception\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 limit-breach disclosure quality markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_sscov(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Source System Coverage (SSCOV)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bgeneral ledger\b|\bgl\b",
                r"\bcore banking\b|\bcore system\b",
                r"\btreasury system\b|\btreasury platform\b",
                r"\bsystem of record\b|\bsource system\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 source-system coverage markers (GL/core/treasury). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    # ─────────────────────────────────────────────────────────────────────────
    # Regulatory & Compliance Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_rmp(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Regulatory Mapping Precision (RMP).

        RMP = (Verified Correct Reg Refs / Total Reg Refs in Doc) × 100

        Distinguishes current valid regulation references from obsolete ones
        (e.g., LIBOR, old CRD versions).
        """
        text_lower = document_text.lower()

        def _flatten(value) -> list[str]:
            if value is None:
                return []
            if isinstance(value, str):
                return [value]
            if isinstance(value, dict):
                flattened: list[str] = []
                for nested in value.values():
                    flattened.extend(_flatten(nested))
                return flattened
            if isinstance(value, (list, tuple, set)):
                flattened: list[str] = []
                for nested in value:
                    flattened.extend(_flatten(nested))
                return flattened
            return [str(value)]

        structured_text = "\n".join(_flatten(fields)).lower()
        combined_text = f"{text_lower}\n{structured_text}".strip()

        # IMPORTANT: RMP is about *explicit regulation/taxonomy citations*, not generic
        # compliance language (e.g., "data governance" or "retention policy"). Keeping
        # patterns specific prevents false inflation on policy documents.
        valid_refs = [
            # Basel / BCBS
            r"\bbcbs\s*239\b",
            r"\bbcbs\b.{0,30}\bprinciple\b",
            r"\bbasel\s*(?:ii|iii|iv)\b",
            # EU banking regs
            r"\beba\s+(?:rts|its)\b",
            r"\bcrr\s*(?:2|3)?\b",
            r"\bcrd\s*v\b",
            r"\b(?:crr|crd)\b.{0,30}\barticle\b",
            # US banking regs
            r"\b12\s*cfr\b",
            r"\bdodd[\s\-]frank\b",
            # Filing / disclosure programs
            r"\bpillar\s*3\b",
            r"\bicaap\b|\bilaap\b",
            # AML-focused regs (still relevant in compliance filings)
            r"\bfatf\b",
            r"\b(aml\s*5d|amld)\b|\banti[\s\-]money laundering directive\b",
        ]
        obsolete_refs = [
            r"\blibor\b",
            r"\bcrd\s*(?:i|ii|iii|iv)\b",
            r"\bbasel\s*ii\b",
        ]

        valid_found = sum(1 for p in valid_refs if re.search(p, combined_text))
        obsolete_found = sum(1 for p in obsolete_refs if re.search(p, combined_text))

        structured_reference_fields = [
            "related_regulators",
            "related_law",
            "establishment_reference",
            "issuing_body",
            "parent_authority",
        ]
        structured_hits = sum(1 for key in structured_reference_fields if fields.get(key))

        total_valid = valid_found + structured_hits
        total_refs = max(total_valid + obsolete_found, 1)

        det_score = (total_valid / total_refs) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Found {valid_found} text reference pattern(s), {structured_hits} structured regulatory "
            f"reference field(s), and {obsolete_found} obsolete reference(s) "
            f"({total_refs} total evidence points). Deterministic: {det_score:.0f}. "
            f"Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_dli(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        BCBS 239 Data Lineage Integrity (DLI).

        DLI = (Fields with Automated Lineage / Total Critical Risk Fields) × 100

        Rewards automated data lineage markers; penalises manual intervention
        indicators such as spreadsheet references.
        """
        text_lower = document_text.lower()

        lineage_markers = [
            r"\bdata lineage\b|\blineage\b",
            r"\bsource system\b|\bsystem of record\b",
            r"\bdata warehouse\b|\bdwh\b",
            r"\baudit trail\b",
            r"\bautomated extract\b|\bapi feed\b",
            r"\bmetadata\b",
            r"\bdata catalog\b",
            r"\bfield mapping\b",
        ]
        manual_markers = [
            r"\bmanual(?:ly)?\s+(?:adjusted|entered|updated|override)\b",
            r"\bspreadsheet\b",
            r"\bexcel\b",
            r"\bcopy[\s\-]paste\b",
        ]

        lineage_count = sum(1 for p in lineage_markers if re.search(p, text_lower))
        manual_count = sum(1 for p in manual_markers if re.search(p, text_lower))

        total = max(lineage_count + manual_count, 1)
        det_score = (lineage_count / total) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Found {lineage_count} automated lineage marker(s) and "
            f"{manual_count} manual-intervention flag(s). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_rcc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Regulatory Change Coverage (RCC).

        RCC estimates whether the filing/documentation explicitly addresses
        regulatory change control (revision history, effective dates,
        superseded rules) and avoids obvious obsolete references.
        """
        text_lower = document_text.lower()

        change_markers = [
            r"\brevision history\b|\bchange log\b|\bchangelog\b",
            r"\bversion\b\s*[:\-]?\s*\d+(?:\.\d+)*\b",
            r"\beffective date\b|\bin force\b|\bapplicable from\b",
            r"\bamend(?:ed|ment)\b|\bupdated\b|\brevised\b|\bsupersed(?:e|ed|es)\b",
            r"\bimplementation\b\s+date\b|\btransition\b\s+period\b",
        ]
        obsolete_markers = [
            r"\blibor\b",
            r"\bcrd\s*iv\b|\bcrd4\b",
            r"\bbasel\s*ii\b",
        ]

        change_hits = sum(1 for p in change_markers if re.search(p, text_lower))
        obsolete_hits = sum(1 for p in obsolete_markers if re.search(p, text_lower))

        det_score = (change_hits / len(change_markers)) * 100
        if obsolete_hits > 0:
            det_score = max(0.0, det_score - 20.0 * min(obsolete_hits, 3))

        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)
        reasoning = (
            f"Detected {change_hits}/{len(change_markers)} change-control marker(s) "
            f"and {obsolete_hits} obsolete reference flag(s). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_dcs(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Disclosure Completeness Score (DCS).

        DCS approximates Pillar 3 / regulatory disclosure coverage by checking
        for key disclosure topics and quantitative evidence (tables/numbers).
        """
        text_lower = document_text.lower()

        # Framework-aware disclosure topics:
        # - If this looks like a Pillar 3 / BCBS / ICAAP-type filing, use banking disclosure topics.
        # - If this looks like PCI-DSS, use policy/framework disclosure topics.
        # - Otherwise, use a lightweight generic compliance disclosure checklist.
        is_banking_filing = bool(
            re.search(r"\bpillar\s*3\b|\bbcbs\b|\bbasel\b|\bicaap\b|\bilaap\b|\bcrr\b|\bcrd\b", text_lower)
        )
        is_pci = bool(re.search(r"\bpci[\s\-]?dss\b", text_lower))

        if is_banking_filing:
            topics: dict[str, str] = {
                "capital": r"\bcapital\b|\bcet1\b|\btier\s*1\b|\btotal capital\b",
                "rwa": r"\brisk\-?weighted assets\b|\brwa\b",
                "leverage": r"\bleverage\s+ratio\b|\btier\s*1\s+leverage\b",
                "liquidity": r"\bliquidity\b|\blcr\b|\bnsfr\b|\bhqla\b",
                "credit_risk": r"\bcredit risk\b|\bpd\b|\blgd\b|\bead\b",
                "market_risk": r"\bmarket risk\b|\bvar\b|\bstress test\b",
                "operational_risk": r"\boperational risk\b|\bop risk\b|\borx\b",
                "governance": r"\bgovernance\b|\brisk appetite\b|\bboard\b|\brisk committee\b",
            }
        elif is_pci:
            topics = {
                "scope": r"\bscope\b|\bin\s*scope\b|\bout\s*of\s*scope\b",
                "roles": r"\brole\b|\bresponsibilit\w+\b|\bowner\b|\baccountable\b",
                "requirements": r"\brequirement\s+\d+(?:\.\d+)*\b|\bcontrol\s+requirement\b",
                "evidence": r"\bevidence\b|\bartifact\b|\blog\b|\baudit\s+trail\b",
                "risk": r"\brisk\s+assessment\b|\bthreat\b|\bvulnerabilit\w+\b",
                "incident_response": r"\bincident\s+response\b|\bbreach\b|\bcontainment\b",
                "testing": r"\btesting\b|\bvalidate\b|\bmonitor\b|\breview\s+cycle\b",
                "third_party": r"\bthird\s*party\b|\bservice\s+provider\b|\bvendor\b",
            }
        else:
            topics = {
                "purpose": r"\bpurpose\b|\bobjective\b",
                "scope": r"\bscope\b",
                "definitions": r"\bdefinitions\b|\bterms\b",
                "roles": r"\broles\b|\bresponsibilit\w+\b|\bowner\b",
                "controls": r"\bcontrol\b|\brequirement\b",
                "exceptions": r"\bexception\b|\bwaiver\b",
                "review_cycle": r"\breview\s+cycle\b|\bannual\b|\bquarterly\b",
                "versioning": r"\bversion\b|\brevision\s+history\b|\beffective\s+date\b",
            }

        topics_found = sum(1 for p in topics.values() if re.search(p, text_lower))

        # Quantitative evidence: counts presence of many numeric artifacts.
        numeric_artifacts = (
            len(re.findall(r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b", document_text))
            + len(re.findall(r"\b\d+(?:\.\d+)?\s*%\b", document_text))
            + len(re.findall(r"\brequirement\s+\d+(?:\.\d+)*\b", text_lower))
        )
        table_markers = sum(
            1
            for p in [r"\btable\b", r"\bfigure\b", r"\bannex\b", r"\bschedule\b"]
            if re.search(p, text_lower)
        )

        topic_component = (topics_found / len(topics)) * 70
        quant_component = min((numeric_artifacts / 30.0) * 25, 25.0) + min(
            (table_markers / 2.0) * 5, 5.0
        )
        det_score = min(topic_component + quant_component, 100.0)

        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)
        reasoning = (
            f"Disclosure topics present: {topics_found}/{len(topics)}. "
            f"Quant artifacts: {numeric_artifacts}, table markers: {table_markers}. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_gsc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Governance Sign-off Completeness (GSC).

        GSC checks for explicit governance attestation and sign-off evidence
        (board/committee approval, accountable roles, signatories, dates).
        """
        text_lower = document_text.lower()

        required_markers = [
            r"\bapproved\b|\bapproval\b|\bsigned\b|\bsignature\b|\battest\w*\b",
            r"\bboard\b|\brisk committee\b|\baudit committee\b",
            r"\bchief risk officer\b|\bcro\b|\bcfo\b|\bceo\b",
            r"\bdate\b\s*[:\-]?\s*(?:\d{1,2}[\-/]\d{1,2}[\-/]\d{2,4}|\d{4}[\-/]\d{1,2}[\-/]\d{1,2})\b",
            r"\baccountable\b|\bresponsible\b|\bowner\b",
        ]
        draft_markers = [r"\bdraft\b", r"\bfor review\b", r"\bnot final\b"]

        hits = sum(1 for p in required_markers if re.search(p, text_lower))
        drafts = sum(1 for p in draft_markers if re.search(p, text_lower))

        det_score = (hits / len(required_markers)) * 100
        if drafts > 0:
            det_score = max(0.0, det_score - 20.0)

        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)
        reasoning = (
            f"Governance sign-off evidence: {hits}/{len(required_markers)} marker(s) present. "
            f"Draft flags: {drafts}. Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_cmc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Control Mapping Coverage (CMC).

        CMC estimates whether a filing includes a control framework mapping
        (controls/tests/owners/evidence) tied to regulatory requirements.
        """
        text_lower = document_text.lower()

        mapping_markers = [
            r"\bcontrol\s+id\b|\bcontrol\s+identifier\b",
            r"\brequirement\s+id\b|\bregulatory\s+requirement\b",
            r"\bmapping\b|\bcross\-?reference\b",
            r"\bcontrol owner\b|\bprocess owner\b",
            r"\btesting\b|\bcontrol test\b|\bvalidation\b",
            r"\bevidence\b|\baudit\s+trail\b",
        ]

        hits = sum(1 for p in mapping_markers if re.search(p, text_lower))
        det_score = (hits / len(mapping_markers)) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Found {hits}/{len(mapping_markers)} control-mapping marker(s). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_rcpc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Recordkeeping & Classification Policy Coverage (RCPC).

        RCPC checks for retention periods, classification levels, and
        lifecycle handling (archive/destruction/legal hold).
        """
        text_lower = document_text.lower()

        policy_markers = [
            r"\bretention\b|\bretain\b|\bretention period\b",
            r"\bdata classification\b|\bclassification level\b|\bconfidential\b|\binternal\b|\bpublic\b",
            r"\barchive\b|\barchiving\b|\bstorage\b",
            r"\bdestruct\w*\b|\bdisposal\b|\bdeletion\b",
            r"\blegal hold\b|\be\-?discovery\b",
        ]

        hits = sum(1 for p in policy_markers if re.search(p, text_lower))
        det_score = (hits / len(policy_markers)) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Recordkeeping/classification coverage: {hits}/{len(policy_markers)} marker(s) present. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Investment Banking & M&A Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_qoe_transparency(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Quality of Earnings (QoE) Normalization Transparency.

        QoE_Transparency = (Evidence-Supported Add-backs / Total Add-backs) × 100
        """
        text_lower = document_text.lower()

        add_back_patterns = [
            r"\badd[\s\-]back\b",
            r"\bnon[\s\-]recurring\b",
            r"\bone[\s\-]time\b.{0,20}\bcharge\b",
            r"\brestructuring\b",
            r"\bimpairment\b",
            r"\bunusual item\b",
        ]
        evidence_patterns = [
            r"\binvoice\b",
            r"\breceipt\b|\bvoucher\b",
            r"\bthird[\s\-]party\b.{0,20}\bverif\w+\b",
            r"\baudited\b",
            r"\bsupporting document\b",
            r"\bboard approval\b",
        ]

        add_backs = max(
            sum(1 for p in add_back_patterns if re.search(p, text_lower)), 1
        )
        evidence = sum(1 for p in evidence_patterns if re.search(p, text_lower))

        det_score = min((evidence / add_backs) * 100, 100.0)
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Detected {evidence} supporting evidence artifact(s) for "
            f"{add_backs} add-back item(s). Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_fosi(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Fairness Opinion Sensitivity Index (FOSI).

        FOSI = (Methods Used / 3) × (1 − CV(Valuations)) × 100

        Checks presence of the three industry-standard valuation methodologies.
        """
        text_lower = document_text.lower()

        valuation_methods: dict[str, str] = {
            "dcf": r"\bdiscounted cash flow\b|\bdcf\b|\bpresent value of\b",
            "precedent_tx": r"\bprecedent transaction\b|\bcomparable transaction\b",
            "trading_comps": r"\btrading comp\b|\bpublic comparable\b|\bpeer group\b|\bebitda multiple\b",
        }

        methods_found = sum(1 for p in valuation_methods.values() if re.search(p, text_lower))
        det_score = min((methods_found / 3) * 100, 100.0)
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        missing = [k for k, p in valuation_methods.items() if not re.search(p, text_lower)]
        reasoning = (
            f"Identified {methods_found}/3 standard valuation methodologies. "
            f"{'Missing: ' + ', '.join(missing) + '.' if missing else 'All methodologies present.'} "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_ats(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Assumption Transparency Score (ATS)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bassumption\b",
                r"\bsource\b|\bdata source\b",
                r"\brationale\b|\bjustification\b",
                r"\bmanagement case\b|\bbase case\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 assumption transparency markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_sac(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Sensitivity Analysis Coverage (SAC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bsensitivity\b|\bscenario analysis\b",
                r"\bwacc\b",
                r"\bgrowth\b|\bterminal growth\b",
                r"\bmultiple\b|\bebitda multiple\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 sensitivity-analysis coverage markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_csj(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Comparable Set Justification (CSJ)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bcomparable set\b|\bpeer set\b",
                r"\binclusion criteria\b",
                r"\bexclusion criteria\b",
                r"\bselection rationale\b|\bjustification\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 comparable-set justification markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_cidc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Conflict & Independence Disclosure Completeness (CIDC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bindependence statement\b|\bindependent advisor\b",
                r"\bfee disclosure\b|\bcompensation\b",
                r"\bconflict of interest\b|\bconflict disclosure\b",
                r"\bengagement letter\b|\bmandate\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 conflict/independence disclosure markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_drt(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Data Room Traceability (DRT)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bdata room\b|\bvirtual data room\b|\bvdr\b",
                r"\bdocument reference\b|\bsource document\b",
                r"\bappendix\b|\bannex\b|\bexhibit\b",
                r"\btraceable\b|\bcross-reference\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 data-room traceability markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    # ─────────────────────────────────────────────────────────────────────────
    # Fraud & Investigation Metrics
    # ─────────────────────────────────────────────────────────────────────────

    def calculate_snad(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        SAR Narrative Actionability Density (SNAD).

        SNAD = (Σ Six-Element Presence Flags / 6) × 100

        Verifies presence of Who, What, When, Where, Why, How in the SAR narrative.
        """
        text_lower = document_text.lower()

        six_elements: dict[str, str] = {
            "who": r"\bsubject\b|\bsuspect\b|\bindividual\b.{0,30}\b(?:conducted|performed|made)\b",
            "what": r"\bsuspicious activity\b|\btransaction\b.{0,30}\bfraud\b|\bwhat\b.{0,20}\boccurred\b",
            "when": r"\b(?:date|time|period|on|during)\b.{0,30}\b(?:transaction|activity|occurred)\b",
            "where": r"\b(?:branch|account|location|institution|bank)\b",
            "why": r"\bsuspicious because\b|\bbecause\b|\bindication\b|\bred flag\b|\bconcern\b",
            "how": r"\btransfer(?:red)?\b|\bwire\b|\bdeposit\b|\bstructured\b|\bmechanism\b",
        }

        found = sum(1 for p in six_elements.values() if re.search(p, text_lower))
        det_score = (found / 6) * 100
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        missing = [k for k, p in six_elements.items() if not re.search(p, text_lower)]
        reasoning = (
            f"SAR six-element check: {found}/6 elements present. "
            f"{'Missing: ' + ', '.join(missing) + '.' if missing else 'All elements present.'} "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_wcw(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """
        Whistleblower Credibility Weight (WCW).

        WCW = (Independent Evidence Artifacts / Stated Claims) × Reliability Factor
        """
        text_lower = document_text.lower()

        evidence_patterns = [
            r"\bemail\b",
            r"\breceipt\b|\bvoucher\b",
            r"\bsystem log\b|\bserver log\b|\baudit log\b",
            r"\bphone record\b|\bphone log\b",
            r"\bwitness\b",
            r"\btransaction record\b",
            r"\bscreen(?:shot|capture)\b",
        ]
        claim_patterns = [
            r"\ballege[sd]?\b",
            r"\bclaim(?:s|ed)?\b",
            r"\breport(?:s|ed)?\b.{0,20}\bsuspect\w*\b",
            r"\bassert(?:s|ed)?\b",
            r"\bstated\b.{0,20}\bthat\b",
        ]

        evidence = sum(1 for p in evidence_patterns if re.search(p, text_lower))
        claims = max(sum(1 for p in claim_patterns if re.search(p, text_lower)), 1)

        reliability_factor = min(evidence / max(evidence, 1), 1.0) if evidence > 0 else 0.5
        det_score = min((evidence / claims) * reliability_factor * 100, 100.0)
        blended, llm_used = self._blend(det_score, llm_score, allow_override=allow_override)

        reasoning = (
            f"Found {evidence} independent evidence artifact(s) vs {claims} stated claim(s). "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {blended:.0f}."
        )
        return (
            round(blended, 1),
            reasoning,
            round(det_score, 1),
            (round(float(llm_score), 1) if llm_score is not None else None),
            round(llm_used, 1),
        )

    def calculate_tcs(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Timeline Coherence Score (TCS)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\btimeline\b|\bchronolog\w+\b",
                r"\bon \d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b",
                r"\bbefore\b|\bafter\b|\bsubsequently\b",
                r"\bincident date\b|\bevent date\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 timeline coherence markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_eccc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Evidence Chain-of-Custody Completeness (ECCC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bevidence id\b|\bartifact id\b",
                r"\bcollection date\b|\bcollected on\b",
                r"\bhandler\b|\bcustodian\b",
                r"\bchain of custody\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 chain-of-custody markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_tdc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Transaction Detail Completeness (TDC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bamount\b",
                r"\bdate\b",
                r"\bsender\b|\boriginator\b",
                r"\breceiver\b|\bbeneficiary\b",
                r"\bchannel\b|\bwire\b|\bach\b|\bcard\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/5 transaction-detail completeness markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_detr(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Disposition & Escalation Traceability (DETR)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bdisposition\b|\bdecision\b",
                r"\bapprover\b|\bapproved by\b",
                r"\brationale\b|\bjustification\b",
                r"\bescalation\b|\bescalated to\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 disposition/escalation traceability markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    def calculate_rnc(
        self,
        document_text: str,
        fields: dict,
        llm_score: Optional[float] = None,
        allow_override: bool = False,
    ) -> tuple[float, str, float, Optional[float], float]:
        """Regulatory Notification Completeness (RNC)."""
        score, hits, _, det_score, llm_used = self._keyword_metric(
            document_text,
            positive_patterns=[
                r"\bregulatory notification\b|\breported to regulator\b",
                r"\bnotification date\b|\bfiled on\b",
                r"\breference number\b|\bcase reference\b",
                r"\bfincen\b|\bfca\b|\bmas\b|\beba\b|\bsec\b",
            ],
            llm_score=llm_score,
            allow_override=allow_override,
        )
        reasoning = (
            f"Detected {hits}/4 regulatory-notification completeness markers. "
            f"Deterministic: {det_score:.0f} | Blended (70/30): {score:.0f}."
        )
        return score, reasoning, det_score, (round(float(llm_score), 1) if llm_score is not None else None), llm_used

    # ─────────────────────────────────────────────────────────────────────────
    # Domain Dispatcher
    # ─────────────────────────────────────────────────────────────────────────

    def evaluate_domain(
        self,
        banking_domain: str,
        document_text: str,
        fields: dict,
        llm_domain_scores: Optional[dict] = None,
    ) -> list[dict]:
        """
        Run all applicable metric calculations for the detected banking domain.

        Args:
            banking_domain: One of the six defined banking domain names.
            document_text:  Full extracted document text.
            fields:         Fields extracted by the LLM.
            llm_domain_scores: Optional dict of LLM semantic scores keyed by
                               short metric code (e.g., "boti", "cpi").

        Returns:
            List of banking metric result dicts, each containing:
              name, score, description, calculation_logic, risk_impact, reasoning.
        """
        llm = llm_domain_scores or {}

        def _llm_score(value: object) -> Optional[float]:
            if value is None:
                return None
            if isinstance(value, dict):
                try:
                    raw = value.get("score")
                    if raw is None:
                        return None
                    score_float = float(raw)
                    return max(0.0, min(100.0, score_float))
                except (ValueError, TypeError) as e:
                    logger.debug("Failed to parse LLM score from dict: %s", e)
                    return None
            try:
                score_float = float(value)  # type: ignore[arg-type]
                return max(0.0, min(100.0, score_float))
            except (ValueError, TypeError) as e:
                logger.debug("Failed to parse LLM score: %s", e)
                return None
        results: list[dict] = []

        # ── KYC / AML ────────────────────────────────────────────────────────
        if banking_domain == "Customer Onboarding (KYC/AML)":
            boti_score, boti_reason, boti_det, _, boti_llm_used = self.calculate_boti(
                document_text, fields, _llm_score(llm.get("boti"))
            )
            results.append(
                {
                    "name": "Beneficial Ownership Transparency Index (BOTI)",
                    "score": int(round(boti_score)),
                    "deterministic_score": int(round(boti_det)),
                    "llm_score": int(round(boti_llm_used)),
                    "description": (
                        "Measures the percentage of natural persons identified who hold "
                        ">25% control, relative to the total ownership structure documented."
                    ),
                    "calculation_logic": (
                        "BOTI = (NaturalOwners_Identified / RequiredOwners_OrgChart) × 100. "
                        "Rules check for 'Passport', 'ID', or 'SSN' markers against the list "
                        "of owners extracted from the corporate structure."
                    ),
                    "risk_impact": (
                        "Poor BOTI allows money laundering through shell companies. "
                        "Regulatory pass threshold is ≥95. Failing BOTI can result in the loss "
                        "of correspondent banking relationships."
                    ),
                    "reasoning": boti_reason,
                }
            )

            iess_score, iess_reason, iess_det, _, iess_llm_used = self.calculate_iess(
                document_text, fields, _llm_score(llm.get("iess"))
            )
            results.append(
                {
                    "name": "Identity Evidence Strength Score (IESS)",
                    "score": int(round(iess_score)),
                    "deterministic_score": int(round(iess_det)),
                    "llm_score": int(round(iess_llm_used)),
                    "description": (
                        "Evaluates the confidence in identity document authenticity based on "
                        "security features: MRZ checksum, hologram detection, and biometric match."
                    ),
                    "calculation_logic": (
                        "IESS = Σ(FeatureWeight_i × Confidence_i) for n features including "
                        "MRZ checksum match, hologram detection, face match confidence, "
                        "and OCR checksum integrity."
                    ),
                    "risk_impact": (
                        "Accepting a fake ID leads to severe AML regulatory breaches. "
                        "Low IESS indicates elevated synthetic identity fraud and PEP screening risk."
                    ),
                    "reasoning": iess_reason,
                }
            )

            spec_score, spec_reason, spec_det, _, spec_llm_used = self.calculate_spec(
                document_text, fields, _llm_score(llm.get("spec"))
            )
            results.append(
                {
                    "name": "Sanctions/PEP Screening Evidence Coverage (SPEC)",
                    "score": int(round(spec_score)),
                    "deterministic_score": int(round(spec_det)),
                    "llm_score": int(round(spec_llm_used)),
                    "description": "Measures whether sanctions/PEP screening includes date, source lists, result, and reviewer sign-off.",
                    "calculation_logic": "Coverage of mandatory screening evidence markers across sanctions and PEP checks.",
                    "risk_impact": "Insufficient screening evidence creates AML control failure and audit non-compliance risk.",
                    "reasoning": spec_reason,
                }
            )

            cedj_score, cedj_reason, cedj_det, _, cedj_llm_used = self.calculate_cedj(
                document_text, fields, _llm_score(llm.get("cedj"))
            )
            results.append(
                {
                    "name": "CDD/EDD Trigger Justification Quality (CEDJ)",
                    "score": int(round(cedj_score)),
                    "deterministic_score": int(round(cedj_det)),
                    "llm_score": int(round(cedj_llm_used)),
                    "description": "Measures whether CDD/EDD triggers are explicitly justified with clear risk rationale.",
                    "calculation_logic": "Checks for CDD/EDD references plus trigger drivers such as PEP, adverse media, or high-risk jurisdiction.",
                    "risk_impact": "Weak trigger rationale reduces defendability of AML decisions during supervisory review.",
                    "reasoning": cedj_reason,
                }
            )

            soft_score, soft_reason, soft_det, _, soft_llm_used = self.calculate_soft(
                document_text, fields, _llm_score(llm.get("soft"))
            )
            results.append(
                {
                    "name": "Source-of-Funds Traceability (SOFT)",
                    "score": int(round(soft_score)),
                    "deterministic_score": int(round(soft_det)),
                    "llm_score": int(round(soft_llm_used)),
                    "description": "Measures traceability of source-of-funds claims to referenced evidence artifacts.",
                    "calculation_logic": "Checks for source-of-funds declarations and supporting artifacts (payslips, statements, contracts).",
                    "risk_impact": "Poor traceability increases exposure to layered money-laundering and onboarding control breaches.",
                    "reasoning": soft_reason,
                }
            )

            avs_score, avs_reason, avs_det, _, avs_llm_used = self.calculate_avs(
                document_text, fields, _llm_score(llm.get("avs"))
            )
            results.append(
                {
                    "name": "Address Verification Strength (AVS)",
                    "score": int(round(avs_score)),
                    "deterministic_score": int(round(avs_det)),
                    "llm_score": int(round(avs_llm_used)),
                    "description": "Measures whether proof-of-address is present, recent, and aligned with customer details.",
                    "calculation_logic": "Checks for proof-of-address documents, recency indicators, and explicit address matching evidence.",
                    "risk_impact": "Weak address verification increases synthetic identity and account abuse risk.",
                    "reasoning": avs_reason,
                }
            )

            rre_score, rre_reason, rre_det, _, rre_llm_used = self.calculate_rre(
                document_text, fields, _llm_score(llm.get("rre"))
            )
            results.append(
                {
                    "name": "Risk Rating Explainability (RRE)",
                    "score": int(round(rre_score)),
                    "deterministic_score": int(round(rre_det)),
                    "llm_score": int(round(rre_llm_used)),
                    "description": "Measures whether customer risk rating includes clear driver-level explainability.",
                    "calculation_logic": "Checks for risk score/rating plus key drivers: jurisdiction, product, channel, ownership complexity.",
                    "risk_impact": "Unexplained risk ratings weaken governance and undermine model/compliance defensibility.",
                    "reasoning": rre_reason,
                }
            )

        # ── Loan & Credit ────────────────────────────────────────────────────
        elif banking_domain == "Loan & Credit Documentation":
            cpi_score, cpi_reason, cpi_det, _, cpi_llm_used = self.calculate_cpi(
                document_text, fields, _llm_score(llm.get("cpi"))
            )
            results.append(
                {
                    "name": "Collateral Perfection Index (CPI)",
                    "score": int(round(cpi_score)),
                    "deterministic_score": int(round(cpi_det)),
                    "llm_score": int(round(cpi_llm_used)),
                    "description": (
                        "Measures the presence and legal validity of all required fields to "
                        "legally 'perfect' a security interest in collateral."
                    ),
                    "calculation_logic": (
                        "CPI = (Validated Legal Clauses Found / Required Perfection Clauses) × 100. "
                        "Regex searches for 'Granting Clause', 'Legal Description', 'Lien Perfection', "
                        "execution date, governing law, default provisions, and notarization."
                    ),
                    "risk_impact": (
                        "Unperfected collateral makes the bank an unsecured creditor in bankruptcy, "
                        "risking 100% loss of principal. Regulatory pass = 100. "
                        "Triggers 'Safety and Soundness' citations during OCC/EBA examinations."
                    ),
                    "reasoning": cpi_reason,
                }
            )

            ccts_score, ccts_reason, ccts_det, _, ccts_llm_used = self.calculate_ccts(
                document_text, fields, _llm_score(llm.get("ccts"))
            )
            results.append(
                {
                    "name": "Covenant Compliance Transparency Score (CCTS)",
                    "score": int(round(ccts_score)),
                    "deterministic_score": int(round(ccts_det)),
                    "llm_score": int(round(ccts_llm_used)),
                    "description": (
                        "Measures the clarity and auditability of financial ratio calculations "
                        "(e.g., Debt/EBITDA) against the loan covenants."
                    ),
                    "calculation_logic": (
                        "CCTS = (Traceable Data Points for Ratio / Total Data Points Required) × 100. "
                        "Checks for EBITDA, Total Debt, Revenue, Leverage Ratio, Current Ratio, "
                        "DSCR, and covenant threshold disclosures."
                    ),
                    "risk_impact": (
                        "Poor visibility leads to 'covenant-lite' risks and massive write-downs. "
                        "Missing EBITDA detail is a primary early-warning indicator of borrower distress."
                    ),
                    "reasoning": ccts_reason,
                }
            )

            rifc_score, rifc_reason, rifc_det, _, rifc_llm_used = self.calculate_rifc(
                document_text, fields, _llm_score(llm.get("rifc"))
            )
            results.append(
                {
                    "name": "Rate Index & Fallback Correctness (RIFC)",
                    "score": int(round(rifc_score)),
                    "deterministic_score": int(round(rifc_det)),
                    "llm_score": int(round(rifc_llm_used)),
                    "description": "Measures whether rate index and fallback language are complete and benchmark-safe.",
                    "calculation_logic": "Checks for SOFR/fallback transition language and penalizes LIBOR-only references.",
                    "risk_impact": "Missing fallback clauses creates pricing and enforceability risk during benchmark transitions.",
                    "reasoning": rifc_reason,
                }
            )

            eac_score, eac_reason, eac_det, _, eac_llm_used = self.calculate_eac(
                document_text, fields, _llm_score(llm.get("eac"))
            )
            results.append(
                {
                    "name": "Execution & Authority Completeness (EAC)",
                    "score": int(round(eac_score)),
                    "deterministic_score": int(round(eac_det)),
                    "llm_score": int(round(eac_llm_used)),
                    "description": "Measures presence of valid execution signatures and authority evidence.",
                    "calculation_logic": "Checks signatures, authorized signatories, board resolution/approval, and execution date markers.",
                    "risk_impact": "Authority gaps can invalidate enforceability and increase legal challenge risk.",
                    "reasoning": eac_reason,
                }
            )

            rsi_score, rsi_reason, rsi_det, _, rsi_llm_used = self.calculate_rsi(
                document_text, fields, _llm_score(llm.get("rsi"))
            )
            results.append(
                {
                    "name": "Repayment Schedule Integrity (RSI)",
                    "score": int(round(rsi_score)),
                    "deterministic_score": int(round(rsi_det)),
                    "llm_score": int(round(rsi_llm_used)),
                    "description": "Measures internal consistency and completeness of repayment schedule terms.",
                    "calculation_logic": "Checks for amortization schedule, tenor/maturity, payment frequency, and installment details.",
                    "risk_impact": "Schedule gaps drive servicing errors, dispute risk, and covenant monitoring failures.",
                    "reasoning": rsi_reason,
                }
            )

            bgic_score, bgic_reason, bgic_det, _, bgic_llm_used = self.calculate_bgic(
                document_text, fields, _llm_score(llm.get("bgic"))
            )
            results.append(
                {
                    "name": "Borrower/Guarantor Identification Consistency (BGIC)",
                    "score": int(round(bgic_score)),
                    "deterministic_score": int(round(bgic_det)),
                    "llm_score": int(round(bgic_llm_used)),
                    "description": "Measures cross-document consistency of borrower and guarantor identity references.",
                    "calculation_logic": "Checks presence of borrower/guarantor identifiers and explicit consistency/matching cues.",
                    "risk_impact": "Identity inconsistency can undermine claim enforceability and collateral recovery.",
                    "reasoning": bgic_reason,
                }
            )

            cvr_score, cvr_reason, cvr_det, _, cvr_llm_used = self.calculate_cvr(
                document_text, fields, _llm_score(llm.get("cvr"))
            )
            results.append(
                {
                    "name": "Collateral Valuation Recency (CVR)",
                    "score": int(round(cvr_score)),
                    "deterministic_score": int(round(cvr_det)),
                    "llm_score": int(round(cvr_llm_used)),
                    "description": "Measures whether collateral valuation/appraisal evidence is current within policy windows.",
                    "calculation_logic": "Checks for appraisal report, valuation date, and policy recency references.",
                    "risk_impact": "Outdated valuations distort secured exposure and increase loss-given-default risk.",
                    "reasoning": cvr_reason,
                }
            )

        # ── Treasury & Liquidity ─────────────────────────────────────────────
        elif banking_domain == "Treasury & Liquidity Reports":
            hec_score, hec_reason, hec_det, _, hec_llm_used = self.calculate_hec(
                document_text, fields, _llm_score(llm.get("hec"))
            )
            results.append(
                {
                    "name": "HQLA Eligibility Confidence (HEC)",
                    "score": int(round(hec_score)),
                    "deterministic_score": int(round(hec_det)),
                    "llm_score": int(round(hec_llm_used)),
                    "description": (
                        "Measures the percentage of assets classified as High-Quality Liquid Assets "
                        "that are genuinely unencumbered and meet 12 CFR §329.20 criteria."
                    ),
                    "calculation_logic": (
                        "HEC = 1 − (Assets with Encumbrance Flags / Total Assets in Buffer). "
                        "Scans asset listings for 'pledged', 'encumbered', 'restricted', "
                        "or 'repo' metadata flags."
                    ),
                    "risk_impact": (
                        "Overstating HQLA creates a false sense of security. "
                        "During a bank run, encumbered assets cannot be liquidated, "
                        "risking insolvency and central bank emergency intervention."
                    ),
                    "reasoning": hec_reason,
                }
            )

            isrr_score, isrr_reason, isrr_det, _, isrr_llm_used = self.calculate_isrr(
                document_text, fields, _llm_score(llm.get("isrr"))
            )
            results.append(
                {
                    "name": "Inter-System Reconciliation Ratio (ISRR)",
                    "score": int(round(isrr_score)),
                    "deterministic_score": int(round(isrr_det)),
                    "llm_score": int(round(isrr_llm_used)),
                    "description": (
                        "Measures the delta between the document's stated cash balance and "
                        "the balance reported by the core banking system at the same timestamp."
                    ),
                    "calculation_logic": (
                        "ISRR = (1 − |Doc Balance − System Balance| / System Balance) × 100. "
                        "Checks reconciliation markers and penalises discrepancy/mismatch flags."
                    ),
                    "risk_impact": (
                        "Internal 'ghost' balances cause failed regulatory audits and "
                        "liquidity mismanagement. Persistent discrepancies signal potential fraud."
                    ),
                    "reasoning": isrr_reason,
                }
            )

            ctta_score, ctta_reason, ctta_det, _, ctta_llm_used = self.calculate_ctta(
                document_text, fields, _llm_score(llm.get("ctta"))
            )
            results.append(
                {
                    "name": "Cut-off Time & Timestamp Alignment (CTTA)",
                    "score": int(round(ctta_score)),
                    "deterministic_score": int(round(ctta_det)),
                    "llm_score": int(round(ctta_llm_used)),
                    "description": "Measures alignment between reporting cut-off and source-system timestamps.",
                    "calculation_logic": "Checks for cut-off time, timestamp, source timing references, and explicit alignment signals.",
                    "risk_impact": "Timestamp misalignment can invalidate liquidity positions and supervisory reporting quality.",
                    "reasoning": ctta_reason,
                }
            )

            ssc_score, ssc_reason, ssc_det, _, ssc_llm_used = self.calculate_ssc(
                document_text, fields, _llm_score(llm.get("ssc"))
            )
            results.append(
                {
                    "name": "Stress Scenario Coverage (SSC)",
                    "score": int(round(ssc_score)),
                    "deterministic_score": int(round(ssc_det)),
                    "llm_score": int(round(ssc_llm_used)),
                    "description": "Measures whether stress scenarios, assumptions, and outcomes are adequately documented.",
                    "calculation_logic": "Checks for scenario definitions, assumptions, result disclosures, and baseline/adverse coverage.",
                    "risk_impact": "Insufficient stress coverage weakens liquidity preparedness and contingency planning.",
                    "reasoning": ssc_reason,
                }
            )

            iocc_score, iocc_reason, iocc_det, _, iocc_llm_used = self.calculate_iocc(
                document_text, fields, _llm_score(llm.get("iocc"))
            )
            results.append(
                {
                    "name": "Inflow/Outflow Classification Completeness (IOCC)",
                    "score": int(round(iocc_score)),
                    "deterministic_score": int(round(iocc_det)),
                    "llm_score": int(round(iocc_llm_used)),
                    "description": "Measures completeness of required inflow/outflow classifications in liquidity reports.",
                    "calculation_logic": "Checks for inflow, outflow, category/classification, and required liquidity bucket terms.",
                    "risk_impact": "Classification gaps distort LCR/NSFR components and internal limit monitoring.",
                    "reasoning": iocc_reason,
                }
            )

            lbdq_score, lbdq_reason, lbdq_det, _, lbdq_llm_used = self.calculate_lbdq(
                document_text, fields, _llm_score(llm.get("lbdq"))
            )
            results.append(
                {
                    "name": "Limit Breach Disclosure Quality (LBDQ)",
                    "score": int(round(lbdq_score)),
                    "deterministic_score": int(round(lbdq_det)),
                    "llm_score": int(round(lbdq_llm_used)),
                    "description": "Measures whether limit breaches include actions, approvals, and escalation documentation.",
                    "calculation_logic": "Checks for breach disclosure, remediation action, approval records, and escalation markers.",
                    "risk_impact": "Poor breach disclosure weakens governance and can mask unresolved liquidity control failures.",
                    "reasoning": lbdq_reason,
                }
            )

            sscov_score, sscov_reason, sscov_det, _, sscov_llm_used = self.calculate_sscov(
                document_text, fields, _llm_score(llm.get("sscov"))
            )
            results.append(
                {
                    "name": "Source System Coverage (SSCOV)",
                    "score": int(round(sscov_score)),
                    "deterministic_score": int(round(sscov_det)),
                    "llm_score": int(round(sscov_llm_used)),
                    "description": "Measures coverage of system-of-record references across GL, core banking, and treasury systems.",
                    "calculation_logic": "Checks for explicit source-system references to GL, core banking, treasury, and system-of-record terms.",
                    "risk_impact": "Incomplete source-system coverage reduces traceability and audit confidence in report values.",
                    "reasoning": sscov_reason,
                }
            )

        # ── Regulatory & Compliance ──────────────────────────────────────────
        elif banking_domain == "Regulatory & Compliance Filings":
            rmp_score, rmp_reason, rmp_det, _, rmp_llm_used = self.calculate_rmp(
                document_text, fields, _llm_score(llm.get("rmp"))
            )
            results.append(
                {
                    "name": "Regulatory Mapping Precision (RMP)",
                    "score": int(round(rmp_score)),
                    "deterministic_score": int(round(rmp_det)),
                    "llm_score": int(round(rmp_llm_used)),
                    "description": (
                        "Measures the density of accurate cross-references to specific "
                        "regulatory paragraphs (e.g., EBA RTS, Basel III/IV Principles)."
                    ),
                    "calculation_logic": (
                        "RMP = (Verified Correct Reg Refs / Total Reg Refs in Doc) × 100. "
                        "Validates references to BCBS 239, Basel III/IV, EBA RTS, Dodd-Frank, SOFR; "
                        "penalises obsolete references such as LIBOR or outdated CRD versions."
                    ),
                    "risk_impact": (
                        "Citing obsolete regulations triggers regulatory pushback and "
                        "expensive multi-month audit remediation. A 'Fatal Benchmark Error' "
                        "prevents document finalization."
                    ),
                    "reasoning": rmp_reason,
                }
            )

            dli_score, dli_reason, dli_det, _, dli_llm_used = self.calculate_dli(
                document_text, fields, _llm_score(llm.get("dli"))
            )
            results.append(
                {
                    "name": "BCBS 239 Data Lineage Integrity (DLI)",
                    "score": int(round(dli_score)),
                    "deterministic_score": int(round(dli_det)),
                    "llm_score": int(round(dli_llm_used)),
                    "description": (
                        "Measures the ability to trace every numeric value in a risk report "
                        "back to its single authoritative source system without manual intervention."
                    ),
                    "calculation_logic": (
                        "DLI = (Fields with Automated Lineage / Total Critical Risk Fields) × 100. "
                        "Rewards data warehouse, API feed, and audit trail markers; "
                        "penalises spreadsheet, Excel, and manual-adjustment references."
                    ),
                    "risk_impact": (
                        "'Spreadsheet risk' hides true exposure. BCBS 239 Principle 3 violations "
                        "trigger capital add-ons. Regulators require immutable automated data lineage."
                    ),
                    "reasoning": dli_reason,
                }
            )

            rcc_score, rcc_reason, rcc_det, _, rcc_llm_used = self.calculate_rcc(
                document_text, fields, _llm_score(llm.get("rcc"))
            )
            results.append(
                {
                    "name": "Regulatory Change Coverage (RCC)",
                    "score": int(round(rcc_score)),
                    "deterministic_score": int(round(rcc_det)),
                    "llm_score": int(round(rcc_llm_used)),
                    "description": (
                        "Measures whether the filing documents regulatory change control "
                        "(effective dates, revisions, superseded rules) and avoids obvious obsolete references."
                    ),
                    "calculation_logic": (
                        "RCC checks for revision history/change log/effective date markers and penalises "
                        "obsolete references (e.g., LIBOR)."
                    ),
                    "risk_impact": (
                        "Poor change coverage increases the risk of filing against outdated requirements, "
                        "triggering regulatory resubmissions and supervisory findings."
                    ),
                    "reasoning": rcc_reason,
                }
            )

            dcs_score, dcs_reason, dcs_det, _, dcs_llm_used = self.calculate_dcs(
                document_text, fields, _llm_score(llm.get("dcs"))
            )
            results.append(
                {
                    "name": "Disclosure Completeness Score (DCS)",
                    "score": int(round(dcs_score)),
                    "deterministic_score": int(round(dcs_det)),
                    "llm_score": int(round(dcs_llm_used)),
                    "description": (
                        "Measures coverage of key Pillar 3 / regulatory disclosure topics and the presence of "
                        "supporting quantitative evidence (tables/numbers)."
                    ),
                    "calculation_logic": (
                        "DCS = topic coverage (70%) + quantitative evidence (30%). Topics include capital, RWA, "
                        "leverage, liquidity, and major risk categories."
                    ),
                    "risk_impact": (
                        "Incomplete disclosures can be treated as misreporting or non-compliance, resulting in "
                        "supervisory actions and reputational damage."
                    ),
                    "reasoning": dcs_reason,
                }
            )

            gsc_score, gsc_reason, gsc_det, _, gsc_llm_used = self.calculate_gsc(
                document_text, fields, _llm_score(llm.get("gsc"))
            )
            results.append(
                {
                    "name": "Governance Sign-off Completeness (GSC)",
                    "score": int(round(gsc_score)),
                    "deterministic_score": int(round(gsc_det)),
                    "llm_score": int(round(gsc_llm_used)),
                    "description": (
                        "Measures evidence of accountable governance sign-off (board/committee approval, "
                        "executive ownership, signatories, and dates)."
                    ),
                    "calculation_logic": (
                        "GSC checks for approval/signature markers, governance bodies, accountable roles, and "
                        "dated attestations; penalises obvious draft indicators."
                    ),
                    "risk_impact": (
                        "Missing sign-off weakens accountability and can invalidate the filing in internal governance "
                        "and supervisory review."
                    ),
                    "reasoning": gsc_reason,
                }
            )

            cmc_score, cmc_reason, cmc_det, _, cmc_llm_used = self.calculate_cmc(
                document_text, fields, _llm_score(llm.get("cmc"))
            )
            results.append(
                {
                    "name": "Control Mapping Coverage (CMC)",
                    "score": int(round(cmc_score)),
                    "deterministic_score": int(round(cmc_det)),
                    "llm_score": int(round(cmc_llm_used)),
                    "description": (
                        "Measures whether controls, owners, tests, and evidence are mapped to regulatory requirements."
                    ),
                    "calculation_logic": (
                        "CMC checks for control IDs, requirement IDs, mapping/cross-reference language, owners, "
                        "testing and evidence artifacts."
                    ),
                    "risk_impact": (
                        "Weak control mapping increases the likelihood of unremediated compliance gaps and adverse "
                        "audit findings."
                    ),
                    "reasoning": cmc_reason,
                }
            )

            rcpc_score, rcpc_reason, rcpc_det, _, rcpc_llm_used = self.calculate_rcpc(
                document_text, fields, _llm_score(llm.get("rcpc"))
            )
            results.append(
                {
                    "name": "Recordkeeping & Classification Policy Coverage (RCPC)",
                    "score": int(round(rcpc_score)),
                    "deterministic_score": int(round(rcpc_det)),
                    "llm_score": int(round(rcpc_llm_used)),
                    "description": (
                        "Measures whether retention, classification, archival, destruction, and legal hold procedures "
                        "are stated and actionable."
                    ),
                    "calculation_logic": (
                        "RCPC checks for retention periods, data classification labels, archive/storage language, "
                        "destruction/disposal, and legal hold/e-discovery references."
                    ),
                    "risk_impact": (
                        "Poor recordkeeping controls elevate regulatory and litigation risk, including inability to "
                        "produce evidence under supervisory request or legal discovery."
                    ),
                    "reasoning": rcpc_reason,
                }
            )

        # ── Investment Banking & M&A ──────────────────────────────────────────
        elif banking_domain == "Investment Banking & M&A":
            qoe_score, qoe_reason, qoe_det, _, qoe_llm_used = self.calculate_qoe_transparency(
                document_text, fields, _llm_score(llm.get("qoe"))
            )
            results.append(
                {
                    "name": "QoE Normalization Transparency",
                    "score": int(round(qoe_score)),
                    "deterministic_score": int(round(qoe_det)),
                    "llm_score": int(round(qoe_llm_used)),
                    "description": (
                        "Measures the percentage of EBITDA add-backs supported by third-party "
                        "documentary evidence (invoices for non-recurring expenses)."
                    ),
                    "calculation_logic": (
                        "QoE_Transparency = (Evidence-Supported Add-backs / Total Add-backs) × 100. "
                        "Checks invoice/receipt evidence against restructuring, impairment, "
                        "and non-recurring charge disclosures."
                    ),
                    "risk_impact": (
                        "Unsupported add-backs inflate enterprise value by an EBITDA multiple. "
                        "Overpaying from inflated QoE leads to acquisition write-downs "
                        "and shareholder litigation."
                    ),
                    "reasoning": qoe_reason,
                }
            )

            fosi_score, fosi_reason, fosi_det, _, fosi_llm_used = self.calculate_fosi(
                document_text, fields, _llm_score(llm.get("fosi"))
            )
            results.append(
                {
                    "name": "Fairness Opinion Sensitivity Index (FOSI)",
                    "score": int(round(fosi_score)),
                    "deterministic_score": int(round(fosi_det)),
                    "llm_score": int(round(fosi_llm_used)),
                    "description": (
                        "Measures the number of independent valuation methodologies applied "
                        "(DCF, Precedent Transactions, Trading Comps) and their robustness."
                    ),
                    "calculation_logic": (
                        "FOSI = (Methods Used / 3) × (1 − CV(Valuations)). "
                        "Industry standard requires all three: DCF, Precedent Transactions, "
                        "and Trading Comparables."
                    ),
                    "risk_impact": (
                        "Reliance on a single valuation model exposes the Board of Directors "
                        "to shareholder litigation during change-of-control transactions."
                    ),
                    "reasoning": fosi_reason,
                }
            )

            ats_score, ats_reason, ats_det, _, ats_llm_used = self.calculate_ats(
                document_text, fields, _llm_score(llm.get("ats"))
            )
            results.append(
                {
                    "name": "Assumption Transparency Score (ATS)",
                    "score": int(round(ats_score)),
                    "deterministic_score": int(round(ats_det)),
                    "llm_score": int(round(ats_llm_used)),
                    "description": "Measures clarity of valuation/model assumptions, sources, and rationale.",
                    "calculation_logic": "Checks for assumption disclosure, source references, rationale, and base/management case markers.",
                    "risk_impact": "Opaque assumptions increase valuation bias risk and weaken board decision defensibility.",
                    "reasoning": ats_reason,
                }
            )

            sac_score, sac_reason, sac_det, _, sac_llm_used = self.calculate_sac(
                document_text, fields, _llm_score(llm.get("sac"))
            )
            results.append(
                {
                    "name": "Sensitivity Analysis Coverage (SAC)",
                    "score": int(round(sac_score)),
                    "deterministic_score": int(round(sac_det)),
                    "llm_score": int(round(sac_llm_used)),
                    "description": "Measures coverage of key valuation sensitivities (WACC, growth, multiples).",
                    "calculation_logic": "Checks for sensitivity analysis markers and key sensitivity dimensions.",
                    "risk_impact": "Missing sensitivity coverage increases downside risk of valuation error and litigation exposure.",
                    "reasoning": sac_reason,
                }
            )

            csj_score, csj_reason, csj_det, _, csj_llm_used = self.calculate_csj(
                document_text, fields, _llm_score(llm.get("csj"))
            )
            results.append(
                {
                    "name": "Comparable Set Justification (CSJ)",
                    "score": int(round(csj_score)),
                    "deterministic_score": int(round(csj_det)),
                    "llm_score": int(round(csj_llm_used)),
                    "description": "Measures explicit justification for comparable company/transaction set construction.",
                    "calculation_logic": "Checks for inclusion criteria, exclusion criteria, and selection rationale disclosures.",
                    "risk_impact": "Unjustified peer selection can skew valuation outcomes and fairness conclusions.",
                    "reasoning": csj_reason,
                }
            )

            cidc_score, cidc_reason, cidc_det, _, cidc_llm_used = self.calculate_cidc(
                document_text, fields, _llm_score(llm.get("cidc"))
            )
            results.append(
                {
                    "name": "Conflict & Independence Disclosure Completeness (CIDC)",
                    "score": int(round(cidc_score)),
                    "deterministic_score": int(round(cidc_det)),
                    "llm_score": int(round(cidc_llm_used)),
                    "description": "Measures completeness of independence, fee, and conflict disclosures.",
                    "calculation_logic": "Checks for independence statements, fee disclosures, conflict disclosures, and mandate references.",
                    "risk_impact": "Disclosure gaps increase governance and conflict-management risk in transaction approvals.",
                    "reasoning": cidc_reason,
                }
            )

            drt_score, drt_reason, drt_det, _, drt_llm_used = self.calculate_drt(
                document_text, fields, _llm_score(llm.get("drt"))
            )
            results.append(
                {
                    "name": "Data Room Traceability (DRT)",
                    "score": int(round(drt_score)),
                    "deterministic_score": int(round(drt_det)),
                    "llm_score": int(round(drt_llm_used)),
                    "description": "Measures traceability from analysis statements back to referenced data room artifacts.",
                    "calculation_logic": "Checks for data-room references, source document links, annex/exhibit markers, and cross-references.",
                    "risk_impact": "Weak traceability reduces diligence reliability and increases post-transaction dispute risk.",
                    "reasoning": drt_reason,
                }
            )

        # ── Fraud & Investigation ────────────────────────────────────────────
        elif banking_domain == "Fraud & Investigation Records":
            snad_score, snad_reason, snad_det, _, snad_llm_used = self.calculate_snad(
                document_text, fields, _llm_score(llm.get("snad"))
            )
            results.append(
                {
                    "name": "SAR Narrative Actionability Density (SNAD)",
                    "score": int(round(snad_score)),
                    "deterministic_score": int(round(snad_det)),
                    "llm_score": int(round(snad_llm_used)),
                    "description": (
                        "Measures the presence of the Six Essential Elements "
                        "(Who, What, When, Where, Why, How) in the SAR narrative section."
                    ),
                    "calculation_logic": (
                        "SNAD = (Σ Element Presence Flags / 6) × 100. "
                        "Each of the six narrative elements is verified via pattern matching. "
                        "A missing 'How' element = 83% maximum score."
                    ),
                    "risk_impact": (
                        "Ineffective SARs lead to FinCEN/NCA citations and 'look-back' orders "
                        "requiring years of re-analysis. Low SNAD prevents law enforcement action."
                    ),
                    "reasoning": snad_reason,
                }
            )

            wcw_score, wcw_reason, wcw_det, _, wcw_llm_used = self.calculate_wcw(
                document_text, fields, _llm_score(llm.get("wcw"))
            )
            results.append(
                {
                    "name": "Whistleblower Credibility Weight (WCW)",
                    "score": int(round(wcw_score)),
                    "deterministic_score": int(round(wcw_det)),
                    "llm_score": int(round(wcw_llm_used)),
                    "description": (
                        "Measures the ratio of corroborating evidence files "
                        "(emails, receipts, system logs) attached to the whistleblower claim."
                    ),
                    "calculation_logic": (
                        "WCW = (Independent Evidence Artifacts / Stated Claims) × "
                        "Evidence Reliability Factor. Rewards email, receipt, and audit log "
                        "attachments over unsubstantiated allegations."
                    ),
                    "risk_impact": (
                        "Low WCW floods investigators with low-value claims, "
                        "delaying detection of genuine insider trading or fraud."
                    ),
                    "reasoning": wcw_reason,
                }
            )

            tcs_score, tcs_reason, tcs_det, _, tcs_llm_used = self.calculate_tcs(
                document_text, fields, _llm_score(llm.get("tcs"))
            )
            results.append(
                {
                    "name": "Timeline Coherence Score (TCS)",
                    "score": int(round(tcs_score)),
                    "deterministic_score": int(round(tcs_det)),
                    "llm_score": int(round(tcs_llm_used)),
                    "description": "Measures chronological coherence and explicit time markers in investigations.",
                    "calculation_logic": "Checks for timeline/chronology sections, dated events, sequence cues, and incident date markers.",
                    "risk_impact": "Timeline inconsistency degrades case quality and weakens escalation/legal defensibility.",
                    "reasoning": tcs_reason,
                }
            )

            eccc_score, eccc_reason, eccc_det, _, eccc_llm_used = self.calculate_eccc(
                document_text, fields, _llm_score(llm.get("eccc"))
            )
            results.append(
                {
                    "name": "Evidence Chain-of-Custody Completeness (ECCC)",
                    "score": int(round(eccc_score)),
                    "deterministic_score": int(round(eccc_det)),
                    "llm_score": int(round(eccc_llm_used)),
                    "description": "Measures completeness of evidence chain-of-custody metadata.",
                    "calculation_logic": "Checks for evidence IDs, collection dates, handlers/custodians, and chain-of-custody references.",
                    "risk_impact": "Chain-of-custody gaps can invalidate investigative evidence.",
                    "reasoning": eccc_reason,
                }
            )

            tdc_score, tdc_reason, tdc_det, _, tdc_llm_used = self.calculate_tdc(
                document_text, fields, _llm_score(llm.get("tdc"))
            )
            results.append(
                {
                    "name": "Transaction Detail Completeness (TDC)",
                    "score": int(round(tdc_score)),
                    "deterministic_score": int(round(tdc_det)),
                    "llm_score": int(round(tdc_llm_used)),
                    "description": "Measures completeness of key transaction dimensions for case analysis.",
                    "calculation_logic": "Checks for amount, date, sender, receiver, and channel attributes.",
                    "risk_impact": "Missing transaction attributes limits triage quality and hampers investigation closure.",
                    "reasoning": tdc_reason,
                }
            )

            detr_score, detr_reason, detr_det, _, detr_llm_used = self.calculate_detr(
                document_text, fields, _llm_score(llm.get("detr"))
            )
            results.append(
                {
                    "name": "Disposition & Escalation Traceability (DETR)",
                    "score": int(round(detr_score)),
                    "deterministic_score": int(round(detr_det)),
                    "llm_score": int(round(detr_llm_used)),
                    "description": "Measures traceability of decisions, approvers, rationale, and escalation actions.",
                    "calculation_logic": "Checks for disposition/decision records, approvers, rationale, and escalation markers.",
                    "risk_impact": "Weak decision traceability increases oversight and regulatory challenge risk.",
                    "reasoning": detr_reason,
                }
            )

            rnc_score, rnc_reason, rnc_det, _, rnc_llm_used = self.calculate_rnc(
                document_text, fields, _llm_score(llm.get("rnc"))
            )
            results.append(
                {
                    "name": "Regulatory Notification Completeness (RNC)",
                    "score": int(round(rnc_score)),
                    "deterministic_score": int(round(rnc_det)),
                    "llm_score": int(round(rnc_llm_used)),
                    "description": "Measures whether regulator notification timing and references are documented.",
                    "calculation_logic": "Checks for notification records, filing date, reference/case ID, and regulator identifiers.",
                    "risk_impact": "Notification gaps increase enforcement risk for delayed or incomplete reporting.",
                    "reasoning": rnc_reason,
                }
            )

        else:
            logger.warning(
                "Unknown banking domain '%s' — no domain-specific metrics calculated.",
                banking_domain,
            )

        # ── Enrich each result with confidence, threshold & metric_code ───────
        for result in results:
            self._enrich_metric_result(result, llm_domain_scores or {})

        return results

    # ─────────────────────────────────────────────────────────────────────────
    # Metric enrichment
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _metric_code_from_name(name: str) -> str:
        """Derive the short metric code from the full metric name."""
        _name_to_code: dict[str, str] = {
            "Beneficial Ownership Transparency Index (BOTI)": "boti",
            "Identity Evidence Strength Score (IESS)": "iess",
            "Sanctions/PEP Screening Evidence Coverage (SPEC)": "spec",
            "CDD/EDD Trigger Justification Quality (CEDJ)": "cedj",
            "Source-of-Funds Traceability (SOFT)": "soft",
            "Address Verification Strength (AVS)": "avs",
            "Risk Rating Explainability (RRE)": "rre",
            "Collateral Perfection Index (CPI)": "cpi",
            "Covenant Compliance Transparency Score (CCTS)": "ccts",
            "Rate Index & Fallback Correctness (RIFC)": "rifc",
            "Execution & Authority Completeness (EAC)": "eac",
            "Repayment Schedule Integrity (RSI)": "rsi",
            "Borrower/Guarantor Identification Consistency (BGIC)": "bgic",
            "Collateral Valuation Recency (CVR)": "cvr",
            "HQLA Eligibility Confidence (HEC)": "hec",
            "Inter-System Reconciliation Ratio (ISRR)": "isrr",
            "Cut-off Time & Timestamp Alignment (CTTA)": "ctta",
            "Stress Scenario Coverage (SSC)": "ssc",
            "Inflow/Outflow Classification Completeness (IOCC)": "iocc",
            "Limit Breach Disclosure Quality (LBDQ)": "lbdq",
            "Source System Coverage (SSCOV)": "sscov",
            "Regulatory Mapping Precision (RMP)": "rmp",
            "BCBS 239 Data Lineage Integrity (DLI)": "dli",
            "Regulatory Change Coverage (RCC)": "rcc",
            "Disclosure Completeness Score (DCS)": "dcs",
            "Governance Sign-off Completeness (GSC)": "gsc",
            "Control Mapping Coverage (CMC)": "cmc",
            "Recordkeeping & Classification Policy Coverage (RCPC)": "rcpc",
            "QoE Normalization Transparency": "qoe",
            "Fairness Opinion Sensitivity Index (FOSI)": "fosi",
            "Assumption Transparency Score (ATS)": "ats",
            "Sensitivity Analysis Coverage (SAC)": "sac",
            "Comparable Set Justification (CSJ)": "csj",
            "Conflict & Independence Disclosure Completeness (CIDC)": "cidc",
            "Data Room Traceability (DRT)": "drt",
            "SAR Narrative Actionability Density (SNAD)": "snad",
            "Whistleblower Credibility Weight (WCW)": "wcw",
            "Timeline Coherence Score (TCS)": "tcs",
            "Evidence Chain-of-Custody Completeness (ECCC)": "eccc",
            "Transaction Detail Completeness (TDC)": "tdc",
            "Disposition & Escalation Traceability (DETR)": "detr",
            "Regulatory Notification Completeness (RNC)": "rnc",
        }
        for full_name, code in _name_to_code.items():
            if full_name in name or name in full_name:
                return code
        return name.lower()[:6]

    def _enrich_metric_result(self, result: dict, llm_domain_scores: dict) -> None:
        """
        Mutates result dict in-place to add:
        - metric_code
        - deterministic_score
        - llm_score
        - confidence (1 - |D-L|/100)
        - regulatory_pass_threshold
        - regulatory_reference
        - passes_regulatory_threshold
        """
        from app.config import settings  # local import to avoid circular

        metric_code = self._metric_code_from_name(result.get("name", ""))
        result["metric_code"] = metric_code

        blended = float(result.get("score", 0))

        det_existing = result.get("deterministic_score")
        llm_existing = result.get("llm_score")
        llm_raw = llm_domain_scores.get(metric_code)
        if isinstance(llm_raw, dict):
            llm_s = float(llm_raw.get("score", blended))
            llm_reasoning = (
                llm_raw.get("reasoning")
                or llm_raw.get("rationale")
                or llm_raw.get("explanation")
                or ""
            )
            if isinstance(llm_reasoning, str) and llm_reasoning.strip():
                result["llm_reasoning"] = llm_reasoning.strip()

            llm_evidence = llm_raw.get("evidence")
            if isinstance(llm_evidence, list):
                result["llm_evidence"] = [str(x).strip() for x in llm_evidence if str(x).strip()][:3]
        elif llm_raw is not None:
            llm_s = float(llm_raw)
        else:
            llm_s = blended  # No LLM score; treat as equal to blended

        if det_existing is not None and llm_existing is not None:
            try:
                det_s = float(det_existing)
                llm_s_used = float(llm_existing)
            except Exception:
                det_s = None
                llm_s_used = None
        else:
            det_s = None
            llm_s_used = None

        if det_s is None or llm_s_used is None:
            # Backward-compatible fallback: Recover deterministic score from blend formula
            # D = (blended - L*0.3) / 0.7
            det_s = (blended - llm_s * 0.3) / 0.7
            det_s = max(0.0, min(100.0, round(det_s, 1)))
            llm_s_used = llm_s

        det_s = max(0.0, min(100.0, float(det_s)))
        llm_s_used = max(0.0, min(100.0, float(llm_s_used)))

        result["deterministic_score"] = int(round(det_s))
        result["llm_score"] = int(round(llm_s_used))
        result["confidence"] = round(max(0.0, 1.0 - abs(det_s - llm_s_used) / 100.0), 2)

        # Regulatory threshold lookup
        thresholds = getattr(settings, "BANKING_REGULATORY_THRESHOLDS", {})
        threshold_info = thresholds.get(metric_code, {})
        threshold_val = threshold_info.get("threshold", None)
        threshold_label = threshold_info.get("label", "")

        result["regulatory_pass_threshold"] = threshold_val
        result["regulatory_reference"] = threshold_label
        result["passes_regulatory_threshold"] = (
            blended >= threshold_val if threshold_val is not None else True
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Banking issue generation
    # ─────────────────────────────────────────────────────────────────────────

    def extract_banking_issues(
        self, banking_metrics: list[dict], domain: str
    ) -> list[dict]:
        """
        Generate IssueSchema-compatible dicts for failing banking metrics.

        Any metric scoring below its regulatory_pass_threshold is reported as a
        Critical or Warning issue with the relevant regulation_reference attached.

        Args:
            banking_metrics: Enriched metric result dicts from evaluate_domain().
            domain: Banking domain name (for context in descriptions).

        Returns:
            List of issue dicts compatible with IssueSchema.
        """
        def _hint_for_metric(code: str) -> str:
            code_l = (code or "").lower()
            hints: dict[str, str] = {
                "spec": "Include sanctions/PEP screening run date, source watchlists, screening result, and reviewer sign-off.",
                "cedj": "Document CDD/EDD trigger rationale with explicit risk indicators (PEP, adverse media, jurisdiction).",
                "soft": "Link source-of-funds claims to verifiable evidence artifacts (statements, payslips, contracts).",
                "avs": "Add recent proof-of-address evidence and explicit address-match confirmation.",
                "rre": "Document risk rating drivers (jurisdiction, product, channel, ownership complexity) clearly.",
                "rifc": "Replace LIBOR-only terms with compliant benchmark and fallback language (e.g., SOFR).",
                "eac": "Add missing signatures, authority evidence, and board resolution references.",
                "rsi": "Add complete repayment schedule terms covering tenor, dates, and payment frequency.",
                "bgic": "Reconcile borrower/guarantor identifiers consistently across all related documents.",
                "cvr": "Attach current collateral valuation evidence and policy-window recency confirmation.",
                "ctta": "Document cut-off times and verify timestamp alignment between report and source systems.",
                "ssc": "Include defined stress scenarios with assumptions and documented outcomes.",
                "iocc": "Complete inflow/outflow categories with required classification buckets.",
                "lbdq": "Document breach action taken, approvals, and escalation trail for each limit breach.",
                "sscov": "Reference all source systems of record (GL/core/treasury) used for report construction.",
                "rmp": "Add explicit regulation/taxonomy citations (e.g., CRR/CRD, EBA RTS/ITS, BCBS 239, Pillar 3) and map sections to those references.",
                "dli": "Document data lineage (source systems, system-of-record, ETL/feeds, audit trail) and controls over manual adjustments.",
                "rcc": "Add change control evidence: version history, effective date, revision log, and how regulatory updates are tracked.",
                "dcs": "Add the mandatory disclosure sections for the document’s framework (e.g., Pillar 3 topics or policy/framework sections like scope, roles, requirements, evidence, review cycle).",
                "gsc": "Add governance sign-off: accountable owner, approver(s), approval date, and remove any draft markers.",
                "cmc": "Provide a control mapping matrix linking requirements → controls → owners → testing cadence → evidence artifacts.",
                "rcpc": "Specify recordkeeping & classification: retention periods, labels, storage, disposal, and legal hold / e-discovery handling.",
                "ats": "List key valuation assumptions with data sources and rationale.",
                "sac": "Add sensitivity analysis for WACC, growth, and valuation multiples.",
                "csj": "Document inclusion/exclusion criteria for comparable sets and justify peer selection.",
                "cidc": "Disclose independence, fees, and conflict-of-interest statements explicitly.",
                "drt": "Add traceable links from conclusions to data-room documents and exhibit references.",
                "tcs": "Rebuild a chronological timeline with explicit event timestamps.",
                "eccc": "Capture full chain-of-custody metadata for evidence artifacts (ID, dates, handlers).",
                "tdc": "Add missing transaction dimensions (amount, date, sender, receiver, channel).",
                "detr": "Record decision, approver, rationale, and escalation path for each case action.",
                "rnc": "Include regulator notification timestamps, references, and filing identifiers.",
            }
            return hints.get(code_l, "Strengthen document evidence and add audit-ready artifacts supporting this metric.")

        def _format_metric_issue_description(metric: dict, score: float, threshold: int | None, deficit: float) -> str:
            metric_name = metric.get("name", "This metric")
            llm_reason = (metric.get("llm_reasoning") or "").strip()
            
            target = f"{threshold}" if threshold is not None else "N/A"
            parts: list[str] = [f"{metric_name} scored {int(score)}/100 (target: {target})."]
            
            if llm_reason:
                parts.append(llm_reason)
            else:
                parts.append(f"Requires attention: {_hint_for_metric(metric.get('metric_code', ''))}")
                
            return " ".join(p for p in parts if p)

        issues: list[dict] = []
        for metric in banking_metrics:
            score = metric.get("score", 100)
            threshold = metric.get("regulatory_pass_threshold")
            passes = metric.get("passes_regulatory_threshold", True)
            metric_name = metric.get("name", "Unknown Metric")
            metric_code = metric.get("metric_code", "")
            regulation = metric.get("regulatory_reference", "")

            if not passes and threshold is not None:
                deficit = threshold - score
                severity = "critical" if deficit >= 20 else "warning"
                issues.append(
                    {
                        "field_name": metric_name,
                        "issue_type": "banking_metric_below_threshold",
                        "description": _format_metric_issue_description(metric, score, threshold, deficit),
                        "severity": severity,
                        "regulation_reference": regulation,
                        "metric_dimension": domain,
                    }
                )
            elif score < 75:
                # Score above threshold but still low quality — Warning
                issues.append(
                    {
                        "field_name": metric_name,
                        "issue_type": "banking_metric_low",
                        "description": (
                            f"{metric_name} scored {score}/100 — below the recommended quality baseline of 75. "
                            f"{(metric.get('llm_reasoning') or '').strip()} "
                            f"Recommended fix: {_hint_for_metric(metric_code)}"
                        ),
                        "severity": "warning",
                        "regulation_reference": regulation,
                        "metric_dimension": domain,
                    }
                )

        return issues

    # ─────────────────────────────────────────────────────────────────────────
    # Dependency Block / Legal Hold
    # ─────────────────────────────────────────────────────────────────────────

    def check_dependency_block(
        self,
        domain: str,
        banking_metrics: list[dict],
        document_text: str = "",
    ) -> tuple[bool, str]:
        """
        Evaluate whether any critical dependency threshold has been breached,
        triggering a Legal Hold on the document.

        Args:
            domain: Detected banking domain.
            banking_metrics: Enriched metric list from evaluate_domain().

        Returns:
            Tuple (legal_hold: bool, reason: str).
        """
        from app.config import settings  # local import

        block_rules = getattr(settings, "DEPENDENCY_BLOCK_RULES", {})
        domain_rules: list[dict] = block_rules.get(domain, [])

        # The Regulatory domain includes both *filings* (Pillar 3, ICAAP, SAR, etc.)
        # and general compliance/policy documents (e.g., PCI-DSS policies). Legal
        # Hold is intended for filing/submission blockers only.
        text_lower = (document_text or "").lower()
        filing_like = bool(
            re.search(
                r"\bpillar\s*3\b|\bicaap\b|\bilaap\b|\bbcbs\b|\bbasel\b|\bcrr\b|\bcrd\b|\beba\b|\bfincen\b|\bsar\b",
                text_lower,
            )
        )

        scores_by_code = {m.get("metric_code"): m.get("score", 100) for m in banking_metrics}

        for rule in domain_rules:
            metric_code = rule.get("metric_code", "")
            required_threshold = rule.get("threshold", 0)
            actual_score = scores_by_code.get(metric_code, 100)

            if domain == "Regulatory & Compliance Filings" and not filing_like:
                # Still surface the metric as an issue below threshold, but avoid
                # halting workflows with a Legal Hold for non-filing policy docs.
                continue

            if actual_score < required_threshold:
                message = rule.get(
                    "message",
                    f"Metric {metric_code} scored {actual_score}, below threshold {required_threshold}.",
                )
                logger.warning(
                    "LEGAL HOLD triggered for domain '%s': %s (score=%s, threshold=%s)",
                    domain, metric_code, actual_score, required_threshold,
                )
                return True, message

        return False, ""

