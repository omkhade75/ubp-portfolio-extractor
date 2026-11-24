import re
from typing import List, Tuple, Optional
from decimal import Decimal
import pymupdf

from app.models.schemas import CurrentAccountItem
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines
from app.extraction.summary_parser import is_iso_currency

def parse_current_accounts_page(page: pymupdf.Page, page_num: int) -> Tuple[List[CurrentAccountItem], Optional[Decimal], Optional[Decimal]]:
    """
    Parses Current Accounts section using relative positioning and dynamic currency detection.
    Returns (list_of_accounts, subtotal_usd, subtotal_percentage).
    """
    _, lines = extract_visual_words_and_lines(page)
    accounts: List[CurrentAccountItem] = []
    subtotal_usd = None
    subtotal_pct = None

    pw = page.rect.width
    ph = page.rect.height

    in_accounts = False
    acc_counter = 1

    for l in lines:
        t = l.text.strip().upper()
        if "CURRENT ACCOUNTS" in t:
            in_accounts = True
            # Check if this line itself has subtotal or next line has it
            words = l.words
            for w in words:
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    if subtotal_usd is None:
                        subtotal_usd = fn.value
                    elif subtotal_pct is None:
                        subtotal_pct = fn.value
            continue

        if "LOANS" in t or "SUMMARY OF NET ASSETS" in t or "PAGE" in t or l.y > ph * 0.90:
            in_accounts = False
            continue

        if not in_accounts:
            continue

        # Look for subtotal if not found on header line
        if subtotal_usd is None:
            # Check if line contains only numbers e.g. 251’270.71 9.75
            num_words = [w for w in l.words if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None]
            if len(num_words) >= 2 and len(l.words) <= 3:
                subtotal_usd = parse_financial_number(num_words[0].text).value
                subtotal_pct = parse_financial_number(num_words[1].text).value
                continue

        # Look for account data line dynamically
        has_iso = any(is_iso_currency(w.text.strip()) for w in l.words)
        if "CURRENT ACCOUNT" in t or has_iso:
            words = l.words
            # Extract currency: left-aligned word or first iso currency
            curr = None
            for w in words:
                if w.x0 < pw * 0.10 and is_iso_currency(w.text.strip()):
                    curr = w.text.strip().upper()
                    break
            if curr is None:
                for w in words:
                    if is_iso_currency(w.text.strip()):
                        curr = w.text.strip().upper()
                        break

            # Extract amount (pw * 0.07 <= x < pw * 0.16)
            amt_val = None
            for w in words:
                if pw * 0.07 <= w.x0 < pw * 0.16:
                    fn = parse_financial_number(w.text)
                    if fn.is_valid and fn.value is not None:
                        amt_val = fn.value
                        break

            # Extract description / account number (pw * 0.12 <= x < pw * 0.65)
            desc_words = [w for w in words if pw * 0.12 <= w.x0 < pw * 0.65]
            desc = " ".join(w.text for w in desc_words).strip()
            
            # Extract account number
            acc_num = None
            m_acc = re.search(r"NUMBER\s+([0-9A-Za-z]+)", desc)
            if m_acc:
                acc_num = m_acc.group(1)

            # Numbers on right:
            # Market value: pw * 0.65 <= x < pw * 0.83
            # Value in USD: pw * 0.82 <= x < pw * 0.91
            # % Assets: x >= pw * 0.90
            mkt_val = None
            usd_val = None
            pct_val = None

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

            if amt_val is not None or usd_val is not None:
                accounts.append(CurrentAccountItem(
                    id=f"ACC-{acc_counter:03d}",
                    currency=curr or "USD",
                    amount=amt_val,
                    account_name=desc or f"Current Account {curr or ''}".strip(),
                    account_number=acc_num,
                    market_value=mkt_val or amt_val,
                    market_value_usd=usd_val or amt_val,
                    percentage_assets=pct_val,
                    source_page=page_num,
                    raw_text=l.text
                ))
                acc_counter += 1

    return accounts, subtotal_usd, subtotal_pct
