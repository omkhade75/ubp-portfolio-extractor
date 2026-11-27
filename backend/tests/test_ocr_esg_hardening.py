import pytest
from app.extraction.identifier_engine import normalize_security_identifier, IdentifierResult
from app.extraction.summary_parser import parse_portfolio_esg_generic
from app.extraction.word_extractor import VisualLine, ExtractedWord
from app.extraction.table_header_engine import HOLDINGS_SYNONYMS, build_table_column_map

def test_portfolio_esg_generic_splitting():
    # 1. Delimited with parentheses on one side only (Test 02 Page 1)
    prev, curr = parse_portfolio_esg_generic("PORTFOLIO ESG (PREVIOUS / CURRENT) BBB+ / A (AVERAGE)")
    assert prev == "BBB+"
    assert curr == "A (AVERAGE)"

    # 2. Both sides with parentheses / qualifiers
    prev, curr = parse_portfolio_esg_generic("PORTFOLIO ESG RATING: AA (LEADER) / AA (LEADER)")
    assert prev == "AA (LEADER)"
    assert curr == "AA (LEADER)"

    # 3. Numeric ESG score (078 / 078)
    prev, curr = parse_portfolio_esg_generic("PORTFOLIO ESG RATING 078 / 078")
    assert prev == "078"
    assert curr == "078"

    # 4. Standard codes
    prev, curr = parse_portfolio_esg_generic("PORTFOLIO ESG: AA / A")
    assert prev == "AA"
    assert curr == "A"

    # 5. Space-separated qualified
    prev, curr = parse_portfolio_esg_generic("PORTFOLIO ESG RATING AA (LEADER) AA (LEADER)")
    assert prev == "AA (LEADER)"
    assert curr == "AA (LEADER)"

    # 6. Single rating
    prev, curr = parse_portfolio_esg_generic("PORTFOLIO ESG RATING: AA (AVERAGE)")
    assert prev is None
    assert curr == "AA (AVERAGE)"

def test_ocr_identifier_format_and_confusion_handling():
    # Case 1: Exact valid ISIN
    res = normalize_security_identifier("XSSYN0001081")
    assert res.status == "PASS"
    assert res.normalized_identifier == "XSSYN0001081"
    assert res.provenance == "EXACT_MATCH"

    # Case 2: Extra 'O' inserted between alpha prefix and numeric payload (Tesseract artifact)
    res = normalize_security_identifier("XSSYNO0001081")
    assert res.status == "NORMALIZED"
    assert res.normalized_identifier == "XSSYN0001081"
    assert "Extraneous 'O'" in res.provenance

    # Case 3: Extra 'O' in XSSYNO0001090
    res = normalize_security_identifier("XSSYNO0001090")
    assert res.status == "NORMALIZED"
    assert res.normalized_identifier == "XSSYN0001090"

    # Case 4: Windows OCR OOOI -> 0001 substitution
    res = normalize_security_identifier("XSSYNOOOI090")
    assert res.status == "NORMALIZED"
    assert res.normalized_identifier == "XSSYN0001090"
    assert "Suffix letters" in res.provenance

    # Case 5: CUSIP / Hyphenated test code tail confusion (OI -> 01)
    res = normalize_security_identifier("CUSP-TEST-OI")
    assert res.status == "NORMALIZED"
    assert res.normalized_identifier == "CUSP-TEST-01"

    # Case 6: Standard hyphenated codes
    res = normalize_security_identifier("CH-VAL-TEST-42002")
    assert res.status == "PASS"
    assert res.normalized_identifier == "CH-VAL-TEST-42002"

    res = normalize_security_identifier("PB-TEST-PE-0056")
    assert res.status == "PASS"
    assert res.normalized_identifier == "PB-TEST-PE-0056"

    # Case 7: Uncertain identifier preserves raw text and flags REVIEW_REQUIRED
    res = normalize_security_identifier("UNKNOWN_RANDOM_CODE")
    assert res.status == "REVIEW_REQUIRED"
    assert "REVIEW_REQUIRED" in res.normalized_identifier

def _w(text: str, x0: float, y0: float, x1: float, y1: float) -> ExtractedWord:
    return ExtractedWord(
        text=text, x0=x0, y0=y0, x1=x1, y1=y1,
        raw_x0=x0, raw_y0=y0, raw_x1=x1, raw_y1=y1,
        block_no=0, line_no=0, word_no=0, confidence=100.0
    )

