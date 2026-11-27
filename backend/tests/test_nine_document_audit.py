import os
from decimal import Decimal
import pytest

from app.extraction.table_reconstructor import extract_ubp_statement
from app.config import SAMPLE_PDFS_DIR


def _synthetic_path(filename: str) -> str:
    return os.path.join(r"D:\UserData\Downloads", filename)


@pytest.mark.parametrize(
    "pdf_path,expected_portfolio,expected_net_assets,expected_holdings,expected_annual_rows",
    [
        (str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf"), "1002590", Decimal("2267669.27"), 12, 12),
        (str(SAMPLE_PDFS_DIR / "2_UBP_1002590_Oct2025.pdf"), "1002590", Decimal("2279848.49"), 16, 12),
        (str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf"), "1002590", Decimal("2577594.26"), 17, 12),
        (str(SAMPLE_PDFS_DIR / "4_UBP_1002591_Jul2025.pdf"), "1002591", Decimal("858466.51"), 9, 9),
        (str(SAMPLE_PDFS_DIR / "5_UBP_1002591_Oct2025.pdf"), "1002591", Decimal("919794.74"), 9, 9),
        (_synthetic_path("Synthetic_Portfolio_Test_01.pdf"), "SYN-4101", Decimal("1080000.00"), 12, 6),
        (_synthetic_path("Synthetic_Portfolio_Test_02.pdf"), "SYN-5202", Decimal("1420000.00"), 13, 7),
        (_synthetic_path("Synthetic_Portfolio_Test_03.pdf"), "SYN-6303", Decimal("1815000.00"), 12, 6),
        (_synthetic_path("Synthetic_Portfolio_Test_04.pdf"), "SYN-7404", Decimal("2120000.00"), 14, 6),
        (_synthetic_path("Synthetic_Portfolio_Test_05.pdf"), "SYN-8505", Decimal("1500000.00"), 12, 6),
        (_synthetic_path("Synthetic_Portfolio_Test_06.pdf"), "SYN-9606", Decimal("1900000.00"), 14, 6),
        (_synthetic_path("Synthetic_Portfolio_Test_07.pdf"), "SYN-9707", Decimal("1750000.00"), 12, 6),
        (_synthetic_path("Synthetic_Portfolio_Test_08.pdf"), "SYN-10808", Decimal("1600000.00"), 12, 6),
        (_synthetic_path("Synthetic_Portfolio_Test_09.pdf"), "SYN-11809", Decimal("2050000.00"), 12, 7),
        (_synthetic_path("Synthetic_Portfolio_Test_10.pdf"), "SYN-12010", Decimal("1900000.00"), 12, 7),
        (_synthetic_path("Synthetic_Portfolio_Test_11.pdf"), "SYN-13011", Decimal("2350000.00"), 12, 7),
    ],
)
def test_nine_document_full_reconciliation(
    pdf_path,
    expected_portfolio,
    expected_net_assets,
    expected_holdings,
    expected_annual_rows,
):
    if not os.path.exists(pdf_path):
        pytest.skip(f"Document not available on test host: {pdf_path}")

    res = extract_ubp_statement(pdf_path)

    assert res.metadata.portfolio_number == expected_portfolio
    assert len(res.holdings) == expected_holdings
    assert len(res.annual_performance) == expected_annual_rows

    # 1. Zero FAIL validation checks across every document
    fails = [c for c in res.validation_checks if c.level == "FAIL"]
    assert fails == [], f"{os.path.basename(pdf_path)} validation failures: {[f.message for f in fails]}"

    # 2. Overview ending assets & Asset Allocation Net Assets match expected Net Assets
    assert res.portfolio_summary_performance is not None
    assert res.portfolio_summary_performance.ending_assets == expected_net_assets

    aa_net = [a for a in res.asset_allocation if "NET ASSETS" in a.investment_category.upper()]
    assert aa_net and aa_net[0].value_usd == expected_net_assets

    # 3. Net Assets Summary Total Assets matches expected Net Assets
    assert res.net_assets_summary is not None
    assert res.net_assets_summary.total_assets_usd == expected_net_assets

    # 4. Holdings + Current Accounts + Loans (incl. accrued interest) reconcile to Net Assets
    h_val = sum((h.value_in_usd or Decimal("0")) for h in res.holdings)
    h_acc = sum((h.accrued_interest_usd or Decimal("0")) for h in res.holdings)
    ca_val = sum((a.market_value_usd or Decimal("0")) for a in res.current_accounts)
    ln_val = sum((l.usd_equivalent or Decimal("0")) for l in res.loans)
    ln_acc = sum((l.accrued_interest or Decimal("0")) for l in res.loans)

    reconciled_total = h_val + h_acc + ca_val + ln_val + ln_acc
    assert abs(reconciled_total - expected_net_assets) <= Decimal("0.02")


def test_synthetic_04_structured_products_and_zero_column_alignment():
    p04 = _synthetic_path("Synthetic_Portfolio_Test_04.pdf")
    if not os.path.exists(p04):
        pytest.skip("Synthetic_Portfolio_Test_04.pdf not present")

    res = extract_ubp_statement(p04)
    sp = [h for h in res.holdings if "STRUCTURED PRODUCTS" in h.asset_category.upper()]
    assert len(sp) == 2
    assert sum(h.value_in_usd for h in sp) == Decimal("180000.00")
    assert all(h.percentage_of_total_assets == Decimal("4.25") for h in sp)

    # Annual 2022 has change=0 and net_income=26000 (not shifted by right-aligned 0)
    row_2022 = next(r for r in res.annual_performance if r.period == "2022")
    assert row_2022.change_in_total_assets == Decimal("0")
    assert row_2022.net_income == Decimal("26000")

    # Monthly 02.2025 has deposits=0 and change=5000 (not shifted)
    m02 = next(r for r in res.monthly_performance if r.period == "02.2025")
    assert m02.period_deposits_withdrawals == Decimal("0")
    assert m02.change_in_total_assets == Decimal("5000")


def test_synthetic_05_alternative_terminology_and_multi_line_holdings():
    p05 = _synthetic_path("Synthetic_Portfolio_Test_05.pdf")
    if not os.path.exists(p05):
        pytest.skip("Synthetic_Portfolio_Test_05.pdf not present")

    res = extract_ubp_statement(p05)

    # 1. Metadata & Overview
    assert res.metadata.portfolio_number == "SYN-8505"
    assert res.portfolio_summary_performance is not None
    assert res.portfolio_summary_performance.ending_assets == Decimal("1500000.00")
    assert res.portfolio_summary_performance.performance_twr_pct == Decimal("3.10")

    # Cash flows
    cf = res.portfolio_summary_performance
    assert cf.initial_assets == Decimal("1455000.00")
    assert cf.total_incoming_cash == Decimal("60000.00")
    assert cf.total_outgoing_cash == Decimal("-20000.00")
    assert cf.total_incoming_securities == Decimal("20000.00")
    assert cf.total_outgoing_securities == Decimal("-15000.00")
    assert cf.total_inc_out_cash_sec == Decimal("45000.00")
    assert cf.change_in_total_assets == Decimal("45000.00")

    # 2. Holdings table with alternative headers and multi-line rows
    assert len(res.holdings) == 12
    # Verify exact ISINs / identifiers
    expected_ids = [
        "XS8505000017", "XS8505000025", "CH-VAL-8505003",
        "XS8505000041", "US-TEST-8505-A", "XS8505000058",
        "PB-TEST-8505-PE", "CH-VAL-8505007", "XS8505000082",
        "XS8505000090", "XS8505000108", "XS8505000116"
    ]
    extracted_ids = [h.isin_secur_no for h in res.holdings]
    for expected_id in expected_ids:
        assert any(expected_id in (eid or "") for eid in extracted_ids), f"ID {expected_id} missing from extracted holdings: {extracted_ids}"

    # Verify sample holding field mappings (Case B: description line 1, financial values line 2)
    h_nw = next(h for h in res.holdings if "XS8505000058" in (h.isin_secur_no or ""))
    assert "NORTHWIND GROWTH" in h_nw.security_name.upper()
    assert h_nw.units_nominal == Decimal("1000")
    assert h_nw.yield_val == Decimal("7.20")
    assert h_nw.net_avg_cost == Decimal("90.00")
    assert h_nw.market_price == Decimal("100.00")
    assert h_nw.value_in_usd == Decimal("110000.00")
    assert h_nw.percentage_of_total_assets == Decimal("7.33")

    h_mr = next(h for h in res.holdings if "XS8505000017" in (h.isin_secur_no or ""))
    assert "MAPLE RIDGE" in h_mr.security_name.upper()
    assert h_mr.units_nominal == Decimal("1800")
    assert h_mr.yield_val == Decimal("3.55")
    assert h_mr.net_avg_cost == Decimal("99.10")
    assert h_mr.market_price == Decimal("100.00")
    assert h_mr.value_in_usd == Decimal("180000.00")
    assert h_mr.percentage_of_total_assets == Decimal("12.00")

    # 3. Current Accounts
    assert len(res.current_accounts) == 4
    ca_dict = {a.currency: a for a in res.current_accounts}
    assert "USD" in ca_dict and ca_dict["USD"].amount == Decimal("100000.00")
    assert "EUR" in ca_dict and ca_dict["EUR"].amount == Decimal("30000.00")
    assert "CHF" in ca_dict and ca_dict["CHF"].amount == Decimal("20000.00")
    assert "HKD" in ca_dict and ca_dict["HKD"].amount == Decimal("39000.00")
    assert ca_dict["USD"].market_value_usd == Decimal("100000.00")
    assert ca_dict["EUR"].market_value_usd == Decimal("33000.00")
    assert ca_dict["CHF"].market_value_usd == Decimal("22000.00")
    assert ca_dict["HKD"].market_value_usd == Decimal("5000.00")
    assert "8505-USD" in (ca_dict["USD"].account_number or ca_dict["USD"].account_name)

    # 4. Loans
    assert len(res.loans) == 2
    l_usd = next(l for l in res.loans if l.currency == "USD")
    l_chf = next(l for l in res.loans if l.currency == "CHF")
    assert l_usd.amount == Decimal("-25000.00")
    assert l_usd.usd_equivalent == Decimal("-25000.00")
    assert "LN-TEST-8505-A" in (l_usd.loan_reference or l_usd.description or "")
    assert l_chf.amount == Decimal("-13636.36")
    assert l_chf.usd_equivalent == Decimal("-15000.00")
    assert "LN-TEST-8505-B" in (l_chf.loan_reference or l_chf.description or "")


def test_synthetic_11_multi_line_holding_separation():
    p11 = _synthetic_path("Synthetic_Portfolio_Test_11.pdf")
    if not os.path.exists(p11):
        pytest.skip("Synthetic_Portfolio_Test_11.pdf not present")

    res = extract_ubp_statement(p11)

    assert res.metadata.portfolio_number == "SYN-13011"
    assert len(res.holdings) == 12

    # Verify zero FAIL validation checks
    fails = [c for c in res.validation_checks if c.level == "FAIL"]
    assert fails == [], f"Validation failures: {[f.message for f in fails]}"

    # Specifically test the previously defective positions HLD-010 and HLD-011 on page 4
    h10 = next(h for h in res.holdings if h.isin_secur_no == "XS1301100100")
    h11 = next(h for h in res.holdings if h.isin_secur_no == "XS1301100118")
    h12 = next(h for h in res.holdings if h.isin_secur_no == "XS1301100126")

    # 1. HOLDING 10: Euro Principal Protected Note - Maturity 2035
    assert "EURO PRINCIPAL PROTECTED NOTE" in h10.security_name.upper()
    assert "MATURITY 2035" in h10.security_name.upper()
    # Must NOT contain text from Holding 11
    assert "HARBOURFRONT" not in h10.security_name.upper()
    assert h10.units_nominal == Decimal("81818.18")
    assert h10.value_in_usd == Decimal("90000.00")

    # 2. HOLDING 11: Harbourfront Equity Participation Note - HKD Series 10
    assert "HARBOURFRONT EQUITY PARTICIPATION NOTE" in h11.security_name.upper()
    assert "SERIES 10" in h11.security_name.upper()
    assert h11.security_name != ""
    assert h11.units_nominal == Decimal("468000")
    assert h11.value_in_usd == Decimal("60000.00")

    # 3. HOLDING 12: Fairhaven USD Callable Income Note - Class L
    assert "FAIRHAVEN USD CALLABLE INCOME NOTE" in h12.security_name.upper()
    assert "CLASS L" in h12.security_name.upper()
    assert h12.units_nominal == Decimal("60000")
    assert h12.value_in_usd == Decimal("60000.00")


def test_synthetic_10_multi_line_holding_separation():
    p10 = _synthetic_path("Synthetic_Portfolio_Test_10.pdf")
    if not os.path.exists(p10):
        pytest.skip("Synthetic_Portfolio_Test_10.pdf not present")

    res = extract_ubp_statement(p10)

    assert res.metadata.portfolio_number == "SYN-12010"
    assert len(res.holdings) == 12

    # Verify zero FAIL validation checks
    fails = [c for c in res.validation_checks if c.level == "FAIL"]
    assert fails == [], f"Validation failures: {[f.message for f in fails]}"

    # Specifically test positions HLD-010 and HLD-011 on page 4
    h10 = next(h for h in res.holdings if h.isin_secur_no == "XS1201000104")
    h11 = next(h for h in res.holdings if h.isin_secur_no == "XS1201000112")
    h12 = next(h for h in res.holdings if h.isin_secur_no == "XS1201000120")

    # 1. HOLDING 10: Euro Capital Protection Note - Maturity 2034
    assert "EURO CAPITAL PROTECTION NOTE" in h10.security_name.upper()
    assert "MATURITY 2034" in h10.security_name.upper()
    assert "HARBOURVIEW" not in h10.security_name.upper()
    assert h10.units_nominal == Decimal("54545.45")
    assert h10.value_in_usd == Decimal("60000.00")

    # 2. HOLDING 11: Harbourview Equity Participation Note - HKD Series 9
    assert "HARBOURVIEW EQUITY PARTICIPATION NOTE" in h11.security_name.upper()
    assert "SERIES 9" in h11.security_name.upper()
    assert h11.security_name != ""
    assert h11.units_nominal == Decimal("468000")
    assert h11.value_in_usd == Decimal("60000.00")

    # 3. HOLDING 12: Rivermark USD Callable Income Note - Class C
    assert "RIVERMARK USD CALLABLE INCOME NOTE" in h12.security_name.upper()
    assert "CLASS C" in h12.security_name.upper()
    assert h12.units_nominal == Decimal("60000")
    assert h12.value_in_usd == Decimal("60000.00")


def test_synthetic_06_alternate_headers_and_ocr():
    p06 = _synthetic_path("Synthetic_Portfolio_Test_06.pdf")
    if not os.path.exists(p06):
        pytest.skip("Synthetic_Portfolio_Test_06.pdf not present")

    res = extract_ubp_statement(p06)

    assert res.metadata.portfolio_number == "SYN-9606"
    assert len(res.holdings) == 14

    # Verify zero FAIL validation checks
    fails = [c for c in res.validation_checks if c.level == "FAIL"]
    assert fails == [], f"Validation failures: {[f.message for f in fails]}"

    # Verify all holdings have non-empty names
    for h in res.holdings:
        assert h.security_name and len(h.security_name.strip()) >= 3, f"Holding {h.id} has empty name"

    # Verify Structured Products on Page 5
    sp = [h for h in res.holdings if "STRUCTURED PRODUCTS" in h.asset_category.upper()]
    assert len(sp) == 3
    assert any("CROSS-CURRENCY" in h.security_name.upper() for h in sp)
    assert any("HONG KONG TECHNOLOGY" in h.security_name.upper() for h in sp)
    assert any("MATURED STERLING" in h.security_name.upper() for h in sp)


