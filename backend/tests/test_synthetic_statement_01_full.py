import os
from decimal import Decimal
import openpyxl
import pytest

from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook


def _resolve_synthetic_01_path() -> str:
    for p in (
        r"D:\UserData\Downloads\Synthetic_Portfolio_Test_01.pdf",
        r"D:\UserData\Downloads\Synthetic_Portfolio_Test_01(1).pdf",
    ):
        if os.path.exists(p):
            return p
    return r"D:\UserData\Downloads\Synthetic_Portfolio_Test_01.pdf"


SYNTHETIC_01_PATH = _resolve_synthetic_01_path()


@pytest.fixture(scope="module")
def extraction_result():
    if not os.path.exists(SYNTHETIC_01_PATH):
        pytest.skip(f"Synthetic Portfolio Test 01 PDF not found: {SYNTHETIC_01_PATH}")
    return extract_ubp_statement(SYNTHETIC_01_PATH)


def test_metadata_and_portfolio_overview(extraction_result):
    meta = extraction_result.metadata
    assert meta.total_pages == 11
    assert "SYNTHETIC PRIVATE BANK" in meta.bank_name.upper()
    assert meta.institution_provenance == "EXTRACTED"
    assert meta.portfolio_number == "SYN-4101"
    assert meta.portfolio_identifier_source == "EXTRACTED_FROM_PDF"
    assert meta.client_reference == "CLIENT-TEST-4101"
    assert meta.report_currency == "USD"
    assert meta.valuation_date == "30.06.2025"
    assert meta.report_edited_date == "01.07.2025"
    assert meta.reporting_period == "SINCE 01.01.2025 TO 30.06.2025"
    assert meta.portfolio_esg_previous == "AA (AVERAGE)"
    assert meta.portfolio_esg_current == "A (AVERAGE)"

    perf = extraction_result.portfolio_summary_performance
    assert perf is not None
    assert perf.initial_assets == Decimal("1050000.00")
    assert perf.total_incoming_securities == Decimal("8000.00")
    assert perf.total_outgoing_securities == Decimal("-3000.00")
    assert perf.total_incoming_cash == Decimal("25000.00")
    assert perf.total_outgoing_cash == Decimal("-10000.00")
    assert perf.total_inc_out_cash_sec == Decimal("20000.00")
    assert perf.change_in_total_assets == Decimal("10000.00")
    assert perf.ending_assets == Decimal("1080000.00")
    assert perf.number_of_days == 181
    assert perf.performance_twr_pct == Decimal("2.10")

    alloc = {a.investment_category: (a.value_usd, a.percentage) for a in extraction_result.asset_allocation}
    assert alloc["BONDS / NOTES"] == (Decimal("420000.00"), Decimal("38.89"))
    assert alloc["EQUITIES"] == (Decimal("210000.00"), Decimal("19.44"))
    assert alloc["PRIVATE EQUITY"] == (Decimal("180000.00"), Decimal("16.67"))
    assert alloc["ALTERNATIVES"] == (Decimal("140000.00"), Decimal("12.96"))
    assert alloc["STRUCTURED PRODUCTS"] == (Decimal("90000.00"), Decimal("8.33"))
    assert alloc["CURRENT ACCOUNTS"] == (Decimal("100000.00"), Decimal("9.26"))
    assert alloc["LOANS"] == (Decimal("-60000.00"), Decimal("-5.56"))
    assert alloc["NET ASSETS"] == (Decimal("1080000.00"), Decimal("100.00"))


def test_currency_breakdown_usd_eur_hkd(extraction_result):
    cb_map = {item.asset_class: item for item in extraction_result.currency_breakdown}
    assert len(cb_map) == 8
    for item in extraction_result.currency_breakdown:
        assert "AMT" not in item.currencies

    net = cb_map["NET ASSETS"]
    assert net.total_in_thousands == Decimal("1080")
    assert net.total_percentage == Decimal("100.00")
    assert net.currencies["USD"].amount_in_thousands == Decimal("860")
    assert net.currencies["USD"].percentage == Decimal("79.63")
    assert net.currencies["EUR"].amount_in_thousands == Decimal("130")
    assert net.currencies["EUR"].percentage == Decimal("12.04")
    assert net.currencies["HKD"].amount_in_thousands == Decimal("90")
    assert net.currencies["HKD"].percentage == Decimal("8.33")

    sp = cb_map["STRUCTURED PRODUCTS"]
    assert sp.currencies["HKD"].amount_in_thousands == Decimal("90")
    assert sp.currencies["HKD"].percentage == Decimal("100.00")


