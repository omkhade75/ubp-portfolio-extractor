import re
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal
import pymupdf

from app.models.schemas import HoldingItem
from app.processing.number_parser import parse_financial_number
from app.extraction.identifier_engine import normalize_security_identifier, IdentifierResult
from app.extraction.ocr_extractor import detect_page_type
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

            # Must not contain an identifier (check non-amount tokens)
            non_amount_words = [
                w for w in line_text.split()
                if not (parse_financial_number(w).is_valid and parse_financial_number(w).value is not None)
            ]
            if any(is_isin_or_secur_no(w) for w in non_amount_words):
                continue

            remainder = upper[m_start.end():].strip()
            rem_words = remainder.split()
            continuation_noise = {"CONTINUATION", "CONTINUED", "PAGE", "CONT", "(CONTINUED)", "(CONT.)", "SCANNED", "-", "—"}
            non_numeric_words = [
                rw for rw in rem_words
                if not parse_financial_number(rw).is_valid
                and not is_valid_iso_currency(rw)
                and rw not in {"%", "-"}
                and rw not in continuation_noise
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
    header_keywords = {
        "UNITS", "NOMINAL", "POSITION", "INSTRUMENT", "SECURITY", "NAME",
        "DESCRIPTION", "SECUR", "ISIN", "REFERENCE", "YIELD", "DISTRIBUTION",
        "COST", "PRICE", "CLOSING", "VALUE", "VALUATION", "EQUIVALENT", "DENOM"
    }
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
        if any(k in nl_up for k in ["NOMINAL", "RATING", "COST", "PRICE", "INTEREST", "USD", "ASSETS", "ESG", "PREVIOUS", "CURRENT", "DURATION", "CODE", "YIELD", "AMOUNT", "EQUIVALENT", "PORTFOLIO", "CCY"]):
            header_lines.append(nl)
        else:
            break

    tmap = build_table_column_map(header_lines, HOLDINGS_SYNONYMS, "HOLDINGS", page_width)
    return tmap


def _extract_identifier_from_words(
    id_words: List[ExtractedWord],
    line_text: str = ""
) -> Tuple[Optional[str], Optional[IdentifierResult]]:
    """
    Extracts clean security identifier from tokens strictly inside SECURITY_ID column.
    Supports space-split OCR tokens (e.g. 'XSSYNOOOI' + '090') while never returning ordinary prose words.
    Integrates with normalize_security_identifier for deterministic format validation
    and OCR character confusion handling.
    """
    if not id_words:
        return None, None

    # First pass: exact or normalized single token match
    for w in id_words:
        tok = w.text.strip()
        clean = tok.upper()
        if (tok.isdigit() and len(tok) <= 3) or clean in DISALLOWED_ID_WORDS or _is_credit_rating(clean) or clean.startswith("ESG") or re.match(r"^\d{2,4}[./-]\d{2}[./-]\d{2,4}$", tok):
            continue
        res = normalize_security_identifier(tok, confidence=w.confidence)
        if res.status in ("PASS", "NORMALIZED"):
            return res.normalized_identifier, res

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
                clean_j = joined.upper()
                if clean_j in DISALLOWED_ID_WORDS or _is_credit_rating(clean_j) or clean_j.startswith("ESG") or re.match(r"^\d{2,4}[./-]\d{2}[./-]\d{2,4}$", joined):
                    continue
                avg_conf = sum(w.confidence for w in grp) / len(grp)
                res = normalize_security_identifier(joined, confidence=avg_conf)
                if res.status in ("PASS", "NORMALIZED"):
                    return res.normalized_identifier, res

    # Third pass: unfamiliar but structurally valid alphanumeric/hyphenated identifier inside ID column
    for w in id_words:
        clean_tok = w.text.strip().upper()
        if clean_tok.isdigit() and len(clean_tok) <= 3:
            continue
        if (
            clean_tok
            and clean_tok not in DISALLOWED_ID_WORDS
            and not is_valid_iso_currency(clean_tok)
            and not clean_tok.isalpha()
            and not _is_credit_rating(clean_tok)
            and not clean_tok.startswith("ESG")
            and not re.match(r"^\d{2,4}[./-]\d{2}[./-]\d{2,4}$", clean_tok)
            and (any(c.isdigit() for c in clean_tok) or ("-" in clean_tok and len(clean_tok) >= 4))
            and not any(k in clean_tok for k in ["SAMPLE", "VALID", "DEMO"])
        ):
            res = normalize_security_identifier(w.text.strip(), confidence=w.confidence)
            return res.normalized_identifier, res

    return None, None


def has_financial_anchor(l: VisualLine, col_map: TableColumnMap) -> bool:
    """Returns True if the line contains core financial quantities of a holding (ID or units + values)."""
    assigned, _ = assign_words_to_columns(l.words, col_map)
    id_cand, _ = _extract_identifier_from_words(assigned.get("SECURITY_ID", []), line_text=l.text)
    if id_cand:
        return True
    has_units = any(
        parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
        for w in assigned.get("UNITS", [])
    )
    val_words = assigned.get("REPORTING_VALUE", []) + assigned.get("MARKET_VALUE", [])
    has_vals = any(
        not is_valid_iso_currency(w.text)
        and parse_financial_number(w.text).is_valid
        and parse_financial_number(w.text).value is not None
        for w in val_words
    )
    return bool(has_units and has_vals)


def is_description_only_line(l: VisualLine, col_map: TableColumnMap) -> bool:
    """Returns True if the line is purely an introductory description row preceding a financial anchor."""
    assigned, _ = assign_words_to_columns(l.words, col_map)
    name_words = assigned.get("SECURITY_NAME", [])
    if not name_words:
        return False
    # If the line contains financial figures in values/cost/price/units/percentage columns (e.g. accrued interest continuation lines), it is not description-only
    # Note: SECURITY_ID is excluded because non-ID numbers (e.g. 'Series 10' or '2035') spilling into the ID column must not disqualify description lines
    for k in ("MARKET_VALUE", "REPORTING_VALUE", "PERCENTAGE", "AVERAGE_COST", "MARKET_PRICE", "UNITS"):
        for w in assigned.get(k, []):
            wt = w.text.strip()
            if is_valid_iso_currency(wt) or wt in {"-", "—", "/"}:
                continue
            fn = parse_financial_number(wt)
            if fn.is_valid and fn.value is not None:
                return False
    if has_financial_anchor(l, col_map):
        return False
    text = " ".join(w.text for w in name_words).strip()
    return any(c.isalpha() for c in text) and len(text) >= 3


def is_case_b_pair(desc_l: VisualLine, fin_l: VisualLine, col_map: TableColumnMap) -> bool:
    """
    Returns True if desc_l and fin_l form a Case B vertically separated holding:
    desc_l contains the security name description, and fin_l contains the financial anchor
    WITHOUT its own full security name.
    """
    if not is_description_only_line(desc_l, col_map):
        return False
    if not has_financial_anchor(fin_l, col_map):
        return False
    assigned, _ = assign_words_to_columns(fin_l.words, col_map)
    name_words = assigned.get("SECURITY_NAME", [])
    genuine_name_words = []
    for w in name_words:
        wt = w.text.strip().upper()
        if wt in {"ESG", "/", "|", "-", "—"} or re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", wt):
            continue
        if re.match(r"^[A-D]{1,3}[\+\-]?(?:/[A-D]{1,3}[\+\-]?)?$", wt) or wt in {"AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D", "NR"}:
            continue
        genuine_name_words.append(wt)
    if len(genuine_name_words) >= 2 or (genuine_name_words and len(genuine_name_words[0]) >= 6):
        return False
    return True


def is_primary_holding_line(l: VisualLine, col_map: TableColumnMap) -> bool:
    """
    Determines structurally whether a table row is a primary financial holding line.
    Prevents standalone ESG lines, credit ratings, valuation dates, watermarks,
    or empty content from becoming artificial holdings.
    """
    lu = l.text.upper()
    # 1. Date-only line (e.g. market price date '30.09.25' or '31.10.2025')
    if re.match(r"^\s*\d{2}\.\d{2}\.\d{2,4}\s*$", l.text.strip()):
        return False
    # 2. Credit rating only line
    if _is_credit_rating(l.text.strip()):
        return False

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

    # Standalone ESG line without financial substance is never a primary holding
    if re.search(r"\bESG\b", lu) and not has_financial_anchor(l, col_map):
        return False

    # 4. Primary row structural substance check:
    # A valid financial holding must possess real financial content:
    # - Security name description (at least 2 letters, not disallowed noise)
    # - OR Units (valid financial number)
    # - OR Financial value / market price evidence
    name_words = [
        w.text.strip() for w in assigned.get("SECURITY_NAME", [])
        if len(w.text.strip()) >= 2 and w.text.upper() not in DISALLOWED_ID_WORDS
    ]
    has_name = bool(name_words)
    has_units = any(
        parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
        for w in assigned.get("UNITS", [])
    )
    val_words = assigned.get("REPORTING_VALUE", []) + assigned.get("MARKET_VALUE", [])
    has_vals = any(
        not is_valid_iso_currency(w.text)
        and parse_financial_number(w.text).is_valid
        and parse_financial_number(w.text).value is not None
        for w in val_words
    )

    # An empty line or line with NO name, NO units, and NO values cannot become a holding
    if not has_name and not has_units and not has_vals:
        return False

    id_cand, _ = _extract_identifier_from_words(assigned.get("SECURITY_ID", []), line_text=l.text)
    if id_cand is not None:
        return True

    return bool(has_units and has_vals)


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
        # Digital vector pages have precise typography (pitch ~8pt, metadata separation ~4pt); use 3.0pt tolerance.
        # Scanned OCR pages have bounding box tilt and jitter across wide landscape tables; use 5.5pt tolerance.
        _, page_needs_ocr = detect_page_type(page)
        hld_y_tol = 5.5 if page_needs_ocr else 3.0
        _, lines = extract_visual_words_and_lines(page, y_tolerance=hld_y_tol)

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
            if any(f in lu for f in ["ORIGINAL DENOMINATION AND REPORTING", "BLANK FIELDS ARE INTENTIONALLY", "REPORT EDITED ON", "SYNTHETIC TEST ONLY", "UNION BANCAIRE PRIVEE", "EXPLICIT ZERO", "INTENTIONALLY BLANK", "PIXELS ONLY"]):
                continue
            content_lines.append(l)

        # Check if any pre-header line on this page specifies a category banner (e.g. 'STRUCTURED PRODUCTS - SCANNED CONTINUATION PAGE')
        for l in lines:
            if 50.0 < l.y < data_start_y:
                cat_match = is_category_header(
                    l.text.strip(),
                    dynamic_categories,
                    line_x0=l.words[0].x0 if l.words else None,
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

        # If a narrow trailing '%' header was dropped (e.g. by OCR at the right page margin) while body rows clearly
        # contain a rightmost percentage column to the right of REPORTING_VALUE / MARKET_VALUE, infer PERCENTAGE bounds geometrically.
        if (
            "PERCENTAGE" not in col_map.columns
            and col_map.ordered_columns
            and col_map.ordered_columns[-1].semantic_key in ("REPORTING_VALUE", "MARKET_VALUE")
        ):
            last_col = col_map.ordered_columns[-1]
            pct_candidates: List[ExtractedWord] = []
            for cl in content_lines:
                line_pct_toks = []
                for w in cl.words:
                    if w.x0 >= last_col.hx1 + 12.0:
                        wt = w.text.strip()
                        if is_valid_iso_currency(wt) or re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", wt):
                            continue
                        fn = parse_financial_number(wt)
                        if fn.is_valid and fn.value is not None and Decimal("-100") <= fn.value <= Decimal("100"):
                            line_pct_toks.append(w)
                if len(line_pct_toks) == 1:
                    pct_candidates.append(line_pct_toks[0])
            if len(pct_candidates) >= 2:
                pct_col = HeaderColumn(
                    "(%)",
                    "PERCENTAGE",
                    round(min(w.x0 for w in pct_candidates), 2),
                    round(max(w.x1 for w in pct_candidates), 2),
                )
                col_map.ordered_columns.append(pct_col)
                col_map.columns["PERCENTAGE"] = pct_col
                _compute_column_boundaries(col_map.ordered_columns, page_width, section_type="HOLDINGS")
                page_header_maps[-1]["columns"] = [
                    {"key": c.semantic_key, "header": c.raw_label, "x_min": round(c.x_min, 1), "x_max": round(c.x_max, 1)}
                    for c in col_map.ordered_columns
                ]

        def _is_primary_line(l: VisualLine) -> bool:
            return is_primary_holding_line(l, col_map)

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

            # Multi-line Case B: 1 or more description lines followed by a financial anchor
            is_case_b = False
            desc_lines = []
            fin_line_cand = None
            fin_idx = -1
            if is_description_only_line(line, col_map):
                desc_lines = [line]
                scan_k = idx + 1
                while scan_k < len(content_lines) and is_description_only_line(content_lines[scan_k], col_map) and (content_lines[scan_k].y - content_lines[scan_k - 1].y <= 18.0):
                    desc_lines.append(content_lines[scan_k])
                    scan_k += 1
                if scan_k < len(content_lines) and has_financial_anchor(content_lines[scan_k], col_map) and (content_lines[scan_k].y - desc_lines[-1].y <= 24.0):
                    assigned_fin, _ = assign_words_to_columns(content_lines[scan_k].words, col_map)
                    fin_name_words = [
                        w.text.strip().upper() for w in assigned_fin.get("SECURITY_NAME", [])
                        if w.text.strip().upper() not in {"ESG", "/", "|", "-", "—"}
                        and not re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip())
                        and not re.match(r"^[A-D]{1,3}[\+\-]?(?:/[A-D]{1,3}[\+\-]?)?$", w.text.strip().upper())
                    ]
                    if len(fin_name_words) < 2 and (not fin_name_words or len(fin_name_words[0]) < 6):
                        is_case_b = True
                        fin_line_cand = content_lines[scan_k]
                        fin_idx = scan_k

            if is_case_b and fin_line_cand is not None:
                holding_lines = desc_lines + [fin_line_cand]
                next_idx = fin_idx + 1
                while next_idx < len(content_lines):
                    cand = content_lines[next_idx]
                    if is_category_header(
                        cand.text.strip(),
                        dynamic_categories,
                        line_x0=cand.words[0].x0 if cand.words else None,
                        col_map=col_map
                    ):
                        break
                    if _is_primary_line(cand):
                        break
                    # If cand is an introductory description line for the next financial anchor, break
                    if is_description_only_line(cand, col_map):
                        chk_k = next_idx + 1
                        while chk_k < len(content_lines) and is_description_only_line(content_lines[chk_k], col_map) and (content_lines[chk_k].y - content_lines[chk_k - 1].y <= 18.0):
                            chk_k += 1
                        if chk_k < len(content_lines) and (content_lines[chk_k].y - content_lines[chk_k - 1].y <= 24.0):
                            if is_case_b_pair(content_lines[chk_k - 1], content_lines[chk_k], col_map):
                                break
                    holding_lines.append(cand)
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

            elif _is_primary_line(line):
                # Case A: Standard row with financial anchor on line 1
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
                    # If next_l is an introductory description line for the next financial anchor, break
                    if is_description_only_line(next_l, col_map):
                        chk_k = next_idx + 1
                        while chk_k < len(content_lines) and is_description_only_line(content_lines[chk_k], col_map) and (content_lines[chk_k].y - content_lines[chk_k - 1].y <= 18.0):
                            chk_k += 1
                        if chk_k < len(content_lines) and (content_lines[chk_k].y - content_lines[chk_k - 1].y <= 24.0):
                            if is_case_b_pair(content_lines[chk_k - 1], content_lines[chk_k], col_map):
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
    fin_line = next((l for l in lines if has_financial_anchor(l, col_map)), lines[0])
    assigned, unassigned = assign_words_to_columns(fin_line.words, col_map)

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
    isin_secur_no, id_res = _extract_identifier_from_words(id_words, line_text=fin_line.text)

    # Pre-scan ESG ratings & market price dates across all lines
    previous_esg_rating = None
    current_esg_rating = None
    market_price_date = None

    esg_prev_bounds = col_map.extra_bounds.get("ESG_PREVIOUS")
    esg_curr_bounds = col_map.extra_bounds.get("ESG_CURRENT")

    for l in lines:
        cl_text = l.text.strip()
        cl_upper = cl_text.upper()
        m_esg_inline = re.search(
            r"\bESG[:\s]+([A-Za-z0-9\+\-]+(?:\s*\([^\)]*\))?)\s*(?:/|\|)\s*([A-Za-z0-9\+\-]+(?:\s*\([^\)]*\))?)\b",
            cl_text,
            re.IGNORECASE
        )
        if m_esg_inline:
            previous_esg_rating = m_esg_inline.group(1).strip()
            current_esg_rating = m_esg_inline.group(2).strip()
        elif "ESG" in cl_upper and "/" in cl_text:
            parts = [p.strip() for p in re.sub(r"\bESG[:\s]*", "", cl_text, flags=re.IGNORECASE).split("/") if p.strip()]
            if len(parts) == 2 and not any(len(p) > 10 for p in parts):
                previous_esg_rating = parts[0]
                current_esg_rating = parts[1]
        elif esg_prev_bounds and esg_curr_bounds and bool(l.words) and all(
            esg_prev_bounds[0] - 15.0 <= w.x0 and w.x1 <= esg_curr_bounds[1] + 15.0
            for w in l.words
        ) and "ESG" not in cl_upper and len(l.words) <= 4:
            prev_cand = [w.text.strip() for w in l.words if w.x0 <= esg_prev_bounds[1] + 5.0]
            curr_cand = [w.text.strip() for w in l.words if w.x0 >= esg_curr_bounds[0] - 5.0]
            if prev_cand:
                previous_esg_rating = " ".join(prev_cand)
            if curr_cand:
                current_esg_rating = " ".join(curr_cand)

        for w in l.words:
            if re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", w.text.strip()) and market_price_date is None:
                market_price_date = w.text.strip()

    # 3. Security Name: gathered across all lines strictly inside SECURITY_NAME column
    watermark_noise = {"SAMPLE", "VALID", "NOT", "DEMO", "ESG"}
    name_parts: List[str] = []

    for l in lines:
        l_assigned, _ = assign_words_to_columns(l.words, col_map)
        l_name_words = []
        for w in l_assigned.get("SECURITY_NAME", []):
            wt = w.text.strip()
            wu = wt.upper()
            if wu in watermark_noise or wt in {"/", "|"} or re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", wt):
                continue
            if previous_esg_rating and current_esg_rating and ("ESG" in l.text.upper()):
                if wu == "ESG" or wu == previous_esg_rating.upper() or wu == current_esg_rating.upper():
                    continue
            l_name_words.append(w)

        # If this line has NO valid identifier, any tokens in SECURITY_ID that are not noise belong to the description!
        l_id_cand, _ = _extract_identifier_from_words(l_assigned.get("SECURITY_ID", []), line_text=l.text)
        if l_id_cand is None and l_assigned.get("SECURITY_ID"):
            for w in l_assigned["SECURITY_ID"]:
                wt = w.text.strip()
                wu = wt.upper()
                if (
                    wu in watermark_noise
                    or wu in {"/", "|"}
                    or is_valid_iso_currency(wu)
                    or _is_credit_rating(wu)
                    or wu.startswith("ESG")
                    or re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", wu)
                ):
                    continue
                l_name_words.append(w)

        if l_name_words:
            l_name_words.sort(key=lambda w: w.x0)
            name_parts.append(" ".join(w.text for w in l_name_words).strip())

    # If any word in id_words lies cleanly to the left of the matched identifier token (e.g. 'Class', 'A', '04'),
    # attach it back to the security name description rather than losing a right-hand description token across the midpoint split.
    if id_res and id_res.raw_identifier:
        matched_raw = id_res.raw_identifier.upper()
        matched_id_words = [w for w in id_words if w.text.strip().upper() == matched_raw or matched_raw in w.text.strip().upper()]
        id_x0 = min(w.x0 for w in matched_id_words) if matched_id_words else None
        extra_name_words = []
        for w in id_words:
            wu = w.text.strip().upper()
            if wu == matched_raw or wu in watermark_noise:
                continue
            if id_x0 is not None and w.x1 <= id_x0 - 8.0 and len(w.text.strip()) <= 12:
                extra_name_words.append(w)
            elif w.x1 <= fin_line.words[-1].x1 and not any(c.isdigit() for c in w.text) and len(w.text) <= 5:
                extra_name_words.append(w)
        if extra_name_words:
            extra_name_words.sort(key=lambda w: w.x0)
            name_parts.append(" ".join(w.text for w in extra_name_words).strip())

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
    price_col_currency = None
    for w in assigned.get("MARKET_PRICE", []):
        raw_p = re.sub(r"^([\d\.'’,\-]+[*t\+#^])['’\".,]+$", r"\1", w.text.strip())
        if re.match(r"^\d{2}\.\d{2}\.\d{2,4}$", raw_p):
            if market_price_date is None:
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

    # 11. Process Continuation Lines for Accrued Interest or Credit Rating
    accrued_interest_local = None
    accrued_interest_usd = None
    accrued_interest_currency = None

    for cl in lines:
        if cl is fin_line:
            continue
        cl_assigned, cl_unassigned = assign_words_to_columns(cl.words, col_map)
        if cl_unassigned:
            unassigned.extend(cl_unassigned)

        # Credit rating on continuation line inside YIELD_RATING column (e.g. 'AA', 'A')
        for w in cl_assigned.get("YIELD_RATING", []):
            raw_t = w.text.strip()
            if _is_credit_rating(raw_t) and rating_val is None:
                rating_val = raw_t.upper()

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
    for fn_noise in ["EXPLICIT ZERO", "INTENTIONALLY BLANK", "PIXELS ONLY"]:
        if fn_noise in full_security_name.upper():
            full_security_name = re.sub(r"\s*" + re.escape(fn_noise) + r".*$", "", full_security_name, flags=re.IGNORECASE).strip()

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
        raw_identifier=id_res.raw_identifier if id_res else None,
        identifier_status=id_res.status if id_res else ("NOT_PRESENT" if isin_secur_no is None else "PASS"),
        identifier_provenance=id_res.provenance if id_res else None,
        identifier_confidence=id_res.confidence if id_res else None,
        header_confidence=col_map.confidence,
        unassigned_tokens=[w.text for w in unassigned if w.text.strip()],
        source_page=page_num,
        bbox=[min_x, min_y, max_x, max_y],
        raw_text="\n".join(cl.text for cl in lines)
    )
