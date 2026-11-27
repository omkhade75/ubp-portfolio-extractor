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
