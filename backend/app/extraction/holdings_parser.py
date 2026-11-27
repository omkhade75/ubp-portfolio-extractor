import re
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal
import pymupdf

from app.models.schemas import HoldingItem
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines, VisualLine, ExtractedWord
from app.extraction.table_header_engine import (
    HOLDINGS_SYNONYMS,
    TableColumnMap,
    build_table_column_map,
    assign_words_to_columns,
    is_valid_iso_currency,
    HeaderColumn,
    _compute_column_boundaries,
)


def is_iso_currency(token: str) -> bool:
    return is_valid_iso_currency(token)


KNOWN_CATEGORIES = [
    "BONDS/NOTES, BOND FUNDS & CERTIFICATES",
    "EQUITIES, EQUITY FUNDS & CERTIFICATES",
    "EQUITIES & EXCHANGE-TRADED FUNDS",
    "EQUITIES, EQUITIES & ETF",
    "EQUITIES & ETFS",
    "ALTERNATIVE INVESTMENTS & CERTIFICATES",
    "MONEY MARKET INSTRUMENTS",
    "COMMODITIES & PRECIOUS METALS",
    "STRUCTURED PRODUCTS",
    "PRIVATE EQUITY",
    "FIDUCIARY DEPOSITS",
    "REAL ESTATE",
    "BONDS / NOTES",
    "ALTERNATIVES",
    "EQUITIES",
]

DISALLOWED_ID_WORDS = {
    "BONDS", "NOTES", "ALTERNATIVES", "ALTERNATIVE", "EQUITIES", "EQUITY",
    "STRUCTURED", "PRODUCTS", "CERTIFICATES", "FUNDS", "SHARES", "TOTAL",
    "SAMPLE", "NOT", "VALID", "DEMO", "INVESTMENTS", "USD", "EUR", "GBP",
    "CHF", "JPY", "HKD", "SGD", "AUD", "CAD", "NZD", "CNY", "SEK", "NOK",
    "DKK", "NAME", "SECUR", "SECURITY", "UNIT", "UNITS", "NOMINAL", "YIELD",
    "DURATION", "COST", "PRICE", "VALUE", "ASSETS", "SERIES", "CLASS", "IN",
    "MONEY", "MARKET", "REAL", "ESTATE", "COMMODITIES", "PRECIOUS", "METALS",
    "SUBTOTAL", "BALANCE", "PERFORMANCE", "SUMMARY", "OVERVIEW", "ESG", "RATING",
    "PREVIOUS", "CURRENT"
}


def is_isin_or_secur_no(token: str) -> bool:
    """
    Validates structurally whether a token in the identifier column is an ISIN,
    Valoren, CUSIP, SEDOL, UBP internal code, or synthetic alphanumeric code.
    """
    clean = token.strip().upper()
    if not clean or clean in DISALLOWED_ID_WORDS:
        return False
    if clean.isalpha():
        return False

    # Standard ISO 6166 ISIN (2 letters + 9 alphanum + 1 check digit)
    if re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", clean):
        return True
    # Swiss Valoren numbers
    if re.match(r"^\d{6,10}(\.\d{3})?$", clean):
        return True
    # UBP internal security numbers (e.g. XD1356846166, XFCS00X6RSF8)
    if re.match(r"^X[DF][A-Z0-9]{8,12}$", clean):
        return True
    # Synthetic / hyphenated security codes (e.g. CH-VAL-TEST-31001, PB-TEST-PE-0075, US-TEST-002A, CUSIP-TEST-003)
    if re.match(r"^[A-Z0-9]{2,6}(-[A-Z0-9]{2,8})+$", clean) and any(c.isdigit() for c in clean):
        return True
    # Generic alphanumeric identifier with digits and letters (9-15 chars)
    if re.match(r"^[A-Z0-9]{8,15}$", clean) and any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean):
        return True
    # CUSIP
    if re.match(r"^[0-9A-Z]{8}[0-9]$", clean) and any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean):
        return True
    # SEDOL
    if re.match(r"^[B-DF-HJ-NP-TV-Z0-9]{6}[0-9]$", clean) and any(c.isdigit() for c in clean):
        return True
    return False


