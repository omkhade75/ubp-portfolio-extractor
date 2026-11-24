import pytest
from decimal import Decimal
from app.extraction.table_reconstructor import extract_ubp_statement
from app.config import SAMPLE_PDFS_DIR

@pytest.fixture(scope="module")
def oct2025_result():
    f = str(SAMPLE_PDFS_DIR / "5_UBP_1002591_Oct2025.pdf")
    return extract_ubp_statement(f)

@pytest.fixture(scope="module")
def jul2025_result():
    f = str(SAMPLE_PDFS_DIR / "4_UBP_1002591_Jul2025.pdf")
    return extract_ubp_statement(f)

def test_multiline_continuation_preservation(oct2025_result):
    res = oct2025_result
    assert len(res.holdings) == 9
    
    # Verify holding 3 continuation
    h3 = res.holdings[2]
    assert h3.isin_secur_no == "IE00BD9PL588"
    assert "PRIVATE EQUITY -SICAR- FUND II SHS EUR" in h3.security_name
    
    # Verify holding 4 continuation
    h4 = res.holdings[3]
    assert h4.isin_secur_no == "XD0487338556"
    assert "PRIVATE EQUITY FUND LIMITED SHS -A INVESTOR-" in h4.security_name

    # Verify holding 5 continuation
    h5 = res.holdings[4]
    assert h5.isin_secur_no == "IE00BMY47228"
    assert "PRIVATE EQUITY FUND FUND III SHS USD" in h5.security_name

    # Verify holding 6 continuation
    h6 = res.holdings[5]
    assert h6.isin_secur_no == "IE00BMY47228"
    assert "PRIVATE EQUITY -SICAR- FUND III SHS USD -IN UNIT" in h6.security_name

def test_market_price_dates_and_markers(oct2025_result):
    res = oct2025_result
    
    h3 = res.holdings[2]
    assert h3.market_price == Decimal("74.58")
    assert h3.price_marker == "*"
    assert h3.market_price_date == "30.06.25"
    
    h4 = res.holdings[3]
    assert h4.market_price == Decimal("0.89678")
    assert h4.price_marker == "t"
    assert h4.market_price_date == "30.07.25"

    h6 = res.holdings[5]
    assert h6.market_price == Decimal("116.35")
    assert h6.price_marker == "*"
    assert h6.market_price_date == "30.06.25"

    h7 = res.holdings[6]
    assert h7.market_price == Decimal("34.71")
    assert h7.price_marker == "*"
    assert h7.market_price_date == "29.08.25"

def test_esg_field_extraction_holdings_and_portfolio(oct2025_result):
    res = oct2025_result
    
    # Portfolio level overview ESG (both naming conventions)
    assert res.metadata.portfolio_esg_previous == "AA (LEADER)"
    assert res.metadata.portfolio_esg_current == "AA (LEADER)"
    assert res.metadata.portfolio_esg_source_page == 1
    assert res.metadata.portfolio_previous_esg_rating == "AA (LEADER)"
    assert res.metadata.portfolio_current_esg_rating == "AA (LEADER)"
    assert res.portfolio_summary_performance.portfolio_esg_previous == "AA (LEADER)"
    assert res.portfolio_summary_performance.portfolio_esg_current == "AA (LEADER)"
    assert res.portfolio_summary_performance.portfolio_esg_source_page == 1
    assert res.portfolio_summary_performance.portfolio_previous_esg_rating == "AA (LEADER)"
    assert res.portfolio_summary_performance.portfolio_current_esg_rating == "AA (LEADER)"
    
    # Holdings level ESG
    h3 = res.holdings[2]
    assert h3.previous_esg_rating == "AA"
    assert h3.current_esg_rating == "AA"

    h5 = res.holdings[4]
    assert h5.previous_esg_rating == "078"
    assert h5.current_esg_rating == "078"

    h6 = res.holdings[5]
    assert h6.previous_esg_rating == "AA"
    assert h6.current_esg_rating == "AA"

def test_missing_vs_zero_values_preservation(oct2025_result):
    res = oct2025_result
    
    # Explicit source zero: HLD-005 printed 0.00
    h5 = res.holdings[4]
    assert h5.market_price == Decimal("0.00")
    assert h5.total_market_value == Decimal("0.00")
    
    # Unprinted / missing optional fields preserved as None
    h1 = res.holdings[0]
    assert h1.yield_val is None
    assert h1.price_marker is None
    assert h1.market_price_date is None
    assert h1.previous_esg_rating is None
    assert h1.current_esg_rating is None

