import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Sequence

from app.extraction.word_extractor import ExtractedWord, VisualLine

# Strictly real ISO 4217 currency codes so 3-letter non-currency tokens (e.g. "AMT", "NET", "PCT") are never mistaken for currencies.
ISO_4217_CURRENCIES = {
    "USD", "EUR", "GBP", "CHF", "JPY", "HKD", "SGD", "AUD", "CAD", "NZD",
    "CNY", "CNH", "SEK", "NOK", "DKK", "ZAR", "BRL", "INR", "KRW", "MXN",
    "AED", "SAR", "TWD", "THB", "MYR", "IDR", "PHP", "PLN", "CZK", "HUF",
    "TRY", "ILS", "RUB", "QAR", "KWD", "BHD", "OMR", "KZT", "VND", "COP",
    "CLP", "PEN", "ARS", "EGP", "NGN", "KES", "ISK", "RON", "BGN", "HRK"
}


def is_valid_iso_currency(token: str) -> bool:
    """Returns True only for genuine ISO 4217 currency codes."""
    clean = re.sub(r"[^A-Z]", "", token.strip().upper())
    return clean in ISO_4217_CURRENCIES


# Configurable synonym dictionaries for semantic header mapping.
# Ordered by specificity when matching.
HOLDINGS_SYNONYMS: Dict[str, List[str]] = {
    "UNITS": ["UNITS/NOMINAL", "UNITS / NOMINAL", "POSITION / NOMINAL", "POSITION/NOMINAL", "POSITION SIZE", "POSITION", "NOMINAL AMOUNT", "NOMINAL", "UNITS", "QUANTITY", "QTY"],
    "SECURITY_NAME": ["SECURITY NAME", "INSTRUMENT DESCRIPTION", "ASSET DESCRIPTION", "SECURITY DESCRIPTION", "INSTRUMENT NAME", "INVESTMENT NAME", "DESCRIPTION", "DENOMINATION"],
    "SECURITY_ID": ["SECURITY NO.", "SECURITY NO", "SECURITY NUMBER", "SECUR. NO.", "SECUR NO", "REFERENCE CODE", "SECURITY IDENTIFIER", "INSTRUMENT CODE", "REFERENCE", "REF CODE", "ISIN", "IDENTIFIER", "VALOREN"],
    "YIELD_RATING": ["DISTRIBUTION / YIELD", "DISTRIBUTION/YIELD", "YIELD / RATING", "YIELD/RATING", "CURRENT YIELD", "DISTRIBUTION YIELD", "INCOME YIELD", "YIELD", "/AV.PU.PRI"],
    "AVERAGE_COST": ["NET AVERAGE COST", "AVERAGE COST", "AVG. COST", "AVG COST", "COST PRICE", "ACQUISITION PRICE", "PURCHASE PRICE"],
    "MARKET_PRICE": ["MARKET PRICE", "CLOSING PRICE", "CURRENT PRICE", "LAST PRICE", "VALUATION PRICE", "CLOSING"],
    "MARKET_CURRENCY": ["DENOM. CCY", "DENOM CCY", "DENOMINATION CCY", "PRICE CURRENCY", "INSTRUMENT CURRENCY", "CURRENCY", "CCY", "CURR", "DENOM"],
    "MARKET_VALUE": ["TOTAL MARKET VALUE", "VALUATION AMOUNT", "TOTAL VALUATION", "MARKET VALUE", "ACCRUED INTEREST"],
    "REPORTING_VALUE": ["MARKET VALUE IN REPORTING CURRENCY", "VALUE IN REPORTING CURRENCY", "MARKET VALUE IN USD", "REPORTING VALUE", "USD EQUIVALENT", "VALUE IN USD", "REPORTING EQUIVALENT"],
    "PERCENTAGE": ["PERCENTAGE OF ASSETS", "% OF PORTFOLIO", "% PORTFOLIO", "PORTFOLIO %", "ALLOCATION %", "% ASSETS", "%"],
}

