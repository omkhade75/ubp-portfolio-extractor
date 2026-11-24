import sys, os
sys.path.insert(0, r'D:\zz\UBP_Extraction_App\backend')
import pymupdf
from app.extraction.word_extractor import extract_visual_words_and_lines

doc = pymupdf.open(r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\2_UBP_1002590_Oct2025.pdf')
page = doc[2]
_, lines = extract_visual_words_and_lines(page)
for l in lines:
    if 365 < l.y < 425:
        print(f"y={l.y:.1f}: \"{l.text}\"")
        for w in l.words:
            print(f"   w='{w.text}' x0={w.x0:.1f} x1={w.x1:.1f}")
