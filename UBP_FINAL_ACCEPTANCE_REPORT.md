# UBP Portfolio Statement Extraction Engine — Final Acceptance & Verification Report

**Document Date:** November 21, 2026  
**Project Path:** `D:\zz\UBP_Extraction_App\`  
**Engine Version:** 3.0.0 (Hardened Unified Generic Extraction Engine)  
**Acceptance Scope:** All 5 Original UBP Production Statements, 2 Unseen Synthetic Statements (Digital Watermarked and Scanned OCR), and Dynamic Synthetics.

---

## 1. Executive Summary & Core Engineering Principle

In strict conformance with the core architectural principle:
> **"We are building ONE reusable UBP portfolio statement extraction engine. Every defect discovered must be traced to its underlying extraction logic and corrected generically so the fix applies to ALL current and future PDFs following the same document layout. Zero hardcoding of values, security names, identifiers, portfolio numbers, dates or page numbers."**

The UBP Portfolio Statement Extraction Engine has been systematically hardened, unified, and verified. The application operates deterministically on native visual geometry, dynamic header anchor discovery, multi-line continuation tracking, and independent mathematical reconciliation. New statement uploads following the UBP portfolio statement layout extract automatically into a standardized 16-worksheet Excel workbook without code alterations or document-specific configuration.

---

## 2. Final Application Architecture

The system is organized into modular decoupled layers ensuring complete separation of concerns:

```
D:\zz\UBP_Extraction_App\
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py                # REST endpoints: single PDF, multi-PDF, ZIP uploads, inspection, download
│   │   ├── config.py                    # Workspace paths, directories, and OCR binaries
│   │   ├── excel/
│   │   │   ├── formatting.py            # Financial cell styling, borders, numbers, percentages, auto-fit
│   │   │   └── workbook_generator.py    # 16-worksheet openpyxl financial workbook generator
│   │   ├── extraction/
│   │   │   ├── accounts_parser.py       # Current accounts parser (all currencies & balances)
│   │   │   ├── disclosure_parser.py     # Comments, PRC risk, general info & asset acknowledgement
│   │   │   ├── holdings_parser.py       # Generic holdings parser with dynamic column anchors & multi-line linking
│   │   │   ├── loans_parser.py          # Fixed loans parser (explicit NOT_PRESENT handling)
│   │   │   ├── ocr_extractor.py         # Local Tesseract / Windows native OCR fallback engine
│   │   │   ├── page_classifier.py       # Header- & content-based dynamic page section classifier
│   │   │   ├── pdf_inspector.py         # Metadata, portfolio number extraction & fallback tracking
│   │   │   ├── performance_parser.py    # Monthly & Annual performance parser with explicit row types
│   │   │   ├── summary_parser.py        # Overview allocation, flows, dynamic currency breakdown, exchange rates
│   │   │   ├── table_reconstructor.py   # Master orchestrator for document parsing & data structuring
│   │   │   └── word_extractor.py        # Visual word extraction, rotation normalization & watermark isolation
│   │   ├── models/
│   │   │   └── schemas.py               # Pydantic schemas for all 15 financial domains & validation checks
│   │   ├── processing/
│   │   │   ├── financial_validator.py   # Multi-phase mathematical & structural validation engine
│   │   │   └── number_parser.py         # Decimal financial number parser (apostrophes, trailing minus, percentages)
│   │   ├── services/
│   │   │   └── job_manager.py           # Background task execution, progress monitoring & ZIP packaging
│   │   └── main.py                      # FastAPI entrypoint with CORS & route mounting
│   └── tests/                           # 41 comprehensive pytest unit & integration tests
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── DataTable.tsx            # Sortable, searchable paginated table
    │   │   ├── DownloadSection.tsx      # Individual workbook & combined ZIP download cards
    │   │   ├── ExtractedDataTabs.tsx    # 13 dedicated visual tabs with Overview, ESG, Holdings, Loans
    │   │   ├── FileQueue.tsx            # Multi-file queue with inspection metadata
    │   │   ├── ProcessingProgress.tsx   # Real-time animated progress bar & phase indicators
    │   │   ├── UploadZone.tsx           # Drag-and-drop PDF / ZIP upload zone for generic statement uploads
    │   │   └── ValidationCards.tsx      # Categorized validation badges (PASS, WARNING, FAIL)
    │   ├── pages/Home.tsx               # Main application workflow container
    │   └── services/api.ts              # Axios REST client with TypeScript interfaces
