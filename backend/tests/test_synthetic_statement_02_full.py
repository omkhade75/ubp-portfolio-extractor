import os
from decimal import Decimal
import pytest
import openpyxl

from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook
from app.processing.financial_validator import run_financial_validation

SYNTHETIC_TEST_02_PATH = r"D:\UserData\Downloads\Synthetic_Portfolio_Test_02.pdf"

@pytest.fixture(scope="module")
def extraction_result():
    if not os.path.exists(SYNTHETIC_TEST_02_PATH):
        pytest.skip(f"Synthetic Portfolio Test 02 PDF not found: {SYNTHETIC_TEST_02_PATH}")
    return extract_ubp_statement(SYNTHETIC_TEST_02_PATH)

def test_metadata_and_portfolio_overview(extraction_result):
    meta = extraction_result.metadata
    assert meta.portfolio_number == "SYN-5202"
    assert meta.total_pages == 12
    assert meta.valuation_date == "31.10.2025"
    assert meta.report_currency == "USD"

    # Defect 3 verification: Portfolio ESG Previous and Current separated
    assert meta.portfolio_esg_previous == "BBB+"
    assert meta.portfolio_esg_current == "A (AVERAGE)"
    assert meta.portfolio_previous_esg_rating == "BBB+"
    assert meta.portfolio_current_esg_rating == "A (AVERAGE)"
    assert meta.portfolio_esg_source_page == 1
    assert meta.portfolio_esg_provenance == "EXTRACTED"

    perf = extraction_result.portfolio_summary_performance
    assert perf is not None
    assert perf.initial_assets == Decimal("1385000.00")
    assert perf.ending_assets == Decimal("1420000.00")
    assert perf.portfolio_esg_previous == "BBB+"
    assert perf.portfolio_esg_current == "A (AVERAGE)"

def test_currency_breakdown(extraction_result):
    cb_list = extraction_result.currency_breakdown
    assert len(cb_list) > 0
    cb_map = {item.asset_class: item for item in cb_list}
    assert "NET ASSETS" in cb_map
    na = cb_map["NET ASSETS"]
    assert na.total_in_thousands == Decimal("1420")
    # 4 distinct currencies
    assert set(na.currencies.keys()) == {"USD", "EUR", "CHF", "HKD"}

def test_all_13_holdings_and_esg_and_ocr(extraction_result):
    holdings = extraction_result.holdings
    # Defect 1 verification: Exactly 13 genuine holdings, NO phantom ESG holding!
    assert len(holdings) == 13

    # Verify no holding has empty or placeholder security name
    for h in holdings:
        assert h.security_name, f"Holding {h.id} has empty security name"
        assert len(h.security_name.strip()) >= 3

    # Verify Holding 8 (Cobalt Alpine Property Fund) has continuation ESG 078 / 078 attached
    h_cobalt = next(h for h in holdings if "Cobalt" in h.security_name)
    assert h_cobalt.isin_secur_no == "XSSYN0001054"
    assert h_cobalt.previous_esg_rating == "078"
    assert h_cobalt.current_esg_rating == "078"

    # Verify Holding 6 (Silver Fern) has continuation ESG A / AA attached
    h_silver = next(h for h in holdings if "Silver Fern" in h.security_name)
    assert h_silver.isin_secur_no == "XSSYN0001045"
    assert h_silver.previous_esg_rating == "A"
    assert h_silver.current_esg_rating == "AA"

    # Defect 2 verification: Image-only Page 5 OCR security identifiers
    h_p5 = [h for h in holdings if h.source_page == 5]
    assert len(h_p5) == 3

    h_juniper = next(h for h in h_p5 if "Juniper" in h.security_name)
    assert h_juniper.isin_secur_no == "CUSP-TEST-01"

    h_callable = next(h for h in h_p5 if "Callable Note" in h.security_name)
    assert h_callable.isin_secur_no == "XSSYN0001081"
    assert "O" not in h_callable.isin_secur_no[5:]  # Numeric block has no extra letter O

    h_equity_linked = next(h for h in h_p5 if "Equity-Linked" in h.security_name)
    assert h_equity_linked.isin_secur_no == "XSSYN0001090"
    assert "O" not in h_equity_linked.isin_secur_no[5:]  # Numeric block has no letters

def test_accounts_loans_and_exchange_rates(extraction_result):
    # 3 current accounts
    assert len(extraction_result.current_accounts) == 3
    acc_currs = {a.currency for a in extraction_result.current_accounts}
    assert acc_currs == {"USD", "EUR", "CHF"}

    # 2 loans
    assert len(extraction_result.loans) == 2
    for l in extraction_result.loans:
        assert l.amount is not None or l.usd_equivalent is not None

    # 3 exchange rates
    assert len(extraction_result.exchange_rates) == 3

def test_performance_tables(extraction_result):
    assert len(extraction_result.monthly_performance) == 14
    assert len(extraction_result.annual_performance) == 7

def test_financial_validation_integrity(extraction_result):
    v_checks = run_financial_validation(extraction_result)
    assert len(v_checks) > 0
    fail_checks = [c for c in v_checks if c.level == "FAIL"]
    assert len(fail_checks) == 0, f"Unexpected validation failures: {[c.message for c in fail_checks]}"

def test_excel_workbook_generation(tmp_path, extraction_result):
    out_xlsx = generate_ubp_excel_workbook(extraction_result, str(tmp_path))
    assert os.path.exists(out_xlsx)

    wb = openpyxl.load_workbook(out_xlsx)
    # Check sheet count and required sheets
    expected_sheets = [
        "Portfolio_Overview", "Asset_Allocation", "Currency_Breakdown",
        "Holdings", "Transactions", "Current_Accounts", "Loans",
        "Net_Assets_Summary", "Exchange_Rates", "Monthly_Performance",
        "Annual_Performance", "Comments", "Counts", "Validation",
        "Unmapped_Content", "Raw_Page_Text"
    ]
    for s in expected_sheets:
        assert s in wb.sheetnames, f"Missing sheet: {s}"

    # Holdings sheet verification
    ws_h = wb["Holdings"]
    # 1 header + 13 holdings = 14 rows
    assert ws_h.max_row == 14

    # Portfolio Overview sheet verification
    ws_o = wb["Portfolio_Overview"]
    overview_text_cells = [ws_o.cell(r, 1).value for r in range(1, ws_o.max_row + 1)]
    assert "PORTFOLIO ESG RATING (PREVIOUS - CURRENT)" in overview_text_cells