def _is_credit_rating(token: str) -> bool:
    """Matches standard S&P/Moody's/Fitch credit ratings like AAA, AA+, A-, BBB+, Baa1, NR."""
    clean = token.strip().upper()
    return bool(re.match(r"^(?:AAA|AA[\+\-]?|A[\+\-]?|BBB[\+\-]?|BB[\+\-]?|B[\+\-]?|CCC[\+\-]?|CC|C|D|NR|BAA[123]|BA[123]|CAA[123])$", clean))


def is_category_header(
    line_text: str,
    dynamic_categories: Optional[List[str]] = None,
    line_x0: Optional[float] = None,
    col_map: Optional[TableColumnMap] = None
) -> Optional[Tuple[str, Optional[Decimal], Optional[Decimal]]]:
    """
    Checks if a line is an asset category banner line.
    Matches against dynamically discovered categories from Asset Allocation or standard categories.
    Returns (category_name, subtotal_usd, percentage) if matched.
    """
    if line_x0 is not None and line_x0 > 65.0:
        return None
    upper = line_text.upper().strip()
    if any(k in upper for k in ["ORIGINAL DENOMINATION", "BLANK FIELDS ARE", "SYNTHETIC TEST ONLY", "UNION BANCAIRE PRIVEE"]):
        return None

    categories_to_check: List[str] = []
    if dynamic_categories:
        for dc in dynamic_categories:
            dcu = dc.upper().strip()
            if dcu and dcu != "NET ASSETS" and dcu not in categories_to_check:
                categories_to_check.append(dcu)
    for kc in KNOWN_CATEGORIES:
        if kc.upper() not in categories_to_check:
            categories_to_check.append(kc.upper())

    categories_to_check.sort(key=len, reverse=True)

    id_col = col_map.columns.get("SECURITY_ID") if col_map else None

    for cat in categories_to_check:
        if cat in upper:
            m_start = re.match(r"^[\s\-•*]*" + re.escape(cat) + r"(?=\s|$)", upper)
            if not m_start:
                continue

            # Must not contain an identifier
            if any(is_isin_or_secur_no(w) for w in line_text.split()):
                continue

            remainder = upper[m_start.end():].strip()
            rem_words = remainder.split()
            non_numeric_words = [
                rw for rw in rem_words
                if not parse_financial_number(rw).is_valid
                and not is_valid_iso_currency(rw)
                and rw not in {"%", "-"}
            ]
            if non_numeric_words:
                continue

            parts = line_text.split()
            subtotal = None
            pct = None
            if len(parts) >= 3:
                fn_pct = parse_financial_number(parts[-1])
                fn_sub = parse_financial_number(parts[-2])
                if fn_pct.is_valid and fn_sub.is_valid and fn_pct.value is not None:
                    pct = fn_pct.value
                    subtotal = fn_sub.value
            return cat, subtotal, pct

    return None


def _build_default_holdings_map(page_width: float) -> TableColumnMap:
    """Fallback proportional map only when a page contains zero detectable table header."""
    ordered = [
        HeaderColumn("UNITS", "UNITS", page_width * 0.04, page_width * 0.11),
        HeaderColumn("SECURITY NAME", "SECURITY_NAME", page_width * 0.12, page_width * 0.25),
        HeaderColumn("SECURITY NO.", "SECURITY_ID", page_width * 0.43, page_width * 0.51),
        HeaderColumn("YIELD", "YIELD_RATING", page_width * 0.52, page_width * 0.57),
        HeaderColumn("AVG. COST", "AVERAGE_COST", page_width * 0.58, page_width * 0.64),
        HeaderColumn("MARKET PRICE", "MARKET_PRICE", page_width * 0.65, page_width * 0.72),
        HeaderColumn("MARKET VALUE", "MARKET_VALUE", page_width * 0.73, page_width * 0.83),
        HeaderColumn("VALUE IN USD", "REPORTING_VALUE", page_width * 0.84, page_width * 0.92),
        HeaderColumn("%", "PERCENTAGE", page_width * 0.93, page_width * 0.98),
    ]
    _compute_column_boundaries(ordered, page_width)
    return TableColumnMap(
        section_type="HOLDINGS",
        columns={c.semantic_key: c for c in ordered},
        ordered_columns=ordered,
        confidence="REVIEW_REQUIRED"
    )


