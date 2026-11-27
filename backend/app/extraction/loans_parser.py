import re
from typing import List, Tuple, Optional
from decimal import Decimal
import pymupdf

from app.models.schemas import LoanItem
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines, VisualLine
from app.extraction.table_header_engine import (
    LOANS_SYNONYMS,
    TableColumnMap,
    build_table_column_map,
    assign_words_to_columns,
    is_valid_iso_currency,
)

_LOAN_START_RE = re.compile(
    r"\b(?:LOAN\s+FACILITIES|LOANS|FIXED\s+LOANS?|BORROWINGS|CREDIT\s+FACILITIES)\b",
    re.IGNORECASE,
)
_LOAN_STOP_RE = re.compile(
    r"\b(?:SUMMARY\s+OF\s+NET\s+ASSETS|E\.&\s*O\.E\.|PAGE\s+\d+)\b",
    re.IGNORECASE,
)


def _looks_like_loans_header(tu: str) -> bool:
    has_ref = any(k in tu for k in ["LOAN REFERENCE", "DENOMINATION", "REFERENCE", "DESCRIPTION", "MATURITY"])
    has_val = any(k in tu for k in ["PRINCIPAL", "AMOUNT", "OUTSTANDING", "MARKET VALUE", "VALUE IN USD", "INTEREST RATE", "RATE/"])
    return (has_ref and has_val) or ("CURRENCY" in tu and has_val)


