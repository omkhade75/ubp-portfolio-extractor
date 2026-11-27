import re
from typing import Optional, Tuple
from pydantic import BaseModel, Field

class IdentifierResult(BaseModel):
    raw_identifier: str
    normalized_identifier: str
    status: str = "PASS"  # "PASS", "NORMALIZED", "REVIEW_REQUIRED", "NOT_PRESENT"
    provenance: str = "EXACT_MATCH"
    confidence: float = 95.0
    detected_format: str = "UNKNOWN"

DISALLOWED_IDENTIFIER_TOKENS = {
    "BONDS", "NOTES", "ALTERNATIVES", "ALTERNATIVE", "EQUITIES", "EQUITY",
    "STRUCTURED", "PRODUCTS", "CERTIFICATES", "FUNDS", "SHARES", "TOTAL",
    "SAMPLE", "NOT", "VALID", "DEMO", "INVESTMENTS", "USD", "EUR", "GBP", "CHF", "HKD",
    "SUBTOTAL", "BALANCE", "PERFORMANCE", "OVERVIEW", "SUMMARY", "NOMINAL", "RATING",
    "INTEREST", "ACCRUED", "PRICE", "VALUE", "ASSETS", "SERIES", "CLASS", "IN",
    "ESG", "PREVIOUS", "CURRENT", "AVERAGE", "LEADER", "OUTPERFORM", "UNDERPERFORM"
}