def test_cross_section_reconciliation_check(oct2025_result):
    res = oct2025_result
    checks = res.validation_checks
    
    cross_check = next((c for c in checks if c.category == "Cross-Section Reconciliation"), None)
    assert cross_check is not None
    assert cross_check.name == "Portfolio Flow vs Performance Flow"
    assert cross_check.details["reconciliation_status"] == "SOURCE_DISCREPANCY"
    assert "SOURCE_DISCREPANCY" in cross_check.message
    assert "43956.06" in cross_check.details["page1_portfolio_flow"]
    assert "44056" in cross_check.details["monthly_performance_flow"]

def test_generic_portfolio_esg_parsing_variations():
    from app.extraction.summary_parser import parse_portfolio_esg_generic
    
    # Standard ratings with category qualifiers
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS - CURRENT) AA (LEADER) AA (LEADER)")
    assert p == "AA (LEADER)"
    assert c == "AA (LEADER)"

    # Different rating categories (e.g. Synthetic 01 OCR)
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS CURRENT) AA (LEADER) M (LEADER)")
    assert p == "AA (LEADER)"
    assert c == "M (LEADER)"

    # Synthetic 02 with right-side performance text bleeding
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS - CURRENT) A (AVERAGE) A (AVERAGE) PERFORMANCE TWR (USD) 2.30%")
    assert p == "A (AVERAGE)"
    assert c == "A (AVERAGE)"

    # Rating variation with bullet separator
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS • CURRENT) AAA (LEADER) AA+ (LEADER)")
    assert p == "AAA (LEADER)"
    assert c == "AA+ (LEADER)"

    # Laggard and Average categories
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS - CURRENT) B (LAGGARD) CCC (LAGGARD)")
    assert p == "B (LAGGARD)"
    assert c == "CCC (LAGGARD)"

    # Plain codes without parenthetical categories
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS - CURRENT) AA AA")
    assert p == "AA"
    assert c == "AA"

    # Numeric ratings
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS - CURRENT) 078 085")
    assert p == "078"
    assert c == "085"

    # Missing / unprinted rating
    p, c = parse_portfolio_esg_generic("PORTFOLIO ESG RATING (PREVIOUS - CURRENT)")
    assert p is None
    assert c is None

    # Line without ESG rating
    p, c = parse_portfolio_esg_generic("ASSET ALLOCATION IN USD")
    assert p is None
    assert c is None

def test_missing_portfolio_esg_preservation():
    # Statement 1 (1002590) has no portfolio ESG rating printed on Page 1
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    assert res.metadata.portfolio_esg_previous is None
    assert res.metadata.portfolio_esg_current is None
    assert res.metadata.portfolio_esg_source_page is None

    # Check validation check for missing portfolio ESG
    esg_check = next((c for c in res.validation_checks if c.name == "Portfolio ESG Rating"), None)
    assert esg_check is not None
    assert esg_check.level == "PASS"
    assert "not printed in Overview" in esg_check.message

def test_portfolio_overview_excel_esg_section(oct2025_result, tmp_path):
    from app.excel.workbook_generator import generate_ubp_excel_workbook
    import openpyxl

    out_xlsx = str(tmp_path / "test_overview_esg.xlsx")
    generate_ubp_excel_workbook(oct2025_result, out_xlsx)

    wb = openpyxl.load_workbook(out_xlsx)
    assert "Portfolio_Overview" in wb.sheetnames
    ws = wb["Portfolio_Overview"]

    found_prev = False
    found_curr = False
    found_section = False
    for row in ws.iter_rows(values_only=True):
        if row and row[0] == "PORTFOLIO ESG RATING (PREVIOUS - CURRENT)":
            found_section = True
        if row and row[0] == "Portfolio_ESG_Previous":
            found_prev = True
            assert row[1] == "AA (LEADER)"
            assert row[2] == 1
        if row and row[0] == "Portfolio_ESG_Current":
            found_curr = True
            assert row[1] == "AA (LEADER)"
            assert row[2] == 1

    assert found_section, "Structured PORTFOLIO ESG RATING section not found in Portfolio_Overview"
    assert found_prev, "Portfolio_ESG_Previous row not found in Portfolio_Overview"
    assert found_curr, "Portfolio_ESG_Current row not found in Portfolio_Overview"
