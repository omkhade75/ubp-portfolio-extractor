import os
from decimal import Decimal
import pytest
from app.extraction.table_reconstructor import extract_ubp_statement

SYNTHETIC_02_PATH = r"D:\UserData\Downloads\Synthetic_Portfolio_Training_Report_02.pdf"

@pytest.fixture(scope="module")
def extraction_result():
    assert os.path.exists(SYNTHETIC_02_PATH), f"File not found: {SYNTHETIC_02_PATH}"
    return extract_ubp_statement(SYNTHETIC_02_PATH)

def test_metadata_and_client_profile(extraction_result):
    meta = extraction_result.metadata
    assert meta.portfolio_number == "700483"
    assert meta.client_name == "NIKHIL RAO"
    assert meta.client_reference == "NR-2084"
    assert meta.relationship_type == "Individual investor"
    assert meta.valuation_date == "31.10.2025"
    assert meta.report_currency == "USD"
    assert meta.total_pages == 11

def test_page_1_portfolio_summary(extraction_result):
    perf = extraction_result.portfolio_summary_performance
    assert perf is not None
    assert perf.reporting_period == "Since 31.10.2024"
    assert perf.initial_assets == Decimal("1045000.00")
    assert perf.total_incoming_securities == Decimal("160000.00")
    assert perf.total_outgoing_securities == Decimal("-130000.00")
    assert perf.total_incoming_cash == Decimal("120000.00")
    assert perf.total_outgoing_cash == Decimal("-20000.00")
    assert perf.total_inc_out_cash_sec == Decimal("130000.00")
    assert perf.change_in_total_assets == Decimal("25000.00")
    assert perf.ending_assets == Decimal("1200000.00")
    assert perf.number_of_days == 365
    assert perf.performance_twr_pct == Decimal("2.30")

def test_page_2_currency_breakdown(extraction_result):
    cb_map = {item.asset_class: item for item in extraction_result.currency_breakdown}
    assert "CURRENT ACCOUNTS" in cb_map
    ca = cb_map["CURRENT ACCOUNTS"]
    assert ca.total_in_thousands == Decimal("81")
    assert ca.total_percentage == Decimal("6.78")
    assert "USD" in ca.currencies
    assert ca.currencies["USD"].amount_in_thousands == Decimal("81")
    assert ca.currencies["USD"].percentage == Decimal("6.78")
    assert "EUR" in ca.currencies
    assert ca.currencies["EUR"].amount_in_thousands == Decimal("0")
    assert ca.currencies["EUR"].percentage == Decimal("0.00")

    assert "NET ASSETS" in cb_map
    na = cb_map["NET ASSETS"]
    assert na.total_in_thousands == Decimal("1200")
    assert na.total_percentage == Decimal("100.00")
    assert na.currencies["USD"].amount_in_thousands == Decimal("1170")
    assert na.currencies["USD"].percentage == Decimal("97.50")
    assert na.currencies["EUR"].amount_in_thousands == Decimal("30")
    assert na.currencies["EUR"].percentage == Decimal("2.50")

