import os, glob, openpyxl
from decimal import Decimal
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook
from app.config import SAMPLE_PDFS_DIR

statements = [
    (str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf"), "1_UBP_1002590_Jul2025"),
    (str(SAMPLE_PDFS_DIR / "2_UBP_1002590_Oct2025.pdf"), "2_UBP_1002590_Oct2025"),
    (str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf"), "3_UBP_1002590_Jan2026"),
    (str(SAMPLE_PDFS_DIR / "4_UBP_1002591_Jul2025.pdf"), "4_UBP_1002591_Jul2025"),
    (str(SAMPLE_PDFS_DIR / "5_UBP_1002591_Oct2025.pdf"), "5_UBP_1002591_Oct2025"),
]

# Add synthetic statements if found
syn1 = glob.glob(r"D:\zz\UBP_Extraction_App\input\*\Synthetic_Portfolio_Training_Report.pdf")
syn2 = glob.glob(r"D:\zz\UBP_Extraction_App\input\*\Synthetic_Portfolio_Training_Report_02.pdf")
if syn1:
    statements.append((syn1[0], "Synthetic_01"))
if syn2:
    statements.append((syn2[0], "Synthetic_02"))

out_dir = r"D:\zz\UBP_Extraction_App\output\final_fidelity_workbooks"
os.makedirs(out_dir, exist_ok=True)

print("| Statement | Holdings | Blank vs Zero | Flow Recon Status | Flow Period | Diff / Discrepancy | Excel Generated |")
print("|---|---|---|---|---|---|---|")

for path, label in statements:
    if not os.path.exists(path):
        continue
    res = extract_ubp_statement(path)
    h_count = len(res.holdings)
    
    # Check Missing vs Zero
    mvz_chk = next((c for c in res.validation_checks if c.name == "Missing vs Zero Fields Integrity"), None)
    mvz_str = f"{mvz_chk.level} (zeros={mvz_chk.details.get('explicit_zeros')}, blanks={mvz_chk.details.get('source_blanks')})" if mvz_chk else "N/A"
    
    # Check Flow Recon
    flow_chk = next((c for c in res.validation_checks if c.name == "Portfolio Flow vs Performance Flow"), None)
    if flow_chk:
        flow_status = flow_chk.details.get("reconciliation_status", flow_chk.level)
        flow_period = flow_chk.details.get("reporting_period", "N/A")
        diff_val = flow_chk.details.get("difference") or flow_chk.details.get("discrepancy") or "0.00"
    else:
        flow_status = "N/A"
        flow_period = "N/A"
        diff_val = "N/A"
        
    wb_path = generate_ubp_excel_workbook(res, out_dir)
    excel_fn = os.path.basename(wb_path)
    
    # Verify holding IE00BMY47228 in Excel if present
    zero_h = next((h for h in res.holdings if "IE00BMY47228" in (h.isin_secur_no or "") and h.market_price == Decimal("0.00")), None)
    if zero_h:
        wb = openpyxl.load_workbook(wb_path, data_only=True)
        ws = wb["Holdings"]
        headers = [c.value for c in ws[1]]
        isin_col = headers.index("ISIN_Secur_No") + 1
        pct_col = headers.index("Percentage_Total_Assets") + 1
        price_col = headers.index("Market_Price") + 1
        for r in range(2, ws.max_row + 1):
            if ws.cell(r, isin_col).value == "IE00BMY47228" and (ws.cell(r, price_col).value == 0):
                pct_cell = ws.cell(r, pct_col).value
                assert pct_cell is None, f"Excel cell for blank percentage is {pct_cell}, expected None"
    
    print(f"| {label} | {h_count} | {mvz_str} | {flow_status} | {flow_period} | {diff_val} USD | {excel_fn} |")