ACCOUNTS_SYNONYMS: Dict[str, List[str]] = {
    "CURRENCY": ["CURRENCY", "CCY", "CURR"],
    "BALANCE": ["ORIGINAL BALANCE", "BALANCE", "AMOUNT", "PRINCIPAL"],
    "ACCOUNT_DESCRIPTION": ["ACCOUNT DESCRIPTION", "ACCOUNT NAME", "DESCRIPTION", "DENOMINATION"],
    "MATURITY": ["MATURITY DATE", "MATURITY"],
    "INTEREST_RATE": ["INTEREST RATE", "RATE/PURCHASE PRICE", "RATE / PURCHASE PRICE", "RATE/"],
    "MARKET_PRICE": ["MARKET PRICE", "PURCHASE PRICE"],
    "MARKET_VALUE": ["TOTAL MARKET VALUE", "MARKET VALUE"],
    "REPORTING_VALUE": ["REPORTING VALUE (USD)", "REPORTING VALUE", "VALUE IN USD", "USD EQUIVALENT"],
    "PERCENTAGE": ["% ASSETS", "PERCENTAGE OF ASSETS", "ALLOCATION %", "%"],
}

LOANS_SYNONYMS: Dict[str, List[str]] = {
    "CURRENCY": ["CURRENCY", "CCY", "CURR"],
    "PRINCIPAL": ["PRINCIPAL", "OUTSTANDING BALANCE", "ORIGINAL AMOUNT", "AMOUNT", "BALANCE"],
    "LOAN_REFERENCE": ["LOAN REFERENCE", "LOAN DESCRIPTION", "REFERENCE", "DENOMINATION", "DESCRIPTION"],
    "MATURITY": ["MATURITY DATE", "MATURITY", "DUE DATE"],
    "INTEREST_RATE": ["INTEREST RATE", "RATE/PURCHASE PRICE", "RATE/", "RATE", "RATE/ PURCHASE PRICE"],
    "MARKET_PRICE": ["MARKET PRICE"],
    "MARKET_VALUE": ["TOTAL MARKET VALUE", "MARKET VALUE"],
    "REPORTING_VALUE": ["OUTSTANDING (USD)", "OUTSTANDING", "REPORTING VALUE (USD)", "REPORTING VALUE", "VALUE IN USD", "USD EQUIVALENT"],
    "PERCENTAGE": ["% ASSETS", "PERCENTAGE", "%"],
}

PERFORMANCE_SYNONYMS: Dict[str, List[str]] = {
    "PERIOD": ["PERIOD"],
    "PERFORMANCE_PCT": ["PERFORMANCE (END-OF-PER)", "PERFORMANCE"],
    "CUMULATIVE_PCT": ["CUMULATIVE PERFORMANCE", "CUMULATIVE", "(GLOBAL)"],
    "END_OF_PERIOD_ASSETS": ["END-OF-PER. ASSETS", "END-OF-PER.", "END OF PERIOD ASSETS"],
    "DEPOSITS_WITHDRAWALS": ["PERIOD'S DEPOSITS AND WITHDRAWALS", "DEPOSITS / WITHDRAWALS", "DEPOSITS AND WITHDRAWALS", "DEPOSITS"],
    "CHANGE_IN_ASSETS": ["CHANGE IN TOTAL ASSETS", "CHANGE IN ASSETS"],
    "NET_INCOME": ["NET INCOME"],
    "RETURN_ON_NI_PCT": ["RETURN ON N.I.", "RETURN ON NET INCOME"],
}


@dataclass
class HeaderColumn:
    """Represents a reconstructed physical & semantic column header on a page."""
    raw_label: str
    semantic_key: str
    hx0: float
    hx1: float
    x_min: float = 0.0
    x_max: float = 0.0
    confidence: str = "HIGH"


@dataclass
class TableColumnMap:
    """Dynamic per-table horizontal column layout and confidence assessment."""
    section_type: str
    columns: Dict[str, HeaderColumn] = field(default_factory=dict)
    ordered_columns: List[HeaderColumn] = field(default_factory=list)
    confidence: str = "HIGH"
    header_y_min: Optional[float] = None
    header_y_max: Optional[float] = None
    unrecognized_headers: List[str] = field(default_factory=list)
    extra_bounds: Dict[str, Tuple[float, float]] = field(default_factory=dict)


def _group_line_words_into_phrases(
    words: List[ExtractedWord],
    max_gap: float = 8.5
) -> List[Tuple[str, float, float]]:
    """Groups closely spaced words on a single visual header line into phrase spans (text, x0, x1)."""
    if not words:
        return []
    sorted_w = sorted(words, key=lambda w: w.x0)
    phrases: List[Tuple[str, float, float]] = []
    cur_words = [sorted_w[0]]

    for w in sorted_w[1:]:
        gap = w.x0 - cur_words[-1].x1
        # Keep tightly joined header text together unless separated by clear column whitespace
        if gap <= max_gap:
            cur_words.append(w)
        else:
            phrases.append((
                " ".join(cw.text for cw in cur_words).strip(),
                cur_words[0].x0,
                cur_words[-1].x1
            ))
            cur_words = [w]

    if cur_words:
        phrases.append((
            " ".join(cw.text for cw in cur_words).strip(),
            cur_words[0].x0,
            cur_words[-1].x1
        ))
    return phrases


