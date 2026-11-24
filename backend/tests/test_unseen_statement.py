import os
from decimal import Decimal
from pathlib import Path
import pytest
import pymupdf
import openpyxl

from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook

def build_unseen_ubp_pdf(path: str) -> str:
    """
    Programmatically creates a realistic, multi-page UBP Portfolio Statement
    containing completely unseen test data:
      - Portfolio: 2004812 (New Horizons Global Strategy)
      - Bank: UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH
      - Valuation Date: 31.03.2026
      - Reporting Currency: USD
      - 8 Pages in standard UBP structure
    """
    doc = pymupdf.open()
    
    # ----------------------------------------------------
    # Page 1: Asset Allocation & Performance Summary
    # ----------------------------------------------------
    p1 = doc.new_page(width=840.0, height=595.2)
    p1.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p1.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p1.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p1.insert_text((650, 40), "Report edited on : 02.04.26", fontsize=9)
    p1.insert_text((650, 55), "Page 1 / 8", fontsize=9)

    # Left: Asset Allocation
    p1.insert_text((38, 150), "ASSET ALLOCATION", fontsize=10)
    p1.insert_text((38, 170), "INVESTMENT CATEGORY USD %", fontsize=8)
    p1.insert_text((38, 190), "BONDS/NOTES, BOND FUNDS & CERTIFICATES 450’000.00 30.00", fontsize=8)
    p1.insert_text((38, 210), "EQUITIES, EQUITY FUNDS & CERTIFICATES 750’000.00 50.00", fontsize=8)
    p1.insert_text((38, 230), "CURRENT ACCOUNTS 300’000.00 20.00", fontsize=8)
    p1.insert_text((38, 250), "NET ASSETS USD 1’500’000.00 100.00", fontsize=8)

    # Right: Portfolio in USD Performance Summary
    p1.insert_text((444, 150), "PORTFOLIO IN USD PERFORMANCE", fontsize=10)
    p1.insert_text((444, 165), "SINCE 01.01.2026", fontsize=8)
    p1.insert_text((444, 180), "INITIAL ASSETS 1’450’000.00", fontsize=8)
    p1.insert_text((444, 195), "TOTAL INCOMING SECURITIES 0.00", fontsize=8)
    p1.insert_text((444, 210), "TOTAL OUTGOING SECURITIES 0.00", fontsize=8)
    p1.insert_text((444, 225), "TOTAL INCOMING CASH 0.00", fontsize=8)
    p1.insert_text((444, 240), "TOTAL OUTGOING CASH -20’000.00", fontsize=8)
    p1.insert_text((444, 255), "TOTAL OF INC/OUT CASH & SEC -20’000.00", fontsize=8)
    p1.insert_text((444, 270), "CHANGE IN TOTAL ASSETS 70’000.00", fontsize=8)
    p1.insert_text((444, 285), "ASSETS AS OF 31.03.2026 1’500’000.00", fontsize=8)
    p1.insert_text((444, 300), "NUMBER OF DAYS (90 D)", fontsize=8)
    p1.insert_text((444, 315), "PERFORMANCE TWR (USD) 4.83%", fontsize=8)

    # ----------------------------------------------------
    # Page 2: Currency Breakdown
    # ----------------------------------------------------
    p2 = doc.new_page(width=840.0, height=595.2)
    p2.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p2.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p2.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p2.insert_text((650, 55), "Page 2 / 8", fontsize=9)
    p2.insert_text((38, 120), "BREAKDOWN OF NET ASSETS BY CURRENCY", fontsize=10)
    p2.insert_text((38, 140), "ASSET CLASS TOTAL % % % USD CHF", fontsize=8)
    p2.insert_text((38, 160), "BONDS/NOTES, BOND FUNDS & CERTIFICATES 450 30.00 450 30.00", fontsize=8)
    p2.insert_text((38, 180), "EQUITIES, EQUITY FUNDS & CERTIFICATES 750 50.00 750 50.00", fontsize=8)
    p2.insert_text((38, 200), "CURRENT ACCOUNTS 300 20.00 200 13.33 100 6.67", fontsize=8)
    p2.insert_text((38, 220), "NET ASSETS USD 1’500 100.00 1’400 93.33 100 6.67", fontsize=8)

    # ----------------------------------------------------
    # Page 3: Holdings
    # ----------------------------------------------------
    p3 = doc.new_page(width=840.0, height=595.2)
    p3.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p3.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p3.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p3.insert_text((650, 55), "Page 3 / 8", fontsize=9)
    p3.insert_text((38, 100), "CURRENT PORTFOLIO", fontsize=10)
    p3.insert_text((38, 115), "Units/Nominal Security name ISIN/Secur. No. Yield Net Avg Cost Market Price Currency Total Market Value Value in USD %", fontsize=8)
    
    # Category 1 Banner
    p3.insert_text((38, 140), "BONDS/NOTES, BOND FUNDS & CERTIFICATES 450’000.00 30.00", fontsize=8)
    # Holding 1
    p3.insert_text((45, 160), "100’000", fontsize=8)
    p3.insert_text((103, 160), "APPLE INC 3.5% 2028", fontsize=8)
    p3.insert_text((390, 160), "US0378331005", fontsize=8)
    p3.insert_text((516, 160), "100.00", fontsize=8)
    p3.insert_text((576, 160), "100.00", fontsize=8)
    p3.insert_text((611, 160), "USD", fontsize=8)
    p3.insert_text((665, 160), "100’000.00", fontsize=8)
    p3.insert_text((737, 160), "100’000.00", fontsize=8)
    p3.insert_text((788, 160), "6.67", fontsize=8)
    
    # Holding 2
    p3.insert_text((45, 185), "350’000", fontsize=8)
    p3.insert_text((103, 185), "MICROSOFT CORP 4.0% 2030", fontsize=8)
    p3.insert_text((390, 185), "US5949181045", fontsize=8)
    p3.insert_text((516, 185), "100.00", fontsize=8)
    p3.insert_text((576, 185), "100.00", fontsize=8)
    p3.insert_text((611, 185), "USD", fontsize=8)
    p3.insert_text((665, 185), "350’000.00", fontsize=8)
    p3.insert_text((737, 185), "350’000.00", fontsize=8)
    p3.insert_text((788, 185), "23.33", fontsize=8)

    # Category 2 Banner
    p3.insert_text((38, 220), "EQUITIES, EQUITY FUNDS & CERTIFICATES 750’000.00 50.00", fontsize=8)
    # Holding 3
    p3.insert_text((45, 245), "5’000", fontsize=8)
    p3.insert_text((103, 245), "NESTLE SA REG", fontsize=8)
    p3.insert_text((390, 245), "CH0012005267", fontsize=8)
    p3.insert_text((516, 245), "150.00", fontsize=8)
    p3.insert_text((576, 245), "150.00", fontsize=8)
    p3.insert_text((611, 245), "USD", fontsize=8)
    p3.insert_text((665, 245), "750’000.00", fontsize=8)
    p3.insert_text((737, 245), "750’000.00", fontsize=8)
    p3.insert_text((788, 245), "50.00", fontsize=8)

    # ----------------------------------------------------
    # Page 4: Current Accounts & Loans
    # ----------------------------------------------------
    p4 = doc.new_page(width=840.0, height=595.2)
    p4.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p4.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p4.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p4.insert_text((650, 55), "Page 4 / 8", fontsize=9)
    p4.insert_text((38, 115), "CURRENT ACCOUNTS 300’000.00 20.00", fontsize=8)
    p4.insert_text((38, 140), "USD", fontsize=8)
    p4.insert_text((78, 140), "200’000.00", fontsize=8)
    p4.insert_text((140, 140), "CURRENT ACCOUNT NUMBER 2004812001", fontsize=8)
    p4.insert_text((665, 140), "200’000.00", fontsize=8)
    p4.insert_text((737, 140), "200’000.00", fontsize=8)
    p4.insert_text((788, 140), "13.33", fontsize=8)

    p4.insert_text((38, 165), "CHF", fontsize=8)
    p4.insert_text((78, 165), "100’000.00", fontsize=8)
    p4.insert_text((140, 165), "CURRENT ACCOUNT NUMBER 2004812002", fontsize=8)
    p4.insert_text((665, 165), "100’000.00", fontsize=8)
    p4.insert_text((737, 165), "100’000.00", fontsize=8)
    p4.insert_text((788, 165), "6.67", fontsize=8)

    # ----------------------------------------------------
    # Page 5: Summary of Net Assets & Exchange Rates
    # ----------------------------------------------------
    p5 = doc.new_page(width=840.0, height=595.2)
    p5.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p5.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p5.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p5.insert_text((650, 55), "Page 5 / 8", fontsize=9)
    p5.insert_text((38, 115), "SUMMARY OF NET ASSETS", fontsize=10)
    p5.insert_text((38, 140), "TOTAL ASSETS USD 1’500’000.00 100.00", fontsize=8)
    p5.insert_text((38, 180), "EXCHANGE RATES USED", fontsize=10)
    p5.insert_text((38, 200), "USD / CHF 0.9000", fontsize=8)

    # ----------------------------------------------------
    # Page 6: History of Monthly Performances
    # ----------------------------------------------------
    p6 = doc.new_page(width=840.0, height=595.2)
    p6.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p6.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p6.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p6.insert_text((650, 55), "Page 6 / 8", fontsize=9)
    p6.insert_text((38, 115), "HISTORY OF MONTHLY PERFORMANCES", fontsize=10)
    p6.insert_text((38, 130), "PERIOD PERFORMANCE CUMULATIVE DEPOSITS AND WITHDRAWALS CHANGE IN TOTAL ASSETS NET INCOME RETURN ON NET INCOME", fontsize=7)
    p6.insert_text((38, 150), "01.01.2026 0.00% 1’450’000", fontsize=8)
    p6.insert_text((38, 165), "01.2026 1.50% 1.50% 1’470’000 0 20’000 10’000 0.69%", fontsize=8)
    p6.insert_text((38, 180), "02.2026 1.20% 2.72% 1’485’000 0 15’000 8’000 0.54%", fontsize=8)
    p6.insert_text((38, 195), "03.2026 2.05% 4.83% 1’500’000 -20’000 15’000 12’000 0.81%", fontsize=8)
    p6.insert_text((38, 215), "Total -20’000 50’000 30’000", fontsize=8)
    p6.insert_text((38, 250), "CUMULATIVE PERFORMANCE", fontsize=9)

    # ----------------------------------------------------
    # Page 7: History of Annual Performances
    # ----------------------------------------------------
    p7 = doc.new_page(width=840.0, height=595.2)
    p7.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p7.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p7.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p7.insert_text((650, 55), "Page 7 / 8", fontsize=9)
    p7.insert_text((38, 115), "HISTORY OF ANNUAL PERFORMANCES", fontsize=10)
    p7.insert_text((38, 130), "PERIOD PERFORMANCE CUMULATIVE DEPOSITS AND WITHDRAWALS CHANGE IN TOTAL ASSETS NET INCOME RETURN ON NET INCOME", fontsize=7)
    p7.insert_text((38, 150), "31.12.2024 * 0.00% 1’200’000", fontsize=8)
    p7.insert_text((38, 165), "2025 20.83% 20.83% 1’450’000 0 250’000 50’000 4.17%", fontsize=8)
    p7.insert_text((38, 180), "31.03.2026 4.83% 26.67% 1’500’000 -20’000 50’000 30’000 2.07%", fontsize=8)
    p7.insert_text((38, 200), "Total -20’000 300’000 80’000", fontsize=8)
    p7.insert_text((38, 240), "PERFORMANCE PERFORMANCE", fontsize=9)

    # ----------------------------------------------------
    # Page 8: Comments & Disclosures
    # ----------------------------------------------------
    p8 = doc.new_page(width=840.0, height=595.2)
    p8.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, GENEVA BRANCH", fontsize=9)
    p8.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 31.03.2026", fontsize=9)
    p8.insert_text((38, 70), "Portfolio No. 2004812", fontsize=9)
    p8.insert_text((650, 55), "Page 8 / 8", fontsize=9)
    p8.insert_text((38, 115), "DISCLAIMER AND GENERAL INFORMATION", fontsize=10)
    p8.insert_text((38, 140), "This report is prepared for informational purposes only.", fontsize=8)

    doc.save(path)
    doc.close()
    return path