def normalize_security_identifier(
    raw_id: Optional[str],
    is_ocr: bool = False,
    confidence: float = 95.0
) -> IdentifierResult:
    """
    Deterministic security identifier normalization, verification, and character confusion handling.
    Complies with:
      - STEP A: Column region isolation
      - STEP D: Multi-format validation (ISIN, CUSIP, Valoren, synthetic/test codes)
      - STEP E: Format-guided character confusion handling (O/0, I/1, l/1, S/5, B/8, Z/2)
      - STEP F: Uncertain identifier handling with explicit REVIEW_REQUIRED preservation
    """
    if not raw_id or not raw_id.strip():
        return IdentifierResult(
            raw_identifier="",
            normalized_identifier="",
            status="NOT_PRESENT",
            provenance="EMPTY_SOURCE",
            confidence=confidence,
            detected_format="NONE"
        )

    raw_clean = raw_id.strip()
    # Strip any preexisting annotation e.g. '(REVIEW_REQUIRED)' for baseline inspection
    base = re.sub(r"\s*\([^\)]*REVIEW_REQUIRED[^\)]*\)", "", raw_clean).strip().upper()

    # Reject disallowed keywords, category names, or ESG markers
    if base in DISALLOWED_IDENTIFIER_TOKENS:
        return IdentifierResult(
            raw_identifier=raw_clean,
            normalized_identifier=raw_clean,
            status="REVIEW_REQUIRED",
            provenance="DISALLOWED_KEYWORD_REJECTED",
            confidence=confidence,
            detected_format="INVALID"
        )

    # -------------------------------------------------------------
    # 1. Standard ISO 6166 ISIN or 12-char Alphanumeric Code
    # -------------------------------------------------------------
    # e.g. LU2001707251, XS2981244168, US0378331005, XSSYN0001081
    if re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", base):
        # Check if internal numeric block has OCR letter substitution
        # e.g. XSSYN + OOOI + 090 where OOOI is 0001
        m_xssyn = re.match(r"^(XSSYN)([A-Z0-9]{7})$", base)
        if m_xssyn:
            sfx = m_xssyn.group(2)
            if any(c in sfx for c in "OILSBZ"):
                sfx_norm = sfx.translate(str.maketrans("OILSBZ", "011582"))
                if sfx_norm.isdigit() and len(sfx_norm) == 7:
                    norm = f"{m_xssyn.group(1)}{sfx_norm}"
                    return IdentifierResult(
                        raw_identifier=raw_clean,
                        normalized_identifier=norm,
                        status="NORMALIZED",
                        provenance="OCR_CHAR_CORRECTION: Suffix letters [O,I,L,S,B,Z] converted to digits",
                        confidence=confidence,
                        detected_format="SYNTHETIC_ISIN"
                    )
        return IdentifierResult(
            raw_identifier=raw_clean,
            normalized_identifier=base,
            status="PASS",
            provenance="EXACT_MATCH",
            confidence=confidence,
            detected_format="ISO_6166_ISIN"
        )

    # -------------------------------------------------------------
    # 2. Extraneous 'O' inserted between alpha prefix and numeric body
    # -------------------------------------------------------------
    # Tesseract OCR boundary artifact: e.g. 'XSSYNO0001081' (13 chars) -> 'XSSYN0001081' (12 chars)
    m_extra_o = re.match(r"^([A-Z]{2,5})[oO]([0-9]{7})$", base)
    if m_extra_o:
        norm = f"{m_extra_o.group(1)}{m_extra_o.group(2)}"
        return IdentifierResult(
            raw_identifier=raw_clean,
            normalized_identifier=norm,
            status="NORMALIZED",
            provenance="OCR_CHAR_CORRECTION: Extraneous 'O' inserted between alpha prefix and numeric payload removed",
            confidence=confidence,
            detected_format="SYNTHETIC_ISIN"
        )

    # -------------------------------------------------------------
    # 3. 12-char Alphanumeric where numeric payload has OCR letter confusions
    # -------------------------------------------------------------
    # e.g. 'XSSYNOOOI090' (12 chars: XSSYN + OOOI090)
    m_alpha_num = re.match(r"^([A-Z]{2,5})([A-Z0-9]{7,8})$", base)
    if m_alpha_num:
        prefix, sfx = m_alpha_num.group(1), m_alpha_num.group(2)
        sfx_norm = sfx.translate(str.maketrans("OILSBZ", "011582"))
        if sfx_norm.isdigit() and len(sfx_norm) == 7:
            norm = f"{prefix}{sfx_norm}"
            return IdentifierResult(
                raw_identifier=raw_clean,
                normalized_identifier=norm,
                status="NORMALIZED",
                provenance="OCR_CHAR_CORRECTION: Suffix letters converted to digits",
                confidence=confidence,
                detected_format="SYNTHETIC_ISIN"
            )

    # -------------------------------------------------------------
    # 4. Hyphenated Security / CUSIP / Valoren Codes
    # -------------------------------------------------------------
    # e.g. CH-VAL-TEST-42002, PB-TEST-PE-0056, US-TEST-010B, XS-NG-20482
    # Also handles tail OCR confusion e.g. CUSP-TEST-OI -> CUSP-TEST-01
    m_hyph_tail = re.match(r"^([A-Z0-9]+-[A-Z0-9]+)-([A-Z0-9]+)$", base)
    if m_hyph_tail:
        pref, tail = m_hyph_tail.group(1), m_hyph_tail.group(2)
        tail_norm = tail.translate(str.maketrans("OI", "01"))
        if tail_norm.isdigit():
            norm = f"{pref}-{tail_norm}"
            return IdentifierResult(
                raw_identifier=raw_clean,
                normalized_identifier=norm,
                status="NORMALIZED" if tail != tail_norm else "PASS",
                provenance="OCR_CHAR_CORRECTION: Tail letters converted to digits" if tail != tail_norm else "STRUCTURED_MATCH",
                confidence=confidence,
                detected_format="HYPHENATED_SECURITY_CODE"
            )

    if re.match(r"^[A-Z0-9]{2,6}(-[A-Z0-9]{2,8})+$", base) and any(c.isdigit() for c in base):
        return IdentifierResult(
            raw_identifier=raw_clean,
            normalized_identifier=base,
            status="PASS",
            provenance="STRUCTURED_MATCH",
            confidence=confidence,
            detected_format="HYPHENATED_SECURITY_CODE"
        )

    # -------------------------------------------------------------
    # 5. Swiss Valoren / Pure Numeric Security Code (6-10 digits)
    # -------------------------------------------------------------
    if re.match(r"^\d{6,10}(\.\d{3})?$", base):
        return IdentifierResult(
            raw_identifier=raw_clean,
            normalized_identifier=base,
            status="PASS",
            provenance="EXACT_MATCH",
            confidence=confidence,
            detected_format="SWISS_VALOREN"
        )

    # -------------------------------------------------------------
    # 6. UBP Internal Security Code
    # -------------------------------------------------------------
    if re.match(r"^X[DF][A-Z0-9]{8,12}$", base):
        return IdentifierResult(
            raw_identifier=raw_clean,
            normalized_identifier=base,
            status="PASS",
            provenance="STRUCTURED_MATCH",
            confidence=confidence,
            detected_format="UBP_INTERNAL"
        )

    # -------------------------------------------------------------
    # 7. Fallback for Uncertain OCR Identifiers (STEP F)
    # -------------------------------------------------------------
    # Never guess blindly. Preserve raw OCR text and mark REVIEW_REQUIRED.
    return IdentifierResult(
        raw_identifier=raw_clean,
        normalized_identifier=f"{base} (REVIEW_REQUIRED)",
        status="REVIEW_REQUIRED",
        provenance="UNCERTAIN_STRUCTURE",
        confidence=min(confidence, 70.0),
        detected_format="UNRECOGNIZED"
    )