def test_all_10_holdings_extracted(extraction_result):
    holdings = extraction_result.holdings
    assert len(holdings) == 10

    expected_holdings = [
        {
            "category": "BONDS/NOTES, BOND FUNDS & CERTIFICATES",
            "name": "NORTHSTAR GLOBAL BOND FUND - USD CLASS",
            "sec_no": "XS-NG-20482",
            "units": Decimal("1250.00"),
            "yield": Decimal("3.80"),
            "cost": Decimal("101.25"),
            "price": Decimal("116.22"),
            "curr": "USD",
            "mkt_val": Decimal("145280.40"),
            "pct": Decimal("12.11")
        },
        {
            "category": "BONDS/NOTES, BOND FUNDS & CERTIFICATES",
            "name": "MERIDIAN INVESTMENT GRADE NOTES 2029",
            "sec_no": "XS-MI-88214",
            "units": Decimal("220000"),
            "yield": Decimal("4.15"),
            "cost": Decimal("100.00"),
            "price": Decimal("100.00"),
            "curr": "USD",
            "mkt_val": Decimal("220000.00"),
            "pct": Decimal("18.33")
        },
        {
            "category": "BONDS/NOTES, BOND FUNDS & CERTIFICATES",
            "name": "PACIFIC INCOME BOND PORTFOLIO - CLASS A",
            "sec_no": "SG-PB-51903",
            "units": Decimal("1500.00"),
            "yield": Decimal("3.65"),
            "cost": Decimal("96.40"),
            "price": Decimal("100.00"),
            "curr": "USD",
            "mkt_val": Decimal("150000.00"),
            "pct": Decimal("12.50")
        },
        {
            "category": "PRIVATE EQUITY",
            "name": "SILVERPEAK PRIVATE CREDIT FUND II - EUR",
            "sec_no": "IE-SP-20461",
            "units": Decimal("27397.26"),
            "yield": Decimal("7.20"),
            "cost": Decimal("1.020"),
            "price": Decimal("1.095"),
            "curr": "EUR",
            "mkt_val": Decimal("30000.00"),
            "pct": Decimal("2.50")
        },
        {
            "category": "PRIVATE EQUITY",
            "name": "HORIZON INFRASTRUCTURE GROWTH FUND",
            "sec_no": "LU-HI-77120",
            "units": Decimal("246140"),
            "yield": Decimal("6.10"),
            "cost": Decimal("0.920"),
            "price": Decimal("1.000"),
            "curr": "USD",
            "mkt_val": Decimal("246140.25"),
            "pct": Decimal("20.51")
        },
        {
            "category": "PRIVATE EQUITY",
            "name": "SUMMIT PRIVATE EQUITY FUND III - USD",
            "sec_no": "US-SE-33187",
            "units": Decimal("110000"),
            "yield": Decimal("8.40"),
            "cost": Decimal("1.000"),
            "price": Decimal("1.000"),
            "curr": "USD",
            "mkt_val": Decimal("110000.00"),
            "pct": Decimal("9.17")
        },
        {
            "category": "ALTERNATIVE INVESTMENTS & CERTIFICATES",
            "name": "ATLAS MULTI-STRATEGY OPPORTUNITIES FUND",
            "sec_no": "KY-AM-44108",
            "units": Decimal("784.60"),
            "yield": Decimal("5.90"),
            "cost": Decimal("90.10"),
            "price": Decimal("100.00"),
            "curr": "USD",
            "mkt_val": Decimal("78460.10"),
            "pct": Decimal("6.54")
        },
        {
            "category": "ALTERNATIVE INVESTMENTS & CERTIFICATES",
            "name": "CRESCENT TRADE FINANCE FUND - SERIES B",
            "sec_no": "SG-CT-90771",
            "units": Decimal("50000"),
            "yield": Decimal("6.75"),
            "cost": Decimal("1.000"),
            "price": Decimal("1.000"),
            "curr": "USD",
            "mkt_val": Decimal("50000.00"),
            "pct": Decimal("4.17")
        },
        {
            "category": "EQUITIES & EXCHANGE-TRADED FUNDS",
            "name": "GLOBAL LEADERS EQUITY ETF",
            "sec_no": "IE-GL-62419",
            "units": Decimal("625.00"),
            "yield": Decimal("0.00"),
            "cost": Decimal("78.20"),
            "price": Decimal("89.00"),
            "curr": "USD",
            "mkt_val": Decimal("55625.35"),
            "pct": Decimal("4.64")
        },
        {
            "category": "EQUITIES & EXCHANGE-TRADED FUNDS",
            "name": "ASIA-PACIFIC DIVIDEND FUND",
            "sec_no": "LU-AP-88253",
            "units": Decimal("331.50"),
            "yield": Decimal("0.00"),
            "cost": Decimal("95.00"),
            "price": Decimal("100.00"),
            "curr": "USD",
            "mkt_val": Decimal("33150.00"),
            "pct": Decimal("2.76")
        }
    ]

    for idx, (h, exp) in enumerate(zip(holdings, expected_holdings)):
        assert h.asset_category == exp["category"], f"Holding {idx+1} category mismatch: {h.asset_category} != {exp['category']}"
        assert h.security_name == exp["name"], f"Holding {idx+1} name mismatch: {h.security_name} != {exp['name']}"
        assert h.isin_secur_no == exp["sec_no"], f"Holding {idx+1} secur_no mismatch: {h.isin_secur_no} != {exp['sec_no']}"
        assert h.units_nominal == exp["units"], f"Holding {idx+1} units mismatch: {h.units_nominal} != {exp['units']}"
        if exp["yield"] is not None:
            assert h.yield_val == exp["yield"], f"Holding {idx+1} yield mismatch: {h.yield_val} != {exp['yield']}"
        assert h.net_avg_cost == exp["cost"], f"Holding {idx+1} cost mismatch: {h.net_avg_cost} != {exp['cost']}"
        assert h.market_price == exp["price"], f"Holding {idx+1} price mismatch: {h.market_price} != {exp['price']}"
        assert h.market_value_currency == exp["curr"], f"Holding {idx+1} currency mismatch: {h.market_value_currency} != {exp['curr']}"
        assert h.total_market_value == exp["mkt_val"], f"Holding {idx+1} mkt_val mismatch: {h.total_market_value} != {exp['mkt_val']}"
        assert h.percentage_of_total_assets == exp["pct"], f"Holding {idx+1} pct mismatch: {h.percentage_of_total_assets} != {exp['pct']}"

    # Recalculate each category subtotal directly from individual holdings
    pdf_subtotals = {
        "BONDS/NOTES, BOND FUNDS & CERTIFICATES": (Decimal("515280.40"), Decimal("42.94")),
        "PRIVATE EQUITY": (Decimal("386140.25"), Decimal("32.18")),
        "ALTERNATIVE INVESTMENTS & CERTIFICATES": (Decimal("128460.10"), Decimal("10.71")),
        "EQUITIES & EXCHANGE-TRADED FUNDS": (Decimal("88775.35"), Decimal("7.40"))
    }
    for cat, (expected_sum, expected_pct) in pdf_subtotals.items():
        cat_holdings = [h for h in holdings if h.asset_category == cat]
        calc_sum = sum(h.total_market_value for h in cat_holdings)
        calc_pct = sum(h.percentage_of_total_assets for h in cat_holdings)
        assert calc_sum == expected_sum, f"Category '{cat}' subtotal mismatch: calc {calc_sum} != printed {expected_sum}"
        assert calc_pct == expected_pct, f"Category '{cat}' pct mismatch: calc {calc_pct} != printed {expected_pct}"