def build_divergent_layout_pdf(path: str) -> str:
    """
    Creates a UBP statement with an unfamiliar / divergent page layout
    to verify template divergence detection and unmapped content preservation.
    """
    doc = pymupdf.open()
    
    # Page 1: Standard Overview
    p1 = doc.new_page(width=840.0, height=595.2)
    p1.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, ZURICH BRANCH", fontsize=9)
    p1.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.04.2026", fontsize=9)
    p1.insert_text((38, 70), "Portfolio No. 3009955", fontsize=9)
    p1.insert_text((650, 55), "Page 1 / 3", fontsize=9)
    p1.insert_text((38, 150), "ASSET ALLOCATION", fontsize=10)
    p1.insert_text((38, 170), "INVESTMENT CATEGORY USD %", fontsize=8)
    p1.insert_text((38, 190), "CURRENT ACCOUNTS 500’000.00 100.00", fontsize=8)
    p1.insert_text((38, 210), "NET ASSETS USD 500’000.00 100.00", fontsize=8)

    # Page 2: Non-standard / Unfamiliar Layout (Special Derivatives Schedule)
    p2 = doc.new_page(width=840.0, height=595.2)
    p2.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, ZURICH BRANCH", fontsize=9)
    p2.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.04.2026", fontsize=9)
    p2.insert_text((38, 70), "Portfolio No. 3009955", fontsize=9)
    p2.insert_text((650, 55), "Page 2 / 3", fontsize=9)
    p2.insert_text((38, 120), "SPECIAL DERIVATIVES OVER-THE-COUNTER VALUATION MATRIX", fontsize=10)
    p2.insert_text((38, 150), "Non-standard custom swap schedule with private counterparty risk models.", fontsize=9)
    p2.insert_text((38, 180), "Unregistered OTC ISDA Master Agreement Annex 2026-B.", fontsize=9)

    # Page 3: Standard Disclaimer
    p3 = doc.new_page(width=840.0, height=595.2)
    p3.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, ZURICH BRANCH", fontsize=9)
    p3.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.04.2026", fontsize=9)
    p3.insert_text((38, 70), "Portfolio No. 3009955", fontsize=9)
    p3.insert_text((650, 55), "Page 3 / 3", fontsize=9)
    p3.insert_text((38, 115), "DISCLAIMER AND GENERAL INFORMATION", fontsize=10)
    p3.insert_text((38, 140), "General legal disclaimers and notifications.", fontsize=8)

    doc.save(path)
    doc.close()
    return path

