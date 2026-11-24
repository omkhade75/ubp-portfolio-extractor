import os
import sys
from pathlib import Path
import openpyxl
import fitz  # PyMuPDF
from decimal import Decimal

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

print("Starting Workbook & PDF Audit Inspection...")

for pdf_name in pdf_files:
    pdf_path = PDF_DIR / pdf_name
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    print(f"\n==================================================")
    print(f"PDF: {pdf_name} (Pages: {page_count})")
    
    # Locate corresponding excel file
    matching_excels = list(OUTPUT_DIR.glob(f"*{pdf_name[:15]}*.xlsx"))
    if not matching_excels:
        # Check by prefix
        num_prefix = pdf_name.split("_")[0]
        matching_excels = [f for f in OUTPUT_DIR.glob("*.xlsx") if f"_{num_prefix}_" in f.name or f.name.startswith(f"UBP_{num_prefix}_")]
    
    print(f"Matching Excels in output: {[f.name for f in matching_excels]}")
    if matching_excels:
        target_excel = matching_excels[0]
        wb = openpyxl.load_workbook(str(target_excel), data_only=True)
        print(f"Loaded Excel: {target_excel.name}")
        print(f"Worksheets ({len(wb.sheetnames)}): {wb.sheetnames}")
        
        # Check sheets
        for sname in ["Holdings", "Current_Accounts", "Loans", "Monthly_Performance", "Annual_Performance", "Currency_Breakdown", "Validation_Report", "Transactions", "Metadata"]:
            if sname in wb.sheetnames:
                ws = wb[sname]
                print(f"  Sheet '{sname}': max_row={ws.max_row}, max_col={ws.max_column}")