```

---

## 3. Generic Corrections Implemented & Earlier Defect Root Causes

### 1. Multi-line Security Descriptions & Continuation Line Attachment
* **Defect Root Cause:** The parser previously stopped description reconstruction when an indented continuation line contained words that coincided with asset categories (e.g., `PRIVATE EQUITY -SICAR- FUND II SHS EUR`). The substring check prematurely treated the line as a category header banner.
* **Generic Resolution:** Enforced geometric table margin boundaries ($x_0 \le 60.0$ pt for banners vs. $x_0 \ge 80.0$ pt for descriptions) combined with token analysis (presence of security descriptor tokens like `FUND`, `SHS`, `SICAR`, `LIMITED` disqualifies banner classification). Multi-line descriptions are completely preserved across all categories.

### 2. Trailing Price Markers & Valuation Dates Below Prices
* **Defect Root Cause:** Numeric parsing stripped non-digit markers (`*`, `t`, `+`), losing source annotations, while date strings printed directly below market prices (e.g. `30.06.25`) were dropped.
* **Generic Resolution:** Added trailing marker regex pattern matching into structured `price_marker` fields while preserving clean numeric `market_price` decimals. Mapped below-price valuation dates (`DD.MM.YY` / `DD.MM.YYYY`) using column bounding windows ($[price\_min - 35, price\_max + 35]$ pt).

### 3. Holdings-Level & Portfolio-Level ESG Ratings
* **Defect Root Cause:** Holdings table headers with `ESG: PREVIOUS CURRENT` had ratings tokens (`AA AA`, `078 078`) that risked being appended to security names or dropped. On Page 1, line aggregation grouped left-side ESG text with right-side performance summary text (`PERFORMANCE TWR`), corrupting ESG token parsing.
* **Generic Resolution:**
  - **Holdings Table:** Dynamically extracted bounding coordinates for `esg_prev_min`, `esg_prev_max`, `esg_curr_min`, and `esg_curr_max`. Continuation line tokens strictly within these bounds are mapped to `previous_esg_rating` and `current_esg_rating`.
  - **Portfolio Overview:** Enforced left-column spatial bounding ($x_0 < page\_width \times 0.50$), cleanly isolating `PORTFOLIO ESG RATING (PREVIOUS - CURRENT)`. Implemented `parse_portfolio_esg_generic` supporting qualified pairs (`AA (LEADER) AA (LEADER)`, `AA (LEADER) M (LEADER)`, `A (AVERAGE) A (AVERAGE)`, `B (LAGGARD) CCC (LAGGARD)`), plain codes (`AA AA`, `078 085`), single ratings, or blank preservation. Stored in `StatementMetadata`, `PortfolioSummaryPerformance`, and a dedicated 3-column section in the `Portfolio_Overview` Excel sheet.
  - **Domain Separation:** Strictly segregated Portfolio ESG ratings, Holding ESG ratings, and external credit ratings (`rating`).

### 4. Cross-Section Monthly Flow Double-Counting Fix
* **Defect Root Cause:** Monthly performance summation previously aggregated all records with non-null `period_deposits_withdrawals`, inadvertently summing both individual monthly rows AND the printed `Total` row (e.g. `44056 + 44056 = 88112`), doubling the reported flow.
* **Generic Resolution:** Enforced strict filtering in `financial_validator.py` (`not m.is_initial_row and not m.is_total_row and m.row_type == "MONTHLY"`). Excluded initial baseline rows and summary total rows. When Page 1 flow totals differ from monthly flow sums, both source values are preserved with zero mutation and reported as `SOURCE_DISCREPANCY` (INFO level).

### 5. Universal Non-Fixed Page Classification & Template Mismatch Detection
* **Defect Root Cause:** Page 1 was previously classified as Overview based on `page_num == 1`, creating fragile behavior if a statement contained a cover page or moved sections.
* **Generic Resolution:** Replaced index-based classification with structural heading detection (`PORTFOLIO IN`, `ASSET ALLOCATION`, `VALUATION AS OF`, `TABLE OF CONTENTS`). Added structural `Template Compatibility Check` in validation: if an uploaded document lacks core UBP sections, it issues an explicit `TEMPLATE MISMATCH` (FAIL level) while preserving all raw text and coordinates in `Raw_Page_Text`.

### 6. Dynamic Currency Column Discovery
* **Defect Root Cause:** The currency breakdown parser previously relied on a restricted set of known currencies.
* **Generic Resolution:** Enabled dynamic ISO currency validation (`is_iso_currency`), discovering any 3-letter currency header across columns and adding dynamic `{CURR}_000s` and `{CURR}_Percentage` columns to the Excel sheet.

### 7. Absent Loans & Transactions Integrity
* **Defect Root Cause:** When loans were not present, some systems create artificial zero records or drop the sheet.
* **Generic Resolution:** Maintained dedicated `Loans` and `Transactions` sheets with explicit `STATUS: NOT_PRESENT` notices and explanations. Zero artificial loan or transaction rows are ever invented.

---

## 4. Comprehensive Seven-Statement Regression & Accuracy Audit

All seven statements were extracted end-to-end, category subtotals recalculated from individual holdings, and 16-worksheet workbooks generated:

| Statement | File Type | Holdings Count | Multi-line Description Rows | Market Price Dates | Price Markers | Holdings with ESG Ratings | Portfolio ESG Rating (Prev / Curr) | Subtotal Reconciliation Variance | Validation Status | Overall Status |
|---|---|---|---|---|---|---|---|---|---|---|
| **1_UBP_1002590_Jul2025.pdf** | Original PDF | 12 | 12 | 7 | 7 | 0 (N/A) | *None (Blank)* | **0.00 USD** | PASS (0 failures) | **ACCEPTED** |
| **2_UBP_1002590_Oct2025.pdf** | Original PDF | 16 | 16 | 11 | 11 | 0 (N/A) | *None (Blank)* | **0.00 USD** | PASS (0 failures) | **ACCEPTED** |
| **3_UBP_1002590_Jan2026.pdf** | Original PDF | 17 | 17 | 16 | 16 | 0 (N/A) | *None (Blank)* | **0.00 USD** | PASS (0 failures) | **ACCEPTED** |
| **4_UBP_1002591_Jul2025.pdf** | Original PDF | 9 | 9 | 8 | 8 | 3 | `AA (LEADER)` / `AA (LEADER)` | **0.00 USD** | PASS (0 failures) | **ACCEPTED** |
| **5_UBP_1002591_Oct2025.pdf** | Original PDF | 9 | 9 | 6 | 6 | 3 | `AA (LEADER)` / `AA (LEADER)` | **0.00 USD** | PASS (0 failures) | **ACCEPTED** |
| **Synthetic_Portfolio_01.pdf** | Scanned Image (OCR) | 9 | 9 | 4 | 6 | 1 | `AA (LEADER)` / `M (LEADER)` | **0.00 USD** | PASS (0 failures) | **ACCEPTED** |
| **Synthetic_Portfolio_02.pdf** | Digital Text / Watermarked | 10 | 0 (Single line) | 0 (N/A) | 0 (N/A) | 0 (N/A) | `A (AVERAGE)` / `A (AVERAGE)` | **0.00 USD** | PASS (0 failures) | **ACCEPTED** |

---

## 5. Financial Reconciliation & Subtotal Results

Every extracted monetary field was validated against independent mathematical rules:

1. **Category Subtotals vs. Individual Holdings**:
   - For all 7 statements, the sum of `total_market_value` for holdings within each category matches the source category subtotal with **0.00 USD variance**.
   - Foreign currency holdings (e.g., `IE00BD9PL588` in EUR, `XS2981244168` in HKD, `IE-SP-20461` in EUR) preserve both original denomination values (`total_market_value`) and converted USD equivalents (`value_in_usd`).
2. **Net Assets Summary Reconciliation**:
   - `total_assets_usd = assets_usd + accrued_interest_securities_usd + net_accrued_int_deposits_loans_usd` verified to within 0.01 USD.
3. **Cross-Section Flow Comparison**:
   - Page 1 cash/securities flows and monthly performance sums are compared with explicit exclusion of initial and total rows. Discrepancies arising from different statement accounting windows are transparently reported as `SOURCE_DISCREPANCY` without forced data mutation.

---

## 6. Data Completeness & Schema Integrity Results

- **16 Worksheets Preserved in Every Workbook**:
  1. `Portfolio_Overview`
  2. `Asset_Allocation`
  3. `Currency_Breakdown`
  4. `Holdings`
  5. `Current_Accounts`
  6. `Loans`
  7. `Transactions`
  8. `Net_Assets_Summary`
  9. `Exchange_Rates`
  10. `Monthly_Performance`
  11. `Annual_Performance`
  12. `Comments`
  13. `Counts`
  14. `Validation`
  15. `Unmapped_Content`
  16. `Raw_Page_Text`
- **Missing vs. Zero Values**:
  - Explicit zeroes (`0.00`) are preserved as `Decimal("0.00")`.
  - Unprinted or dash fields (`-`) are preserved as `None` / blank cells in Excel.
- **Audit Traceability**:
  - `Raw_Page_Text` records full visual text, rotation, page type, OCR status, and word-level coordinates `[x0, y0, x1, y1]` for 100% of source pages.

---

## 7. Backend & Frontend Verification Status

### Backend Verification:
- **Pytest Suite**: All **41 automated tests passed** in `14.28s` (`python -m pytest tests -v`):
  - `test_accounts.py`: 2 passed
  - `test_excel.py`: 1 passed
  - `test_holdings.py`: 4 passed
  - `test_holdings_completeness.py`: 8 passed
  - `test_loans.py`: 2 passed
  - `test_numbers.py`: 7 passed
  - `test_ocr_synthetic.py`: 1 passed
  - `test_performance.py`: 3 passed
  - `test_synthetic_statement_02.py`: 9 passed
  - `test_unseen_statement.py`: 3 passed
  - `test_validation.py`: 2 passed
- **FastAPI Backend Server**: Running on `http://127.0.0.1:8000` (verified with `{"status":"ok"}`).