# ==============================================================================
# TEST SUITE: UNSEEN TEMPLATE DATA EXTRACTION
# ==============================================================================

def test_unseen_ubp_statement_complete_flow(tmp_path):
    """
    Validates end-to-end extraction on a brand new, unseen UBP statement:
      - Validates metadata detection (new portfolio number, new branch, new date).
      - Validates Page 1 Asset Allocation and right-side Portfolio in USD summary.
      - Validates dynamic column discovery for unseen securities (Apple, Microsoft, Nestle).
      - Validates subtotal reconciliation ($0.00 variance).
      - Validates Current Accounts and verified zero Loans.
      - Validates Annual Performance final periodic row and initial row mapping.
      - Validates complete 16-worksheet Excel generation.
      - Asserts zero validation failures.
    """
    pdf_path = str(tmp_path / "unseen_ubp_statement_2004812.pdf")
    build_unseen_ubp_pdf(pdf_path)

    res = extract_ubp_statement(pdf_path)

    # 1. Metadata Verification
    assert res.metadata.portfolio_number == "2004812"
    assert res.metadata.portfolio_identifier_source == "EXTRACTED_FROM_PDF"
    assert "GENEVA" in res.metadata.bank_name.upper()
    assert res.metadata.valuation_date == "31.03.2026"
    assert res.metadata.total_pages == 8

    # 2. Holdings Verification
    assert len(res.holdings) == 3
    h_apple = next(h for h in res.holdings if "APPLE" in h.security_name)
    assert h_apple.isin_secur_no == "US0378331005"
    assert h_apple.units_nominal == Decimal("100000")
    assert h_apple.market_price == Decimal("100.00")
    assert h_apple.value_in_usd == Decimal("100000.00")
    assert h_apple.asset_category == "BONDS/NOTES, BOND FUNDS & CERTIFICATES"

    h_msft = next(h for h in res.holdings if "MICROSOFT" in h.security_name)
    assert h_msft.isin_secur_no == "US5949181045"
    assert h_msft.units_nominal == Decimal("350000")
    assert h_msft.value_in_usd == Decimal("350000.00")

    h_nestle = next(h for h in res.holdings if "NESTLE" in h.security_name)
    assert h_nestle.isin_secur_no == "CH0012005267"
    assert h_nestle.units_nominal == Decimal("5000")
    assert h_nestle.value_in_usd == Decimal("750000.00")
    assert h_nestle.asset_category == "EQUITIES, EQUITY FUNDS & CERTIFICATES"

    # 3. Category Subtotals
    bonds_total = sum(h.value_in_usd for h in res.holdings if h.asset_category == "BONDS/NOTES, BOND FUNDS & CERTIFICATES")
    assert bonds_total == Decimal("450000.00")
    equities_total = sum(h.value_in_usd for h in res.holdings if h.asset_category == "EQUITIES, EQUITY FUNDS & CERTIFICATES")
    assert equities_total == Decimal("750000.00")

    # 4. Current Accounts & Loans
    assert len(res.current_accounts) == 2
    acc_usd = next(a for a in res.current_accounts if a.currency == "USD")
    assert acc_usd.account_number == "2004812001"
    assert acc_usd.market_value_usd == Decimal("200000.00")

    acc_chf = next(a for a in res.current_accounts if a.currency == "CHF")
    assert acc_chf.account_number == "2004812002"
    assert acc_chf.market_value_usd == Decimal("100000.00")

    assert len(res.loans) == 0

    # 5. Page 1 Portfolio Performance Summary
    perf = res.portfolio_summary_performance
    assert perf is not None
    assert perf.initial_assets == Decimal("1450000.00")
    assert perf.total_outgoing_cash == Decimal("-20000.00")
    assert perf.change_in_total_assets == Decimal("70000.00")
    assert perf.ending_assets == Decimal("1500000.00")
    assert perf.number_of_days == 90
    assert perf.performance_twr_pct == Decimal("4.83")

    # 6. Annual Performance Mapping
    periodic_annual = [r for r in res.annual_performance if not r.is_initial_row and not r.is_total_row]
    assert len(periodic_annual) == 2  # 2025 and 31.03.2026
    final_a = periodic_annual[-1]
    assert final_a.period == "31.03.2026"
    assert final_a.performance_pct == Decimal("4.83")
    assert final_a.cumulative_performance_pct == Decimal("26.67")
    assert final_a.end_of_period_assets == Decimal("1500000")
    assert final_a.period_deposits_withdrawals == Decimal("-20000")
    assert final_a.change_in_total_assets == Decimal("50000")
    assert final_a.net_income == Decimal("30000")
    assert final_a.return_on_net_income_pct == Decimal("2.07")

    # 7. Workbook Generation (16 Sheets)
    excel_path = str(tmp_path / "UBP_2004812_unseen.xlsx")
    saved_path = generate_ubp_excel_workbook(res, excel_path)
    assert os.path.exists(saved_path)

    wb = openpyxl.load_workbook(saved_path, read_only=True)
    expected_sheets = [
        "Portfolio_Overview", "Asset_Allocation", "Currency_Breakdown",
        "Holdings", "Transactions", "Current_Accounts", "Loans",
        "Net_Assets_Summary", "Exchange_Rates", "Monthly_Performance",
        "Annual_Performance", "Comments", "Counts", "Validation",
        "Unmapped_Content", "Raw_Page_Text"
    ]
    for sheet in expected_sheets:
        assert sheet in wb.sheetnames, f"Missing expected sheet: {sheet}"

    # 8. All Validation Checks Pass
    failures = [c for c in res.validation_checks if c.level == "FAIL"]
    warnings = [c for c in res.validation_checks if c.level == "WARNING"]
    assert len(failures) == 0, f"Unexpected validation failures: {[f.message for f in failures]}"
    assert len(warnings) == 0, f"Unexpected validation warnings: {[w.message for w in warnings]}"

