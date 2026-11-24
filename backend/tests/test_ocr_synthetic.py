import os
import pytest
from decimal import Decimal
import pymupdf
import openpyxl

from app.extraction.ocr_extractor import detect_page_type
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook

SYNTHETIC_PDF = r"D:\UserData\Downloads\Synthetic_Portfolio_Training_Report.pdf"

@pytest.mark.skipif(not os.path.exists(SYNTHETIC_PDF), reason="Synthetic training report PDF not found")
def test_ocr_synthetic_portfolio_report_complete_flow():
    doc = pymupdf.open(SYNTHETIC_PDF)
    assert len(doc) == 11

    # Verify Task 1: Type detection on all pages
    for pno in range(len(doc)):
        ptype, needs_ocr = detect_page_type(doc[pno])
        assert ptype in ("IMAGE_BASED", "MIXED")
        assert needs_ocr is True

    # Run full deterministic extraction
    res = extract_ubp_statement(SYNTHETIC_PDF)

    # Verify Task 4 & 5: Metadata and Bank Identification
    assert res.metadata.total_pages == 11
    assert res.metadata.portfolio_number == "548271"
    assert res.metadata.valuation_date == "30.09.2025"
    assert res.metadata.bank_name == "NOT_STATED"
    assert res.metadata.report_currency == "USD"

    # Verify Task 6: Page 1 Asset Allocation
    assert len(res.asset_allocation) == 5
    net_assets_alloc = [a for a in res.asset_allocation if "NET ASSETS" in a.investment_category.upper()][0]
    assert net_assets_alloc.value_usd == Decimal("800221.42")
    assert net_assets_alloc.percentage == Decimal("100.00")

    # Verify Task 6: Page 1 Portfolio Summary Performance
    perf = res.portfolio_summary_performance
    assert perf is not None
    assert perf.initial_assets == Decimal("764690.84")
    assert perf.total_incoming_securities == Decimal("409037.21")
    assert perf.total_outgoing_securities == Decimal("336735.18")
    assert perf.total_incoming_cash == Decimal("0.00")
    assert perf.total_outgoing_cash == Decimal("34060.26")
    assert perf.total_inc_out_cash_sec == Decimal("38241.77")
    assert perf.ending_assets == Decimal("800221.42")
    assert perf.number_of_days == 272
    assert perf.performance_twr_pct == Decimal("-0.39")

    # Verify Task 6: Page 2 Currency Breakdown
    assert len(res.currency_breakdown) == 5
    net_curr = [c for c in res.currency_breakdown if "NET ASSETS" in c.asset_class.upper()][0]
    assert "USD" in net_curr.currencies
    assert "EUR" in net_curr.currencies

    # Verify Task 6: Pages 3 & 4 Holdings (9 holdings)
    assert len(res.holdings) == 9
    for h in res.holdings:
        assert h.isin_secur_no is not None
        assert len(h.isin_secur_no) >= 11
        assert h.value_in_usd is not None

    # Verify Task 6: Page 5 Current Accounts (1 account)
    assert len(res.current_accounts) == 1
    assert res.current_accounts[0].market_value_usd == Decimal("35339.34")
    assert len(res.loans) == 0

    # Verify Task 6: Page 6 Summary of Net Assets & Exchange Rates
    assert res.net_assets_summary is not None
    assert res.net_assets_summary.total_assets_usd == Decimal("800221.42")
    assert len(res.exchange_rates) >= 1
    eur_rate = [r for r in res.exchange_rates if "EUR" in (r.target_currency or "") or "EUR" in (r.base_currency or "")][0]
    assert eur_rate.rate == Decimal("1.17290262")

    # Verify Task 6: Page 7 Monthly Performance
    assert len(res.monthly_performance) == 14
    total_m = [r for r in res.monthly_performance if r.is_total_row][0]
    assert total_m.period_deposits_withdrawals == Decimal("38329")
    assert total_m.net_income == Decimal("6649")

    # Verify Task 6: Page 8 Annual Performance
    assert len(res.annual_performance) >= 8
    final_a = [r for r in res.annual_performance if r.period == "30.09.2025"][0]
    assert final_a.performance_pct == Decimal("-0.39")
    assert final_a.cumulative_performance_pct == Decimal("-23.14")
    assert final_a.end_of_period_assets == Decimal("800222")

    # Verify Task 7: Validation Corrections & Integrity
    fails = [c for c in res.validation_checks if c.level == "FAIL"]
    assert len(fails) == 0, f"Expected 0 failures in validation checks, got: {fails}"

    # Verify Excel Generation with 16 Worksheets
    out_path = r"D:\zz\UBP_Extraction_App\output\test_ocr_synthetic.xlsx"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    saved = generate_ubp_excel_workbook(res, out_path)
    assert os.path.exists(saved)

    wb = openpyxl.load_workbook(saved)
    assert len(wb.sheetnames) == 16
    assert "Holdings" in wb.sheetnames
    assert "Raw_Page_Text" in wb.sheetnames
    assert "Validation" in wb.sheetnames

    # Check Raw_Page_Text contains OCR metadata
    raw_ws = wb["Raw_Page_Text"]
    header = [c.value for c in raw_ws[1]]
    assert "Page_Type" in header
    assert "OCR_Applied" in header
    assert "OCR_Confidence" in header
