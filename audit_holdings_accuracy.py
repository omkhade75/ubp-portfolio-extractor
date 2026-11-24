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

audit_holdings_report = []

for pdf_name in pdf_files:
    pdf_path = PDF_DIR / pdf_name
    stem = pdf_name.replace(".pdf", "")
    matching = [f for f in OUTPUT_DIR.glob(f"*{stem}*.xlsx") if f.is_file() and not f.name.startswith("~")]
    if not matching:
        continue
    excel_file = matching[0]
    wb = openpyxl.load_workbook(str(excel_file), data_only=True)
    ws = wb["Holdings"]
    
    rows = list(ws.iter_rows(values_only=True))
    headers = rows[0]
    h_data = [dict(zip(headers, r)) for r in rows[1:] if any(r)]
    
    # Also read raw PDF holdings pages
    doc = fitz.open(str(pdf_path))
    
    # Find holdings pages
    holdings_pages = []
    for pno in range(len(doc)):
        text = doc[pno].get_text("text").upper()
        if "UNITS/NOMINAL" in text and "SECURITY NAME" in text:
            holdings_pages.append(pno + 1)
            
    print(f"\n==========================================")
    print(f"File: {pdf_name}")
    print(f"  Holdings Pages in PDF: {holdings_pages}")
    print(f"  Extracted Holdings in Excel: {len(h_data)}")
    
    # Check each holding
    file_record = {
        "pdf": pdf_name,
        "holdings_pages": holdings_pages,
        "holdings_count": len(h_data),
        "holdings": []
    }
    
    for h in h_data:
        h_info = {
            "id": h.get("Holding_ID"),
            "category": h.get("Asset_Category"),
            "name": h.get("Security_Name"),
            "isin": h.get("ISIN_Secur_No"),
            "units": h.get("Units_Nominal"),
            "cost": h.get("Net_Average_Cost"),
            "cost_curr": h.get("Cost_Currency"),
            "price": h.get("Market_Price"),
            "price_curr": h.get("Market_Price_Currency"),
            "price_date": h.get("Market_Price_Date"),
            "market_val": h.get("Total_Market_Value"),
            "market_val_curr": h.get("Market_Value_Currency"),
            "accrued_int": h.get("Accrued_Interest"),
            "usd_value": h.get("Value_in_USD"),
            "pct_assets": h.get("Percentage_of_Total_Assets"),
            "page": h.get("Source_Page")
        }
        file_record["holdings"].append(h_info)
        
    audit_holdings_report.append(file_record)

with open(BASE_DIR / "audit_holdings_report.json", "w", encoding="utf-8") as f:
    json.dump(audit_holdings_report, f, indent=2, default=str)

print("Saved audit_holdings_report.json")