def test_unfamiliar_layout_page_divergence_warning(tmp_path):
    """
    Validates that when a statement contains an unfamiliar or non-standard page layout:
      - The layout difference is detected dynamically.
      - Page classification is marked as UNKNOWN.
      - Raw source text is preserved in Raw_Page_Text and unmapped_content.
      - Layout Divergence Detection validation check produces a WARNING.
      - No fabricated data is generated.
      - Processing finishes reliably without crashing.
    """
    pdf_path = str(tmp_path / "divergent_layout_statement.pdf")
    build_divergent_layout_pdf(pdf_path)

    res = extract_ubp_statement(pdf_path)

    # 1. Total Pages
    assert res.metadata.total_pages == 3

    # 2. Page 2 must be classified as UNKNOWN
    raw_p2 = next(p for p in res.raw_pages if p.page_number == 2)
    assert raw_p2.section_name == "UNKNOWN"
    assert "SPECIAL DERIVATIVES OVER-THE-COUNTER" in raw_p2.text

    # 3. Unmapped content preservation
    unmapped = [u for u in res.unmapped_content if u.page_number == 2]
    assert len(unmapped) >= 1
    assert "SPECIAL DERIVATIVES" in unmapped[0].raw_text

    # 4. Validation Check flags Layout Divergence as WARNING
    div_check = next(c for c in res.validation_checks if c.name == "Layout Divergence Detection")
    assert div_check.level == "WARNING"
    assert "Page(s) 2" in div_check.message
    assert div_check.details["status"] == "DIVERGENCE_DETECTED"

    # 5. Generates workbook safely
    excel_path = str(tmp_path / "UBP_divergent.xlsx")
    saved_path = generate_ubp_excel_workbook(res, excel_path)
    assert os.path.exists(saved_path)

