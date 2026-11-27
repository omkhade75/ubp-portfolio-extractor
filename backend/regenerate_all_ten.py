import os
import sys
import shutil
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook
from app.config import SAMPLE_PDFS_DIR
import openpyxl

docs = [
    (str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf"), "1_UBP_1002590_Jul2025.xlsx"),
    (str(SAMPLE_PDFS_DIR / "2_UBP_1002590_Oct2025.pdf"), "2_UBP_1002590_Oct2025.xlsx"),
    (str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf"), "3_UBP_1002590_Jan2026.xlsx"),
    (str(SAMPLE_PDFS_DIR / "4_UBP_1002591_Jul2025.pdf"), "4_UBP_1002591_Jul2025.xlsx"),
    (str(SAMPLE_PDFS_DIR / "5_UBP_1002591_Oct2025.pdf"), "5_UBP_1002591_Oct2025.xlsx"),
    (r"D:\UserData\Downloads\Synthetic_Portfolio_Test_01.pdf", "UBP_SYN-4101_Synthetic_Portfolio_Test_01.xlsx"),
    (r"D:\UserData\Downloads\Synthetic_Portfolio_Test_02.pdf", "UBP_SYN-5202_Synthetic_Portfolio_Test_02.xlsx"),
    (r"D:\UserData\Downloads\Synthetic_Portfolio_Test_03.pdf", "UBP_SYN-6303_Synthetic_Portfolio_Test_03.xlsx"),
    (r"D:\UserData\Downloads\Synthetic_Portfolio_Test_04.pdf", "UBP_SYN-7404_Synthetic_Portfolio_Test_04.xlsx"),
    (r"D:\UserData\Downloads\Synthetic_Portfolio_Test_05.pdf", "UBP_SYN-8505_Synthetic_Portfolio_Test_05.xlsx"),
]

out_dir = r"D:\zz\UBP_Extraction_App\test_outputs_audit"
os.makedirs(out_dir, exist_ok=True)
dl_dir = r"D:\UserData\Downloads"

summary_results = []

for pdf_path, xlsx_name in docs:
    print(f"Processing {os.path.basename(pdf_path)}...")
    res = extract_ubp_statement(pdf_path)
    audit_out = os.path.join(out_dir, xlsx_name)
    wb_path = generate_ubp_excel_workbook(res, audit_out)
    dl_out = os.path.join(dl_dir, xlsx_name)
    shutil.copy2(wb_path, dl_out)
    
    wb = openpyxl.load_workbook(wb_path, data_only=True)
    sheet_count = len(wb.sheetnames)
    
    fails = [c for c in res.validation_checks if c.level == "FAIL"]
    warns = [c for c in res.validation_checks if c.level == "WARNING"]
    
    ending_assets = res.portfolio_summary_performance.ending_assets if res.portfolio_summary_performance else None
    twr = res.portfolio_summary_performance.performance_twr_pct if res.portfolio_summary_performance else None
    
    summary_results.append({
        "pdf": os.path.basename(pdf_path),
        "portfolio": res.metadata.portfolio_number,
        "val_date": res.metadata.valuation_date,
        "ending_assets": str(ending_assets),
        "twr": f"{twr}%" if twr is not None else "N/A",
        "holdings_count": len(res.holdings),
        "accounts_count": len(res.current_accounts),
        "loans_count": len(res.loans),
        "annual_count": len(res.annual_performance),
        "monthly_count": len(res.monthly_performance),
        "sheets": sheet_count,
        "fails": len(fails),
        "warns": len(warns),
        "sheet_names": wb.sheetnames,
        "xlsx_audit": audit_out,
        "xlsx_dl": dl_out,
    })

print("\n" + "=" * 125)
header = f"{'PDF':<35} | {'PORTFOLIO':<10} | {'VAL DATE':<10} | {'NET ASSETS':<15} | {'TWR %':<8} | {'HLD':<4} | {'ACC':<4} | {'LN':<3} | {'SHT':<4} | {'FAIL':<4}"
print(header)
print("-" * 125)
for s in summary_results:
    line = f"{s['pdf']:<35} | {s['portfolio']:<10} | {s['val_date']:<10} | {s['ending_assets']:<15} | {s['twr']:<8} | {s['holdings_count']:<4} | {s['accounts_count']:<4} | {s['loans_count']:<4} | {s['sheets']:<4} | {s['fails']:<4}"
    print(line)
print("=" * 125)

# Save json summary for reporting
import json
with open(os.path.join(out_dir, "ten_document_summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary_results, f, indent=2)
print("Done! Summary written to ten_document_summary.json")
