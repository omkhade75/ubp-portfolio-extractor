import re
from typing import List, Tuple, Optional
from decimal import Decimal
import pymupdf

from app.models.schemas import LoanItem
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines, VisualLine
from app.extraction.summary_parser import is_iso_currency

def parse_loans_page(page: pymupdf.Page, page_num: int) -> Tuple[List[LoanItem], Optional[Decimal], Optional[Decimal]]:
    """
    Parses Loans section when present on the Accounts & Loans page using dynamic anchors.
    Handles loan primary lines and subsequent accrued interest lines.
    Returns (list_of_loans, subtotal_usd, subtotal_percentage).
    """
    _, lines = extract_visual_words_and_lines(page)
    loans: List[LoanItem] = []
    subtotal_usd = None
    subtotal_pct = None

    pw = page.rect.width
    ph = page.rect.height

    in_loans = False
    loan_lines: List[List[VisualLine]] = []
    current_loan_group: List[VisualLine] = []

    for l in lines:
        t = l.text.strip().upper()
        if "LOANS" in t:
            in_loans = True
            # Check if this line has subtotal or next line has it
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

        if "SUMMARY OF NET ASSETS" in t or "PAGE" in t or l.y > ph * 0.90:
            in_loans = False
            continue

        # Look for subtotal line if not yet found
        if subtotal_usd is None:
            num_words = [w for w in l.words if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None]
            if len(num_words) >= 2 and len(l.words) <= 3:
                subtotal_usd = parse_financial_number(num_words[0].text).value
                subtotal_pct = parse_financial_number(num_words[1].text).value
                continue

        # Loan lines start with "FIXED LOAN" or reference "TR..." or maturity date
        if "FIXED LOAN" in t or re.search(r"TR[0-9A-Za-z\.]+", t):
            if current_loan_group:
                loan_lines.append(current_loan_group)
            current_loan_group = [l]
        elif current_loan_group:
            # Continuation line (often contains accrued interest)
            current_loan_group.append(l)

    if current_loan_group:
        loan_lines.append(current_loan_group)

    loan_counter = 1
    for group in loan_lines:
        prim_l = group[0]
        words = prim_l.words

        # Currency dynamically detected
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

        # Amount (pw * 0.07 <= x < pw * 0.16)
        amt_val = None
        for w in words:
            if pw * 0.07 <= w.x0 < pw * 0.16:
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    amt_val = fn.value
                    break

        # Description & reference (pw * 0.12 <= x < pw * 0.50)
        desc_words = [w for w in words if pw * 0.12 <= w.x0 < pw * 0.50]
        desc = " ".join(w.text for w in desc_words).strip()
        ref = None
        m_ref = re.search(r"(TR[0-9A-Za-z\.]+)", desc)
        if m_ref:
            ref = m_ref.group(1)

        # Maturity date (pw * 0.45 <= x < pw * 0.60)
        maturity_date = None
        for w in words:
            if pw * 0.45 <= w.x0 < pw * 0.60 and re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip()):
                maturity_date = w.text.strip()
                break

        # Interest rate (pw * 0.55 <= x < pw * 0.68)
        rate_val = None
        for w in words:
            if pw * 0.55 <= w.x0 < pw * 0.68:
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    rate_val = fn.value
                    break

        # Market value (pw * 0.68 <= x < pw * 0.83)
        # USD equivalent (pw * 0.82 <= x < pw * 0.91)
        # % Assets (x >= pw * 0.90)
        mkt_val = None
        usd_val = None
        pct_val = None
        for w in words:
            if pw * 0.68 <= w.x0 < pw * 0.83:
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

        # Accrued interest from second line (if present)
        accrued_int = None
        if len(group) > 1:
            sec_l = group[1]
            for w in sec_l.words:
                if pw * 0.68 <= w.x0 < pw * 0.91:
                    fn = parse_financial_number(w.text)
                    if fn.is_valid and fn.value is not None:
                        accrued_int = fn.value
                        break

        raw_group_text = "\n".join(gl.text for gl in group)

        loans.append(LoanItem(
            id=f"LOAN-{loan_counter:03d}",
            currency=curr or "USD",
            amount=amt_val,
            description=desc,
            loan_reference=ref,
            maturity_date=maturity_date,
            interest_rate=rate_val,
            market_value=mkt_val,
            accrued_interest=accrued_int,
            usd_equivalent=usd_val,
            percentage_assets=pct_val,
            source_page=page_num,
            raw_text=raw_group_text
        ))
        loan_counter += 1

    return loans, subtotal_usd, subtotal_pct