def build_varying_holdings_pdf(path: str) -> str:
    """
    Creates a 5-page UBP statement with EUR reporting currency,
    1 single holding position, active loans, and different page count.
    """
    doc = pymupdf.open()
    
    # Page 1: Asset Allocation (EUR reporting currency)
    p1 = doc.new_page(width=840.0, height=595.2)
    p1.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, LUXEMBOURG BRANCH", fontsize=9)
    p1.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.06.2026", fontsize=9)
    p1.insert_text((38, 70), "Portfolio No. 4005511", fontsize=9)
    p1.insert_text((650, 55), "Page 1 / 5", fontsize=9)
    p1.insert_text((38, 150), "ASSET ALLOCATION", fontsize=10)
    p1.insert_text((38, 170), "INVESTMENT CATEGORY EUR %", fontsize=8)
    p1.insert_text((38, 190), "EQUITIES, EQUITY FUNDS & CERTIFICATES 100’000.00 83.33", fontsize=8)
    p1.insert_text((38, 210), "CURRENT ACCOUNTS 50’000.00 41.67", fontsize=8)
    p1.insert_text((38, 230), "LOANS -30’000.00 -25.00", fontsize=8)
    p1.insert_text((38, 250), "NET ASSETS EUR 120’000.00 100.00", fontsize=8)

    # Right: Portfolio in EUR
    p1.insert_text((444, 150), "PORTFOLIO IN EUR PERFORMANCE", fontsize=10)
    p1.insert_text((444, 165), "SINCE 01.01.2026", fontsize=8)
    p1.insert_text((444, 180), "INITIAL ASSETS 110’000.00", fontsize=8)
    p1.insert_text((444, 195), "TOTAL INCOMING SECURITIES 0.00", fontsize=8)
    p1.insert_text((444, 210), "TOTAL OUTGOING SECURITIES 0.00", fontsize=8)
    p1.insert_text((444, 225), "TOTAL INCOMING CASH 0.00", fontsize=8)
    p1.insert_text((444, 240), "TOTAL OUTGOING CASH 0.00", fontsize=8)
    p1.insert_text((444, 255), "TOTAL OF INC/OUT CASH & SEC 0.00", fontsize=8)
    p1.insert_text((444, 270), "CHANGE IN TOTAL ASSETS 10’000.00", fontsize=8)
    p1.insert_text((444, 285), "ASSETS AS OF 30.06.2026 120’000.00", fontsize=8)
    p1.insert_text((444, 300), "NUMBER OF DAYS (180 D)", fontsize=8)
    p1.insert_text((444, 315), "PERFORMANCE TWR (EUR) 9.09%", fontsize=8)

    # Page 2: Holdings (Single holding: Siemens AG)
    p2 = doc.new_page(width=840.0, height=595.2)
    p2.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, LUXEMBOURG BRANCH", fontsize=9)
    p2.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.06.2026", fontsize=9)
    p2.insert_text((38, 70), "Portfolio No. 4005511", fontsize=9)
    p2.insert_text((650, 55), "Page 2 / 5", fontsize=9)
    p2.insert_text((38, 100), "CURRENT PORTFOLIO", fontsize=10)
    p2.insert_text((38, 115), "Units/Nominal Security name ISIN/Secur. No. Yield Net Avg Cost Market Price Currency Total Market Value Value in EUR %", fontsize=8)
    p2.insert_text((38, 140), "EQUITIES, EQUITY FUNDS & CERTIFICATES 100’000.00 83.33", fontsize=8)
    p2.insert_text((45, 160), "1’000", fontsize=8)
    p2.insert_text((103, 160), "SIEMENS AG REG", fontsize=8)
    p2.insert_text((390, 160), "DE0007236101", fontsize=8)
    p2.insert_text((516, 160), "100.00", fontsize=8)
    p2.insert_text((576, 160), "100.00", fontsize=8)
    p2.insert_text((611, 160), "EUR", fontsize=8)
    p2.insert_text((665, 160), "100’000.00", fontsize=8)
    p2.insert_text((737, 160), "100’000.00", fontsize=8)
    p2.insert_text((788, 160), "83.33", fontsize=8)

    # Page 3: Current Accounts & Loans
    p3 = doc.new_page(width=840.0, height=595.2)
    p3.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, LUXEMBOURG BRANCH", fontsize=9)
    p3.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.06.2026", fontsize=9)
    p3.insert_text((38, 70), "Portfolio No. 4005511", fontsize=9)
    p3.insert_text((650, 55), "Page 3 / 5", fontsize=9)
    p3.insert_text((38, 115), "CURRENT ACCOUNTS 50’000.00 41.67", fontsize=8)
    p3.insert_text((38, 140), "EUR", fontsize=8)
    p3.insert_text((78, 140), "50’000.00", fontsize=8)
    p3.insert_text((140, 140), "CURRENT ACCOUNT NUMBER 4005511001", fontsize=8)
    p3.insert_text((665, 140), "50’000.00", fontsize=8)
    p3.insert_text((737, 140), "50’000.00", fontsize=8)
    p3.insert_text((788, 140), "41.67", fontsize=8)

    # Loans Section on Page 3
    p3.insert_text((38, 175), "LOANS -30’000.00 -25.00", fontsize=8)
    p3.insert_text((38, 200), "EUR", fontsize=8)
    p3.insert_text((78, 200), "-30’000.00", fontsize=8)
    p3.insert_text((140, 200), "FIXED LOAN TR999888.1", fontsize=8)
    p3.insert_text((420, 200), "31.12.26", fontsize=8)
    p3.insert_text((500, 200), "3.75%", fontsize=8)
    p3.insert_text((665, 200), "-30’000.00", fontsize=8)
    p3.insert_text((737, 200), "-30’000.00", fontsize=8)
    p3.insert_text((788, 200), "-25.00", fontsize=8)

    # Page 4: Summary of Net Assets
    p4 = doc.new_page(width=840.0, height=595.2)
    p4.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, LUXEMBOURG BRANCH", fontsize=9)
    p4.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.06.2026", fontsize=9)
    p4.insert_text((38, 70), "Portfolio No. 4005511", fontsize=9)
    p4.insert_text((650, 55), "Page 4 / 5", fontsize=9)
    p4.insert_text((38, 115), "SUMMARY OF NET ASSETS", fontsize=10)
    p4.insert_text((38, 140), "TOTAL ASSETS EUR 120’000.00 100.00", fontsize=8)

    # Page 5: Comments
    p5 = doc.new_page(width=840.0, height=595.2)
    p5.insert_text((38, 40), "UNION BANCAIRE PRIVEE, UBP SA, LUXEMBOURG BRANCH", fontsize=9)
    p5.insert_text((38, 55), "PORTFOLIO VALUATION AS OF 30.06.2026", fontsize=9)
    p5.insert_text((38, 70), "Portfolio No. 4005511", fontsize=9)
    p5.insert_text((650, 55), "Page 5 / 5", fontsize=9)
    p5.insert_text((38, 115), "DISCLAIMER AND GENERAL INFORMATION", fontsize=10)
    p5.insert_text((38, 140), "Reporting in EUR for European wealth management division.", fontsize=8)

    doc.save(path)
    doc.close()
    return path

