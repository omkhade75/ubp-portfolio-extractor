import re
from typing import List, Tuple, Optional, Dict
from decimal import Decimal
import pymupdf

from app.models.schemas import (
    AssetAllocationItem,
    PortfolioSummaryPerformance,
    CurrencyBreakdownItem,
    CurrencyDetail,
    NetAssetsSummaryData,
    ExchangeRateItem
)
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines

COMMON_ISO_CURRENCIES = {
    "USD", "EUR", "GBP", "CHF", "JPY", "HKD", "SGD", "AUD", "CAD", "NZD",
    "CNY", "SEK", "NOK", "DKK", "ZAR", "BRL", "INR", "KRW", "MXN", "AED", "SAR"
}

def is_iso_currency(token: str) -> bool:
    clean = token.strip().upper()
    return clean in COMMON_ISO_CURRENCIES or (len(clean) == 3 and clean.isalpha() and clean.isupper())

def parse_asset_allocation_page(page: pymupdf.Page, page_num: int) -> List[AssetAllocationItem]:
    """
    Parses Page 1 Asset Allocation table (left column of the overview page).
    Categories: BONDS/NOTES, EQUITIES, ALTERNATIVE INVESTMENTS, STRUCTURED PRODUCTS, CURRENT ACCOUNTS, LOANS, NET ASSETS USD.
    """
    _, lines = extract_visual_words_and_lines(page)
    items: List[AssetAllocationItem] = []

    mid_x = page.rect.width * 0.50
    in_allocation_section = False

    for l in lines:
        left_words = [w for w in l.words if w.x0 < mid_x]
        if not left_words:
            continue

        t = " ".join(w.text for w in left_words).strip()
        tu = t.upper()

        if "ASSET ALLOCATION" in tu:
            in_allocation_section = True
            continue

        if "TABLE OF CONTENTS" in tu or ("NET ASSETS" in tu and items):
            # If NET ASSETS is on this line, parse it then end
            pass

        if not in_allocation_section:
            continue

        if "INVESTMENT CATEGORY" in tu and ("USD" in tu or "%" in tu):
            continue

        # Look for category lines with financial numbers at the end
        words = left_words
        if len(words) < 2:
            continue

        # Look for percentage and amount from right to left
        last_word = words[-1].text.strip()
        second_last_word = words[-2].text.strip() if len(words) >= 2 else ""

        # Try parsing percentage from last word
        fn_pct = parse_financial_number(last_word)
        fn_val = parse_financial_number(second_last_word)

        if fn_pct.is_valid and fn_val.is_valid and fn_pct.value is not None and fn_val.value is not None:
            category_words = words[:-2]
            cat_name = " ".join(w.text for w in category_words).strip()
            if cat_name:
                items.append(AssetAllocationItem(
                    investment_category=cat_name,
                    value_usd=fn_val.value,
                    percentage=fn_pct.value,
                    raw_value=second_last_word,
                    raw_percentage=last_word,
                    source_page=page_num
                ))
                if "NET ASSETS" in cat_name.upper():
                    in_allocation_section = False

    return items

