import pymupdf
from typing import List, Dict, Any, NamedTuple, Tuple, Optional, Set

class ExtractedWord(NamedTuple):
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    raw_x0: float
    raw_y0: float
    raw_x1: float
    raw_y1: float
    block_no: int
    line_no: int
    word_no: int
    confidence: float = 100.0

class VisualLine(NamedTuple):
    y: float
    y0: float
    y1: float
    words: List[ExtractedWord]
    text: str

def get_watermark_lines(page: pymupdf.Page) -> Set[Tuple[int, int]]:
    """
    Identifies watermark text lines by inspecting geometric orientation (diagonal spans),
    font size, and typical watermark phrases ('SAMPLE - NOT VALID', 'SAMPLE / NOT VALID').
    Returns a set of (block_no, line_no) tuples corresponding to watermark lines.
    """
    wm_lines: Set[Tuple[int, int]] = set()
    text_dict = page.get_text("dict")
    for bno, b in enumerate(text_dict.get("blocks", [])):
        for lno, l in enumerate(b.get("lines", [])):
            d = l.get("dir", (1.0, 0.0))
            is_diag = abs(d[1]) > 0.05 and abs(d[0]) > 0.05
            txt = " ".join(s.get("text", "") for s in l.get("spans", [])).upper().strip()
            # 1. Diagonal watermark lines
            if is_diag and any(k in txt for k in ["SAMPLE", "NOT VALID", "VALID", "DEMO"]):
                wm_lines.add((bno, lno))
            # 2. Prominent watermark phrases
            elif "SAMPLE / NOT VALID" in txt or "SAMPLE - NOT VALID" in txt:
                wm_lines.add((bno, lno))
            # 3. Large font watermark spans
            elif any(s.get("size", 0) >= 18.0 and any(k in s.get("text", "").upper() for k in ["SAMPLE", "NOT VALID", "VALID"]) for s in l.get("spans", [])):
                wm_lines.add((bno, lno))
    return wm_lines

def get_page_text(page: pymupdf.Page) -> str:
    """
    Returns full text of page. If page lacks selectable text and has images,
    seamlessly invokes local OCR fallback.
    """
    from app.extraction.ocr_extractor import detect_page_type, extract_page_with_ocr
    _, needs_ocr = detect_page_type(page)
    if needs_ocr:
        ocr_text, _, _, _, _ = extract_page_with_ocr(page, page.number + 1)
        return ocr_text
    return page.get_text("text")

def extract_visual_words_and_lines(
    page: pymupdf.Page,
    y_tolerance: float = 3.5,
    filter_watermarks: bool = True
) -> Tuple[List[ExtractedWord], List[VisualLine]]:
    """
    Extracts words and groups them into visual reading-order lines.
    Automatically detects if page is image-based or lacks selectable text,
    falling back to local OCR engine.
    """
    from app.extraction.ocr_extractor import detect_page_type, extract_page_with_ocr
    _, needs_ocr = detect_page_type(page)
    if needs_ocr:
        _, words, lines, _, _ = extract_page_with_ocr(page, page.number + 1, y_tolerance=y_tolerance)
        return words, lines

    rot_mat = page.rotation_matrix
    raw_words = page.get_text("words", sort=False)
    wm_lines = get_watermark_lines(page) if filter_watermarks else set()
    
    extracted_words: List[ExtractedWord] = []
    for w in raw_words:
        rx0, ry0, rx1, ry1, text, bno, lno, wno = w
        if filter_watermarks and (bno, lno) in wm_lines:
            continue
        raw_rect = pymupdf.Rect(rx0, ry0, rx1, ry1)
        vis_rect = raw_rect * rot_mat
        
        extracted_words.append(ExtractedWord(
            text=text,
            x0=round(vis_rect.x0, 2),
            y0=round(vis_rect.y0, 2),
            x1=round(vis_rect.x1, 2),
            y1=round(vis_rect.y1, 2),
            raw_x0=round(rx0, 2),
            raw_y0=round(ry0, 2),
            raw_x1=round(rx1, 2),
            raw_y1=round(ry1, 2),
            block_no=bno,
            line_no=lno,
            word_no=wno,
            confidence=100.0
        ))

    # Sort words by visual y0, then x0
    extracted_words.sort(key=lambda item: (item.y0, item.x0))

    # Group into lines
    lines: List[VisualLine] = []
    current_words: List[ExtractedWord] = []
    current_y_anchor: Optional[float] = None

    for w in extracted_words:
        if current_y_anchor is None or abs(w.y0 - current_y_anchor) > y_tolerance:
            if current_words:
                current_words.sort(key=lambda item: item.x0)
                line_y = sum(x.y0 for x in current_words) / len(current_words)
                min_y = min(x.y0 for x in current_words)
                max_y = max(x.y1 for x in current_words)
                line_str = " ".join(x.text for x in current_words)
                lines.append(VisualLine(y=round(line_y, 2), y0=round(min_y, 2), y1=round(max_y, 2), words=current_words, text=line_str))
            current_words = [w]
            current_y_anchor = w.y0
        else:
            current_words.append(w)

    if current_words:
        current_words.sort(key=lambda item: item.x0)
        line_y = sum(x.y0 for x in current_words) / len(current_words)
        min_y = min(x.y0 for x in current_words)
        max_y = max(x.y1 for x in current_words)
        line_str = " ".join(x.text for x in current_words)
        lines.append(VisualLine(y=round(line_y, 2), y0=round(min_y, 2), y1=round(max_y, 2), words=current_words, text=line_str))

    return extracted_words, lines