def test_monthly_performance(extraction_result):
    rows = extraction_result.monthly_performance
    assert len(rows) == 14

    # Initial row
    init_row = rows[0]
    assert init_row.is_initial_row is True
    assert init_row.period == "31.10.2024"
    assert init_row.end_of_period_assets == Decimal("1045000")
    assert init_row.cumulative_performance_pct == Decimal("0.00")
    assert init_row.performance_pct is None  # Blank distinguishable from 0.00

    # Total row
    tot_row = rows[-1]
    assert tot_row.is_total_row is True
    assert tot_row.period_deposits_withdrawals == Decimal("130000")
    assert tot_row.change_in_total_assets == Decimal("25000")

def test_annual_performance(extraction_result):
    rows = extraction_result.annual_performance
    assert len(rows) == 8

    # Initial row
    init_row = rows[0]
    assert init_row.is_initial_row is True
    assert init_row.period == "01.01.2020"
    assert init_row.end_of_period_assets == Decimal("250000")
    assert init_row.cumulative_performance_pct == Decimal("0.00")

    # Final reporting periodic row
    final_row = rows[-2]
    assert final_row.is_initial_row is False
    assert final_row.period == "31.10.2025"
    assert final_row.performance_pct == Decimal("2.30")
    assert final_row.cumulative_performance_pct == Decimal("24.96")
    assert final_row.end_of_period_assets == Decimal("1200000")
    assert final_row.period_deposits_withdrawals == Decimal("130000")
    assert final_row.change_in_total_assets == Decimal("25000")
    assert final_row.net_income == Decimal("4300")
    assert final_row.return_on_net_income_pct == Decimal("0.42")

    # Total row
    tot_row = rows[-1]
    assert tot_row.is_total_row is True
    assert tot_row.period_deposits_withdrawals == Decimal("805000")
    assert tot_row.change_in_total_assets == Decimal("145000")
    assert tot_row.net_income == Decimal("22150")