def parse_portfolio_esg_generic(raw_text: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Dynamically extracts Previous and Current Portfolio ESG ratings from source line text.
    Handles any UBP statement layout generically:
      - Ratings with qualifiers: 'AA (LEADER) AA (LEADER)', 'AA (LEADER) M (LEADER)', 'A (AVERAGE) A (AVERAGE)'
      - Simple rating codes: 'AA AA', '078 085', 'B CCC'
      - Single ratings: 'AA (LEADER)', 'AA'
      - Flexible parenthetical headers: (PREVIOUS - CURRENT), (PREVIOUS • CURRENT), (PREVIOUS CURRENT), (PREVIOUS / CURRENT)
    Never hardcodes portfolio numbers or specific rating strings.
    """
    m = re.search(r"PORTFOLIO\s+ESG\s+RATING(?:\s*\([^\)]*\))?\s*(.*)", raw_text, re.IGNORECASE)
    if not m:
        return None, None
    rem = m.group(1).strip()
    if not rem:
        return None, None

    # Strip any trailing right-side performance words that might bleed into the line
    rem = re.split(r"\b(?:PERFORMANCE|TWR|SINCE|VALUATION|ASSETS)\b", rem, flags=re.IGNORECASE)[0].strip()
    if not rem:
        return None, None

    # Check for two qualified ratings: e.g. 'AA (LEADER) AA (LEADER)'
    m_qual = re.match(r"^([A-Za-z0-9\/\+\-]+(?:\s*\([A-Za-z0-9\s\/\+\-]+\)))\s+([A-Za-z0-9\/\+\-]+(?:\s*\([A-Za-z0-9\s\/\+\-]+\)))$", rem)
    if m_qual:
        return m_qual.group(1).strip(), m_qual.group(2).strip()

    # Check for two simple tokens: e.g. 'AA AA' or '078 085'
    m_simple = re.match(r"^([A-Za-z0-9\/\+\-]+)\s+([A-Za-z0-9\/\+\-]+)$", rem)
    if m_simple:
        return m_simple.group(1).strip(), m_simple.group(2).strip()

    # Single qualified rating: 'AA (LEADER)'
    m_single_qual = re.match(r"^([A-Za-z0-9\/\+\-]+\s*\([A-Za-z0-9\s\/\+\-]+\))$", rem)
    if m_single_qual:
        return None, m_single_qual.group(1).strip()

    # Single simple token: 'AA'
    m_single = re.match(r"^([A-Za-z0-9\/\+\-]+)$", rem)
    if m_single:
        return None, m_single.group(1).strip()

    # General token splitting
    tokens = rem.split()
    if len(tokens) >= 4 and "(" in tokens[1] and "(" in tokens[3]:
        return f"{tokens[0]} {tokens[1]}", f"{tokens[2]} {tokens[3]}"
    elif len(tokens) == 2:
        return tokens[0], tokens[1]

    return None, rem

def parse_portfolio_summary_performance(page: pymupdf.Page, page_num: int) -> Optional[PortfolioSummaryPerformance]:
    """
    Parses Page 1 right-side PORTFOLIO IN USD performance summary table.
    Fields:
      - Reporting Period (e.g. SINCE 01.01.2025)
      - Initial Assets
      - Total Incoming Securities
      - Total Outgoing Securities
      - Total Incoming Cash
      - Total Outgoing Cash
      - Total of Inc/Out Cash & Sec
      - Change in Total Assets
      - Assets as of [Valuation Date]
      - Number of Days
      - Performance TWR (USD)
      - Portfolio ESG Rating (Previous, Current, Source Page)
    """
    _, lines = extract_visual_words_and_lines(page)
    raw_vals: Dict[str, str] = {}

    rep_period = None
    init_assets = None
    inc_sec = None
    out_sec = None
    inc_cash = None
    out_cash = None
    tot_inc_out = None
    chg_assets = None
    val_date = None
    end_assets = None
    num_days = None
    twr_pct = None
    port_prev_esg = None
    port_curr_esg = None
    port_esg_source_page = None

    mid_x_left = page.rect.width * 0.50
    for l in lines:
        if "PORTFOLIO ESG RATING" in l.text.upper() or "ESG RATING" in l.text.upper():
            # First check left-column words to prevent right-column bleeding
            left_words = [w for w in l.words if w.x0 < mid_x_left]
            left_text = " ".join(w.text for w in left_words).strip()
            
            p_prev, p_curr = parse_portfolio_esg_generic(left_text if "PORTFOLIO ESG" in left_text.upper() else l.text)
            if p_prev or p_curr:
                port_prev_esg = p_prev
                port_curr_esg = p_curr
                port_esg_source_page = page_num
                if port_prev_esg:
                    raw_vals["portfolio_esg_previous"] = port_prev_esg
                    raw_vals["portfolio_previous_esg_rating"] = port_prev_esg
                if port_curr_esg:
                    raw_vals["portfolio_esg_current"] = port_curr_esg
                    raw_vals["portfolio_current_esg_rating"] = port_curr_esg
                raw_vals["portfolio_esg_source_page"] = str(page_num)

    mid_x = page.rect.width * 0.45
    for l in lines:
        right_words = [w for w in l.words if w.x0 >= mid_x]
        if not right_words:
            continue

        t = " ".join(w.text for w in right_words).strip()
        tu = t.upper()

        if "SINCE" in tu:
            m_s = re.search(r"SINCE\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})", t, re.IGNORECASE)
            if m_s:
                rep_period = f"SINCE {m_s.group(1)}"
                raw_vals["reporting_period"] = rep_period

        if "INITIAL ASSETS" in tu:
            val_str = t.split("INITIAL ASSETS")[-1].strip().lstrip(":").strip()
            fn = parse_financial_number(val_str)
            if fn.is_valid and fn.value is not None:
                init_assets = fn.value
                raw_vals["initial_assets"] = val_str

        if "TOTAL INCOMING SECURITIES" in tu:
            val_str = t.split("TOTAL INCOMING SECURITIES")[-1].strip().lstrip(":").strip()
            fn = parse_financial_number(val_str)
            if fn.is_valid and fn.value is not None:
                inc_sec = fn.value
                raw_vals["total_incoming_securities"] = val_str

        if "TOTAL OUTGOING SECURITIES" in tu:
            val_str = t.split("TOTAL OUTGOING SECURITIES")[-1].strip().lstrip(":").strip()
            fn = parse_financial_number(val_str)
            if fn.is_valid and fn.value is not None:
                out_sec = fn.value
                raw_vals["total_outgoing_securities"] = val_str

        if "TOTAL INCOMING CASH" in tu:
            val_str = t.split("TOTAL INCOMING CASH")[-1].strip().lstrip(":").strip()
            fn = parse_financial_number(val_str)
            if fn.is_valid and fn.value is not None:
                inc_cash = fn.value
                raw_vals["total_incoming_cash"] = val_str

        if "TOTAL OUTGOING CASH" in tu:
            val_str = t.split("TOTAL OUTGOING CASH")[-1].strip().lstrip(":").strip()
            fn = parse_financial_number(val_str)
            if fn.is_valid and fn.value is not None:
                out_cash = fn.value
                raw_vals["total_outgoing_cash"] = val_str

        if "TOTAL OF INC/OUT CASH & SEC" in tu or "TOTAL OF INC/OUT" in tu:
            val_str = re.split(r"TOTAL OF INC/OUT(?: CASH & SEC)?", t, flags=re.IGNORECASE)[-1].strip().lstrip(":").strip()
            fn = parse_financial_number(val_str)
            if fn.is_valid and fn.value is not None:
                tot_inc_out = fn.value
                raw_vals["total_inc_out_cash_sec"] = val_str

        if "CHANGE IN TOTAL ASSETS" in tu:
            val_str = t.split("CHANGE IN TOTAL ASSETS")[-1].strip().lstrip(":").strip()
            fn = parse_financial_number(val_str)
            if fn.is_valid and fn.value is not None:
                chg_assets = fn.value
                raw_vals["change_in_total_assets"] = val_str

        if "ASSETS AS OF" in tu:
            m_a = re.search(r"ASSETS AS OF\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4})", t, re.IGNORECASE)
            if m_a:
                val_date = m_a.group(1).strip()
                val_str = t[m_a.end():].strip().lstrip(":").strip()
                fn = parse_financial_number(val_str)
                if fn.is_valid and fn.value is not None:
                    end_assets = fn.value
                    raw_vals["ending_assets"] = val_str
                    raw_vals["valuation_date"] = val_date
            else:
                val_str = right_words[-1].text.strip()
                fn = parse_financial_number(val_str)
                if fn.is_valid and fn.value is not None:
                    end_assets = fn.value
                    raw_vals["ending_assets"] = val_str

        if "NUMBER OF DAYS" in tu:
            m_d = re.search(r"NUMBER OF DAYS\s*(?:\([^\)]*\))?\s*:?\s*([0-9]+)", t, re.IGNORECASE) or re.search(r"\(\s*([0-9]+)\s*D?\s*\)", t, re.IGNORECASE) or re.search(r"([0-9]+)", t.split("NUMBER OF DAYS")[-1])
            if m_d:
                try:
                    num_days = int(m_d.group(1))
                    raw_vals["number_of_days"] = m_d.group(0)
                except ValueError:
                    pass

        if "PERFORMANCE TWR" in tu:
            m_twr = re.search(r"([0-9\.\-]+)%", t)
            if m_twr:
                val_str = m_twr.group(0)
                fn = parse_financial_number(val_str)
                if fn.is_valid and fn.value is not None:
                    twr_pct = fn.value
                    raw_vals["performance_twr_pct"] = val_str

    if init_assets is not None or end_assets is not None or twr_pct is not None:
        if rep_period is None and val_date and num_days:
            try:
                from datetime import datetime, timedelta
                val_dt = datetime.strptime(val_date, "%d.%m.%Y")
                start_dt = val_dt - timedelta(days=num_days)
                rep_period = f"Since {start_dt.strftime('%d.%m.%Y')}"
                raw_vals["reporting_period"] = rep_period
            except Exception:
                pass

        return PortfolioSummaryPerformance(
            reporting_period=rep_period,
            initial_assets=init_assets,
            total_incoming_securities=inc_sec,
            total_outgoing_securities=out_sec,
            total_incoming_cash=inc_cash,
            total_outgoing_cash=out_cash,
            total_inc_out_cash_sec=tot_inc_out,
            change_in_total_assets=chg_assets,
            valuation_date=val_date,
            ending_assets=end_assets,
            number_of_days=num_days,
            performance_twr_pct=twr_pct,
            portfolio_esg_previous=port_prev_esg,
            portfolio_esg_current=port_curr_esg,
            portfolio_esg_source_page=port_esg_source_page,
            portfolio_previous_esg_rating=port_prev_esg,
            portfolio_current_esg_rating=port_curr_esg,
            source_page=page_num,
            raw_values=raw_vals
        )
    return None

def parse_currency_breakdown_page(page: pymupdf.Page, page_num: int) -> List[CurrencyBreakdownItem]:
    """
    Parses Page 2 Currency Breakdown table (in 000's USD).
    Dynamically identifies all currencies present across the columns and uses
    header column anchors to avoid token-shift errors.
    """
    _, lines = extract_visual_words_and_lines(page)
    items: List[CurrencyBreakdownItem] = []

    # 1. Detect header line with currency columns
    # Example: ASSET CLASS TOTAL % USD % HKD % or ASSET CLASS TOTAL % USD % EUR* %
    header_line = None
    for l in lines:
        tu = l.text.strip().upper()
        if "ASSET CLASS" in tu and "TOTAL" in tu:
            header_line = l
            break

    if not header_line:
        return items

    # Build column anchors from header line
    anchors = []  # list of (name, is_pct, x_coord)
    curr = None
    currency_columns: List[str] = []

    for w in header_line.words:
        wt = re.sub(r"[^A-Z%]", "", w.text.upper())
        if wt == "TOTAL":
            anchors.append(("TOTAL", False, w.x0))
        elif wt == "%":
            if anchors and anchors[-1][0] == "TOTAL":
                anchors.append(("TOTAL_PCT", True, w.x0))
            elif curr:
                anchors.append((f"{curr}_PCT", True, w.x0))
        elif is_iso_currency(wt):
            curr = wt
            if curr not in currency_columns:
                currency_columns.append(curr)
            anchors.append((f"{curr}_AMT", False, w.x0))

    if not currency_columns:
        currency_columns = ["USD"]

    in_table = False
    for l in lines:
        t = l.text.strip()
        if "ASSET CLASS" in t and "TOTAL" in t:
            in_table = True
            continue
        if "ALLOCATION BY INVESTMENT CATEGORY" in t or "BREAKDOWN BY CURRENCY" in t:
            in_table = False
            continue

        if not in_table:
            continue

        words = l.words
        if len(words) < 2:
            continue

        # Find where numbers start
        num_start_idx = -1
        for idx, w in enumerate(words):
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                if idx + 1 < len(words):
                    fn_next = parse_financial_number(words[idx + 1].text)
                    if fn_next.is_valid and fn_next.value is not None:
                        num_start_idx = idx
                        break

        if num_start_idx > 0:
            cat_name = " ".join(w.text for w in words[:num_start_idx]).strip()
            # Normalize NET ASSETS USD -> NET ASSETS
            cat_name = re.sub(r"\s+USD$", "", cat_name)

            # Map numeric tokens to closest column anchors
            row_vals: Dict[str, Decimal] = {}
            row_raw_vals: Dict[str, str] = {}
            for w in words[num_start_idx:]:
                fn = parse_financial_number(w.text)
                if not fn.is_valid or fn.value is None:
                    continue
                best_a = min(anchors, key=lambda a: abs(a[2] - w.x0))
                row_vals[best_a[0]] = fn.value
                row_raw_vals[best_a[0]] = w.text

            fn_total = row_vals.get("TOTAL")
            fn_total_pct = row_vals.get("TOTAL_PCT")

            curr_dict: Dict[str, CurrencyDetail] = {}
            for c in currency_columns:
                amt = row_vals.get(f"{c}_AMT")
                pct = row_vals.get(f"{c}_PCT")
                raw_amt = row_raw_vals.get(f"{c}_AMT")
                raw_pct = row_raw_vals.get(f"{c}_PCT")
                if amt is not None or pct is not None:
                    curr_dict[c] = CurrencyDetail(
                        amount_in_thousands=amt,
                        percentage=pct,
                        raw_amount=raw_amt,
                        raw_pct=raw_pct
                    )

            items.append(CurrencyBreakdownItem(
                asset_class=cat_name,
                total_in_thousands=fn_total,
                total_percentage=fn_total_pct,
                currencies=curr_dict,
                source_page=page_num,
                raw_text=l.text
            ))

    return items

def parse_net_assets_summary_page(page: pymupdf.Page, page_num: int) -> Tuple[Optional[NetAssetsSummaryData], List[ExchangeRateItem]]:
    """
    Parses Summary of Net Assets and Exchange Rates Used.
    """
    _, lines = extract_visual_words_and_lines(page)
    
    summary_data = NetAssetsSummaryData(source_page=page_num, raw_text="")
    exchange_rates: List[ExchangeRateItem] = []

    full_text_lines = []
    in_summary = False
    in_exchange_rates = False

    for l in lines:
        t = l.text.strip()
        full_text_lines.append(t)
        
        if "SUMMARY OF NET ASSETS" in t:
            in_summary = True
            in_exchange_rates = False
            continue

        if "EXCHANGE RATES USED" in t:
            in_summary = False
            in_exchange_rates = True
            continue

        if "E.& O.E." in t or "PAGE" in t:
            in_summary = False
            in_exchange_rates = False
            continue

        words = l.words
        if in_summary and len(words) >= 2:
            # Look for line like: ASSETS 2’260’653.31 99.69
            # or ACCRUED INTEREST ON SECURITIES 7’015.96 0.31
            # or NET ACCRUED INT DEP AND LOANS 0.00 0.00 or 2'364.96- 0.09-
            # or TOTAL ASSETS 2’267’669.27 100.00
            # or COMMITMENTS 0.00
            line_upper = t.upper()
            
            # Find numbers from right
            fn_last = parse_financial_number(words[-1].text)
            fn_second_last = parse_financial_number(words[-2].text) if len(words) >= 3 else None

            if "TOTAL ASSETS" in line_upper:
                if fn_last.is_valid:
                    summary_data.total_assets_pct = fn_last.value
                if fn_second_last and fn_second_last.is_valid:
                    summary_data.total_assets_usd = fn_second_last.value
            elif "ACCRUED INTEREST ON SECURITIES" in line_upper:
                if fn_last.is_valid:
                    summary_data.accrued_interest_securities_pct = fn_last.value
                if fn_second_last and fn_second_last.is_valid:
                    summary_data.accrued_interest_securities_usd = fn_second_last.value
            elif "NET ACCRUED INT" in line_upper:
                if fn_last.is_valid:
                    summary_data.net_accrued_int_deposits_loans_pct = fn_last.value
                if fn_second_last and fn_second_last.is_valid:
                    summary_data.net_accrued_int_deposits_loans_usd = fn_second_last.value
            elif "ASSETS" in line_upper and "TOTAL" not in line_upper:
                if fn_last.is_valid:
                    summary_data.assets_pct = fn_last.value
                if fn_second_last and fn_second_last.is_valid:
                    summary_data.assets_usd = fn_second_last.value
            elif "COMMITMENTS" in line_upper:
                if fn_last.is_valid:
                    summary_data.commitments_usd = fn_last.value

        elif in_exchange_rates:
            # Example: 1 USD 7.84833538 HKD, 1 USD = 0.8524 EUR, or USD / CHF 0.9000
            m_rate = re.search(r"(?:1\s+)?([A-Z]{3})\s*(?:=|\/)?\s*([0-9\.]+)\s+([A-Z]{3})", t)
            if m_rate:
                base_c = m_rate.group(1)
                rate_val = Decimal(m_rate.group(2))
                target_c = m_rate.group(3)
                exchange_rates.append(ExchangeRateItem(
                    base_currency=base_c,
                    target_currency=target_c,
                    rate=rate_val,
                    raw_text=t,
                    source_page=page_num
                ))
            else:
                m_rate2 = re.search(r"([A-Z]{3})\s*\/\s*([A-Z]{3})\s*(?:=)?\s*([0-9\.]+)", t)
                if m_rate2:
                    base_c = m_rate2.group(1)
                    target_c = m_rate2.group(2)
                    rate_val = Decimal(m_rate2.group(3))
                    exchange_rates.append(ExchangeRateItem(
                        base_currency=base_c,
                        target_currency=target_c,
                        rate=rate_val,
                        raw_text=t,
                        source_page=page_num
                    ))

    if summary_data.assets_usd is None and summary_data.total_assets_usd is not None:
        acc_sec = summary_data.accrued_interest_securities_usd or Decimal("0")
        acc_loans = summary_data.net_accrued_int_deposits_loans_usd or Decimal("0")
        summary_data.assets_usd = summary_data.total_assets_usd - acc_sec - acc_loans

    summary_data.raw_text = "\n".join(full_text_lines)
    return summary_data, exchange_rates
