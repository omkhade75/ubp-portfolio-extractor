import re
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal
import pymupdf

from app.models.schemas import HoldingItem
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines, VisualLine

COMMON_ISO_CURRENCIES = {
    "USD", "EUR", "GBP", "CHF", "JPY", "HKD", "SGD", "AUD", "CAD", "NZD",
    "CNY", "SEK", "NOK", "DKK", "ZAR", "BRL", "INR", "KRW", "MXN", "AED", "SAR"
}

def is_iso_currency(token: str) -> bool:
    clean = token.strip().upper()
    return clean in COMMON_ISO_CURRENCIES or (len(clean) == 3 and clean.isalpha() and clean.isupper())

KNOWN_CATEGORIES = [
    "BONDS/NOTES, BOND FUNDS & CERTIFICATES",
    "EQUITIES, EQUITY FUNDS & CERTIFICATES",
    "EQUITIES & EXCHANGE-TRADED FUNDS",
    "EQUITIES, EQUITIES & ETF",
    "EQUITIES & ETFS",
    "ALTERNATIVE INVESTMENTS & CERTIFICATES",
    "STRUCTURED PRODUCTS",
    "PRIVATE EQUITY",
    "MONEY MARKET INSTRUMENTS",
    "COMMODITIES & PRECIOUS METALS",
    "REAL ESTATE",
    "FIDUCIARY DEPOSITS"
]