def _normalize_header_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.upper().replace("’", "'")).strip()


def match_semantic_field(
    phrase: str,
    synonyms: Dict[str, List[str]],
    allow_dynamic_reporting_ccy: bool = True
) -> Optional[str]:
    """
    Matches a multi-line or single-line header phrase to a canonical semantic column key.
    Uses longest-synonym-first precedence to prevent substring ambiguity
    (e.g. 'SECURITY NO.' vs 'SECURITY NAME', 'VALUE IN USD' vs 'MARKET VALUE').
    """
    norm = _normalize_header_text(phrase)
    if not norm:
        return None

    # Special pattern: VALUE IN <CCY> or REPORTING VALUE (<CCY>)
    if allow_dynamic_reporting_ccy:
        if re.match(r"^(?:VALUE\s+IN|REPORTING\s+VALUE(?:\s*\(?[A-Z]{3}\)?)?)\s*(?:USD|EUR|CHF|GBP|HKD|SGD)?$", norm):
            if "REPORTING_VALUE" in synonyms:
                return "REPORTING_VALUE"
        if re.match(r"^OUTSTANDING\s*(?:\([A-Z]{3}\))?$", norm) and "REPORTING_VALUE" in synonyms:
            return "REPORTING_VALUE"

    # Build flat list (semantic_key, synonym) sorted longest-first
    candidates: List[Tuple[str, str]] = []
    for skey, syns in synonyms.items():
        for syn in syns:
            candidates.append((skey, syn.upper()))
    candidates.sort(key=lambda pair: len(pair[1]), reverse=True)

    for skey, syn in candidates:
        if norm == syn:
            return skey

    for skey, syn in candidates:
        if len(syn) >= 3 and syn in norm:
            # Avoid 'VALUE' matching 'MARKET VALUE' when 'MARKET VALUE' wasn't checked? Sorted longest-first guarantees 'MARKET VALUE' wins first.
            # Avoid 'CURRENCY' or 'PRICE' stealing 'REPORTING VALUE' or 'MARKET PRICE'
            return skey

    # Fallback: split composite stacked phrases (e.g. 'SECUR. NO. DURATION RATING')
    for skey, syn in candidates:
        if syn in norm.replace(".", "") or syn.replace(".", "") in norm.replace(".", ""):
            return skey

    return None