def detect_holdings_table_map(lines: List[VisualLine], page_width: float) -> TableColumnMap:
    """
    Detects the holdings table header region and reconstructs individual column
    boundaries using header word geometry and semantic synonyms.
    """
    header_keywords = {"UNITS", "NOMINAL", "SECURITY", "NAME", "SECUR", "ISIN", "YIELD", "COST", "PRICE", "VALUE"}
    start_idx = -1
    for idx, l in enumerate(lines):
        if l.y > 180.0:
            break
        tu = l.text.upper()
        hits = sum(1 for kw in header_keywords if kw in tu)
        if hits >= 3 and l.words and l.words[-1].x1 >= page_width * 0.65:
            start_idx = idx
            break

    if start_idx < 0:
        return _build_default_holdings_map(page_width)

    header_lines = [lines[start_idx]]
    base_y = lines[start_idx].y
    for next_idx in range(start_idx + 1, min(len(lines), start_idx + 4)):
        nl = lines[next_idx]
        if nl.y - base_y > 28.0:
            break
        if is_category_header(nl.text.strip(), line_x0=nl.words[0].x0 if nl.words else None):
            break
        # Include continuation header lines (e.g. 'NOMINAL RATING /AV.PU.PRI COST PRICE ...' or 'ESG: PREVIOUS CURRENT')
        nl_up = nl.text.upper()
        if any(k in nl_up for k in ["NOMINAL", "RATING", "COST", "PRICE", "INTEREST", "USD", "ASSETS", "ESG", "PREVIOUS", "CURRENT", "DURATION"]):
            header_lines.append(nl)
        else:
            break

    tmap = build_table_column_map(header_lines, HOLDINGS_SYNONYMS, "HOLDINGS", page_width)
    return tmap


def _extract_identifier_from_words(id_words: List[ExtractedWord]) -> Tuple[Optional[str], Optional[str]]:
    """
    Extracts clean security identifier from tokens strictly inside SECURITY_ID column.
    Supports space-split OCR tokens (e.g. 'XSSYNOOOI' + '090') while never returning ordinary prose words.
    """
    if not id_words:
        return None, None

    # First pass: exact single token match
    for w in id_words:
        tok = w.text.strip()
        if is_isin_or_secur_no(tok):
            return tok, None

    # Second pass: only join immediately adjacent fragments (OCR intra-token split, gap < 8pt)
    # Never join two horizontal columns such as ESG scores ('078' ... '078') separated by wide spacing.
    if len(id_words) >= 2:
        adjacent_groups: List[List[ExtractedWord]] = [[id_words[0]]]
        for w in id_words[1:]:
            if (w.x0 - adjacent_groups[-1][-1].x1) < 8.0:
                adjacent_groups[-1].append(w)
            else:
                adjacent_groups.append([w])
        for grp in adjacent_groups:
            if len(grp) >= 2:
                joined = "".join(w.text.strip() for w in grp)
                if is_isin_or_secur_no(joined):
                    return joined, None

    # Third pass: unfamiliar but structurally valid alphanumeric/hyphenated identifier inside ID column
    for w in id_words:
        clean_tok = w.text.strip().upper()
        if (
            clean_tok
            and clean_tok not in DISALLOWED_ID_WORDS
            and not is_valid_iso_currency(clean_tok)
            and not clean_tok.isalpha()
            and (any(c.isdigit() for c in clean_tok) or ("-" in clean_tok and len(clean_tok) >= 4))
            and not any(k in clean_tok for k in ["SAMPLE", "VALID", "DEMO"])
        ):
            return f"{w.text.strip()} (REVIEW_REQUIRED)", None

    return None, None


