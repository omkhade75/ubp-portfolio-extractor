import sys, os
sys.path.insert(0, r'D:\zz\UBP_Extraction_App\backend')
import pymupdf
from app.extraction.word_extractor import extract_visual_words_and_lines

def inspect():
    paths = [
        r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\5_UBP_1002591_Oct2025.pdf',
        r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\4_UBP_1002591_Jul2025.pdf',
        r'D:\zz\UBP_Extraction_App\input\1af036ec-e7dd-4b88-bbeb-e9c70bb46137\2_UBP_1002590_Oct2025.pdf',
    ]
    for p in paths:
        fn = os.path.basename(p)
        print(f"\n======================================")
        print(f"FILE: {fn}")
        doc = pymupdf.open(p)
        # Check Page 1 for Portfolio-level ESG
        p1 = doc[0]
        _, lines1 = extract_visual_words_and_lines(p1)
        for l in lines1:
            if "ESG" in l.text.upper():
                print(f"P1 ESG line: {l.text}")
                for w in l.words:
                    print(f"   w='{w.text}' [{w.x0:.1f} - {w.x1:.1f}]")

        # Check Page 3 for holdings and ESG lines
        p3 = doc[2]
        _, lines3 = extract_visual_words_and_lines(p3)
        for l in lines3:
            if 100 < l.y < 420:
                print(f"P3 y={l.y:.1f}: {l.text}")
                for w in l.words:
                    if w.x0 > 300:
                        print(f"   w='{w.text}' [{w.x0:.1f} - {w.x1:.1f}]")

if __name__ == '__main__':
    inspect()