def test_comments_and_disclosures(extraction_result):
    comments = extraction_result.comments_disclosures
    assert 9 in comments.general_info_pages or 9 in comments.source_pages
    assert 10 in comments.prc_pages or 10 in comments.source_pages
    assert 11 in comments.ack_pages or 11 in comments.source_pages
    assert len(comments.general_information) > 50
    assert len(comments.product_risk_classification) > 50
    assert len(comments.acknowledgement_of_assets) > 50

def test_validation_integrity(extraction_result):
    checks = extraction_result.validation_checks
    fails = [c for c in checks if c.level == "FAIL"]
    assert len(fails) == 0, f"Expected 0 validation failures, got: {fails}"

def test_generated_excel_holdings_accuracy(tmp_path, extraction_result):
    import openpyxl
    from app.excel.workbook_generator import generate_ubp_excel_workbook
    out_xlsx = generate_ubp_excel_workbook(extraction_result, str(tmp_path))
    assert os.path.exists(out_xlsx)

    wb = openpyxl.load_workbook(out_xlsx)
    ws = wb["Holdings"]
    assert ws.max_row == 11  # 1 header + 10 holdings

    expected_excel_rows = [
        ("XS-NG-20482", 1250.0, 116.22, 145280.40, "USD", 0.1211),
        ("XS-MI-88214", 220000.0, 100.00, 220000.00, "USD", 0.1833),
        ("SG-PB-51903", 1500.0, 100.00, 150000.00, "USD", 0.1250),
        ("IE-SP-20461", 27397.26, 1.095, 30000.00, "EUR", 0.0250),
        ("LU-HI-77120", 246140.0, 1.00, 246140.25, "USD", 0.2051),
        ("US-SE-33187", 110000.0, 1.00, 110000.00, "USD", 0.0917),
        ("KY-AM-44108", 784.6, 100.00, 78460.10, "USD", 0.0654),
        ("SG-CT-90771", 50000.0, 1.00, 50000.00, "USD", 0.0417),
        ("IE-GL-62419", 625.0, 89.00, 55625.35, "USD", 0.0464),
        ("LU-AP-88253", 331.5, 100.00, 33150.00, "USD", 0.0276),
    ]

    for idx, (sec_no, exp_units, exp_price, exp_mkt_val, exp_curr, exp_pct) in enumerate(expected_excel_rows):
        r = idx + 2
        act_sec = ws.cell(r, 4).value
        act_units = float(ws.cell(r, 5).value)
        act_price = float(ws.cell(r, 8).value)
        act_mkt_val = float(ws.cell(r, 11).value)
        act_curr = ws.cell(r, 12).value
        act_pct = float(ws.cell(r, 16).value)

        assert act_sec == sec_no, f"Row {r} secur_no mismatch: {act_sec} != {sec_no}"
        assert abs(act_units - exp_units) < 0.01, f"Row {r} units mismatch: {act_units} != {exp_units}"
        assert abs(act_price - exp_price) < 0.01, f"Row {r} price mismatch: {act_price} != {exp_price}"
        assert abs(act_mkt_val - exp_mkt_val) < 0.01, f"Row {r} mkt_val mismatch: {act_mkt_val} != {exp_mkt_val}"
        assert act_curr == exp_curr, f"Row {r} curr mismatch: {act_curr} != {exp_curr}"
        assert abs(act_pct - exp_pct) < 0.0001, f"Row {r} pct mismatch: {act_pct} != {exp_pct}"