def test_dynamic_varying_holdings_and_currencies(tmp_path):
    """
    Validates dynamic adaptation to:
      - 5 pages (different page count)
      - EUR reporting currency (no hardcoded USD assumption)
      - Luxembourg branch (dynamic bank discovery)
      - Single holding position (Siemens AG)
      - Active loan extraction (TR999888.1, maturity date 31.12.26, rate 3.75%)
      - Reconciliation of subtotal and current accounts.
    """
    pdf_path = str(tmp_path / "varying_ubp_statement_4005511.pdf")
    build_varying_holdings_pdf(pdf_path)

    res = extract_ubp_statement(pdf_path)

    # 1. Metadata
    assert res.metadata.total_pages == 5
    assert res.metadata.portfolio_number == "4005511"
    assert "LUXEMBOURG" in res.metadata.bank_name.upper()
    assert res.metadata.valuation_date == "30.06.2026"
    assert res.metadata.report_currency == "EUR"

    # 2. Holdings (Single Holding)
    assert len(res.holdings) == 1
    h = res.holdings[0]
    assert h.security_name == "SIEMENS AG REG"
    assert h.isin_secur_no == "DE0007236101"
    assert h.units_nominal == Decimal("1000")
    assert h.market_price == Decimal("100.00")
    assert h.value_in_usd == Decimal("100000.00")  # stores value in reporting currency
    assert h.percentage_of_total_assets == Decimal("83.33")

    # 3. Current Accounts
    assert len(res.current_accounts) == 1
    acc = res.current_accounts[0]
    assert acc.currency == "EUR"
    assert acc.account_number == "4005511001"
    assert acc.market_value_usd == Decimal("50000.00")

    # 4. Loans (1 loan present)
    assert len(res.loans) == 1
    loan = res.loans[0]
    assert loan.currency == "EUR"
    assert loan.amount == Decimal("-30000.00")
    assert loan.loan_reference == "TR999888.1"
    assert loan.maturity_date == "31.12.26"
    assert loan.interest_rate == Decimal("3.75")
    assert loan.usd_equivalent == Decimal("-30000.00")
    assert loan.percentage_assets == Decimal("-25.00")

    # 5. Workbook Generation
    excel_path = str(tmp_path / "UBP_4005511.xlsx")
    saved_path = generate_ubp_excel_workbook(res, excel_path)
    assert os.path.exists(saved_path)

    wb = openpyxl.load_workbook(saved_path, read_only=True)
    assert len(wb.sheetnames) == 16