def test_esg_line_never_primary_holding():
    from app.extraction.holdings_parser import is_primary_holding_line
    # Build standard table column map
    header_line = VisualLine(
        y=95.0,
        y0=90.0,
        y1=105.0,
        text="UNITS / NOMINAL SECURITY NAME SECURITY NO. YIELD / AVG. COST MARKET PRICE CCY MARKET VALUE VALUE IN USD",
        words=[
            _w("UNITS", 38.0, 95.0, 70.0, 105.0),
            _w("SECURITY", 80.0, 95.0, 130.0, 105.0),
            _w("NAME", 135.0, 95.0, 165.0, 105.0),
            _w("SECURITY", 280.0, 95.0, 330.0, 105.0),
            _w("NO.", 335.0, 95.0, 355.0, 105.0),
            _w("YIELD", 380.0, 95.0, 410.0, 105.0),
            _w("AVG.", 430.0, 95.0, 455.0, 105.0),
            _w("MARKET", 480.0, 95.0, 520.0, 105.0),
            _w("PRICE", 525.0, 95.0, 550.0, 105.0),
            _w("CCY", 570.0, 95.0, 590.0, 105.0),
            _w("MARKET", 610.0, 95.0, 650.0, 105.0),
            _w("VALUE", 655.0, 95.0, 685.0, 105.0),
            _w("VALUE", 710.0, 95.0, 740.0, 105.0),
            _w("IN", 745.0, 95.0, 755.0, 105.0),
            _w("USD", 760.0, 95.0, 780.0, 105.0),
        ]
    )
    col_map = build_table_column_map([header_line], HOLDINGS_SYNONYMS, "HOLDINGS", 842.0)

    # 1. ESG 078 / 078 line
    esg_line = VisualLine(
        y=239.0,
        y0=234.0,
        y1=249.0,
        text="ESG 078 / 078",
        words=[
            _w("ESG", 285.0, 239.0, 305.0, 249.0),
            _w("078", 310.0, 239.0, 330.0, 249.0),
            _w("/", 335.0, 239.0, 340.0, 249.0),
            _w("078", 345.0, 239.0, 365.0, 249.0),
        ]
    )

    # 2. Date-only line
    date_line = VisualLine(
        y=245.0,
        y0=240.0,
        y1=255.0,
        text="30.09.25",
        words=[_w("30.09.25", 520.0, 245.0, 560.0, 255.0)]
    )

    # 3. Valid holding line
    holding_line = VisualLine(
        y=220.0,
        y0=215.0,
        y1=230.0,
        text="500 Cobalt Alpine Property Fund - CHF Class XSSYN0001054 4.80% 99.00 100.00 CHF 35,555.56 40,000.00",
        words=[
            _w("500", 45.0, 220.0, 65.0, 230.0),
            _w("Cobalt", 85.0, 220.0, 120.0, 230.0),
            _w("Alpine", 125.0, 220.0, 160.0, 230.0),
            _w("XSSYN0001054", 290.0, 220.0, 360.0, 230.0),
            _w("4.80%", 385.0, 220.0, 415.0, 230.0),
            _w("99.00", 435.0, 220.0, 465.0, 230.0),
            _w("100.00", 490.0, 220.0, 530.0, 230.0),
            _w("CHF", 575.0, 220.0, 595.0, 230.0),
            _w("35,555.56", 615.0, 220.0, 665.0, 230.0),
            _w("40,000.00", 715.0, 220.0, 765.0, 230.0),
        ]
    )

    # Inline is_primary check using the module's logic
    from app.extraction.holdings_parser import assign_words_to_columns, _extract_identifier_from_words, _is_credit_rating
    from app.processing.number_parser import parse_financial_number
    import re

    def check_primary(l):
        lu = l.text.upper()
        if re.search(r"\bESG\b", lu):
            return False
        if re.match(r"^\s*\d{2}\.\d{2}\.\d{2,4}\s*$", l.text.strip()):
            return False
        if _is_credit_rating(l.text.strip()):
            return False

        assigned, _ = assign_words_to_columns(l.words, col_map)
        name_words = [w.text.strip() for w in assigned.get("SECURITY_NAME", []) if len(w.text.strip()) >= 2]
        has_name = bool(name_words)
        has_units = any(parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None for w in assigned.get("UNITS", []))
        val_words = assigned.get("REPORTING_VALUE", []) + assigned.get("MARKET_VALUE", [])
        has_vals = any(parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None for w in val_words)

        if not has_name and not has_units and not has_vals:
            return False

        id_cand, _ = _extract_identifier_from_words(assigned.get("SECURITY_ID", []), line_text=l.text)
        if id_cand is not None:
            return True
        return bool(has_units and has_vals)

    assert is_primary_holding_line(holding_line, col_map) is True
    assert is_primary_holding_line(esg_line, col_map) is False
    assert is_primary_holding_line(date_line, col_map) is False
