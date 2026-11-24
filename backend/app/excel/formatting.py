import re
from typing import Any
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Typography
FONT_NAME = "Calibri"
HEADER_FONT = Font(name=FONT_NAME, size=10, bold=True, color="0F172A")
TITLE_FONT = Font(name=FONT_NAME, size=12, bold=True, color="0F172A")
SECTION_FONT = Font(name=FONT_NAME, size=11, bold=True, color="1E293B")
DATA_FONT = Font(name=FONT_NAME, size=9.5, color="1E293B")
BOLD_DATA_FONT = Font(name=FONT_NAME, size=9.5, bold=True, color="0F172A")
WARNING_FONT = Font(name=FONT_NAME, size=9.5, color="B45309", bold=True)
FAIL_FONT = Font(name=FONT_NAME, size=9.5, color="B91C1C", bold=True)
PASS_FONT = Font(name=FONT_NAME, size=9.5, color="15803D", bold=True)

# Fills
HEADER_FILL = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
SUBTOTAL_FILL = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
PASS_FILL = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
WARN_FILL = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
FAIL_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")

# Alignments
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_LEFT_WRAP = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")

# Borders
BORDER_THIN_GRAY = Side(style="thin", color="E2E8F0")
BORDER_HEADER_BOTTOM = Side(style="medium", color="CBD5E1")
BORDER_DOUBLE_BOTTOM = Side(style="double", color="64748B")

CELL_BORDER = Border(
    left=BORDER_THIN_GRAY,
    right=BORDER_THIN_GRAY,
    top=BORDER_THIN_GRAY,
    bottom=BORDER_THIN_GRAY
)

HEADER_BORDER = Border(
    left=BORDER_THIN_GRAY,
    right=BORDER_THIN_GRAY,
    top=BORDER_THIN_GRAY,
    bottom=BORDER_HEADER_BOTTOM
)

TOTAL_BORDER = Border(
    top=BORDER_THIN_GRAY,
    bottom=BORDER_DOUBLE_BOTTOM
)

# Number Formats
FMT_AMOUNT = '#,##0.00;[Red]-#,##0.00;"-"'
FMT_INTEGER = '#,##0;[Red]-#,##0;"0"'
FMT_PERCENT = '0.00%;[Red]-0.00%;"0.00%"'
FMT_PERCENT_PLAIN = '0.00'
FMT_PRICE = '#,##0.0000;[Red]-#,##0.0000;"-"'

ILLEGAL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

def clean_excel_string(val: Any) -> Any:
    """Strips non-printable XML/Excel control characters that cause openpyxl errors."""
    if isinstance(val, str):
        return ILLEGAL_CHARACTERS_RE.sub("", val)
    return val

def style_header_row(ws, row_idx: int, max_col: int):
    """Styles table header row with enterprise formatting."""
    ws.row_dimensions[row_idx].height = 24
    for col_idx in range(1, max_col + 1):
        cell = ws.cell(row=row_idx, column=col_idx)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.border = HEADER_BORDER
        if cell.alignment.horizontal is None:
            cell.alignment = ALIGN_LEFT

def autofit_columns(ws, max_len_cap: int = 60, min_len: int = 12):
    """Calculates optimal column width to prevent text clipping."""
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or '')
            if '\n' in val_str:
                val_str = max(val_str.split('\n'), key=len)
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = min(max_len_cap, max(min_len, max_len + 3))