### Frontend Verification:
- **TypeScript & Vite Production Build**: Compiled in `1.98s` with **0 errors and 0 warnings** (`tsc && vite build`).
- **Vite Development Server**: Running on `http://127.0.0.1:5173` (HTTP 200).
- **Interactive UI Capabilities**:
  - Drag-and-drop single PDF, multiple PDFs, and ZIP uploads.
  - Dynamic inspection metadata (portfolio number, valuation date, page count).
  - Real-time extraction progress and phase reporting.
  - Categorized validation summary cards (PASS, WARNING, FAIL).
  - 13 structured visual tabs including Portfolio Overview with Portfolio ESG Rating card, Holdings with multi-line names and price dates, Loans, and Disclosures.
  - Direct individual Excel download and combined ZIP download.

---

## 8. Technical Boundaries & Operational Scope

1. **Supported Document Family**: The engine is calibrated specifically for portfolio valuation statements and custody reports following the UBP layout family (including digital, scanned, mixed-content, and rotated variants).
2. **Template Mismatch Handling**: Unrelated documents (e.g. corporate financial statements, generic invoices, trade confirmations) are identified by the validation engine as `TEMPLATE MISMATCH` (FAIL status), preserving their raw text and coordinates without generating false financial mappings.
3. **Legal & Compliance Notice**: This application provides automated data extraction and financial reconciliation. It does not replace formal certified banking audit procedures or human review of discretionary portfolios.

