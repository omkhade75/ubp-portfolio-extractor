import os
import sys
from pathlib import Path
import openpyxl
import fitz  # PyMuPDF
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

audit_results = {}

for pdf_name in pdf_files:
    pdf_path = PDF_DIR / pdf_name
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    
    # Locate workbook
    stem = pdf_name.replace(".pdf", "")
    matching = [f for f in OUTPUT_DIR.glob(f"*{stem}*.xlsx") if f.is_file() and not f.name.startswith("~")]
    
    excel_file = matching[0] if matching else None
    wb = openpyxl.load_workbook(str(excel_file), data_only=True) if excel_file else None
    
    res = {
        "filename": pdf_name,
        "source_pages": page_count,
        "excel_name": excel_file.name if excel_file else None,
        "sheets": wb.sheetnames if wb else [],
        "sheet_stats": {},
        "holdings": [],
        "accounts": [],
        "loans": [],
        "currency_breakdown": [],
        "monthly_perf": [],
        "annual_perf": [],
        "net_assets_summary": {},
        "exchange_rates": [],
        "unmapped": [],
        "validation_checks": []
    }
    
    if wb:
        for sname in wb.sheetnames:
            ws = wb[sname]
            res["sheet_stats"][sname] = {
                "max_row": ws.max_row,
                "max_col": ws.max_column
            }
        
        # Read holdings
        if "Holdings" in wb.sheetnames:
            ws = wb["Holdings"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r):
                    res["holdings"].append(dict(zip(headers, r)))
                    
        # Read current accounts
        if "Current_Accounts" in wb.sheetnames:
            ws = wb["Current_Accounts"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r):
                    res["accounts"].append(dict(zip(headers, r)))

        # Read loans
        if "Loans" in wb.sheetnames:
            ws = wb["Loans"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r) and r[0] != "None":
                    res["loans"].append(dict(zip(headers, r)))

        # Read monthly perf
        if "Monthly_Performance" in wb.sheetnames:
            ws = wb["Monthly_Performance"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r):
                    res["monthly_perf"].append(dict(zip(headers, r)))

        # Read annual perf
        if "Annual_Performance" in wb.sheetnames:
            ws = wb["Annual_Performance"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r):
                    res["annual_perf"].append(dict(zip(headers, r)))

        # Read Net Assets Summary
        if "Net_Assets_Summary" in wb.sheetnames:
            ws = wb["Net_Assets_Summary"]
            rows = list(ws.iter_rows(values_only=True))
            for r in rows[1:]:
                if len(r) >= 2 and r[0]:
                    res["net_assets_summary"][str(r[0])] = r[1]

        # Read Currency Breakdown
        if "Currency_Breakdown" in wb.sheetnames:
            ws = wb["Currency_Breakdown"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r):
                    res["currency_breakdown"].append(dict(zip(headers, r)))

        # Read Exchange Rates
        if "Exchange_Rates" in wb.sheetnames:
            ws = wb["Exchange_Rates"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r):
                    res["exchange_rates"].append(dict(zip(headers, r)))

        # Read Unmapped Content
        if "Unmapped_Content" in wb.sheetnames:
            ws = wb["Unmapped_Content"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r) and r[0] != "None":
                    res["unmapped"].append(dict(zip(headers, r)))

        # Read Validation
        if "Validation" in wb.sheetnames:
            ws = wb["Validation"]
            rows = list(ws.iter_rows(values_only=True))
            headers = rows[0] if rows else []
            for r in rows[1:]:
                if any(r):
                    res["validation_checks"].append(dict(zip(headers, r)))

    audit_results[pdf_name] = res

# Save summary json
with open(BASE_DIR / "audit_summary.json", "w", encoding="utf-8") as f:
    json.dump(audit_results, f, indent=2, default=str)

print("Saved audit_summary.json successfully.")
for k, v in audit_results.items():
    print(f"\n{k}:")
    print(f"  Holdings count: {len(v['holdings'])}")
    print(f"  Accounts count: {len(v['accounts'])}")
    print(f"  Loans count: {len(v['loans'])}")
    print(f"  Monthly perf: {len(v['monthly_perf'])}")
    print(f"  Annual perf: {len(v['annual_perf'])}")
    print(f"  Currency breakdown: {len(v['currency_breakdown'])}")
    print(f"  Exchange rates: {len(v['exchange_rates'])}")
    print(f"  Unmapped rows: {len(v['unmapped'])}")
    print(f"  Validation rows: {len(v['validation_checks'])}")