def is_category_header(
    line_text: str,
    dynamic_categories: Optional[List[str]] = None,
    line_x0: Optional[float] = None
) -> Optional[Tuple[str, Optional[Decimal], Optional[Decimal]]]:
    """
    Checks if a line is an asset category header line.
    Matches against dynamically discovered categories from Asset Allocation,
    standard UBP categories, or structural category banner patterns.
    Returns (category_name, subtotal_usd, percentage) if matched.
    """
    if line_x0 is not None and line_x0 > 60.0:
        return None
    upper = line_text.upper().strip()
    
    # 1. Check against dynamic categories (from Page 1 Asset Allocation) and known categories
    categories_to_check = []
    if dynamic_categories:
        for dc in dynamic_categories:
            if dc and dc.upper() not in categories_to_check:
                categories_to_check.append(dc.upper())
    for kc in KNOWN_CATEGORIES:
        if kc.upper() not in categories_to_check:
            categories_to_check.append(kc.upper())

    # Sort categories by length descending to match longest category title first
    categories_to_check.sort(key=len, reverse=True)

    for cat in categories_to_check:
        if cat in upper:
            # Must not be a security holding line that has an ISIN/security number
            if any(is_isin_or_secur_no(w) for w in line_text.split()):
                continue

            # Must start with the category name (allowing leading bullet or whitespace)
            m_start = re.match(r"^[\s\-•*]*" + re.escape(cat), upper)
            if not m_start:
                continue

            # Remainder of line after category name must only contain numeric values
            # (subtotal and percentage) and optional ISO currency/percentage symbols.
            # If it contains security descriptors (e.g. FUND, SHS, SICAR, LIMITED), it is not a header.
            remainder = upper[m_start.end():].strip()
            rem_words = remainder.split()
            non_numeric_words = [
                rw for rw in rem_words
                if not parse_financial_number(rw).is_valid
                and rw not in COMMON_ISO_CURRENCIES
                and rw not in {"%", "-", "USD", "EUR", "CHF", "GBP"}
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

DISALLOWED_ID_WORDS = {
    "BONDS", "NOTES", "ALTERNATIVES", "ALTERNATIVE", "EQUITIES", "EQUITY",
    "STRUCTURED", "PRODUCTS", "CERTIFICATES", "FUNDS", "SHARES", "TOTAL",
    "SAMPLE", "NOT", "VALID", "DEMO", "INVESTMENTS", "USD", "EUR", "GBP",
    "CHF", "JPY", "HKD", "SGD", "AUD", "CAD", "NZD", "CNY", "SEK", "NOK",
    "DKK", "NAME", "SECUR", "SECURITY", "UNIT", "UNITS", "NOMINAL", "YIELD",
    "DURATION", "COST", "PRICE", "VALUE", "ASSETS", "SERIES", "CLASS", "IN",
    "MONEY", "MARKET", "REAL", "ESTATE", "COMMODITIES", "PRECIOUS", "METALS",
    "SUBTOTAL", "BALANCE", "PERFORMANCE", "SUMMARY", "OVERVIEW"
}

def is_isin_or_secur_no(token: str) -> bool:
    """
    Validates if token is an ISIN or UBP security number.
    Format 1: standard ISO 6166 ISIN (2 country letters + 9-10 alphanumeric + 1 check digit)
    Format 2: Swiss Valoren or internal secur no (e.g. 127676268.000, 133885351.000, XD1356846166, XFCS00X6RSF8)
    Format 3: Synthetic / hyphenated security numbers (e.g. XS-NG-20482, SG-PB-51903, IE-SP-20461, LU-HI-77120)
    Format 4: Generic alphanumeric security identifiers with digits and letters (e.g. SGXZ40236853)
    Format 5: CUSIP (9 alphanumeric characters with check digit)
    Format 6: SEDOL (7 alphanumeric characters with check digit)
    Must never match ordinary words, category names, currency codes, or watermark text.
    """
    clean = token.strip().upper()
    if not clean or clean in DISALLOWED_ID_WORDS:
        return False
    if clean.isalpha():
        return False

    # Standard ISO 6166 ISIN (must end in a numeric check digit)
    if re.match(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$", clean):
        return True
    # Swiss Valoren numbers: digits (with optional .000 or similar subcode)
    if re.match(r"^\d{6,10}(\.\d{3})?$", clean):
        return True
    # UBP internal security numbers (e.g. XD1356846166, XFCS00X6RSF8)
    if re.match(r"^X[D|F][A-Z0-9]{8,12}$", clean):
        return True
    # Synthetic / hyphenated security numbers (e.g. XS-NG-20482, SG-PB-51903)
    if re.match(r"^[A-Z]{2}-[A-Z0-9]{2,4}-[0-9]{4,6}$", clean):
        return True
    if re.match(r"^[A-Z0-9]{2,5}(-[A-Z0-9]{2,6})+$", clean) and any(c.isdigit() for c in clean):
        return True
    # Generic alphanumeric identifier with digits and letters (e.g. SGXZ40236853)
    if re.match(r"^[A-Z0-9]{9,14}$", clean) and any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean):
        return True
    # CUSIP (9 alphanumeric characters with at least one digit and check digit)
    if re.match(r"^[0-9A-Z]{8}[0-9]$", clean) and any(c.isdigit() for c in clean) and any(c.isalpha() for c in clean):
        return True
    # SEDOL (7 alphanumeric characters with at least one digit)
    if re.match(r"^[B-DF-HJ-NP-TV-Z0-9]{6}[0-9]$", clean) and any(c.isdigit() for c in clean):
        return True
    return False

def detect_holdings_column_anchors(lines: List[VisualLine], page_width: float) -> Dict[str, float]:
    """
    Dynamically identifies column positions on a UBP holdings page by inspecting
    the table header line(s). Falls back to proportional page boundaries when
    headers are unspaced or clumped.
    """
    anchors = {
        "units_max": page_width * 0.115,        # ~96.8 on 842 pt landscape
        "isin_min": page_width * 0.43,          # ~360
        "isin_max": page_width * 0.58,          # ~485
        "esg_prev_min": page_width * 0.43,      # ~362
        "esg_prev_max": page_width * 0.48,      # ~404
        "esg_curr_min": page_width * 0.47,      # ~395
        "esg_curr_max": page_width * 0.52,      # ~437
        "yield_min": page_width * 0.51,         # ~430
        "yield_max": page_width * 0.59,         # ~495
        "cost_min": page_width * 0.57,          # ~480
        "cost_max": page_width * 0.66,          # ~555
        "price_min": page_width * 0.64,         # ~540
        "price_max": page_width * 0.74,         # ~620
        "mkt_val_min": page_width * 0.73,       # ~615
        "mkt_val_max": page_width * 0.85,       # ~715
        "usd_val_min": page_width * 0.83,       # ~700
        "usd_val_max": page_width * 0.93,       # ~780
        "pct_min": page_width * 0.90,           # ~760
    }

    # Only inspect header lines that span across the table columns (>= 70% of page width)
    spanning_header_lines = [
        l for l in lines
        if l.y <= 145.0 and l.words and l.words[-1].x1 >= page_width * 0.70
        and ("UNITS" in l.text.upper() or "NOMINAL" in l.text.upper() or "SECUR" in l.text.upper())
    ]
    if not spanning_header_lines:
        return anchors

    header_words = [w for l in spanning_header_lines for w in l.words]
    market_words = [w for w in header_words if "MARKET" in w.text.upper()]
    value_words = [w for w in header_words if "VALUE" in w.text.upper()]
    has_total_mkt_val = any("TOTAL" in w.text.upper() for w in header_words)

    for w in header_words:
        wt = w.text.upper()
        if ("SECUR" in wt or "ISIN" in wt) and "SECURITY" not in wt and "NAME" not in wt:
            anchors["isin_min"] = w.x0 - 20.0
            anchors["isin_max"] = w.x1 + 45.0
        elif "PREVIOUS" in wt and any("ESG" in hw.text.upper() for hw in header_words):
            anchors["esg_prev_min"] = w.x0 - 15.0
            anchors["esg_prev_max"] = w.x1 + 10.0
        elif "CURRENT" in wt and any("ESG" in hw.text.upper() for hw in header_words):
            anchors["esg_curr_min"] = w.x0 - 10.0
            anchors["esg_curr_max"] = w.x1 + 15.0
        elif "YIELD" in wt or "DURATION" in wt:
            anchors["yield_min"] = min(anchors["yield_min"], w.x0 - 15.0)
            anchors["yield_max"] = max(anchors["yield_max"], w.x1 + 25.0)
        elif "NET" in wt or "AVERAGE" in wt or "COST" in wt or "AVG." in wt:
            anchors["cost_min"] = min(anchors["cost_min"], w.x0 - 15.0)
            anchors["cost_max"] = max(anchors["cost_max"], w.x1 + 30.0)
        elif "TOTAL" in wt:
            anchors["mkt_val_min"] = w.x0 - 20.0
        elif "%" in wt or "ASSETS" in wt:
            anchors["pct_min"] = min(anchors["pct_min"], w.x0 - 15.0)

    if len(market_words) >= 2 and not has_total_mkt_val:
        m0, m1 = market_words[0], market_words[1]
        anchors["price_min"] = m0.x0 - 20.0
        anchors["price_max"] = m0.x1 + 35.0
        anchors["usd_val_min"] = m1.x0 - 15.0
        anchors["usd_val_max"] = (anchors.get("pct_min") or page_width * 0.90) - 5.0
        anchors["mkt_val_min"] = anchors["usd_val_min"]
        anchors["mkt_val_max"] = anchors["usd_val_max"]
    elif market_words:
        m0 = market_words[0]
        anchors["price_min"] = m0.x0 - 20.0
        anchors["price_max"] = m0.x1 + 40.0
        if value_words:
            anchors["usd_val_min"] = value_words[-1].x0 - 20.0

    return anchors

def parse_holdings_pages(
    doc: pymupdf.Document,
    holdings_page_indices: List[int],
    dynamic_categories: Optional[List[str]] = None
) -> Tuple[List[HoldingItem], Dict[str, Dict[str, Any]]]:
    """
    Parses holdings across all identified holdings pages.
    Tracks ongoing asset category continuity.
    Uses dynamic column anchors and category discovery.
    Returns (list_of_holdings, category_subtotals_dict).
    """
    holdings: List[HoldingItem] = []
    category_subtotals: Dict[str, Dict[str, Any]] = {}
    current_category = "UNKNOWN"
    holding_id_counter = 1

    for pno in holdings_page_indices:
        page = doc[pno]
        page_num = pno + 1
        page_width = page.rect.width
        _, lines = extract_visual_words_and_lines(page)

        # Detect column anchors dynamically for this page
        anchors = detect_holdings_column_anchors(lines, page_width)

        # Filter out running header and footer lines
        content_lines: List[VisualLine] = []
        for l in lines:
            if l.y < 105.0:  # Header area
                continue
            if l.y > 540.0:  # Footer area
                continue
            content_lines.append(l)

        idx = 0
        while idx < len(content_lines):
            line = content_lines[idx]
            text = line.text.strip()

            # Check category header
            cat_match = is_category_header(text, dynamic_categories, line_x0=line.words[0].x0 if line.words else None)
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

            # Check if this line is a Primary Holding line:
            # 1. Has an identifier in [isin_min - 25.0, isin_max + 25.0]
            # 2. OR has units in [0, units_max] AND numeric financial data in price/val columns
            # (Must not be a category header line or footer line)
            has_secur_id = any(
                is_isin_or_secur_no(w.text)
                for w in line.words
                if anchors["isin_min"] - 25.0 <= w.x0 <= anchors["isin_max"] + 25.0
            )
            has_units = any(
                w.x1 <= anchors["units_max"] + 5.0 and parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
                for w in line.words
            )
            has_financial = any(
                w.x0 >= anchors["price_min"] - 20.0 and parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
                for w in line.words
            )

            is_primary_holding_line = has_secur_id or (has_units and has_financial)

            if is_primary_holding_line:
                # Primary holding line found!
                holding_lines = [line]
                next_idx = idx + 1
                while next_idx < len(content_lines):
                    next_l = content_lines[next_idx]
                    if is_category_header(next_l.text.strip(), dynamic_categories, line_x0=next_l.words[0].x0 if next_l.words else None):
                        break
                    next_has_secur_id = any(
                        is_isin_or_secur_no(w.text)
                        for w in next_l.words
                        if anchors["isin_min"] - 25.0 <= w.x0 <= anchors["isin_max"] + 25.0
                    )
                    next_has_units = any(
                        w.x1 <= anchors["units_max"] + 5.0 and parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
                        for w in next_l.words
                    )
                    next_has_financial = any(
                        w.x0 >= anchors["price_min"] - 20.0 and parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
                        for w in next_l.words
                    )
                    if next_has_secur_id or (next_has_units and next_has_financial):
                        break
                    holding_lines.append(next_l)
                    next_idx += 1

                # Parse the holding item from holding_lines
                holding_item = _build_holding_item(
                    f"HLD-{holding_id_counter:03d}",
                    current_category,
                    holding_lines,
                    page_num,
                    anchors
                )
                if holding_item:
                    holdings.append(holding_item)
                    holding_id_counter += 1

                idx = next_idx
            else:
                idx += 1

    return holdings, category_subtotals

def _build_holding_item(
    holding_id: str,
    asset_category: str,
    lines: List[VisualLine],
    page_num: int,
    anchors: Optional[Dict[str, float]] = None
) -> Optional[HoldingItem]:
    """
    Reconstructs an individual holding from its primary line and continuation lines
    using dynamically detected column anchors.
    """
    prim_line = lines[0]
    words = prim_line.words

    units_max = anchors["units_max"] if anchors else 98.0
    isin_min = anchors["isin_min"] if anchors else 360.0
    isin_max = anchors["isin_max"] if anchors else 480.0
    yield_min = anchors["yield_min"] if anchors else 430.0
    yield_max = anchors["yield_max"] if anchors else 495.0
    cost_min = anchors["cost_min"] if anchors else 480.0
    cost_max = anchors["cost_max"] if anchors else 555.0
    price_min = anchors["price_min"] if anchors else 540.0
    price_max = anchors["price_max"] if anchors else 620.0
    mkt_val_min = anchors["mkt_val_min"] if anchors else 615.0
    mkt_val_max = anchors["mkt_val_max"] if anchors else 715.0
    usd_val_min = anchors["usd_val_min"] if anchors else 700.0
    usd_val_max = anchors["usd_val_max"] if anchors else 780.0
    pct_min = anchors["pct_min"] if anchors else 760.0
    esg_prev_min = anchors["esg_prev_min"] if anchors and "esg_prev_min" in anchors else 360.0
    esg_prev_max = anchors["esg_prev_max"] if anchors and "esg_prev_max" in anchors else 405.0
    esg_curr_min = anchors["esg_curr_min"] if anchors and "esg_curr_min" in anchors else 400.0
    esg_curr_max = anchors["esg_curr_max"] if anchors and "esg_curr_max" in anchors else 440.0

    # 1. Units / Nominal & currency prefix
    units_words = [w for w in words if w.x1 <= units_max or (w.x0 < units_max and w.x1 <= units_max + 2.0)]
    units_nominal_val = None
    units_curr = None
    for w in units_words:
        if is_iso_currency(w.text.strip()):
            units_curr = w.text.strip().upper()
        else:
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                units_nominal_val = fn.value

    units_raw = " ".join(w.text for w in units_words).strip()
    if units_nominal_val is None and units_raw:
        fn = parse_financial_number(re.sub(r"^[A-Z]{3}\s+", "", units_raw))
        if fn.is_valid and fn.value is not None:
            units_nominal_val = fn.value

    # 2. Security Identifier Detection: strictly within the detected Security Number column
    isin_secur_no = None
    isin_x0 = None
    secur_col_candidates = [
        w for w in words
        if (isin_min - 25.0 <= w.x0 <= isin_max + 25.0)
    ]
    # First priority: matches standard validated security identifier format
    for w in secur_col_candidates:
        if is_isin_or_secur_no(w.text):
            isin_secur_no = w.text.strip()
            isin_x0 = w.x0
            break

    # Second priority: structurally valid unfamiliar candidate residing in the security number column
    # Must have identifier characteristics (digits or hyphens). Pure English words are never shifted into ID column.
    if isin_secur_no is None:
        for w in secur_col_candidates:
            clean_tok = w.text.strip().upper()
            if (
                clean_tok
                and clean_tok not in DISALLOWED_ID_WORDS
                and not is_iso_currency(clean_tok)
                and not clean_tok.isalpha()
                and (any(c.isdigit() for c in clean_tok) or ("-" in clean_tok and len(clean_tok) >= 4))
                and not any(k in clean_tok for k in ["SAMPLE", "VALID", "DEMO"])
            ):
                isin_secur_no = f"{w.text.strip()} (REVIEW_REQUIRED)"
                isin_x0 = w.x0
                break

    # 3. Security Name: strictly to the left of the Security Number column
    name_parts = []
    cutoff_isin = isin_x0 if isin_x0 else isin_min
    prim_name_words = [
        w for w in words
        if w not in units_words and w.x0 < cutoff_isin
        and w.text.upper() not in {"SAMPLE", "VALID", "NOT", "DEMO"}
    ]
    if prim_name_words:
        name_parts.append(" ".join(w.text for w in prim_name_words).strip())

    market_price_date = None
    price_marker = None
    previous_esg_rating = None
    current_esg_rating = None
    accrued_interest_local = None
    accrued_interest_usd = None

    for cl in lines[1:]:
        # Check if line is solely an ESG rating line
        is_esg_line = bool(cl.words) and all(
            esg_prev_min - 20.0 <= w.x0 and w.x1 <= esg_curr_max + 20.0
            for w in cl.words
        ) and "ESG" not in cl.text.upper() and len(cl.words) <= 4

        if is_esg_line:
            prev_cand = [w.text.strip() for w in cl.words if w.x0 <= esg_prev_max + 5.0]
            curr_cand = [w.text.strip() for w in cl.words if w.x0 >= esg_curr_min - 5.0]
            if prev_cand:
                previous_esg_rating = " ".join(prev_cand)
            if curr_cand:
                current_esg_rating = " ".join(curr_cand)
            continue

        # Continuation line name words
        cname_words = [
            w for w in cl.words
            if (w.x1 > units_max or w.x0 >= units_max - 5.0)
            and w.x0 < cutoff_isin
            and w.text.upper() not in {"SAMPLE", "VALID", "NOT", "DEMO"}
        ]
        if cname_words:
            c_text = " ".join(w.text for w in cname_words).strip()
            if c_text:
                name_parts.append(c_text)

        # Market price date: DD.MM.YY or DD.MM.YYYY
        for w in cl.words:
            if (price_min - 35.0 <= w.x0 <= price_max + 35.0) and re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip()):
                market_price_date = w.text.strip()
            # Accrued interest tokens appear at x >= mkt_val_min
            if mkt_val_min <= w.x0 < usd_val_min:
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    accrued_interest_local = fn.value
            elif w.x0 >= usd_val_min:
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    accrued_interest_usd = fn.value

    full_security_name = " ".join([p for p in name_parts if p]).strip()

    # 4. Numbers to the right of ISIN on primary line
    right_words = [w for w in words if w.x0 > (isin_x0 or isin_min)]
    
    yield_val = None
    net_avg_cost = None
    net_avg_cost_currency = None
    market_price = None
    market_price_currency = None
    total_market_value = None
    market_value_currency = None
    value_in_usd = None
    percentage_of_total_assets = None

    # Identify currency tokens strictly by column geometry
    accrued_interest_currency = None
    for w in right_words:
        cand = w.text.strip().upper()
        if is_iso_currency(cand):
            if cost_min - 20.0 <= w.x0 < price_min - 20.0:
                net_avg_cost_currency = cand
            else:
                market_value_currency = cand

    # Parse numeric tokens by dynamic x position:
    # Yield: yield_min <= x0 < yield_max
    for w in right_words:
        if yield_min <= w.x0 < yield_max:
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                yield_val = fn.value

    # Net Average Cost: cost_min <= x0 < cost_max
    for w in right_words:
        if cost_min <= w.x0 < cost_max:
            clean_t = re.sub(r"[^\d\.'’\-]", "", w.text.strip())
            fn = parse_financial_number(clean_t)
            if fn.is_valid and fn.value is not None:
                net_avg_cost = fn.value

    # Market Price: price_min <= x0 < min(price_max, usd_val_min)
    effective_price_max = min(price_max, usd_val_min) if (usd_val_min and usd_val_min > price_min) else price_max
    for w in right_words:
        if price_min <= w.x0 < effective_price_max:
            raw_p = w.text.strip()
            if is_iso_currency(raw_p):
                continue
            m_marker = re.search(r"^[\d\.'’\-]+([*t\+#^a-zA-Z])$", raw_p)
            if m_marker:
                price_marker = m_marker.group(1)
            clean_t = re.sub(r"[^\d\.'’\-]", "", raw_p)
            fn = parse_financial_number(clean_t)
            if fn.is_valid and fn.value is not None:
                market_price = fn.value

    # Check primary line for market price date if not found on continuation line
    if market_price_date is None:
        for w in right_words:
            if (price_min - 20.0 <= w.x0 <= price_max + 20.0) and re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip()):
                market_price_date = w.text.strip()

    # Total Market Value: mkt_val_min <= x0 < mkt_val_max
    for w in right_words:
        if mkt_val_min <= w.x0 < mkt_val_max:
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                total_market_value = fn.value

    # Value in USD: usd_val_min <= x0 < usd_val_max
    for w in right_words:
        if usd_val_min <= w.x0 < usd_val_max:
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                value_in_usd = fn.value

    # % Assets: x0 >= pct_min
    for w in right_words:
        if w.x0 >= pct_min:
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None:
                percentage_of_total_assets = fn.value

    if total_market_value is None and value_in_usd is not None:
        total_market_value = value_in_usd
    if value_in_usd is None and total_market_value is not None and (market_value_currency == "USD" or not market_value_currency):
        value_in_usd = total_market_value

    accrued_interest = accrued_interest_local or accrued_interest_usd
    if market_value_currency == "USD" and accrued_interest_usd is not None:
        accrued_interest = accrued_interest_usd

    all_words = [w for cl in lines for w in cl.words]
    min_x = min(w.x0 for w in all_words) if all_words else 0.0
    min_y = min(w.y0 for w in all_words) if all_words else 0.0
    max_x = max(w.x1 for w in all_words) if all_words else 0.0
    max_y = max(w.y1 for w in all_words) if all_words else 0.0
    bbox = [min_x, min_y, max_x, max_y]

    raw_text = "\n".join(cl.text for cl in lines)

    return HoldingItem(
        id=holding_id,
        asset_category=asset_category,
        units_nominal=units_nominal_val,
        units_nominal_raw=units_raw,
        security_name=full_security_name,
        isin_secur_no=isin_secur_no,
        yield_val=yield_val,
        net_avg_cost=net_avg_cost,
        net_avg_cost_currency=net_avg_cost_currency,
        market_price=market_price,
        price_marker=price_marker,
        market_price_currency=market_price_currency,
        market_price_date=market_price_date,
        total_market_value=total_market_value,
        market_value_currency=market_value_currency or "USD",
        accrued_interest=accrued_interest,
        accrued_interest_currency=accrued_interest_currency or market_value_currency or "USD",
        accrued_interest_usd=accrued_interest_usd or (accrued_interest if market_value_currency == "USD" else None),
        value_in_usd=value_in_usd,
        percentage_of_total_assets=percentage_of_total_assets,
        previous_esg_rating=previous_esg_rating,
        current_esg_rating=current_esg_rating,
        esg_rating_previous=previous_esg_rating,
        esg_rating_current=current_esg_rating,
        source_page=page_num,
        bbox=bbox,
        raw_text=raw_text
    )