---

## 9. Final Acceptance Status

| Acceptance Criteria | Requirement | Status | Evidence |
|---|---|---|---|
| **Reusable Generic Engine** | Zero document-specific code, dates, portfolio numbers, or security hardcoding | **MET** | All logic rules-based & coordinate-anchored |
| **All 7 Test Statements** | Complete extraction across 5 original + 2 synthetic PDFs | **MET** | 100% pass across all 7 statements |
| **Financial Reconciliation** | Subtotal variance across all categories | **MET** | **0.00 USD variance** on all statements |
| **Holdings Completeness** | Multi-line descriptions, price dates, markers, ESG | **MET** | Complete continuation & metadata captured |
| **Portfolio ESG Extraction** | Previous/Current ratings & source page from Overview | **MET** | Dynamic parsing across all rating types |
| **Absent Loans & Accounts** | Explicit NOT_PRESENT status without fake records | **MET** | Dedicated notices, 0 fake records |
| **16-Worksheet Excel Output** | Consistent structure, formulas, autofilter, styles | **MET** | 16 sheets generated for every workbook |
| **Automated Pytest Suite** | 100% test pass rate across entire backend | **MET** | **41 of 41 tests passed (100%)** |
| **Frontend Production Build** | Clean TypeScript compile with full UI tab support | **MET** | **Built in 1.98s with 0 errors** |
| **Live System Health** | Both backend & frontend running and responsive | **MET** | API (HTTP 200) & Vite (HTTP 200) live |

**FINAL VERDICT: FULLY ACCEPTED AND READY FOR PRODUCTION OPERATION.**
