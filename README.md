# UBP Portfolio Statement Extraction System

A professional, locally running full-stack financial document extraction and validation application inspired by the workflow, validation standards, and output quality of Taurus.

Built specifically for Union Bancaire Privée (UBP) portfolio valuation statements.

## Key Highlights
- **100% Deterministic Local Processing**: No LLMs, No OpenAI/Claude/Gemini APIs, No vision models, No cloud PDF extraction services, No fabricated data.
- **Enterprise UI**: Clean, human-crafted React + Vite + TypeScript interface with drag-and-drop uploads, live pipeline progress, interactive validation cards, multi-tab financial data tables, and Excel/ZIP downloads.
- **Taurus-Aligned Excel Structure**: 16 dedicated worksheets per workbook:
  1. `Portfolio_Overview`
  2. `Asset_Allocation`
  3. `Currency_Breakdown`
  4. `Holdings`
  5. `Current_Accounts`
  6. `Loans`
  7. `Transactions` (explicit notice of non-itemized structure)
  8. `Net_Assets_Summary`
  9. `Exchange_Rates`
  10. `Monthly_Performance`
  11. `Annual_Performance`
  12. `Comments`
  13. `Counts`
  14. `Validation`
  15. `Unmapped_Content`
  16. `Raw_Page_Text`
- **Zero Silent Data Loss Architecture**: Complete audit trail with page-by-page raw text and unmapped content tracking.

## Technology Stack
- **Frontend**: React 18 / 19, Vite, TypeScript, Tailwind CSS, Lucide icons
- **Backend**: Python 3.13, FastAPI, Pydantic
- **PDF Engine**: PyMuPDF (fitz) coordinate-based word extraction, pdfplumber
- **Data & Normalization**: Python Decimal, pandas, regex
- **Excel Generation**: openpyxl
- **Testing**: pytest

## Quick Start (Windows)
Double-click `start_app.bat` or run:

### Backend:
```bash
cd D:\zz\UBP_Extraction_App
set PYTHONPATH=D:\zz\UBP_Extraction_App\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend:
```bash
cd D:\zz\UBP_Extraction_App\frontend
npx vite --host localhost --port 5173
```

- Web Interface: [http://localhost:5173](http://localhost:5173)
- FastAPI Swagger Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
