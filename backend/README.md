# UBP Portfolio Statement Extraction Backend

Deterministic Python extraction and financial validation engine for Union Bancaire Privée (UBP) portfolio valuation statements.

## Features
- **Deterministic Extraction**: Coordinate-based extraction with visual rotation compensation using PyMuPDF (fitz) and pdfplumber.
- **Financial Normalization**: Strict Decimal-based parser for Swiss/European numbers with apostrophes, trailing negative signs, percentages, and asterisks.
- **Template Detection & Multi-page Linking**: Handles dynamic report lengths (11 pages, 12 pages, etc.) and holdings continuing across page boundaries.
- **Independent Financial Validation**: Automated checks for data completeness, holdings integrity, category reconciliation, net asset balance equations, and monthly performance sums.
- **Taurus-Style Excel Generation**: 16 dedicated worksheets formatted to institutional standards with freeze panes, auto-filters, and clean typography.
- **No Silent Data Loss**: Complete raw page text records and unmapped content retention.

## Running Tests
```bash
set PYTHONPATH=D:\zz\UBP_Extraction_App\backend
python -m pytest tests -v
```

## Running Backend
```bash
set PYTHONPATH=D:\zz\UBP_Extraction_App\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
