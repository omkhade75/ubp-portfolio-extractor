import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple, NamedTuple

class SourceValueState:
    EXPLICIT_ZERO = "EXPLICIT_ZERO"
    NUMERIC_VALUE = "NUMERIC_VALUE"
    SOURCE_DASH = "SOURCE_DASH"
    SOURCE_BLANK = "SOURCE_BLANK"
    UNREADABLE = "UNREADABLE"
    CALCULATED = "CALCULATED"

class FinancialNumber(NamedTuple):
    raw: str
    value: Optional[Decimal]
    is_valid: bool
    is_negative: bool
    has_asterisk: bool
    is_percentage: bool
    currency: Optional[str] = None
    error: Optional[str] = None
    state: str = SourceValueState.NUMERIC_VALUE
    is_dash: bool = False

# Known currency symbols/codes
COMMON_CURRENCIES = {"USD", "EUR", "HKD", "CHF", "GBP", "SGD", "JPY", "CAD", "AUD"}

def clean_financial_string(text: str) -> str:
    """Standardizes typographical marks in financial strings."""
    if not text:
        return ""
    # Normalize various apostrophe and dash characters
    res = text.strip()
    res = res.replace("’", "'").replace("‘", "'").replace("`", "'").replace("·", "'").replace("•", "'")
    res = res.replace("–", "-").replace("—", "-").replace("−", "-")
    # OCR number repair: e.g. 250' ooo -> 250'000, 649 '022 -> 649'022
    res = re.sub(r"(\d+)'\s*([oO]{3})", r"\1'000", res)
    res = re.sub(r"(\d+)\s*'\s*(\d+)", r"\1'\2", res)
    # Strip trailing period if number already contains a decimal period
    if res.endswith(".") and res[:-1].count(".") >= 1:
        res = res[:-1].strip()
    return res

def parse_financial_number(
    raw_text: Optional[str],
    allow_blank: bool = True,
    default_currency: Optional[str] = None
) -> FinancialNumber:
    """
    Deterministically parses UBP and Swiss/European financial numbers into Decimal.
    Supports:
      - 2’267’669.27
      - 64’470.32- (trailing minus)
      - -64’470.32 (leading minus)
      - (64’470.32) (parentheses negative)
      - 1’227.62* (asterisk price with date)
      - 20.90% or -0.33%
      - 0.00 or 0 or '-'
    Preserves exact Decimal precision without float conversion.
    Never silently converts invalid characters to 0.00.
    """
    if raw_text is None:
        if allow_blank:
            return FinancialNumber(raw="", value=None, is_valid=True, is_negative=False, has_asterisk=False, is_percentage=False, state=SourceValueState.SOURCE_BLANK)
        return FinancialNumber(raw="", value=None, is_valid=False, is_negative=False, has_asterisk=False, is_percentage=False, state=SourceValueState.UNREADABLE, error="Empty input")

    raw = clean_financial_string(raw_text)
    if not raw:
        if allow_blank:
            return FinancialNumber(raw=raw_text, value=None, is_valid=True, is_negative=False, has_asterisk=False, is_percentage=False, state=SourceValueState.SOURCE_BLANK)
        return FinancialNumber(raw=raw_text, value=None, is_valid=False, is_negative=False, has_asterisk=False, is_percentage=False, state=SourceValueState.UNREADABLE, error="Blank string")

    # Check for dash representing unavailable, not applicable, or nil marker
    # In accordance with source fidelity standards, dash is preserved as None numeric value
    if raw in ("-", "--", "—", "-.-"):
        return FinancialNumber(
            raw=raw_text,
            value=None,
            is_valid=True,
            is_negative=False,
            has_asterisk=False,
            is_percentage=False,
            state=SourceValueState.SOURCE_DASH,
            is_dash=True
        )

    work = raw
    detected_currency = default_currency
    for curr in COMMON_CURRENCIES:
        if curr in work:
            detected_currency = curr
            work = work.replace(curr, "").strip()

    has_asterisk = "*" in work
    if has_asterisk:
        work = work.replace("*", "").strip()

    is_percentage = "%" in work
    if is_percentage:
        work = work.replace("%", "").strip()

    is_negative = False
    # Check parentheses: (123.45)
    if work.startswith("(") and work.endswith(")"):
        is_negative = True
        work = work[1:-1].strip()
    # Check trailing minus: 123.45-
    elif work.endswith("-"):
        is_negative = True
        work = work[:-1].strip()
    # Check leading minus: -123.45
    elif work.startswith("-"):
        is_negative = True
        work = work[1:].strip()

    # Remove thousands separators (apostrophe, comma)
    # Be careful: if comma is decimal separator (e.g. 1.234,56), standard UBP uses period decimal (2’267’669.27)
    clean_digits = work.replace("'", "").replace(",", "").replace(" ", "")
    if clean_digits.endswith(".") and clean_digits[:-1].count(".") >= 1:
        clean_digits = clean_digits[:-1]

    # Validate digits format
    if not re.match(r"^\d+(\.\d+)?$", clean_digits):
        return FinancialNumber(
            raw=raw_text,
            value=None,
            is_valid=False,
            is_negative=is_negative,
            has_asterisk=has_asterisk,
            is_percentage=is_percentage,
            currency=detected_currency,
            state=SourceValueState.UNREADABLE,
            error=f"Cannot parse '{clean_digits}' as Decimal"
        )

    try:
        dec_val = Decimal(clean_digits)
        if is_negative and dec_val != Decimal("0"):
            dec_val = -dec_val
        num_state = SourceValueState.EXPLICIT_ZERO if dec_val == Decimal("0") else SourceValueState.NUMERIC_VALUE
        return FinancialNumber(
            raw=raw_text,
            value=dec_val,
            is_valid=True,
            is_negative=is_negative,
            has_asterisk=has_asterisk,
            is_percentage=is_percentage,
            currency=detected_currency,
            state=num_state,
            is_dash=False
        )
    except InvalidOperation as e:
        return FinancialNumber(
            raw=raw_text,
            value=None,
            is_valid=False,
            is_negative=is_negative,
            has_asterisk=has_asterisk,
            is_percentage=is_percentage,
            currency=detected_currency,
            state=SourceValueState.UNREADABLE,
            error=str(e)
        )

def format_financial_decimal(val: Optional[Decimal], decimal_places: int = 2) -> str:
    """Formats Decimal into standard UBP apostrophe style string: 2'267'669.27"""
    if val is None:
        return ""
    q = Decimal(10) ** -decimal_places
    quantized = val.quantize(q)
    parts = f"{abs(quantized):.{decimal_places}f}".split(".")
    int_part = parts[0]
    frac_part = parts[1] if len(parts) > 1 else ""
    
    # Insert apostrophes
    s = ""
    for i, ch in enumerate(reversed(int_part)):
        if i > 0 and i % 3 == 0:
            s = "'" + s
        s = ch + s
    res = f"{s}.{frac_part}" if frac_part else s
    if val < Decimal("0"):
        res = "-" + res
    return res