def _compute_column_boundaries(
    ordered: List[HeaderColumn],
    page_width: float,
    right_aligned_keys: Optional[set] = None,
    section_type: str = "HOLDINGS",
) -> None:
    """
    Computes non-overlapping [x_min, x_max) intervals for each ordered HeaderColumn.
    Right-aligned numeric columns (e.g., AVG. COST, MARKET PRICE, MARKET VALUE, VALUE IN USD, %)
    often extend visually right of their left-aligned header text up to the left edge of the next header.
    """
    if not ordered:
        return

    n = len(ordered)
    for i, col in enumerate(ordered):
        if i == 0:
            col.x_min = 0.0
        else:
            prev = ordered[i - 1]
            if section_type == "PERFORMANCE":
                # Performance columns have values aligned inside [col.hx0, next_col.hx0);
                # shifting x_min too far left risks capturing right-aligned single digits (e.g. '0') from the prior column.
                col.x_min = max(prev.hx1 + 2.0, col.hx0 - 3.0)
            # Column starts slightly left of its header x0, but strictly after previous header's x1 (or safe split)
            elif col.semantic_key == "SECURITY_NAME" and prev.semantic_key == "UNITS":
                # Ensure description words (which start immediately after units column) belong to SECURITY_NAME
                col.x_min = prev.hx1 + 4.0
            elif col.semantic_key == "SECURITY_ID":
                # Generically split wide gap between description and identifier so IDs are not swallowed by description
                col.x_min = min(max(prev.hx1 + 4.0, col.hx0 - 45.0), (prev.hx1 + col.hx0) / 2.0)
            elif col.semantic_key == "YIELD_RATING":
                # Generically split between identifier column and yield column
                col.x_min = min(max(prev.hx1 + 4.0, col.hx0 - 35.0), (prev.hx1 + col.hx0) / 2.0)
            elif col.semantic_key == "AVERAGE_COST":
                # Generically split between yield and cost columns
                col.x_min = min(max(prev.hx1 + 4.0, col.hx0 - 25.0), (prev.hx1 + col.hx0) / 2.0)
            elif col.semantic_key in ("BALANCE", "PRINCIPAL") and prev.semantic_key == "CURRENCY":
                col.x_min = prev.hx1 + 4.0
            elif col.semantic_key in ("ACCOUNT_DESCRIPTION", "LOAN_REFERENCE") and prev.semantic_key in ("BALANCE", "PRINCIPAL"):
                col.x_min = min(max(prev.hx1 + 4.0, col.hx0 - 30.0), (prev.hx1 + col.hx0) / 2.0)
            elif col.semantic_key == "PERCENTAGE":
                # Keep tight separation between Reporting Value right edge and % Assets
                col.x_min = max(prev.hx1 + 8.0, col.hx0 - 16.0)
            elif col.semantic_key == "MARKET_CURRENCY":
                col.x_min = max(prev.hx1 + 3.0, col.hx0 - 8.0)
            else:
                # For numeric / reference / date columns: can begin slightly left of header if header is narrow
                col.x_min = max(prev.hx1 + 3.0, col.hx0 - 15.0)

    # Set x_max of column i equal to x_min of column i+1 for strict zero-overlap partitioning
    for i in range(n - 1):
        ordered[i].x_max = ordered[i + 1].x_min
    ordered[-1].x_max = page_width


def build_table_column_map(
    header_lines: List[VisualLine],
    synonyms: Dict[str, List[str]],
    section_type: str,
    page_width: float
) -> TableColumnMap:
    """
    Reconstructs multi-line headers into merged semantic columns and computes
    exact non-overlapping horizontal bounds for token assignment.
    """
    tmap = TableColumnMap(section_type=section_type)
    if not header_lines:
        tmap.confidence = "REVIEW_REQUIRED"
        return tmap

    tmap.header_y_min = min(l.y0 for l in header_lines)
    tmap.header_y_max = max(l.y1 for l in header_lines)

    # Separate any dedicated ESG sub-header row (e.g. 'ESG: PREVIOUS CURRENT' in UBP holdings)
    main_header_lines: List[VisualLine] = []
    esg_sub_lines: List[VisualLine] = []
    for hl in sorted(header_lines, key=lambda l: l.y):
        up = hl.text.upper()
        if "ESG:" in up or ("PREVIOUS" in up and "CURRENT" in up):
            esg_sub_lines.append(hl)
        else:
            main_header_lines.append(hl)

    if not main_header_lines:
        main_header_lines = header_lines

    # Collect phrases from primary header line and merge vertically overlapping phrases from secondary lines
    raw_clusters: List[Dict] = []
    for line_idx, hl in enumerate(main_header_lines):
        # Use tight gap (8.5pt) for table headers; Performance headers sometimes have wide word spacing within same column? Check!
        max_gap = 7.5 if section_type in ("HOLDINGS", "CURRENCY_BREAKDOWN", "ACCOUNTS", "LOANS") else 9.0
        phrases = _group_line_words_into_phrases(hl.words, max_gap=max_gap)
        for text, x0, x1 in phrases:
            if line_idx == 0:
                raw_clusters.append({"text": text, "x0": x0, "x1": x1})
            else:
                # Try attaching below an overlapping header cluster
                merged = False
                best_idx = -1
                best_dist = 999.0
                for c_idx, c in enumerate(raw_clusters):
                    overlap = min(c["x1"] + 8.0, x1 + 8.0) - max(c["x0"] - 8.0, x0 - 8.0)
                    dist = abs((c["x0"] + c["x1"]) / 2 - (x0 + x1) / 2)
                    if overlap > 0 and dist < best_dist:
                        best_dist = dist
                        best_idx = c_idx
                if best_idx >= 0:
                    c = raw_clusters[best_idx]
                    c["text"] = f"{c['text']} {text}".strip()
                    c["x0"] = min(c["x0"], x0)
                    c["x1"] = max(c["x1"], x1)
                    merged = True
                if not merged:
                    raw_clusters.append({"text": text, "x0": x0, "x1": x1})

    # Map each merged cluster to a semantic key
    raw_clusters.sort(key=lambda c: c["x0"])
    ordered: List[HeaderColumn] = []
    seen_keys = set()

    for c in raw_clusters:
        skey = match_semantic_field(c["text"], synonyms)
        if skey is None:
            tmap.unrecognized_headers.append(c["text"])
            continue
        if skey in seen_keys:
            # Handle duplicate column name edge cases if any (e.g. PERFORMANCE vs PERFORMANCE on Monthly perf header)
            if skey == "PERFORMANCE_PCT" and "CUMULATIVE_PCT" not in seen_keys:
                skey = "CUMULATIVE_PCT"
            elif skey == "MARKET_VALUE" and "REPORTING_VALUE" not in seen_keys:
                skey = "REPORTING_VALUE"
            else:
                # Merge horizontally if split fragment of same logical column
                existing = next((col for col in ordered if col.semantic_key == skey), None)
                if existing and (c["x0"] - existing.hx1) < 35.0:
                    existing.raw_label = f"{existing.raw_label} {c['text']}".strip()
                    existing.hx1 = max(existing.hx1, c["x1"])
                    continue
                else:
                    tmap.unrecognized_headers.append(c["text"])
                    continue

        seen_keys.add(skey)
        ordered.append(HeaderColumn(
            raw_label=c["text"],
            semantic_key=skey,
            hx0=round(c["x0"], 2),
            hx1=round(c["x1"], 2)
        ))

    ordered.sort(key=lambda col: col.hx0)
    _compute_column_boundaries(ordered, page_width, section_type=section_type)

    tmap.ordered_columns = ordered
    tmap.columns = {col.semantic_key: col for col in ordered}

    # Parse UBP-style ESG sub-header bounds if present
    for el in esg_sub_lines:
        for w in el.words:
            wu = w.text.upper()
            if "PREV" in wu:
                tmap.extra_bounds["ESG_PREVIOUS"] = (w.x0 - 15.0, w.x1 + 10.0)
            elif "CURR" in wu:
                tmap.extra_bounds["ESG_CURRENT"] = (w.x0 - 10.0, w.x1 + 15.0)

    if len(ordered) < 3:
        tmap.confidence = "REVIEW_REQUIRED"
    elif tmap.unrecognized_headers and len(ordered) < 4:
        tmap.confidence = "MEDIUM"
    else:
        tmap.confidence = "HIGH"

    return tmap


