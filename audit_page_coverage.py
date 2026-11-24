import fitz
from pathlib import Path
import json

PDF_DIR = Path(r"D:\zz\Extraction_PDFs_UBP")
pdf_files = [
    "1_UBP_1002590_Jul2025.pdf",
    "2_UBP_1002590_Oct2025.pdf",
    "3_UBP_1002590_Jan2026.pdf",
    "4_UBP_1002591_Jul2025.pdf",
    "5_UBP_1002591_Oct2025.pdf"
]

page_coverage_matrix = []

for pdf_name in pdf_files:
    pdf_path = PDF_DIR / pdf_name
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    
    for pno in range(total_pages):
        page = doc[pno]
        text = page.get_text("text")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        
        # Determine actual content by inspecting headings
        headings = []
        for l in lines:
            lu = l.upper()
            if any(k in lu for k in [
                "ASSET ALLOCATION", "BREAKDOWN OF NET ASSETS BY CURRENCY",
                "CURRENT PORTFOLIO", "BONDS/NOTES", "EQUITIES, EQUITY",
                "ALTERNATIVE INVESTMENTS", "STRUCTURED PRODUCTS",
                "CURRENT ACCOUNTS", "LOANS", "SUMMARY OF NET ASSETS",
                "EXCHANGE RATES", "HISTORY OF MONTHLY PERFORMANCES",
                "HISTORY OF ANNUAL PERFORMANCES", "HISTORY OF YEARLY PERFORMANCES",
                "DISCLAIMER", "GENERAL INFORMATION", "PRODUCT RISK CLASSIFICATION",
                "ACKNOWLEDGEMENT OF ASSETS"
            ]):
                if len(l) < 80:
                    headings.append(l)
        
        first_few = lines[:8] if len(lines) >= 8 else lines
        
        page_coverage_matrix.append({
            "pdf": pdf_name,
            "page_num": pno + 1,
            "total_pages": total_pages,
            "line_count": len(lines),
            "detected_headings": headings[:6],
            "first_few_lines": first_few
        })

print(f"Total pages scanned: {len(page_coverage_matrix)}")
with open(r"D:\zz\UBP_Extraction_App\page_coverage_raw.json", "w", encoding="utf-8") as f:
    json.dump(page_coverage_matrix, f, indent=2)
print("Saved page_coverage_raw.json")
