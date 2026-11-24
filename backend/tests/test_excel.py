import os
import openpyxl
import pytest
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook
from app.config import SAMPLE_PDFS_DIR, OUTPUT_DIR

def test_workbook_generation():
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    out_xlsx = generate_ubp_excel_workbook(res, str(OUTPUT_DIR))
    assert os.path.exists(out_xlsx)
    
    wb = openpyxl.load_workbook(out_xlsx)
    assert len(wb.sheetnames) == 16
    assert "Holdings" in wb.sheetnames
    assert "Validation" in wb.sheetnames
    assert "Transactions" in wb.sheetnames
    assert "Counts" in wb.sheetnames

    # Check holdings sheet
    ws_h = wb["Holdings"]
    assert ws_h.max_row == 13  # 1 header + 12 holdings
    assert ws_h.freeze_panes == "A2"

    # Check Portfolio_Overview performance section
    ws_po = wb["Portfolio_Overview"]
    found_perf_section = False
    for r in range(1, ws_po.max_row + 1):
        if ws_po.cell(r, 1).value == "PORTFOLIO PERFORMANCE & ASSET FLOW SUMMARY (USD)":
            found_perf_section = True
            break
    assert found_perf_section

    # Check Loans sheet has NOT_PRESENT status and no zero-amount rows
    ws_l = wb["Loans"]
    assert ws_l.cell(2, 1).value == "STATUS: NOT_PRESENT"
    # Ensure column 3 (amount) is None, not 0
    assert ws_l.cell(2, 3).value is None

    # Check Currency_Breakdown has dynamic currency header, no HKD_EUR
    ws_cb = wb["Currency_Breakdown"]
    cb_headers = [ws_cb.cell(1, c).value for c in range(1, ws_cb.max_column + 1)]
    assert "HKD_000s" in cb_headers
    assert "HKD_Percentage" in cb_headers
    assert "HKD_EUR_000s" not in cb_headers

    # Check Annual_Performance row 12 is PERIODIC
    ws_ap = wb["Annual_Performance"]
    assert ws_ap.cell(12, 1).value == "30.06.2025"
    assert ws_ap.cell(12, 9).value == "PERIODIC"
    assert ws_ap.cell(12, 2).value == pytest.approx(0.0317)
    assert ws_ap.cell(12, 4).value == 2267669