def parse_holdings_pages(
    doc: pymupdf.Document,
    holdings_page_indices: List[int],
    dynamic_categories: Optional[List[str]] = None
) -> Tuple[List[HoldingItem], Dict[str, Dict[str, Any]]]:
    """
    Generic header-driven parser across all holdings pages.
    Returns (holdings_list, metadata_summary_dict).
    """
    holdings: List[HoldingItem] = []
    category_subtotals: Dict[str, Dict[str, Any]] = {}
    current_category = "UNKNOWN"
    holding_id_counter = 1
    page_header_maps: List[Dict[str, Any]] = []

    for pno in holdings_page_indices:
        page = doc[pno]
        page_num = pno + 1
        page_width = page.rect.width
        page_height = page.rect.height
        _, lines = extract_visual_words_and_lines(page)

        col_map = detect_holdings_table_map(lines, page_width)
        page_header_maps.append({
            "page": page_num,
            "confidence": col_map.confidence,
            "columns": [
                {"key": c.semantic_key, "header": c.raw_label, "x_min": round(c.x_min, 1), "x_max": round(c.x_max, 1)}
                for c in col_map.ordered_columns
            ],
            "unrecognized": col_map.unrecognized_headers,
        })

        data_start_y = (col_map.header_y_max + 2.0) if col_map.header_y_max is not None else 115.0
        footer_y_limit = page_height - 50.0

        # Filter to body rows within the table vertical span
        content_lines: List[VisualLine] = []
        for l in lines:
            if l.y <= data_start_y:
                continue
            if l.y >= footer_y_limit:
                continue
            lu = l.text.upper()
            if any(f in lu for f in ["ORIGINAL DENOMINATION AND REPORTING", "BLANK FIELDS ARE INTENTIONALLY", "REPORT EDITED ON", "SYNTHETIC TEST ONLY", "UNION BANCAIRE PRIVEE"]):
                continue
            content_lines.append(l)

        def _is_primary_line(l: VisualLine) -> bool:
            assigned, _ = assign_words_to_columns(l.words, col_map)
            esg_prev_b = col_map.extra_bounds.get("ESG_PREVIOUS")
            esg_curr_b = col_map.extra_bounds.get("ESG_CURRENT")
            # Standalone ESG continuation line (e.g. '078 078' or 'AA AA') is NEVER a new holding
            if (
                not assigned.get("UNITS")
                and not assigned.get("SECURITY_NAME")
                and not assigned.get("MARKET_VALUE")
                and not assigned.get("REPORTING_VALUE")
            ):
                if esg_prev_b and esg_curr_b and l.words and all(
                    esg_prev_b[0] - 15.0 <= w.x0 and w.x1 <= esg_curr_b[1] + 15.0
                    for w in l.words
                ):
                    return False
                if len(l.words) <= 2 and all(len(w.text.strip()) <= 4 for w in l.words):
                    return False
            id_cand, _ = _extract_identifier_from_words(assigned.get("SECURITY_ID", []))
            if id_cand is not None:
                return True
            unit_nums = [
                w for w in assigned.get("UNITS", [])
                if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
            ]
            val_words = assigned.get("REPORTING_VALUE", []) + assigned.get("MARKET_VALUE", [])
            val_nums = [
                w for w in val_words
                if not is_valid_iso_currency(w.text)
                and parse_financial_number(w.text).is_valid
                and parse_financial_number(w.text).value is not None
            ]
            return bool(unit_nums and val_nums)

        idx = 0
        while idx < len(content_lines):
            line = content_lines[idx]
            text = line.text.strip()

            cat_match = is_category_header(
                text,
                dynamic_categories,
                line_x0=line.words[0].x0 if line.words else None,
                col_map=col_map
            )
            if cat_match:
                cat_name, subtotal, pct = cat_match
                current_category = cat_name
                if subtotal is not None or cat_name not in category_subtotals:
                    category_subtotals[cat_name] = {
                        "subtotal_usd": subtotal,
                        "percentage": pct,
                        "page": page_num
                    }
                idx += 1
                continue

            if _is_primary_line(line):
                holding_lines = [line]
                next_idx = idx + 1
                while next_idx < len(content_lines):
                    next_l = content_lines[next_idx]
                    if is_category_header(
                        next_l.text.strip(),
                        dynamic_categories,
                        line_x0=next_l.words[0].x0 if next_l.words else None,
                        col_map=col_map
                    ):
                        break
                    if _is_primary_line(next_l):
                        break
                    holding_lines.append(next_l)
                    next_idx += 1

                item = _build_holding_item(
                    holding_id=f"HLD-{holding_id_counter:03d}",
                    asset_category=current_category,
                    lines=holding_lines,
                    page_num=page_num,
                    col_map=col_map
                )
                if item:
                    holdings.append(item)
                    holding_id_counter += 1
                idx = next_idx
            else:
                idx += 1

    # Attach column map metadata so validators can inspect boundary confidence
    category_subtotals["__header_maps__"] = page_header_maps  # type: ignore
    return holdings, category_subtotals


