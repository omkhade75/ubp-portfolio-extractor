import pytest
import pymupdf
from decimal import Decimal

from app.extraction.word_extractor import ExtractedWord, VisualLine
from app.extraction.table_header_engine import (
    HOLDINGS_SYNONYMS,
    ACCOUNTS_SYNONYMS,
    LOANS_SYNONYMS,
    PERFORMANCE_SYNONYMS,
    is_valid_iso_currency,
    build_table_column_map,
    assign_words_to_columns,
)
from app.extraction.summary_parser import (
    parse_currency_breakdown_page,
    parse_net_assets_summary_page,
    parse_portfolio_esg_generic,
)
from app.extraction.accounts_parser import parse_current_accounts_page
from app.extraction.loans_parser import parse_loans_page


def test_iso_4217_rejects_non_currency_column_modifiers():
    assert is_valid_iso_currency("USD") is True
    assert is_valid_iso_currency("EUR") is True
    assert is_valid_iso_currency("HKD") is True
    assert is_valid_iso_currency("CHF") is True
    assert is_valid_iso_currency("SGD") is True

    # Common 3-letter table modifiers must NEVER be misclassified as currencies
    for non_ccy in ("AMT", "NET", "PCT", "VAL", "NO.", "REF", "MAX", "MIN", "DAY", "TOT"):
        assert is_valid_iso_currency(non_ccy) is False


def _w(text: str, x0: float, y0: float, x1: float, y1: float, block: int = 0, word: int = 0) -> ExtractedWord:
    return ExtractedWord(text, x0, y0, x1, y1, x0, y0, x1, y1, block, 0, word)


def test_dynamic_renamed_holdings_header_and_strict_token_ownership():
    h1 = VisualLine(
        y=95.0,
        y0=90.0,
        y1=100.0,
        text="QTY INSTRUMENT NAME IDENTIFIER CURRENT YIELD AVG COST LAST PRICE CURRENCY VALUATION AMOUNT REPORTING VALUE ALLOCATION %",
        words=[
            _w("QTY", 40.0, 90.0, 58.0, 100.0, 0, 0),
            _w("INSTRUMENT", 110.0, 90.0, 165.0, 100.0, 0, 1),
            _w("NAME", 167.0, 90.0, 192.0, 100.0, 0, 2),
            _w("IDENTIFIER", 300.0, 90.0, 352.0, 100.0, 0, 3),
            _w("CURRENT", 390.0, 90.0, 428.0, 100.0, 0, 4),
            _w("YIELD", 430.0, 90.0, 455.0, 100.0, 0, 5),
            _w("AVG", 475.0, 90.0, 492.0, 100.0, 0, 6),
            _w("COST", 494.0, 90.0, 518.0, 100.0, 0, 7),
            _w("LAST", 535.0, 90.0, 555.0, 100.0, 0, 8),
            _w("PRICE", 557.0, 90.0, 582.0, 100.0, 0, 9),
            _w("CURR", 600.0, 90.0, 622.0, 100.0, 0, 10),
            _w("VALUATION", 640.0, 90.0, 688.0, 100.0, 0, 11),
            _w("AMOUNT", 690.0, 90.0, 725.0, 100.0, 0, 12),
            _w("REPORTING", 740.0, 90.0, 785.0, 100.0, 0, 13),
            _w("VALUE", 745.0, 90.0, 770.0, 100.0, 0, 14),
            _w("%", 805.0, 90.0, 813.0, 100.0, 0, 15),
        ],
    )
    col_map = build_table_column_map([h1], HOLDINGS_SYNONYMS, "HOLDINGS", 842.0)
    assert col_map.confidence == "HIGH"
    expected_keys = {
        "UNITS", "SECURITY_NAME", "SECURITY_ID", "YIELD_RATING",
        "AVERAGE_COST", "MARKET_PRICE", "MARKET_CURRENCY",
        "MARKET_VALUE", "REPORTING_VALUE", "PERCENTAGE"
    }
    assert expected_keys.issubset(set(col_map.columns.keys()))

    # Verify adjacent header boundaries are strictly non-overlapping
    for i in range(len(col_map.ordered_columns) - 1):
        assert col_map.ordered_columns[i].x_max == col_map.ordered_columns[i + 1].x_min

    # Verify narrow left-shifted security ID token goes strictly to SECURITY_ID, never SECURITY_NAME or YIELD_RATING
    row_words = [
        _w("1,500", 42.0, 120.0, 65.0, 130.0, 1, 0),
        _w("Example", 110.0, 120.0, 145.0, 130.0, 1, 1),
        _w("Global", 147.0, 120.0, 175.0, 130.0, 1, 2),
        _w("Note", 177.0, 120.0, 198.0, 130.0, 1, 3),
        _w("XS9990001112", 302.0, 120.0, 355.0, 130.0, 1, 4),
        _w("4.50", 435.0, 120.0, 452.0, 130.0, 1, 5),
        _w("99.10", 495.0, 120.0, 515.0, 130.0, 1, 6),
        _w("101.20", 555.0, 120.0, 580.0, 130.0, 1, 7),
        _w("EUR", 603.0, 120.0, 619.0, 130.0, 1, 8),
        _w("151,800.00", 670.0, 120.0, 718.0, 130.0, 1, 9),
        _w("165,000.00", 745.0, 120.0, 785.0, 130.0, 1, 10),
        _w("12.50", 798.0, 120.0, 815.0, 130.0, 1, 11),
    ]
    assigned, unassigned = assign_words_to_columns(row_words, col_map)
    assert unassigned == []
    assert [w.text for w in assigned["SECURITY_NAME"]] == ["Example", "Global", "Note"]
    assert [w.text for w in assigned["SECURITY_ID"]] == ["XS9990001112"]
    assert [w.text for w in assigned["YIELD_RATING"]] == ["4.50"]
    assert [w.text for w in assigned["MARKET_CURRENCY"]] == ["EUR"]


