import openpyxl
from pathlib import Path

excel_path = Path(r"D:\zz\UBP_Extraction_App\output\UBP_1002590_1_UBP_1002590_Jul2025.xlsx")
wb = openpyxl.load_workbook(str(excel_path), data_only=True)

for name in ["Unmapped_Content", "Raw_Page_Text", "Validation", "Counts"]:
    ws = wb[name]
    print(f"\n==========================================")
    print(f"SHEET: {name} (Rows: {ws.max_row}, Cols: {ws.max_column})")
    rows = list(ws.iter_rows(values_only=True))
    for i, r in enumerate(rows[:10]):
        print(f"  Row {i+1}: {r}")