def _build_holding_item(
    holding_id: str,
    asset_category: str,
    lines: List[VisualLine],
    page_num: int,
    col_map: TableColumnMap
) -> Optional[HoldingItem]:
    """
    Constructs a structured HoldingItem using strict single-token ownership
    driven by the detected TableColumnMap boundaries.
    """
    prim_line = lines[0]
    assigned, unassigned = assign_words_to_columns(prim_line.words, col_map)

    # 1. Units / Nominal & optional leading denomination currency (e.g. 'HKD 702,000')
    units_words = assigned.get("UNITS", [])
    units_nominal_val = None
    units_curr = None
    for w in units_words:
        if is_valid_iso_currency(w.text):
            units_curr = w.text.strip().upper()
        else:
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                units_nominal_val = fn.value
    units_raw = " ".join(w.text for w in units_words).strip()

    # 2. Security Identifier: strictly from SECURITY_ID column
    id_words = assigned.get("SECURITY_ID", [])
    isin_secur_no, _ = _extract_identifier_from_words(id_words)

    # 3. Security Name: strictly from SECURITY_NAME column (never contains SECURITY_ID words)
    watermark_noise = {"SAMPLE", "VALID", "NOT", "DEMO"}
    name_parts: List[str] = []
    prim_name_words = [
        w for w in assigned.get("SECURITY_NAME", [])
        if w.text.upper() not in watermark_noise
    ]
    if prim_name_words:
        name_parts.append(" ".join(w.text for w in prim_name_words).strip())

    # 4. Yield / Rating on primary line
    yield_val = None
    yield_state = "SOURCE_BLANK"
    rating_val = None
    for w in assigned.get("YIELD_RATING", []):
        raw_t = w.text.strip()
        fn = parse_financial_number(raw_t)
        if fn.is_valid:
            if fn.value is not None:
                yield_val = fn.value
            yield_state = fn.state
        elif _is_credit_rating(raw_t):
            rating_val = raw_t.upper()

    # 5. Average Cost (and optional currency inside cost column)
    net_avg_cost = None
    net_avg_cost_currency = None
    for w in assigned.get("AVERAGE_COST", []):
        raw_t = w.text.strip()
        if is_valid_iso_currency(raw_t):
            net_avg_cost_currency = raw_t.upper()
            continue
        clean_t = re.sub(r"[^\d\.'’\-]", "", raw_t)
        fn = parse_financial_number(clean_t)
        if fn.is_valid and fn.value is not None:
            net_avg_cost = fn.value

    # 6. Market Price & Price Marker (+ possible date or leading instrument currency inside price gap)
    market_price = None
    market_price_state = "SOURCE_BLANK"
    price_marker = None
    market_price_date = None
    price_col_currency = None
    for w in assigned.get("MARKET_PRICE", []):
        raw_p = w.text.strip()
        if re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", raw_p):
            market_price_date = raw_p
            continue
        if is_valid_iso_currency(raw_p):
            price_col_currency = raw_p.upper()
            continue
        m_marker = re.search(r"^[\d\.'’,\-]+([*t\+#^a-zA-Z])$", raw_p)
        if m_marker:
            price_marker = m_marker.group(1)
        clean_t = re.sub(r"[^\d\.'’,\-]", "", raw_p)
        fn = parse_financial_number(clean_t)
        if fn.is_valid:
            market_price = fn.value
            market_price_state = fn.state

    # 7. Market / Price Currency (either dedicated CCY column OR leading ISO token in MARKET_VALUE / MARKET_PRICE)
    market_price_currency = price_col_currency
    market_value_currency = price_col_currency
    for w in assigned.get("MARKET_CURRENCY", []):
        if is_valid_iso_currency(w.text):
            c = w.text.strip().upper()
            market_price_currency = c
            market_value_currency = c
            break

    # 8. Market Value (and fallback UBP currency token when no explicit CCY column exists)
    total_market_value = None
    total_market_value_state = "SOURCE_BLANK"
    for w in assigned.get("MARKET_VALUE", []):
        raw_t = w.text.strip()
        if is_valid_iso_currency(raw_t):
            market_value_currency = raw_t.upper()
            if not market_price_currency:
                market_price_currency = raw_t.upper()
            continue
        fn = parse_financial_number(raw_t)
        if fn.is_valid and total_market_value is None and total_market_value_state == "SOURCE_BLANK":
            total_market_value = fn.value
            total_market_value_state = fn.state

    # 9. Value in Reporting Currency (USD)
    value_in_usd = None
    value_in_usd_state = "SOURCE_BLANK"
    for w in assigned.get("REPORTING_VALUE", []):
        if is_valid_iso_currency(w.text):
            if not market_value_currency:
                market_value_currency = w.text.strip().upper()
            if not market_price_currency:
                market_price_currency = w.text.strip().upper()
            continue
        fn = parse_financial_number(w.text)
        if fn.is_valid:
            value_in_usd = fn.value
            value_in_usd_state = fn.state
            break

    # 10. Percentage of Assets (strictly from PERCENTAGE column — never pulls from earlier columns)
    percentage_of_total_assets = None
    percentage_state = "SOURCE_BLANK"
    for w in assigned.get("PERCENTAGE", []):
        fn = parse_financial_number(w.text)
        if fn.is_valid:
            percentage_of_total_assets = fn.value
            percentage_state = fn.state
            break

    # 11. Process Continuation Lines cleanly (wrapped names, ESG ratings, credit ratings, valuation dates, accrued interest)
    previous_esg_rating = None
    current_esg_rating = None
    accrued_interest_local = None
    accrued_interest_usd = None
    accrued_interest_currency = None

    esg_prev_bounds = col_map.extra_bounds.get("ESG_PREVIOUS")
    esg_curr_bounds = col_map.extra_bounds.get("ESG_CURRENT")

    for cl in lines[1:]:
        cl_text = cl.text.strip()
        cl_upper = cl_text.upper()
        if any(f in cl_upper for f in ["ORIGINAL DENOMINATION", "BLANK FIELDS ARE", "SYNTHETIC TEST ONLY"]):
            continue

        # Pattern A: Inline ESG continuation line (e.g. 'ESG AA / A' or 'ESG: AA / A')
        m_esg_inline = re.search(r"\bESG[:\s]+([A-Za-z0-9\+\-]+)\s*/\s*([A-Za-z0-9\+\-]+)\b", cl_text, re.IGNORECASE)
        if m_esg_inline:
            previous_esg_rating = m_esg_inline.group(1).strip()
            current_esg_rating = m_esg_inline.group(2).strip()
            # Exclude ESG tokens when checking remaining words on this line
            cl_assigned, _ = assign_words_to_columns(cl.words, col_map)
        elif esg_prev_bounds and esg_curr_bounds and bool(cl.words) and all(
            esg_prev_bounds[0] - 15.0 <= w.x0 and w.x1 <= esg_curr_bounds[1] + 15.0
            for w in cl.words
        ) and "ESG" not in cl_upper and len(cl.words) <= 4:
            # Pattern B: UBP columnar ESG line aligned under ESG: PREVIOUS | CURRENT
            prev_cand = [w.text.strip() for w in cl.words if w.x0 <= esg_prev_bounds[1] + 5.0]
            curr_cand = [w.text.strip() for w in cl.words if w.x0 >= esg_curr_bounds[0] - 5.0]
            if prev_cand:
                previous_esg_rating = " ".join(prev_cand)
            if curr_cand:
                current_esg_rating = " ".join(curr_cand)
            continue
        else:
            cl_assigned, cl_unassigned = assign_words_to_columns(cl.words, col_map)
            if cl_unassigned:
                unassigned.extend(cl_unassigned)

        # Continuation wrapped description strictly inside SECURITY_NAME column
        cname_words = [
            w for w in cl_assigned.get("SECURITY_NAME", [])
            if w.text.upper() not in watermark_noise
        ]
        if cname_words:
            c_text = " ".join(w.text for w in cname_words).strip()
            if c_text:
                name_parts.append(c_text)

        # Credit rating on continuation line inside YIELD_RATING column (e.g. 'AA', 'A')
        for w in cl_assigned.get("YIELD_RATING", []):
            raw_t = w.text.strip()
            if _is_credit_rating(raw_t) and rating_val is None:
                rating_val = raw_t.upper()

        # Market price date on continuation line inside MARKET_PRICE column
        for w in cl_assigned.get("MARKET_PRICE", []):
            raw_t = w.text.strip()
            if re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", raw_t) and market_price_date is None:
                market_price_date = raw_t

        # Accrued interest inside MARKET_VALUE / REPORTING_VALUE columns on continuation line
        for w in cl_assigned.get("MARKET_VALUE", []):
            if is_valid_iso_currency(w.text):
                accrued_interest_currency = w.text.strip().upper()
                continue
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                accrued_interest_local = fn.value

        for w in cl_assigned.get("REPORTING_VALUE", []):
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                accrued_interest_usd = fn.value

    full_security_name = " ".join([p for p in name_parts if p]).strip()

    # Preserve fallback currency if UNITS specified it (e.g. HKD 702,000) and CCY was absent
    effective_mkt_curr = market_value_currency or market_price_currency or units_curr or "USD"
    effective_price_curr = market_price_currency or effective_mkt_curr

    if total_market_value is None and value_in_usd is not None:
        total_market_value = value_in_usd
        total_market_value_state = "CALCULATED"
    if value_in_usd is None and total_market_value is not None and effective_mkt_curr == "USD":
        value_in_usd = total_market_value
        value_in_usd_state = total_market_value_state

    accrued_interest = accrued_interest_local if accrued_interest_local is not None else accrued_interest_usd
    if effective_mkt_curr == "USD" and accrued_interest_usd is not None:
        accrued_interest = accrued_interest_usd

    all_words = [w for cl in lines for w in cl.words]
    min_x = min(w.x0 for w in all_words) if all_words else 0.0
    min_y = min(w.y0 for w in all_words) if all_words else 0.0
    max_x = max(w.x1 for w in all_words) if all_words else 0.0
    max_y = max(w.y1 for w in all_words) if all_words else 0.0

    return HoldingItem(
        id=holding_id,
        asset_category=asset_category,
        units_nominal=units_nominal_val,
        units_nominal_raw=units_raw,
        security_name=full_security_name,
        isin_secur_no=isin_secur_no,
        yield_val=yield_val,
        yield_state=yield_state,
        rating=rating_val,
        net_avg_cost=net_avg_cost,
        net_avg_cost_currency=net_avg_cost_currency,
        market_price=market_price,
        market_price_state=market_price_state,
        price_marker=price_marker,
        market_price_currency=effective_price_curr,
        market_price_date=market_price_date,
        total_market_value=total_market_value,
        total_market_value_state=total_market_value_state,
        market_value_currency=effective_mkt_curr,
        accrued_interest=accrued_interest,
        accrued_interest_currency=accrued_interest_currency or effective_mkt_curr,
        accrued_interest_usd=accrued_interest_usd or (accrued_interest if effective_mkt_curr == "USD" else None),
        value_in_usd=value_in_usd,
        value_in_usd_state=value_in_usd_state,
        percentage_of_total_assets=percentage_of_total_assets,
        percentage_state=percentage_state,
        previous_esg_rating=previous_esg_rating,
        current_esg_rating=current_esg_rating,
        esg_rating_previous=previous_esg_rating,
        esg_rating_current=current_esg_rating,
        header_confidence=col_map.confidence,
        unassigned_tokens=[w.text for w in unassigned if w.text.strip()],
        source_page=page_num,
        bbox=[min_x, min_y, max_x, max_y],
        raw_text="\n".join(cl.text for cl in lines)
    )