def test_side_by_side_net_assets_and_exchange_rates_and_non_usd_currency_breakdown(tmp_path):
    pdf_path = str(tmp_path / "generic_layout_test.pdf")
    doc = pymupdf.open()

    # Page 1: Non-USD currency breakdown with 'AMT' modifiers
    p1 = doc.new_page(width=842, height=595)
    p1.insert_text((36, 90), "BREAKDOWN OF NET ASSETS BY CURRENCY (IN THOUSANDS)", fontsize=10)
    p1.insert_text((40, 125), "ASSET CLASS", fontsize=8)
    p1.insert_text((305, 125), "TOTAL", fontsize=8)
    p1.insert_text((360, 125), "%", fontsize=8)
    p1.insert_text((410, 125), "EUR AMT", fontsize=8)
    p1.insert_text((480, 125), "%", fontsize=8)
    p1.insert_text((530, 125), "CHF AMT", fontsize=8)
    p1.insert_text((600, 125), "%", fontsize=8)
    p1.insert_text((40, 150), "BONDS", fontsize=8)
    p1.insert_text((310, 150), "500", fontsize=8)
    p1.insert_text((352, 150), "100.00", fontsize=8)
    p1.insert_text((420, 150), "300", fontsize=8)
    p1.insert_text((472, 150), "60.00", fontsize=8)
    p1.insert_text((540, 150), "200", fontsize=8)
    p1.insert_text((592, 150), "40.00", fontsize=8)

    # Page 2: Two-column side-by-side Net Assets Summary & Exchange Rates + LOAN FACILITIES separation
    p2 = doc.new_page(width=842, height=595)
    p2.insert_text((36, 92), "SUMMARY OF NET ASSETS", fontsize=10)
    p2.insert_text((460, 92), "EXCHANGE RATES USED", fontsize=10)
    p2.insert_text((42, 125), "ASSETS", fontsize=8)
    p2.insert_text((340, 125), "500'000.00", fontsize=8)
    p2.insert_text((470, 125), "1 EUR", fontsize=8)
    p2.insert_text((710, 125), "0.96000000 CHF", fontsize=8)
    p2.insert_text((42, 150), "ACCRUED INTEREST ON SECURITIES", fontsize=8)
    p2.insert_text((360, 150), "0.00", fontsize=8)
    p2.insert_text((42, 175), "NET ACCRUED INT DEP AND LOANS", fontsize=8)
    p2.insert_text((360, 175), "0.00", fontsize=8)
    p2.insert_text((42, 200), "TOTAL ASSETS", fontsize=8)
    p2.insert_text((340, 200), "500'000.00", fontsize=8)
    p2.insert_text((42, 225), "COMMITMENTS", fontsize=8)
    p2.insert_text((360, 225), "0.00", fontsize=8)

    # Page 3: CURRENT ACCOUNTS + LOAN FACILITIES boundary
    p3 = doc.new_page(width=842, height=595)
    p3.insert_text((36, 92), "CURRENT ACCOUNTS", fontsize=10)
    p3.insert_text((40, 125), "CCY", fontsize=8)
    p3.insert_text((150, 125), "BALANCE", fontsize=8)
    p3.insert_text((280, 125), "ACCOUNT DESCRIPTION", fontsize=8)
    p3.insert_text((650, 125), "REPORTING VALUE (USD)", fontsize=8)
    p3.insert_text((40, 150), "USD", fontsize=8)
    p3.insert_text((150, 150), "40,000.00", fontsize=8)
    p3.insert_text((280, 150), "Current Account Number 9901-USD", fontsize=8)
    p3.insert_text((690, 150), "40,000.00", fontsize=8)

    p3.insert_text((36, 225), "LOAN FACILITIES", fontsize=10)
    p3.insert_text((40, 255), "CCY", fontsize=8)
    p3.insert_text((140, 255), "PRINCIPAL", fontsize=8)
    p3.insert_text((260, 255), "LOAN REFERENCE", fontsize=8)
    p3.insert_text((420, 255), "MATURITY", fontsize=8)
    p3.insert_text((520, 255), "INTEREST RATE", fontsize=8)
    p3.insert_text((660, 255), "OUTSTANDING (USD)", fontsize=8)
    p3.insert_text((40, 280), "USD", fontsize=8)
    p3.insert_text((140, 280), "15,000.00-", fontsize=8)
    p3.insert_text((260, 280), "LN-GEN-9901", fontsize=8)
    p3.insert_text((420, 280), "01.09.2027", fontsize=8)
    p3.insert_text((520, 280), "5.25%", fontsize=8)
    p3.insert_text((680, 280), "15,000.00-", fontsize=8)

    doc.save(pdf_path)
    doc.close()

    doc_read = pymupdf.open(pdf_path)
    cb = parse_currency_breakdown_page(doc_read[0], 1)
    assert len(cb) == 1
    assert "AMT" not in cb[0].currencies
    assert set(cb[0].currencies.keys()) == {"EUR", "CHF"}
    assert cb[0].currencies["EUR"].amount_in_thousands == Decimal("300")
    assert cb[0].currencies["CHF"].amount_in_thousands == Decimal("200")

    net_sum, exch = parse_net_assets_summary_page(doc_read[1], 2)
    assert net_sum is not None
    assert net_sum.assets_usd == Decimal("500000.00")
    assert net_sum.assets_pct is None
    assert net_sum.total_assets_usd == Decimal("500000.00")
    assert len(exch) == 1
    assert exch[0].base_currency == "EUR"
    assert exch[0].target_currency == "CHF"
    assert exch[0].rate == Decimal("0.96000000")

    accs, _, _ = parse_current_accounts_page(doc_read[2], 3)
    loans, _, _ = parse_loans_page(doc_read[2], 3)
    assert len(accs) == 1
    assert accs[0].account_number == "9901-USD"
    assert len(loans) == 1
    assert loans[0].loan_reference == "LN-GEN-9901"
    assert loans[0].maturity_date == "01.09.2027"
    assert loans[0].interest_rate == Decimal("5.25")
    assert loans[0].usd_equivalent == Decimal("-15000.00")
    doc_read.close()


def test_portfolio_esg_slash_and_qualifier_variants():
    assert parse_portfolio_esg_generic("PORTFOLIO ESG (PREVIOUS / CURRENT) AA (AVERAGE) / A (AVERAGE)") == (
        "AA (AVERAGE)",
        "A (AVERAGE)",
    )
    assert parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS - CURRENT) AA (LEADER) AA (LEADER)") == (
        "AA (LEADER)",
        "AA (LEADER)",
    )
