import re
from typing import List, Tuple, Optional
from decimal import Decimal
import pymupdf

from app.models.schemas import CurrentAccountItem
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines, VisualLine
from app.extraction.table_header_engine import (
    ACCOUNTS_SYNONYMS,
    TableColumnMap,
    build_table_column_map,
    assign_words_to_columns,
    is_valid_iso_currency,
)

_STOP_RE = re.compile(
    r"\b(?:LOAN\s+FACILITIES|LOANS|BORROWINGS|CREDIT\s+FACILITIES|SUMMARY\s+OF\s+NET\s+ASSETS|E\.&\s*O\.E\.|PAGE\s+\d+)\b",
    re.IGNORECASE,
)


def _looks_like_accounts_header(tu: str) -> bool:
    has_desc = any(k in tu for k in ["DESCRIPTION", "DENOMINATION", "ACCOUNT NAME"])
    has_val = any(k in tu for k in ["BALANCE", "AMOUNT", "MARKET VALUE", "REPORTING VALUE", "VALUE IN USD", "VALUE IN"])
    return (has_desc and has_val) or ("CURRENCY" in tu and has_val)


def _is_header_continuation(nl: VisualLine, base_y: float, pw: float) -> bool:
    if nl.y - base_y > 18.0:
        return False
    tu = nl.text.upper()
    if _STOP_RE.search(tu) or "CURRENT ACCOUNTS" in tu:
        return False
    if any(is_valid_iso_currency(w.text) for w in nl.words if w.x0 < pw * 0.14):
        return False
    return any(
        k in tu
        for k in ["DATE", "PRICE", "INTEREST", "USD", "ASSETS", "COST", "BALANCE", "VALUE", "%"]
    )


