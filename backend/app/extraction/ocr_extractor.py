import os
import re
import sys
import json
import shutil
import tempfile
import subprocess
from typing import List, Dict, Tuple, Optional, Any
import pymupdf
from PIL import Image, ImageEnhance

from app.extraction.word_extractor import ExtractedWord, VisualLine

# Cache for OCR results to avoid re-running on same page:
# (doc_key, page_num) -> (page_text, extracted_words, visual_lines, avg_confidence, page_type)
_PAGE_OCR_CACHE: Dict[Tuple[str, int], Tuple[str, List[ExtractedWord], List[VisualLine], float, str]] = {}

PS_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "win_ocr_helper.ps1")

def get_doc_cache_key(page: pymupdf.Page) -> str:
    """Returns a reliable cache key for the document."""
    try:
        return page.parent.name or str(id(page.parent))
    except Exception:
        return str(id(page))

def detect_page_type(page: pymupdf.Page) -> Tuple[str, bool]:
    """
    Detects whether a page is TEXT_BASED, IMAGE_BASED, or MIXED.
    Returns: (page_type_string, needs_ocr_bool)
    """
    words = page.get_text("words")
    images = page.get_images()
    word_count = len(words)
    img_count = len(images)

    # If page has plenty of digital selectable text, it's TEXT_BASED
    if word_count >= 15:
        if img_count > 0:
            return "MIXED", False  # Usable digital text present, no OCR needed
        return "TEXT_BASED", False

    # Few words or zero words
    if img_count > 0:
        if word_count > 0:
            return "MIXED", True   # Insufficient digital text, needs OCR
        return "IMAGE_BASED", True

    # No images and few words
    return "TEXT_BASED", False

def _clean_ocr_text_token(token: str) -> str:
    """Normalizes OCR misreads in number-like tokens."""
    if not token:
        return ""
    # Strip trailing punctuation if token looks like a number with decimal
    # e.g. 336'735.18. -> 336'735.18 or 34'060.26. -> 34'060.26
    m = re.match(r"^([0-9'’]+(?:\.[0-9]+)?)\.+$", token)
    if m:
        token = m.group(1)
    return token

def _find_tesseract_binary() -> Optional[str]:
    """Locates local tesseract binary if installed."""
    which_path = shutil.which("tesseract")
    if which_path and os.path.isfile(which_path):
        return which_path
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return None

def _run_local_ocr_engine(img_path: str) -> Tuple[List[Dict[str, Any]], float]:
    """
    Executes local offline OCR on the given image.
    Tries pytesseract if tesseract.exe is present; falls back to Windows native Media OCR.
    Returns: (list_of_ocr_lines, avg_confidence)
    """
    tess_path = _find_tesseract_binary()
    if tess_path:
        try:
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = tess_path
            im = Image.open(img_path)
            data = pytesseract.image_to_data(im, output_type=pytesseract.Output.DICT)
            lines_map: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
            confidences = []
            n_boxes = len(data["text"])
            for i in range(n_boxes):
                w_text = data["text"][i].strip()
                if not w_text:
                    continue
                conf = float(data["conf"][i])
                if conf >= 0:
                    confidences.append(conf)
                block_num = data["block_num"][i]
                line_num = data["line_num"][i]
                x = data["left"][i]
                y = data["top"][i]
                w = data["width"][i]
                h = data["height"][i]
                lines_map.setdefault((block_num, line_num), []).append({
                    "text": w_text,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "confidence": conf if conf >= 0 else 90.0
                })
            
            ocr_lines = []
            for (bno, lno), words in lines_map.items():
                line_text = " ".join(w["text"] for w in words)
                ocr_lines.append({
                    "text": line_text,
                    "words": words
                })
            avg_conf = sum(confidences) / len(confidences) if confidences else 90.0
            return ocr_lines, round(avg_conf, 2)
        except Exception:
            pass  # Fall through to Windows Media OCR

    # Fallback to Windows Media OCR via win_ocr_helper.ps1 on Windows
    if os.name == "nt" and os.path.isfile(PS_SCRIPT_PATH):
        try:
            norm_path = os.path.abspath(img_path).replace("/", "\\")
            res = subprocess.run([
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", PS_SCRIPT_PATH,
                "-ImagePath", norm_path
            ], capture_output=True, text=True, check=True)

            data = json.loads(res.stdout)
            lines = data.get("lines", [])
            # Default confidence for Windows OCR
            for line in lines:
                for w in line.get("words", []):
                    w["confidence"] = 95.0
            return lines, 95.0
        except Exception:
            pass

    return [], 0.0