def parse_loans_page(
    page: pymupdf.Page, page_num: int
) -> Tuple[List[LoanItem], Optional[Decimal], Optional[Decimal]]:
    """
    Header-driven parser for Loans / Loan Facilities sections across UBP and synthetic templates.
    Supports section-local headers (e.g. CURRENCY | PRINCIPAL | LOAN REFERENCE | MATURITY | INTEREST RATE | OUTSTANDING (USD))
    as well as UBP shared page-top headers. Recognizes any currency-anchored or loan-reference data row,
    while attaching UBP accrued-interest continuation lines cleanly.
    Returns (list_of_loans, subtotal_usd, subtotal_percentage).
    """
    _, lines = extract_visual_words_and_lines(page)
    loans: List[LoanItem] = []
    subtotal_usd: Optional[Decimal] = None
    subtotal_pct: Optional[Decimal] = None

    pw = page.rect.width
    ph = page.rect.height

    page_top_header_lines: List[VisualLine] = []
    local_header_lines: List[VisualLine] = []
    col_map: Optional[TableColumnMap] = None

    in_loans = False
    loan_lines: List[List[VisualLine]] = []
    current_loan_group: List[VisualLine] = []

    for idx, l in enumerate(lines):
        t = l.text.strip()
        tu = t.upper()

        if not in_loans and l.y < ph * 0.25 and not _LOAN_STOP_RE.search(tu):
            if _looks_like_loans_header(tu) and "CURRENT ACCOUNTS" not in tu:
                page_top_header_lines.append(l)
                if idx + 1 < len(lines):
                    nl = lines[idx + 1]
                    nlu = nl.text.upper()
                    if nl.y - l.y <= 18.0 and "CURRENT ACCOUNTS" not in nlu and not _LOAN_START_RE.search(nlu):
                        page_top_header_lines.append(nl)

        if _LOAN_START_RE.search(tu) and "CURRENT ACCOUNT" not in tu and "TOTAL LOAN" not in tu and not (
            re.search(r"\bFIXED\s+LOAN\b", tu) and any(is_valid_iso_currency(w.text) for w in l.words)
        ):
            in_loans = True
            for w in l.words:
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    if subtotal_usd is None:
                        subtotal_usd = fn.value
                    elif subtotal_pct is None:
                        subtotal_pct = fn.value
            continue

        if not in_loans:
            continue

        if _LOAN_STOP_RE.search(tu) or l.y > ph * 0.90:
            in_loans = False
            continue

        # Capture local table header under LOAN FACILITIES / LOANS
        if _looks_like_loans_header(tu) and not any(is_valid_iso_currency(w.text) for w in l.words if w.x0 < pw * 0.14):
            local_header_lines.append(l)
            col_map = build_table_column_map(local_header_lines, LOANS_SYNONYMS, "LOANS", pw)
            continue

        # Ignore subtotal lines inside Loans
        if "TOTAL LOAN" in tu or "SUBTOTAL" in tu:
            nums = [
                parse_financial_number(w.text).value
                for w in l.words
                if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
            ]
            if nums:
                subtotal_usd = nums[0]
                if len(nums) >= 2:
                    subtotal_pct = nums[1]
            continue

        if subtotal_usd is None and not current_loan_group:
            num_words = [
                w for w in l.words
                if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
            ]
            if len(num_words) >= 2 and len(l.words) <= 3:
                subtotal_usd = parse_financial_number(num_words[0].text).value
                subtotal_pct = parse_financial_number(num_words[1].text).value
                continue

        # Detect start of a loan record generically (not restricted to FIXED LOAN / TR...)
        has_left_iso = any(
            w.x0 < pw * 0.15 and is_valid_iso_currency(re.sub(r"[^A-Z]", "", w.text.upper()))
            for w in l.words
        )
        has_loan_ref = bool(re.search(r"\b(?:TR[0-9A-Za-z\.]+|LN[-A-Z0-9]{3,})\b", tu))
        is_primary_loan = (
            "FIXED LOAN" in tu
            or (has_left_iso and not "ACCRUED INTEREST" in tu)
            or (has_loan_ref and "ACCRUED" not in tu)
        )

        if is_primary_loan:
            if current_loan_group:
                loan_lines.append(current_loan_group)
            current_loan_group = [l]
        elif current_loan_group:
            # Skip non-financial disclosure lines after loan rows
            if "THIS SYNTHETIC" in tu or "FINANCIAL CALCULATIONS" in tu or "NOT VALID FOR" in tu:
                continue
            current_loan_group.append(l)

    if current_loan_group:
        loan_lines.append(current_loan_group)

    if col_map is None and page_top_header_lines:
        col_map = build_table_column_map(page_top_header_lines, LOANS_SYNONYMS, "LOANS", pw)

    loan_counter = 1
    for group in loan_lines:
        prim_l = group[0]
        words = prim_l.words

        curr: Optional[str] = None
        amt_val: Optional[Decimal] = None
        desc = ""
        ref: Optional[str] = None
        maturity_date: Optional[str] = None
        rate_val: Optional[Decimal] = None
        mkt_val: Optional[Decimal] = None
        usd_val: Optional[Decimal] = None
        pct_val: Optional[Decimal] = None
        accrued_int: Optional[Decimal] = None

        if col_map and len(col_map.ordered_columns) >= 2:
            assigned, _ = assign_words_to_columns(words, col_map)

            for w in assigned.get("CURRENCY", []):
                wt = re.sub(r"[^A-Z]", "", w.text.upper())
                if is_valid_iso_currency(wt):
                    curr = wt
                    break
            if curr is None:
                for w in words:
                    wt = re.sub(r"[^A-Z]", "", w.text.upper())
                    if w.x0 < pw * 0.15 and is_valid_iso_currency(wt):
                        curr = wt
                        break

            for w in assigned.get("PRINCIPAL", []):
                wt = re.sub(r"[^A-Z]", "", w.text.upper())
                if is_valid_iso_currency(wt):
                    continue
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    amt_val = fn.value
                    break

            desc_words = [
                w for w in assigned.get("LOAN_REFERENCE", [])
                if not (is_valid_iso_currency(re.sub(r"[^A-Z]", "", w.text.upper())) and w.x0 < pw * 0.15)
            ]
            desc = " ".join(w.text for w in desc_words).strip()

            # Check maturity within MATURITY column first, then fallback across LOAN_REFERENCE (UBP sometimes puts maturity date under LOAN_REFERENCE text or MATURITY DATE)
            for w in assigned.get("MATURITY", []):
                if re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip()):
                    maturity_date = w.text.strip()
                    break
            if not maturity_date:
                for w in desc_words + words:
                    if re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip()):
                        maturity_date = w.text.strip()
                        break

            # Extract interest rate cleanly from INTEREST_RATE column (strips % if present)
            for w in assigned.get("INTEREST_RATE", []):
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    rate_val = fn.value
                    break
            if rate_val is None:
                for w in words:
                    if "%" in w.text:
                        fn = parse_financial_number(w.text)
                        if fn.is_valid and fn.value is not None:
                            rate_val = fn.value
                            break

            for w in assigned.get("MARKET_VALUE", []):
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    mkt_val = fn.value
                    break

            for w in assigned.get("REPORTING_VALUE", []):
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    usd_val = fn.value
                    break

            for w in assigned.get("PERCENTAGE", []):
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    pct_val = fn.value
                    break
        else:
            # Headerless layout fallback (positional zones matching UBP Accounts/Loans pages)
            for w in words:
                wt = re.sub(r"[^A-Z]", "", w.text.upper())
                if w.x0 < pw * 0.14 and is_valid_iso_currency(wt):
                    curr = wt
                    break
            for w in words:
                if pw * 0.07 <= w.x0 < pw * 0.16:
                    fn = parse_financial_number(w.text)
                    if fn.is_valid and fn.value is not None:
                        amt_val = fn.value
                        break
            desc_words = [w for w in words if pw * 0.12 <= w.x0 < pw * 0.50]
            desc = " ".join(w.text for w in desc_words).strip()
            for w in words:
                if pw * 0.45 <= w.x0 < pw * 0.60 and re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip()):
                    maturity_date = w.text.strip()
                    break
            for w in words:
                if pw * 0.55 <= w.x0 < pw * 0.68:
                    fn = parse_financial_number(w.text)
                    if fn.is_valid and fn.value is not None:
                        rate_val = fn.value
                        break
            for w in words:
                if pw * 0.65 <= w.x0 < pw * 0.83:
                    fn = parse_financial_number(w.text)
                    if fn.is_valid and fn.value is not None:
                        mkt_val = fn.value
                elif pw * 0.82 <= w.x0 < pw * 0.91:
                    fn = parse_financial_number(w.text)
                    if fn.is_valid and fn.value is not None:
                        usd_val = fn.value
                elif w.x0 >= pw * 0.90:
                    fn = parse_financial_number(w.text)
                    if fn.is_valid and fn.value is not None:
                        pct_val = fn.value

        # Extract loan reference token (TR..., LN-..., or sole reference identifier)
        m_ref = re.search(r"\b(TR[0-9A-Za-z\.]+|LN[-A-Za-z0-9]+|[A-Z]{2,5}-[A-Z0-9]+-[A-Z0-9\-]+)\b", desc)
        if m_ref:
            ref = m_ref.group(1).strip()
        elif desc and len(desc.split()) == 1 and re.match(r"^[A-Za-z0-9\-\.]{4,}$", desc):
            ref = desc

        # Continuation lines (e.g. UBP accrued interest)
        if len(group) > 1:
            for sec_l in group[1:]:
                if col_map and len(col_map.ordered_columns) >= 2:
                    sec_assigned, _ = assign_words_to_columns(sec_l.words, col_map)
                    for key in ("MARKET_VALUE", "REPORTING_VALUE"):
                        for w in sec_assigned.get(key, []):
                            fn = parse_financial_number(w.text)
                            if fn.is_valid and fn.value is not None:
                                accrued_int = fn.value
                                break
                        if accrued_int is not None:
                            break
                if accrued_int is None:
                    for w in sec_l.words:
                        if pw * 0.65 <= w.x0 < pw * 0.92:
                            fn = parse_financial_number(w.text)
                            if fn.is_valid and fn.value is not None:
                                accrued_int = fn.value
                                break
                if accrued_int is not None:
                    break

        if usd_val is None and amt_val is not None:
            usd_val = amt_val

        raw_group_text = "\n".join(gl.text for gl in group)
        loans.append(LoanItem(
            id=f"LOAN-{loan_counter:03d}",
            currency=curr or "USD",
            amount=amt_val,
            description=desc or ref or "Loan Facility",
            loan_reference=ref,
            maturity_date=maturity_date,
            interest_rate=rate_val,
            market_value=mkt_val,
            accrued_interest=accrued_int,
            usd_equivalent=usd_val,
            percentage_assets=pct_val,
            source_page=page_num,
            raw_text=raw_group_text,
        ))
        loan_counter += 1

    return loans, subtotal_usd, subtotal_pct