def parse_current_accounts_page(
    page: pymupdf.Page, page_num: int
) -> Tuple[List[CurrentAccountItem], Optional[Decimal], Optional[Decimal]]:
    """
    Header-driven parser for Current Accounts sections across UBP and synthetic templates.
    Supports section-local headers, multi-line UBP page-top shared headers, and headerless
    positional layouts. Terminates immediately on any Loans / Net Assets heading.
    Returns (list_of_accounts, subtotal_usd, subtotal_percentage).
    """
    _, lines = extract_visual_words_and_lines(page)
    accounts: List[CurrentAccountItem] = []
    subtotal_usd: Optional[Decimal] = None
    subtotal_pct: Optional[Decimal] = None

    pw = page.rect.width
    ph = page.rect.height

    # Pre-scan for shared page-top table headers (including line-2 stacked continuations like 'IN USD ASSETS')
    page_top_header_lines: List[VisualLine] = []
    for idx, l in enumerate(lines):
        if l.y > ph * 0.25:
            break
        tu = l.text.upper()
        if "CURRENT ACCOUNTS" in tu or _STOP_RE.search(tu):
            break
        if _looks_like_accounts_header(tu):
            page_top_header_lines.append(l)
            if idx + 1 < len(lines) and _is_header_continuation(lines[idx + 1], l.y, pw):
                page_top_header_lines.append(lines[idx + 1])
            break

    local_header_lines: List[VisualLine] = []
    col_map: Optional[TableColumnMap] = None

    in_accounts = False
    acc_counter = 1

    idx = 0
    while idx < len(lines):
        l = lines[idx]
        idx += 1
        t = l.text.strip()
        tu = t.upper()

        if re.search(r"\bCURRENT\s+ACCOUNTS\b", tu) and "TOTAL CURRENT ACCOUNTS" not in tu:
            in_accounts = True
            for w in l.words:
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    if subtotal_usd is None:
                        subtotal_usd = fn.value
                    elif subtotal_pct is None:
                        subtotal_pct = fn.value
            continue

        if _STOP_RE.search(tu) or l.y > ph * 0.90:
            if in_accounts:
                in_accounts = False
            continue

        if not in_accounts:
            continue

        # Capture local table header immediately beneath CURRENT ACCOUNTS (with multi-line continuation)
        if _looks_like_accounts_header(tu) and not any(is_valid_iso_currency(w.text) for w in l.words if w.x0 < pw * 0.14):
            local_header_lines = [l]
            if idx < len(lines) and _is_header_continuation(lines[idx], l.y, pw):
                local_header_lines.append(lines[idx])
                idx += 1
            col_map = build_table_column_map(local_header_lines, ACCOUNTS_SYNONYMS, "ACCOUNTS", pw)
            continue

        # Subtotal rows (e.g. TOTAL CURRENT ACCOUNTS 100'000.00 OR UBP subtotal line 251'270.71 9.75)
        if "TOTAL CURRENT ACCOUNTS" in tu or "SUBTOTAL" in tu:
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

        if subtotal_usd is None:
            num_words = [
                w for w in l.words
                if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
            ]
            if len(num_words) >= 2 and len(l.words) <= 3:
                subtotal_usd = parse_financial_number(num_words[0].text).value
                subtotal_pct = parse_financial_number(num_words[1].text).value
                continue

        # Build column map lazily from page-top shared header if no local header appeared
        if col_map is None and page_top_header_lines:
            col_map = build_table_column_map(page_top_header_lines, ACCOUNTS_SYNONYMS, "ACCOUNTS", pw)

        has_iso = any(is_valid_iso_currency(w.text.strip()) for w in l.words)
        if not ("CURRENT ACCOUNT" in tu or has_iso):
            continue

        words = l.words
        curr: Optional[str] = None
        amt_val: Optional[Decimal] = None
        desc = ""
        mkt_val: Optional[Decimal] = None
        usd_val: Optional[Decimal] = None
        pct_val: Optional[Decimal] = None

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
                    if w.x0 < pw * 0.14 and is_valid_iso_currency(wt):
                        curr = wt
                        break
            if curr is None:
                for w in words:
                    wt = re.sub(r"[^A-Z]", "", w.text.upper())
                    if is_valid_iso_currency(wt):
                        curr = wt
                        break

            for w in assigned.get("BALANCE", []):
                wt = re.sub(r"[^A-Z]", "", w.text.upper())
                if is_valid_iso_currency(wt):
                    continue
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    amt_val = fn.value
                    break

            desc_words = [
                w for w in assigned.get("ACCOUNT_DESCRIPTION", [])
                if not (is_valid_iso_currency(re.sub(r"[^A-Z]", "", w.text.upper())) and w.x0 < pw * 0.14)
            ]
            desc = " ".join(w.text for w in desc_words).strip()

            for w in assigned.get("MARKET_VALUE", []):
                if is_valid_iso_currency(w.text):
                    continue
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

            # Fallback for tables lacking an explicit '% ASSETS' header where [val_usd, pct] occupy right valuation zone
            if "PERCENTAGE" not in col_map.columns and "MARKET_VALUE" not in col_map.columns:
                right_nums = [
                    parse_financial_number(w.text).value
                    for w in words
                    if w.x0 >= pw * 0.72
                    and not is_valid_iso_currency(w.text)
                    and parse_financial_number(w.text).is_valid
                    and parse_financial_number(w.text).value is not None
                ]
                if len(right_nums) == 2 and right_nums[1] is not None and abs(right_nums[1]) <= Decimal("100.0"):
                    usd_val = right_nums[0]
                    pct_val = right_nums[1]
        else:
            # Headerless layout fallback (e.g. unit-test synthetic PDFs with standard column spacing)
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
            desc_words = [w for w in words if pw * 0.12 <= w.x0 < pw * 0.65]
            desc = " ".join(w.text for w in desc_words).strip()
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

        # Extract account number generically (handles 0001, 4101-USD, 4101-EUR, 2004812001, etc.)
        acc_num: Optional[str] = None
        m_acc = re.search(r"(?:NUMBER|NO\.?|AC\.?|ACCOUNT)\s*:?\s*([0-9][A-Za-z0-9\-]*)", desc, re.IGNORECASE)
        if m_acc:
            acc_num = m_acc.group(1).strip()

        if amt_val is not None or usd_val is not None:
            accounts.append(CurrentAccountItem(
                id=f"ACC-{acc_counter:03d}",
                currency=curr or "USD",
                amount=amt_val,
                account_name=desc or f"Current Account {curr or ''}".strip(),
                account_number=acc_num,
                market_value=mkt_val if mkt_val is not None else amt_val,
                market_value_usd=usd_val if usd_val is not None else amt_val,
                percentage_assets=pct_val,
                source_page=page_num,
                raw_text=l.text,
            ))
            acc_counter += 1

    return accounts, subtotal_usd, subtotal_pct
