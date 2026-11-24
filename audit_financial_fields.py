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

discrepancy_log = []

for pdf_name in pdf_files:
    pdf_path = PDF_DIR / pdf_name
    stem = pdf_name.replace(".pdf", "")
    matching = [f for f in OUTPUT_DIR.glob(f"*{stem}*.xlsx") if f.is_file() and not f.name.startswith("~")]
    if not matching:
        continue
    excel_file = matching[0]
    wb = openpyxl.load_workbook(str(excel_file), data_only=True)
    doc = fitz.open(str(pdf_path))
    
    print(f"\n==========================================")
    print(f"Auditing Financial Sections for {pdf_name}")
    
    # 1. Net Assets Summary
    ws_nas = wb["Net_Assets_Summary"]
    nas_rows = {r[0]: r[1] for r in ws_nas.iter_rows(values_only=True) if r[0]}
    
    # Search Net Assets Summary in PDF
    nas_page = None
    for pno in range(len(doc)):
        t = doc[pno].get_text("text").upper()
        if "SUMMARY OF NET ASSETS" in t and "ASSETS" in t and "TOTAL ASSETS" in t:
            nas_page = pno + 1
            break
            
    print(f"  Net Assets Summary on PDF Page: {nas_page}")
    print(f"  Extracted Net Assets Summary: {nas_rows}")
    
    # 2. Accounts
    ws_acc = wb["Current_Accounts"]
    acc_rows = list(ws_acc.iter_rows(values_only=True))
    acc_headers = acc_rows[0]
    acc_data = [dict(zip(acc_headers, r)) for r in acc_rows[1:] if any(r)]
    print(f"  Current Accounts count: {len(acc_data)}")
    for a in acc_data:
        print(f"    Account: {a.get('Account_ID')} | Curr: {a.get('Currency')} | Amt: {a.get('Amount')} | USD: {a.get('Value_in_USD')} | %: {a.get('Percentage_Assets')}")
        
    # 3. Loans
    ws_loan = wb["Loans"]
    loan_rows = list(ws_loan.iter_rows(values_only=True))
    loan_headers = loan_rows[0]
    loan_data = [dict(zip(loan_headers, r)) for r in loan_rows[1:] if any(r) and r[0] != "None"]
    print(f"  Loans count: {len(loan_data)}")
    for l in loan_data:
        print(f"    Loan: {l.get('Loan_ID')} | Curr: {l.get('Currency')} | Amt: {l.get('Original_Amount')} | Ref: {l.get('Loan_Reference')} | Maturity: {l.get('Maturity_Date')} | Rate: {l.get('Interest_Rate_Pct')} | Accrued: {l.get('Accrued_Interest')} | USD: {l.get('USD_Equivalent')}")

    # 4. Exchange rates
    ws_fx = wb["Exchange_Rates"]
    fx_rows = list(ws_fx.iter_rows(values_only=True))
    fx_headers = fx_rows[0]
    fx_data = [dict(zip(fx_headers, r)) for r in fx_rows[1:] if any(r)]
    print(f"  FX count: {len(fx_data)}")
    for fx in fx_data:
        print(f"    FX: {fx.get('Base_Currency')}/{fx.get('Target_Currency')} = {fx.get('Exchange_Rate')}")

    # 5. Monthly & Annual Perf
    ws_mp = wb["Monthly_Performance"]
    mp_rows = list(ws_mp.iter_rows(values_only=True))
    print(f"  Monthly Perf rows (including headers): {len(mp_rows)}")
    ws_ap = wb["Annual_Performance"]
    ap_rows = list(ws_ap.iter_rows(values_only=True))
    print(f"  Annual Perf rows (including headers): {len(ap_rows)}")
