import openpyxl
import fitz
from pathlib import Path
from decimal import Decimal
import json

BASE_DIR = Path(r"D:\zz\UBP_Extraction_App")
PDF_DIR = Path(r"D:\zz\Extraction_PDFs_UBP")
OUTPUT_DIR = BASE_DIR / "output"

pdf_files = [
    "1_UBP_1002590_Jul2025.pdf",
    "2_UBP_1002590_Oct2025.pdf",
    "3_UBP_1002590_Jan2026.pdf",
    "4_UBP_1002591_Jul2025.pdf",
    "5_UBP_1002591_Oct2025.pdf"
]

print("=== CATEGORY SUBTOTAL RECONCILIATION AUDIT ===")

for pdf_name in pdf_files:
    stem = pdf_name.replace(".pdf", "")
    matching = [f for f in OUTPUT_DIR.glob(f"*{stem}*.xlsx") if f.is_file() and not f.name.startswith("~")]
    if not matching:
        continue
    wb = openpyxl.load_workbook(str(matching[0]), data_only=True)
    ws = wb["Holdings"]
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    
    # Group extracted holdings by category
    cat_holdings = {}
    for r in rows[1:]:
        if not any(r): continue
        d = dict(zip(headers, r))
        cat = d.get("Asset_Category")
        val = Decimal(str(d.get("Value_in_USD") or 0))
        acc = Decimal(str(d.get("Accrued_Interest_USD") or d.get("Accrued_Interest") or 0))
        if cat not in cat_holdings:
            cat_holdings[cat] = {"val_sum": Decimal(0), "acc_sum": Decimal(0), "count": 0}
        cat_holdings[cat]["val_sum"] += val
        cat_holdings[cat]["acc_sum"] += acc
        cat_holdings[cat]["count"] += 1
        
    # Get PDF source category subtotals from Currency Breakdown or Asset Allocation
    ws_cb = wb["Currency_Breakdown"]
    cb_rows = list(ws_cb.iter_rows(values_only=True))
    cb_headers = cb_rows[0]
    cb_map = {}
    for r in cb_rows[1:]:
        if not any(r): continue
        d = dict(zip(cb_headers, r))
        ac = d.get("Asset_Class")
        tot = d.get("Total_000s_USD")
        if ac and tot is not None:
            cb_map[ac] = tot
            
    print(f"\n--- {pdf_name} ---")
    for cat, data in cat_holdings.items():
        vsum = data["val_sum"]
        asum = data["acc_sum"]
        total_cat = vsum + (asum if "STRUCTURED" in cat else Decimal(0))
        print(f"  Category: {cat} (Count: {data['count']})")
        print(f"    Holdings USD Value Sum: {vsum:.2f}")
        if asum > 0:
            print(f"    Accrued Int Sum: {asum:.2f} -> Total Cat Sum: {total_cat:.2f}")