def assign_words_to_columns(
    words: Sequence[ExtractedWord],
    col_map: TableColumnMap,
    override_bounds: Optional[Dict[str, Tuple[float, float]]] = None
) -> Tuple[Dict[str, List[ExtractedWord]], List[ExtractedWord]]:
    """
    Implements STRICT TOKEN OWNERSHIP:
    Every word is assigned to AT MOST ONE semantic column based on its horizontal bounds.
    Returns (column_to_words_dict, unassigned_words_list).
    """
    assigned: Dict[str, List[ExtractedWord]] = {col.semantic_key: [] for col in col_map.ordered_columns}
    unassigned: List[ExtractedWord] = []
    owned_ids = set()

    bounds_list: List[Tuple[str, float, float]] = [
        (col.semantic_key, col.x_min, col.x_max)
        for col in col_map.ordered_columns
    ]
    if override_bounds:
        # Replace specific bounds while preserving strict ordering
        by_key = {k: (xmin, xmax) for k, xmin, xmax in bounds_list}
        for k, bnd in override_bounds.items():
            by_key[k] = bnd
        bounds_list = [(k, by_key[k][0], by_key[k][1]) for k, _, _ in bounds_list]

    for w in words:
        if id(w) in owned_ids:
            continue
        w_center = (w.x0 + w.x1) / 2.0
        matched_key = None

        # Priority 1: word x0 lies inside column interval [x_min, x_max)
        for key, xmin, xmax in bounds_list:
            if xmin <= w.x0 < xmax:
                matched_key = key
                break

        # Priority 2: word center lies inside column interval (handles slight overhang)
        if matched_key is None:
            for key, xmin, xmax in bounds_list:
                if xmin <= w_center < xmax:
                    matched_key = key
                    break

        if matched_key is not None:
            assigned[matched_key].append(w)
            owned_ids.add(id(w))
        else:
            unassigned.append(w)

    return assigned, unassigned
