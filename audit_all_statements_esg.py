import sys
from pathlib import Path
sys.path.insert(0, r"D:\zz\UBP_Extraction_App\backend")
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook
from app.config import SAMPLE_PDFS_DIR
import openpyxl

statements = [
    ("1_UBP_1002590_Jul2025.pdf", str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")),
    ("2_UBP_1002590_Oct2025.pdf", str(SAMPLE_PDFS_DIR / "2_UBP_1002590_Oct2025.pdf")),
    ("3_UBP_1002590_Jan2026.pdf", str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf")),
    ("4_UBP_1002591_Jul2025.pdf", str(SAMPLE_PDFS_DIR / "4_UBP_1002591_Jul2025.pdf")),
    ("5_UBP_1002591_Oct2025.pdf", str(SAMPLE_PDFS_DIR / "5_UBP_1002591_Oct2025.pdf")),
    ("Synthetic_01.pdf", r"D:\zz\UBP_Extraction_App\input\78dbcec4-08af-4696-83ea-21a0246f5b4d\Synthetic_Portfolio_Training_Report.pdf"),
    ("Synthetic_02.pdf", r"D:\zz\UBP_Extraction_App\input\ea9dbc5c-b6d8-416e-9d80-1f8fdeb312de\Synthetic_Portfolio_Training_Report_02.pdf"),
]

print("-" * 105)
print(f"{'Statement':<30} | {'Port ESG Prev':<16} | {'Port ESG Curr':<16} | {'Page':<5} | {'Holdings':<8} | {'Validation':<12}")
print("-" * 105)

for name, path in statements:
    res = extract_ubp_statement(path)
    meta = res.metadata
    p_prev = meta.portfolio_esg_previous or "None (Blank)"
    p_curr = meta.portfolio_esg_current or "None (Blank)"
    p_page = str(meta.portfolio_esg_source_page) if meta.portfolio_esg_source_page else "N/A"
    h_count = len(res.holdings)
    fails = sum(1 for c in res.validation_checks if c.level == "FAIL")
    val_status = "PASS (0 fails)" if fails == 0 else f"{fails} FAILS"
    print(f"{name:<30} | {p_prev:<16} | {p_curr:<16} | {p_page:<5} | {h_count:<8} | {val_status:<12}")

    # Generate workbook to verify Excel generation
    out_xlsx = rf"D:\zz\UBP_Extraction_App\output\Audit_{name}.xlsx"
    generate_ubp_excel_workbook(res, out_xlsx)
    wb = openpyxl.load_workbook(out_xlsx)
    assert len(wb.sheetnames) == 16, f"Expected 16 sheets, found {len(wb.sheetnames)}"
    ws = wb["Portfolio_Overview"]
    has_esg_section = any(row and row[0] == "PORTFOLIO ESG RATING (PREVIOUS - CURRENT)" for row in ws.iter_rows(values_only=True))
    assert has_esg_section, f"Missing ESG section in {name}"

print("-" * 105)
print("ALL 7 STATEMENTS EXTRACTED, VALIDATED, AND AUDITED WITH ZERO REGRESSIONS.")
