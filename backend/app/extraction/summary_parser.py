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
from app.extraction.word_extractor import extract_visual_words_and_lines, VisualLine, ExtractedWord
from app.extraction.table_header_engine import is_valid_iso_currency

def is_iso_currency(token: str) -> bool:
    return is_valid_iso_currency(token)

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
    Dynamically extracts Previous and Current Portfolio ESG ratings from source text.
    Handles any UBP / synthetic statement layout generically:
      - Delimited with slash/pipe: 'BBB+ / A (AVERAGE)', 'AA (LEADER) / AA (LEADER)', 'AA / A', '078 / 078'
      - Whitespace-separated qualified: 'AA (LEADER) AA (LEADER)', 'AA (AVERAGE) A (AVERAGE)'
      - Whitespace-separated simple: 'AA AA', '078 085', 'BBB+ A'
      - Single qualified or simple: 'AA (LEADER)', 'A (AVERAGE)', 'AA'
      - Flexible headers: PORTFOLIO ESG RATING (...), PORTFOLIO ESG (PREVIOUS / CURRENT), etc.
    """
    m = re.search(r"PORTFOLIO\s+ESG(?:\s+RATING)?(?:\s*\([^\)]*\))?\s*:?\s*(.*)", raw_text, re.IGNORECASE)
    if not m:
        if "ESG" not in raw_text.upper():
            return None, None
        rem = raw_text.strip()
    else:
        rem = m.group(1).strip()

    if not rem:
        return None, None

    # Strip any trailing right-side performance words that might bleed into the line
    rem = re.split(r"\b(?:PERFORMANCE|TWR|SINCE|VALUATION|ASSETS)\b", rem, flags=re.IGNORECASE)[0].strip()
    if not rem:
        return None, None

    # Pattern 1: Delimited by '/' or '|' outside parentheses
    # e.g. 'BBB+ / A (AVERAGE)', 'AA (LEADER) / A', 'AA / A', '078 / 078'
    if "/" in rem or "|" in rem:
        parts = re.split(r"\s*(?:/|\|)\s*(?![^\(]*\))", rem)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return parts[0].strip(), parts[1].strip()

    # Pattern 2: Two qualified ratings with whitespace: e.g. 'AA (LEADER) AA (LEADER)'
    m_qual = re.match(
        r"^([A-Za-z0-9\/+\-]+(?:\s*\([A-Za-z0-9\s\/+\-]+\)))\s+([A-Za-z0-9\/+\-]+(?:\s*\([A-Za-z0-9\s\/+\-]+\)))$",
        rem,
    )
    if m_qual:
        return m_qual.group(1).strip(), m_qual.group(2).strip()

    # Pattern 3: Two simple tokens with whitespace: 'AA AA', '078 085', 'BBB+ A'
    m_simple = re.match(r"^([A-Za-z0-9+\-]+)\s+([A-Za-z0-9+\-]+)$", rem)
    if m_simple:
        return m_simple.group(1).strip(), m_simple.group(2).strip()

    # Pattern 4: Single qualified rating: 'A (AVERAGE)', 'AA (LEADER)'
    m_single_qual = re.match(r"^([A-Za-z0-9\/+\-]+\s*\([A-Za-z0-9\s\/+\-]+\))$", rem)
    if m_single_qual:
        return None, m_single_qual.group(1).strip()

    # Pattern 5: Single simple token: 'AA', 'BBB+'
    m_single = re.match(r"^([A-Za-z0-9\/+\-]+)$", rem)
    if m_single:
        return None, m_single.group(1).strip()

    # Pattern 6: General token splitting (strip isolated slash separators)
    tokens = [tok for tok in rem.split() if tok not in ("/", "|")]
    if len(tokens) >= 4 and "(" in tokens[1] and "(" in tokens[3]:
        return f"{tokens[0]} {tokens[1]}", f"{tokens[2]} {tokens[3]}"
    elif len(tokens) == 2:
        return tokens[0], tokens[1]

    return None, None

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
        lu = l.text.upper()
        if "PORTFOLIO ESG RATING" in lu or "PORTFOLIO ESG" in lu or "ESG RATING" in lu:
            # Check whichever column contains the PORTFOLIO ESG label to avoid cross-column bleed
            left_words = [w for w in l.words if w.x0 < mid_x_left]
            right_words_esg = [w for w in l.words if w.x0 >= page.rect.width * 0.45]
            left_text = " ".join(w.text for w in left_words).strip()
            right_text_esg = " ".join(w.text for w in right_words_esg).strip()

            if "PORTFOLIO ESG" in left_text.upper() or "ESG RATING" in left_text.upper():
                esg_cand = left_text
            elif "PORTFOLIO ESG" in right_text_esg.upper() or "ESG RATING" in right_text_esg.upper():
                esg_cand = right_text_esg
            else:
                esg_cand = l.text

            p_prev, p_curr = parse_portfolio_esg_generic(esg_cand)
            if not p_prev and not p_curr and (idx + 1) < len(lines):
                # Header might be on current line and rating values on next line
                next_cand = lines[idx + 1].text.strip()
                p_prev, p_curr = parse_portfolio_esg_generic(next_cand)

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
                raw_vals["portfolio_esg_provenance"] = "EXTRACTED"

    mid_x = page.rect.width * 0.45
    for l in lines:
        right_words = [w for w in l.words if w.x0 >= mid_x]
        if not right_words:
            continue

        t = " ".join(w.text for w in right_words).strip()
        tu = t.upper()

        if "SINCE" in tu:
            m_s = re.search(r"SINCE\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4}(?:\s+TO\s+[0-9]{2}\.[0-9]{2}\.[0-9]{4})?)", t, re.IGNORECASE)
            if m_s:
                norm_period = re.sub(r"\s+", " ", m_s.group(1).strip().upper())
                rep_period = f"SINCE {norm_period}"
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
            portfolio_esg_provenance="EXTRACTED" if (port_prev_esg or port_curr_esg) else "NOT_PRESENT",
            portfolio_previous_esg_rating=port_prev_esg,
            portfolio_current_esg_rating=port_curr_esg,
            source_page=page_num,
            raw_values=raw_vals
        )
    return None

def parse_currency_breakdown_page(page: pymupdf.Page, page_num: int) -> List[CurrencyBreakdownItem]:
    """
    Parses Page 2 Currency Breakdown table generically using header column spans.
    Rejects non-currency column modifiers (e.g. 'AMT', 'AMOUNT') using strict ISO 4217 validation,
    and tracks detected unit scale ('THOUSANDS' or 'UNITS') plus ordered detected currencies.
    """
    _, lines = extract_visual_words_and_lines(page)
    items: List[CurrencyBreakdownItem] = []

    full_up = " ".join(l.text.upper() for l in lines)
    if "IN UNITS" in full_up or "FULL AMOUNTS" in full_up or "(UNITS)" in full_up:
        unit_scale = "UNITS"
    else:
        unit_scale = "THOUSANDS"

    # 1. Detect header line with currency columns
    header_line = None
    for l in lines:
        tu = l.text.strip().upper()
        if "ASSET CLASS" in tu and "TOTAL" in tu:
            header_line = l
            break

    if not header_line:
        return items

    # Build column anchors: list of [name, is_pct, hx0, hx1]
    anchors: List[List] = []
    curr = None
    currency_columns: List[str] = []

    for w in sorted(header_line.words, key=lambda x: x.x0):
        wt = re.sub(r"[^A-Z%]", "", w.text.upper())
        if wt == "TOTAL":
            anchors.append(["TOTAL", False, w.x0, w.x1])
            curr = None
        elif wt in ("AMT", "AMOUNT") and curr is not None and anchors and anchors[-1][0] == f"{curr}_AMT":
            # Expand currency header span to include adjacent 'AMT' label (e.g., 'USD AMT')
            anchors[-1][3] = max(anchors[-1][3], w.x1)
        elif wt == "%":
            if anchors and anchors[-1][0] == "TOTAL":
                anchors.append(["TOTAL_PCT", True, w.x0, w.x1])
            elif curr:
                anchors.append([f"{curr}_PCT", True, w.x0, w.x1])
        elif is_valid_iso_currency(wt):
            curr = wt
            if curr not in currency_columns:
                currency_columns.append(curr)
            anchors.append([f"{curr}_AMT", False, w.x0, w.x1])

    if not currency_columns:
        currency_columns = ["USD"]

    # Sort anchors left-to-right and build non-overlapping horizontal intervals
    anchors.sort(key=lambda a: a[2])
    in_table = False
    for l in lines:
        t = l.text.strip()
        tu = t.upper()
        if "ASSET CLASS" in tu and "TOTAL" in tu:
            in_table = True
            continue
        if "ALLOCATION BY INVESTMENT CATEGORY" in tu or "BREAKDOWN BY CURRENCY" in tu or "SUMMARY OF NET ASSETS" in tu:
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
            cat_name = re.sub(r"\s+USD$", "", cat_name, flags=re.IGNORECASE)

            # Map each numeric token to closest anchor center (strictly one owner per column)
            row_vals: Dict[str, Decimal] = {}
            row_raw_vals: Dict[str, str] = {}
            for w in words[num_start_idx:]:
                fn = parse_financial_number(w.text)
                if not fn.is_valid or fn.value is None or not anchors:
                    continue
                w_center = (w.x0 + w.x1) / 2.0
                best_a = min(anchors, key=lambda a: abs(((a[2] + a[3]) / 2.0) - w_center))
                if best_a[0] not in row_vals:
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
                unit_scale=unit_scale,
                detected_currencies=list(currency_columns),
                currencies=curr_dict,
                source_page=page_num,
                raw_text=l.text
            ))

    return items

def _group_region_words_into_lines(words: List[ExtractedWord], y_tol: float = 4.0) -> List[VisualLine]:
    """Re-groups spatially filtered words from a single column/region into VisualLines."""
    if not words:
        return []
    sorted_w = sorted(words, key=lambda w: (w.y0, w.x0))
    grouped: List[List[ExtractedWord]] = []
    cur: List[ExtractedWord] = [sorted_w[0]]
    cur_y = (sorted_w[0].y0 + sorted_w[0].y1) / 2.0
    for w in sorted_w[1:]:
        wy = (w.y0 + w.y1) / 2.0
        if abs(wy - cur_y) <= y_tol:
            cur.append(w)
        else:
            grouped.append(sorted(cur, key=lambda x: x.x0))
            cur = [w]
            cur_y = wy
    if cur:
        grouped.append(sorted(cur, key=lambda x: x.x0))
    return [
        VisualLine(
            y=sum((x.y0 + x.y1) / 2.0 for x in grp) / len(grp),
            y0=min(x.y0 for x in grp),
            y1=max(x.y1 for x in grp),
            words=grp,
            text=" ".join(x.text for x in grp),
        )
        for grp in grouped
    ]

def parse_net_assets_summary_page(page: pymupdf.Page, page_num: int) -> Tuple[Optional[NetAssetsSummaryData], List[ExchangeRateItem]]:
    """
    Parses Summary of Net Assets and Exchange Rates Used generically.
    Supports both vertical stacked layout (UBP standard) and horizontal two-column layout
    where SUMMARY OF NET ASSETS and EXCHANGE RATES USED sit side by side at the same y.
    Supports both 2-column (Amount + %) and 1-column (Amount only) Net Assets tables.
    """
    words, lines = extract_visual_words_and_lines(page)

    summary_data = NetAssetsSummaryData(source_page=page_num, raw_text="")
    exchange_rates: List[ExchangeRateItem] = []

    full_text_lines = [l.text.strip() for l in lines if l.text.strip()]

    # Locate section heading coordinates dynamically using word clusters
    sum_anchor: Optional[Tuple[float, float, float, float]] = None
    exch_anchor: Optional[Tuple[float, float, float, float]] = None
    for l in lines:
        tu = l.text.upper()
        # Look for section header lines (excluding page titles like 'SUMMARY OF NET ASSETS AND EXCHANGE RATES')
        if "SUMMARY OF NET ASSETS" in tu and "AND" not in tu and sum_anchor is None:
            sum_words = [word for word in l.words if word.text.upper() in ("SUMMARY", "OF", "NET", "ASSETS")]
            if sum_words:
                sum_anchor = (sum_words[0].x0, l.y0, sum_words[-1].x1, l.y1)
        if "EXCHANGE RATES" in tu and "AND" not in tu and exch_anchor is None:
            exch_words = [word for word in l.words if word.text.upper() in ("EXCHANGE", "RATES", "USED")]
            if exch_words:
                exch_anchor = (exch_words[0].x0, l.y0, exch_words[-1].x1, l.y1)

    # Fallback if both headers were combined on a single line or include 'AND'
    if sum_anchor is None or exch_anchor is None:
        for l in lines:
            tu = l.text.upper()
            if "SUMMARY OF NET ASSETS" in tu and sum_anchor is None:
                sum_words = [word for word in l.words if word.text.upper() in ("SUMMARY", "OF", "NET", "ASSETS")]
                if sum_words:
                    sum_anchor = (sum_words[0].x0, l.y0, sum_words[-1].x1, l.y1)
            if "EXCHANGE RATES" in tu and exch_anchor is None:
                exch_words = [word for word in l.words if word.text.upper() in ("EXCHANGE", "RATES", "USED")]
                if exch_words:
                    exch_anchor = (exch_words[0].x0, l.y0, exch_words[-1].x1, l.y1)

    is_side_by_side = (
        sum_anchor is not None
        and exch_anchor is not None
        and abs(sum_anchor[1] - exch_anchor[1]) < 30.0
        and abs(exch_anchor[0] - sum_anchor[0]) > page.rect.width * 0.25
    )

    footer_y = page.rect.height * 0.90
    for l in lines:
        if l.y0 < page.rect.height * 0.70:
            continue
        tu = l.text.upper()
        if "E.& O.E." in tu or re.search(r"\bPAGE\s+\d+\s*/\s*\d+", tu):
            footer_y = min(footer_y, l.y0 - 2.0)

    if is_side_by_side:
        assert sum_anchor is not None and exch_anchor is not None
        if exch_anchor[0] > sum_anchor[0]:
            split_x = exch_anchor[0] - 15.0
            sum_words = [w for w in words if w.x0 < split_x and sum_anchor[3] + 2.0 < w.y0 < footer_y]
            exch_words = [w for w in words if w.x0 >= split_x and exch_anchor[3] + 2.0 < w.y0 < footer_y]
        else:
            split_x = sum_anchor[0] - 15.0
            sum_words = [w for w in words if w.x0 >= split_x and sum_anchor[3] + 2.0 < w.y0 < footer_y]
            exch_words = [w for w in words if w.x0 < split_x and exch_anchor[3] + 2.0 < w.y0 < footer_y]
    else:
        sum_y_start = (sum_anchor[3] + 2.0) if sum_anchor else 0.0
        exch_y_start = (exch_anchor[3] + 2.0) if exch_anchor else footer_y
        if sum_anchor and exch_anchor:
            if exch_anchor[1] > sum_anchor[1]:
                sum_words = [w for w in words if sum_y_start < w.y0 < exch_anchor[1] - 2.0 and w.y0 < footer_y]
                exch_words = [w for w in words if exch_y_start < w.y0 < footer_y]
            else:
                exch_words = [w for w in words if exch_y_start < w.y0 < sum_anchor[1] - 2.0 and w.y0 < footer_y]
                sum_words = [w for w in words if sum_y_start < w.y0 < footer_y]
        elif sum_anchor:
            sum_words = [w for w in words if sum_y_start < w.y0 < footer_y]
            exch_words = []
        elif exch_anchor:
            sum_words = []
            exch_words = [w for w in words if exch_y_start < w.y0 < footer_y]
        else:
            sum_words, exch_words = [], []

    sum_lines = _group_region_words_into_lines(sum_words)
    exch_lines = _group_region_words_into_lines(exch_words)

    # Parse Summary of Net Assets lines cleanly (supports 1-col Amount OR 2-col Amount + %)
    for sl in sum_lines:
        tu = sl.text.strip().upper()
        if not tu or tu in ("USD %", "USD", "%") or "THIS SYNTHETIC DOCUMENT" in tu or "FINANCIAL CALCULATIONS USE" in tu:
            continue

        row_nums = []
        for w in sl.words:
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                row_nums.append(fn)

        if not row_nums:
            continue

        # If row has 2+ numeric values -> [..., amount, pct]; if 1 numeric value -> [amount] (NOT pct!)
        amt_val = row_nums[-2].value if len(row_nums) >= 2 else row_nums[-1].value
        pct_val = row_nums[-1].value if len(row_nums) >= 2 else None

        if "TOTAL ASSETS" in tu:
            summary_data.total_assets_usd = amt_val
            if pct_val is not None:
                summary_data.total_assets_pct = pct_val
        elif "ACCRUED INTEREST ON SECURITIES" in tu:
            summary_data.accrued_interest_securities_usd = amt_val
            if pct_val is not None:
                summary_data.accrued_interest_securities_pct = pct_val
        elif "NET ACCRUED INT" in tu:
            summary_data.net_accrued_int_deposits_loans_usd = amt_val
            if pct_val is not None:
                summary_data.net_accrued_int_deposits_loans_pct = pct_val
        elif "ASSETS" in tu and "TOTAL" not in tu:
            summary_data.assets_usd = amt_val
            if pct_val is not None:
                summary_data.assets_pct = pct_val
        elif "COMMITMENTS" in tu:
            summary_data.commitments_usd = amt_val

    # Parse Exchange Rates Used region
    for el in exch_lines:
        t = el.text.strip()
        m_rate = re.search(r"(?:1\s+)?([A-Z]{3})\s*(?:=|\/)?\s*([0-9][0-9\.\']+)\s+([A-Z]{3})", t)
        if m_rate and is_valid_iso_currency(m_rate.group(1)) and is_valid_iso_currency(m_rate.group(3)):
            base_c = m_rate.group(1).upper()
            rate_val = Decimal(m_rate.group(2).replace("'", ""))
            target_c = m_rate.group(3).upper()
            exchange_rates.append(ExchangeRateItem(
                base_currency=base_c,
                target_currency=target_c,
                rate=rate_val,
                raw_text=t,
                source_page=page_num
            ))
        else:
            m_rate2 = re.search(r"([A-Z]{3})\s*\/\s*([A-Z]{3})\s*(?:=)?\s*([0-9][0-9\.\']+)", t)
            if m_rate2 and is_valid_iso_currency(m_rate2.group(1)) and is_valid_iso_currency(m_rate2.group(2)):
                base_c = m_rate2.group(1).upper()
                target_c = m_rate2.group(2).upper()
                rate_val = Decimal(m_rate2.group(3).replace("'", ""))
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