def test_all_12_holdings_clean_column_separation(extraction_result):
    holdings = extraction_result.holdings
    assert len(holdings) == 12

    h_by_id = {h.isin_secur_no: h for h in holdings}
    expected_ids = [
        "XSSYN0000019", "XSSYN0000028", "CH-VAL-TEST-31001",
        "XSSYN0000037", "US-TEST-002A", "XSSYN0000046",
        "PB-TEST-PE-0075", "IE00SYN00005", "XSSYN0000064",
        "XSSYN0000073", "CUSIP-TEST-003", "XSSYN0000082",
    ]
    for eid in expected_ids:
        assert eid in h_by_id, f"Missing expected security ID {eid}"
        h = h_by_id[eid]
        assert eid not in h.security_name, f"Security ID {eid} leaked into security_name: {h.security_name}"

    # Verify Harborview credit rating
    h2 = h_by_id["XSSYN0000028"]
    assert h2.security_name == "Harborview Investment Grade Credit Fund - Class A"
    assert h2.yield_val == Decimal("4.10")
    assert h2.rating == "AA"
    assert h2.value_in_usd == Decimal("140000.00")

    # Verify Alpine Meridian ESG AA/A & EUR->USD
    h6 = h_by_id["XSSYN0000046"]
    assert h6.security_name == "Alpine Meridian Private Credit Fund II - EUR Class"
    assert h6.previous_esg_rating == "AA"
    assert h6.current_esg_rating == "A"
    assert h6.rating == "A"
    assert h6.market_value_currency == "EUR"
    assert h6.total_market_value == Decimal("92400.00")
    assert h6.value_in_usd == Decimal("105000.00")
    assert h6.percentage_of_total_assets == Decimal("9.72")

    # Verify Orchard zero price/value vs blank %
    h8 = h_by_id["IE00SYN00005"]
    assert h8.market_price == Decimal("0.00")
    assert h8.market_price_state == "EXPLICIT_ZERO"
    assert h8.total_market_value == Decimal("0.00")
    assert h8.total_market_value_state == "EXPLICIT_ZERO"
    assert h8.value_in_usd == Decimal("0.00")
    assert h8.percentage_of_total_assets is None
    assert h8.percentage_state == "SOURCE_BLANK"

    # Verify Autocallable HKD -> USD
    h12 = h_by_id["XSSYN0000082"]
    assert h12.units_nominal == Decimal("702000")
    assert h12.market_value_currency == "HKD"
    assert h12.total_market_value == Decimal("702000.00")
    assert h12.value_in_usd == Decimal("90000.00")
    assert h12.percentage_of_total_assets == Decimal("8.33")


def test_accounts_loans_net_assets_and_exchange_rates(extraction_result):
    assert len(extraction_result.current_accounts) == 2
    acc_by_ccy = {a.currency: a for a in extraction_result.current_accounts}
    assert acc_by_ccy["USD"].amount == Decimal("75000.00")
    assert acc_by_ccy["USD"].account_number == "4101-USD"
    assert acc_by_ccy["USD"].market_value_usd == Decimal("75000.00")
    assert acc_by_ccy["EUR"].amount == Decimal("22000.00")
    assert acc_by_ccy["EUR"].account_number == "4101-EUR"
    assert acc_by_ccy["EUR"].market_value_usd == Decimal("25000.00")

    assert len(extraction_result.loans) == 1
    ln = extraction_result.loans[0]
    assert ln.currency == "USD"
    assert ln.amount == Decimal("-60000.00")
    assert ln.loan_reference == "LN-TEST-4101-A"
    assert ln.maturity_date == "15.12.2026"
    assert ln.interest_rate == Decimal("4.8500")
    assert ln.usd_equivalent == Decimal("-60000.00")

    na = extraction_result.net_assets_summary
    assert na is not None
    assert na.assets_usd == Decimal("1080000.00")
    assert na.assets_pct is None
    assert na.accrued_interest_securities_usd == Decimal("0.00")
    assert na.net_accrued_int_deposits_loans_usd == Decimal("0.00")
    assert na.total_assets_usd == Decimal("1080000.00")
    assert na.commitments_usd == Decimal("0.00")

    rates = {(r.base_currency, r.target_currency): r.rate for r in extraction_result.exchange_rates}
    assert rates[("EUR", "USD")] == Decimal("1.13636364")
    assert rates[("USD", "HKD")] == Decimal("7.80000000")


def test_performance_validation_and_excel_workbook(tmp_path, extraction_result):
    assert len(extraction_result.monthly_performance) == 14
    assert len(extraction_result.annual_performance) == 6
    assert extraction_result.monthly_performance[0].period == "01.07.2024"
    assert extraction_result.monthly_performance[-2].return_on_net_income_pct == Decimal("0.14")
    assert extraction_result.annual_performance[-1].period == "30.06.2025"
    assert extraction_result.annual_performance[-1].return_on_net_income_pct == Decimal("1.67")

    fails = [v for v in extraction_result.validation_checks if v.level == "FAIL"]
    assert fails == [], f"Unexpected validation FAIL checks: {fails}"

    out_xlsx = generate_ubp_excel_workbook(extraction_result, str(tmp_path))
    assert os.path.exists(out_xlsx)

    wb = openpyxl.load_workbook(out_xlsx)
    assert len(wb.sheetnames) == 16

    # Check Currency_Breakdown columns contain USD, EUR, HKD and NOT AMT
    cb_ws = wb["Currency_Breakdown"]
    cb_headers = [cb_ws.cell(1, c).value for c in range(1, cb_ws.max_column + 1)]
    assert "USD_000s" in cb_headers
    assert "EUR_000s" in cb_headers
    assert "HKD_000s" in cb_headers
    assert "AMT_000s" not in cb_headers

    # Check Holdings Orchard percentage cell is strictly None/blank (not 0)
    h_ws = wb["Holdings"]
    orchard_row = next(r for r in range(2, h_ws.max_row + 1) if h_ws.cell(r, 4).value == "IE00SYN00005")
    assert h_ws.cell(orchard_row, 8).value == 0.0
    assert h_ws.cell(orchard_row, 16).value is None

    # Check Loans sheet contains LN-TEST-4101-A
    l_ws = wb["Loans"]
    assert l_ws.cell(2, 5).value == "LN-TEST-4101-A"

    # Check Exchange_Rates sheet contains EUR->USD and USD->HKD
    er_ws = wb["Exchange_Rates"]
    assert er_ws.max_row == 3
    assert er_ws.cell(2, 1).value == "EUR"
    assert abs(float(er_ws.cell(2, 3).value) - 1.13636364) < 1e-6
    assert er_ws.cell(3, 1).value == "USD"
    assert abs(float(er_ws.cell(3, 3).value) - 7.8) < 1e-6
