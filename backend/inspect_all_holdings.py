import sys, os
sys.path.insert(0, r'D:\zz\UBP_Extraction_App\backend')
import pymupdf
from app.extraction.word_extractor import extract_visual_words_and_lines
from app.extraction.table_reconstructor import extract_ubp_statement

paths = [
    (r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\1_UBP_1002590_Jul2025.pdf', 'Jul 2025 (1002590)'),
    (r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\2_UBP_1002590_Oct2025.pdf', 'Oct 2025 (1002590)'),
    (r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\3_UBP_1002590_Jan2026.pdf', 'Jan 2026 (1002590)'),
    (r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\4_UBP_1002591_Jul2025.pdf', 'Jul 2025 (1002591)'),
    (r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\5_UBP_1002591_Oct2025.pdf', 'Oct 2025 (1002591)'),
]

for p, label in paths:
    print(f"\n=======================================================")
    print(f"FILE: {label}")
    doc = pymupdf.open(p)
    res = extract_ubp_statement(p)
    print(f"Total holdings: {len(res.holdings)}")
    for h in res.holdings:
        print(f"  [{h.id}] SecID: {h.isin_secur_no} | Date: {h.market_price_date} | Price: {h.market_price}")
        print(f"        Name: {h.security_name}")
        # Check raw lines
        raw_lines = h.raw_text.split('\n')
        if len(raw_lines) > 1:
            print(f"        Raw Lines ({len(raw_lines)}):")
            for rl in raw_lines[1:]:
                print(f"          + {rl}")
