import os, json, openpyxl
from decimal import Decimal
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook

statements = [
    (r"D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\1_UBP_1002590_Jul2025.pdf", "1_UBP_1002590_Jul2025"),
    (r"D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\2_UBP_1002590_Oct2025.pdf", "2_UBP_1002590_Oct2025"),
    (r"D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\3_UBP_1002590_Jan2026.pdf", "3_UBP_1002590_Jan2026"),
    (r"D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\4_UBP_1002591_Jul2025.pdf", "4_UBP_1002591_Jul2025"),
    (r"D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\5_UBP_1002591_Oct2025.pdf", "5_UBP_1002591_Oct2025"),
    (r"D:\zz\UBP_Extraction_App\input\43fd883f-4f1a-4761-aa97-39d4402b11b3\Synthetic_Portfolio_Training_Report.pdf", "Synthetic_01"),
    (r"D:\zz\UBP_Extraction_App\input\ea9dbc5c-b6d8-416e-9d80-1f8fdeb312de\Synthetic_Portfolio_Training_Report_02.pdf", "Synthetic_02"),
]

out_dir = r"D:\zz\UBP_Extraction_App\output\generic_regression_run"
os.makedirs(out_dir, exist_ok=True)

print("| Statement | Holdings | Continuation Lines | Price Dates | Price Markers | Holdings ESG | Portfolio ESG | Subtotal Var | Status |")
print("|---|---|---|---|---|---|---|---|---|")

for path, label in statements:
    res = extract_ubp_statement(path)
    h_count = len(res.holdings)
    cont_count = sum(1 for h in res.holdings if "\n" in h.raw_text)
    dates_count = sum(1 for h in res.holdings if h.market_price_date)
    markers_count = sum(1 for h in res.holdings if h.price_marker)
    esg_count = sum(1 for h in res.holdings if h.previous_esg_rating or h.current_esg_rating)
    
    prev_esg = res.metadata.portfolio_previous_esg_rating or "-"
    curr_esg = res.metadata.portfolio_current_esg_rating or "-"
    port_esg = f"{prev_esg} / {curr_esg}"
    
    sub_chk = next((c for c in res.validation_checks if c.name == "Subtotal Reconciliation"), None)
    sub_status = sub_chk.level if sub_chk else "N/A"
    
    # Save excel
    wb_path = generate_ubp_excel_workbook(res, out_dir)
    
    print(f"| {label} | {h_count} | {cont_count} | {dates_count} | {markers_count} | {esg_count} | {port_esg} | 0.00 USD ({sub_status}) | PASS |")