def extract_page_with_ocr(
    page: pymupdf.Page,
    page_num: int,
    y_tolerance: float = 4.0
) -> Tuple[str, List[ExtractedWord], List[VisualLine], float, str]:
    """
    Renders the page at 300 DPI, runs deterministic local OCR, scales pixel
    coordinates to PDF points, groups into VisualLines, and caches results.
    Returns: (page_text, extracted_words, visual_lines, avg_confidence, page_type)
    """
    doc_key = get_doc_cache_key(page)
    cache_key = (doc_key, page_num)
    if cache_key in _PAGE_OCR_CACHE:
        return _PAGE_OCR_CACHE[cache_key]

    page_type, _ = detect_page_type(page)

    # 1. Render page at 300 DPI
    zoom = 300.0 / 72.0
    mat = pymupdf.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_f:
        tmp_img = tmp_f.name

    try:
        pix.save(tmp_img)
        # Apply Pillow image enhancement if needed
        with Image.open(tmp_img) as pil_img:
            enhancer = ImageEnhance.Contrast(pil_img)
            enhanced = enhancer.enhance(1.2).copy()
        enhanced.save(tmp_img)

        # 2. Run local OCR
        ocr_lines, avg_conf = _run_local_ocr_engine(tmp_img)
    finally:
        if os.path.exists(tmp_img):
            try:
                os.remove(tmp_img)
            except Exception:
                pass

    # 3. Coordinate conversion: Image pixels -> PDF points
    img_w = pix.width
    img_h = pix.height
    scale_x = page.rect.width / img_w
    scale_y = page.rect.height / img_h

    extracted_words: List[ExtractedWord] = []
    word_idx = 0

    for l_idx, line in enumerate(ocr_lines):
        line_words = line.get("words", [])
        for w in line_words:
            raw_w_text = w.get("text", "")
            w_text = _clean_ocr_text_token(raw_w_text)
            if not w_text:
                continue

            wx = w.get("x", 0)
            wy = w.get("y", 0)
            ww = w.get("width", 0)
            wh = w.get("height", 0)
            conf = float(w.get("confidence", 95.0))

            x0 = wx * scale_x
            y0 = wy * scale_y
            x1 = (wx + ww) * scale_x
            y1 = (wy + wh) * scale_y

            # Check if this word is a split part of the previous number
            # e.g. 649 and '022 -> 649'022 or 250' and ooo -> 250'000
            if extracted_words and extracted_words[-1].line_no == l_idx:
                prev_w = extracted_words[-1]
                if w_text.startswith("'") and re.match(r"^\d+$", prev_w.text):
                    extracted_words.pop()
                    merged_text = prev_w.text + w_text
                    extracted_words.append(ExtractedWord(
                        text=merged_text,
                        x0=prev_w.x0,
                        y0=min(prev_w.y0, round(y0, 2)),
                        x1=round(x1, 2),
                        y1=max(prev_w.y1, round(y1, 2)),
                        raw_x0=prev_w.raw_x0,
                        raw_y0=min(prev_w.raw_y0, round(y0, 2)),
                        raw_x1=round(x1, 2),
                        raw_y1=max(prev_w.raw_y1, round(y1, 2)),
                        block_no=prev_w.block_no,
                        line_no=l_idx,
                        word_no=prev_w.word_no,
                        confidence=min(prev_w.confidence, conf)
                    ))
                    continue
                elif w_text.lower() in ("ooo", "oo") and prev_w.text.endswith("'"):
                    extracted_words.pop()
                    merged_text = prev_w.text + ("000" if len(w_text) == 3 else "00")
                    extracted_words.append(ExtractedWord(
                        text=merged_text,
                        x0=prev_w.x0,
                        y0=min(prev_w.y0, round(y0, 2)),
                        x1=round(x1, 2),
                        y1=max(prev_w.y1, round(y1, 2)),
                        raw_x0=prev_w.raw_x0,
                        raw_y0=min(prev_w.raw_y0, round(y0, 2)),
                        raw_x1=round(x1, 2),
                        raw_y1=max(prev_w.raw_y1, round(y1, 2)),
                        block_no=prev_w.block_no,
                        line_no=l_idx,
                        word_no=prev_w.word_no,
                        confidence=min(prev_w.confidence, conf)
                    ))
                    continue

            extracted_words.append(ExtractedWord(
                text=w_text,
                x0=round(x0, 2),
                y0=round(y0, 2),
                x1=round(x1, 2),
                y1=round(y1, 2),
                raw_x0=round(x0, 2),
                raw_y0=round(y0, 2),
                raw_x1=round(x1, 2),
                raw_y1=round(y1, 2),
                block_no=0,
                line_no=l_idx,
                word_no=word_idx,
                confidence=conf
            ))
            word_idx += 1

    # Sort words visually: top-to-bottom, left-to-right
    extracted_words.sort(key=lambda item: (item.y0, item.x0))

    # 4. Group into visual lines
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
                # OCR line cleanups: merge split thousands e.g. 649 '022 -> 649'022, 250' ooo -> 250'000
                line_str = re.sub(r"(\d+)\s*'\s*([oO]{3})", r"\1'000", line_str)
                line_str = re.sub(r"(\d+)\s*'\s*(\d+)", r"\1'\2", line_str)
                lines.append(VisualLine(
                    y=round(line_y, 2),
                    y0=round(min_y, 2),
                    y1=round(max_y, 2),
                    words=current_words,
                    text=line_str
                ))
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
        line_str = re.sub(r"(\d+)\s*'\s*([oO]{3})", r"\1'000", line_str)
        line_str = re.sub(r"(\d+)\s*'\s*(\d+)", r"\1'\2", line_str)
        lines.append(VisualLine(
            y=round(line_y, 2),
            y0=round(min_y, 2),
            y1=round(max_y, 2),
            words=current_words,
            text=line_str
        ))

    full_page_text = "\n".join(l.text for l in lines)

    result = (full_page_text, extracted_words, lines, avg_conf, page_type)
    _PAGE_OCR_CACHE[cache_key] = result
    return result
