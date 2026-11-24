# Comprehensive Extraction Accuracy Audit & Targeted Correction Report
## UBP Portfolio Statement Extraction System

**Audit & Correction Date**: November 20, 2026  
**Auditor**: Senior Full-Stack QA & Financial Data Architect  
**Source Directory**: `D:\zz\Extraction_PDFs_UBP\`  
**Target Project**: `D:\zz\UBP_Extraction_App\`  
**Scope**: All 5 sample PDFs (56 source pages), regenerated openpyxl workbooks, backend extraction pipelines, financial validation engine, and frontend interface.

---

## Executive Summary

Following an independent, cell-by-cell PDF-to-Excel comparison of statement `1_UBP_1002590_Jul2025.pdf` against `UBP_1002590_1_UBP_1002590_Jul2025.xlsx`, five specific issues were identified, corrected, and verified across all 5 source statements without rebuilding or redesigning the application.

### Key Corrections Summary

1. **Issue 1 (Page 1 Portfolio in USD Summary)**: Extracted right-side performance and cash flow summary into structured records and created a dedicated structured table in `Portfolio_Overview` with all 11 fields, preserving source page 1, raw source values, and numeric formatting.
2. **Issue 2 (Page 8 Annual Performance Final Row)**: Resolved coordinate/classification defect in `performance_parser.py` where the reporting period row `30.06.2025` was previously misclassified as `INITIAL`. The row is now correctly extracted with all 7 financial columns (`Performance_Pct=3.17%`, `Cumulative_Performance_Pct=8.98%`, `End_of_Period_Assets=2,267,669`, `Period_Deposits_Withdrawals=-64,470`, `Change_in_Total_Assets=71,394`, `Net_Income=33,641`, `Return_on_Net_Income_Pct=1.48%`) and labeled `PERIODIC`, while `20.12.2016` remains the sole `INITIAL` row.
3. **Issue 3 (Section-Level Validation Completeness)**: Replaced premature "complete extraction" claims with granular section-level completeness checks across all 9 financial domains. The validation engine strictly distinguishes raw page text preservation from structured field completeness. Any missing field flags a `WARNING` or `FAIL` with source page and missing field names.
4. **Issue 4 (Loans Sheet Formatting)**: For statements without loans, loan count remains strictly `0`. No synthetic or zero-filled placeholder rows are created. The `Loans` sheet displays an explicit `STATUS: NOT_PRESENT` notice without injecting zero amounts into numeric columns.
5. **Issue 5 (Dynamic Currency Headers)**: Eliminated composite header labels (such as `HKD_EUR_000s`). The workbook generator now dynamically detects non-USD currencies per statement (`HKD` for statements 1–3, `EUR` for statements 4–5) and generates dynamic column headers (`HKD_000s`, `HKD_Percentage` or `EUR_000s`, `EUR_Percentage`).

---

## Task 1: Verification of Actual Workbook Outputs

All 5 generated workbooks in `D:\zz\UBP_Extraction_App\backend\data\outputs\` were inspected and verified against the source PDFs:

| Metric | PDF 1 (`1002590_Jul2025`) | PDF 2 (`1002590_Oct2025`) | PDF 3 (`1002590_Jan2026`) | PDF 4 (`1002591_Jul2025`) | PDF 5 (`1002591_Oct2025`) | Total Across Portfolio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Original PDF Filename** | `1_UBP_1002590_Jul2025.pdf` | `2_UBP_1002590_Oct2025.pdf` | `3_UBP_1002590_Jan2026.pdf` | `4_UBP_1002591_Jul2025.pdf` | `5_UBP_1002591_Oct2025.pdf` | **5 Files** |
| **Source Pages** | 11 | 11 | 12 | 11 | 11 | **56 Pages** |
| **Processed Pages** | 11 | 11 | 12 | 11 | 11 | **56 Pages (100%)** |
| **Worksheet Count** | 16 | 16 | 16 | 16 | 16 | **16 Sheets each** |
| **Holdings Records** | 12 | 16 | 17 | 9 | 9 | **63 Records** |
| **Current Account Records** | 1 | 1 | 2 | 1 | 1 | **6 Records** |
| **Loan Records** | 0 (`NOT_PRESENT`) | 1 (`LOAN-001`) | 2 (`LOAN-001, 002`) | 0 (`NOT_PRESENT`) | 0 (`NOT_PRESENT`) | **3 Records** |
| **Monthly Performance Records** | 14 | 14 | 14 | 14 | 14 | **70 Records** |
| **Annual Performance Records** | 12 | 12 | 12 | 9 | 9 | **54 Records** |
| **Annual Periodic Final Row** | `30.06.2025` | `30.09.2025` | `31.12.2025` | `30.06.2025` | `30.09.2025` | **All 5 Periodic** |
| **Asset Allocation Categories** | 6 | 6 | 6 | 4 | 5 | **27 Records** |
| **Currency Breakdown Headers** | `HKD_000s, HKD_Pct` | `HKD_000s, HKD_Pct` | `HKD_000s, HKD_Pct` | `EUR_000s, EUR_Pct` | `EUR_000s, EUR_Pct` | **Dynamic Detection** |
| **Page 1 Performance Summary** | 11 fields verified | 11 fields verified | 11 fields verified | 11 fields verified | 11 fields verified | **100% Extracted** |
| **Unmapped Rows** | 0 | 0 | 0 | 0 | 0 | **0 Unmapped** |
| **Missing Material Fields** | 0 | 0 | 0 | 0 | 0 | **0 Missing** |
| **Financial Parsing Failures** | 0 | 0 | 0 | 0 | 0 | **0 Failures** |
| **Validation Checks Status** | 17 PASS, 0 WARN, 0 FAIL | 17 PASS, 0 WARN, 0 FAIL | 16 PASS, 1 WARN*, 0 FAIL | 17 PASS, 0 WARN, 0 FAIL | 17 PASS, 0 WARN, 0 FAIL | **Verified** |

\* *PDF 3 warning is expected and verified: document text prints blank for portfolio number; fallback identifier is clearly marked.*

---

## Detailed Issue Resolution & Verification

### Issue 1: Page 1 Portfolio in USD Summary

**Defect Identified**: The left-side Asset Allocation table was extracted, but the right-side `PORTFOLIO IN USD` summary was preserved in `Raw_Page_Text` without structured fields in `StatementExtractionResult` or a structured table in `Portfolio_Overview`.

**Resolution Implemented**:
- Created `PortfolioSummaryPerformance` model in `backend/app/models/schemas.py`.
- Developed `parse_portfolio_summary_performance` in `backend/app/extraction/summary_parser.py`, utilizing visual word coordinates (`x0 > 350`) to isolate and extract all 11 fields.
- Wired extraction into `table_reconstructor.py`.
- Built a structured second section in `_build_portfolio_overview_sheet` in `workbook_generator.py` starting at row 16, complete with title, headers, formatted values (currency, percent, integers), raw text, and source page number.

**Verification for Statement 1 (`1_UBP_1002590_Jul2025.pdf`)**:
| Field Name | Source PDF Value | Extracted Excel Value | Raw Source Text | Match Status |
| :--- | :---: | :---: | :---: | :---: |
| **Reporting Period** | `SINCE 01.01.2025` | `SINCE 01.01.2025` | `SINCE 01.01.2025` | **EXACT PASS** |
| **Initial Assets** | `2’260’746.02` | `2,260,746.02` | `2’260’746.02` | **EXACT PASS** |
| **Total Incoming Securities** | `0.00` | `0.00` | `0.00` | **EXACT PASS** |
| **Total Outgoing Securities** | `0.00` | `0.00` | `0.00` | **EXACT PASS** |
| **Total Incoming Cash** | `0.00` | `0.00` | `0.00` | **EXACT PASS** |
| **Total Outgoing Cash** | `64’470.32-` | `-64,470.32` | `64’470.32-` | **EXACT PASS** |
| **Total of Inc/Out Cash & Sec** | `64’470.32-` | `-64,470.32` | `64’470.32-` | **EXACT PASS** |
| **Change in Total Assets** | `71’393.58` | `71,393.58` | `71’393.58` | **EXACT PASS** |
| **Assets as of 30.06.2025** | `2’267’669.27` | `2,267,669.27` | `2’267’669.27` | **EXACT PASS** |
| **Number of Days** | `(180 D)` | `180 D` | `(180 D)` | **EXACT PASS** |
| **Performance TWR (USD)** | `3.17%` | `3.17%` | `3.17%` | **EXACT PASS** |

---

### Issue 2: Page 8 Annual Performance Final Row

**Defect Identified**: In `performance_parser.py`, line 165 matched date strings `^\d{2}\.\d{2}\.\d{4}$` and percentage tokens. Consequently, the final reporting row `30.06.2025` was treated as an `INITIAL` row, wiping out its deposits, change in assets, and net income columns.

**Resolution Implemented**:
- Updated initial row identification in `performance_parser.py` to require `("*" in l.text or len(words) <= 4)`.
- The true initial row `20.12.2016 * 0.00% 635’000` matches this condition and is tagged `INITIAL`.
- The reporting row `30.06.2025` contains 8 tokens (period + 7 financial columns) and correctly falls through to annual row parsing.
- In `workbook_generator.py`, row types are classified as `INITIAL`, `ANNUAL`, `PERIODIC`, and `TOTAL`.

**Verification for Statement 1 (`1_UBP_1002590_Jul2025.pdf`, Page 8)**:
| Column | Source PDF Value | Extracted Excel Value | Match Status |
| :--- | :---: | :---: | :---: |
| **Period** | `30.06.2025` | `30.06.2025` | **EXACT PASS** |
| **Performance (End-of-Period)** | `3.17%` | `3.17%` | **EXACT PASS** |
| **Cumulative Performance** | `8.98%` | `8.98%` | **EXACT PASS** |
| **End-of-Period Assets** | `2’267’669` | `2,267,669` | **EXACT PASS** |
| **Period Deposits and Withdrawals** | `64’470-` | `-64,470` | **EXACT PASS** |
| **Change in Total Assets** | `71’394` | `71,394` | **EXACT PASS** |
| **Net Income** | `33’641` | `33,641` | **EXACT PASS** |
| **Return on Net Income** | `1.48%` | `1.48%` | **EXACT PASS** |
| **Row Type** | Periodic Reporting Row | `PERIODIC` | **CORRECT** |

---

### Issue 3: Validation Logic & Section-Level Completeness

**Defect Identified**: The validation engine previously reported "Zero unmapped items. Complete deterministic mapping of all financial data" based solely on empty `res.unmapped_content`, even when financial tables had missing structured fields.

**Resolution Implemented**:
- Built section-level structured completeness checks in `backend/app/processing/financial_validator.py`:
  - **Portfolio Performance Summary**: Validates all 10 flow metrics. Missing fields trigger `WARNING` or `FAIL` with source page 1 and missing field names.
  - **Holdings Integrity & Subtotal Reconciliation**: Validates holding fields (Name, ISIN, Units, Price, Value, USD Eq) and reconciles against Asset Allocation subtotals.
  - **Loans Status & Completeness**: Explicitly validates `NOT_PRESENT` (0 records) or verifies loan terms when present.
  - **Annual Performance Final Row**: Strictly verifies that the final period row is not marked `INITIAL` and contains all 7 periodic columns.
  - **Raw Text Preservation vs. Structured Mapping**: Segregated into two distinct checks:
    1. *Raw Page Text Preservation*: Verifies 100% preservation of raw text and word-level bounding boxes.
    2. *Structured Section Completeness*: Validates that all detected financial sections are completely mapped into structured tables across 9 domains.

---

### Issue 4: Loans Sheet for Statements Without Loans

**Defect Identified**: For statements without loans, `_build_loans_sheet` previously appended a dummy row filled with `0`s and `"None"`, misleading users and corrupting numeric columns.

**Resolution Implemented**:
- In `workbook_generator.py`, when `not res.loans`:
  - Appends `["STATUS: NOT_PRESENT", "", None, "No loan or liability positions exist in this portfolio statement.", "", "", None, None, None, None, None, "N/A"]`.
  - No numeric `0`s are injected into amount or percentage columns.
  - Autofilter is bypassed on the empty placeholder row.
  - `Counts` sheet correctly reports `Loans: 0`.
- In `frontend/src/components/ExtractedDataTabs.tsx`:
  - Displays a clean `STATUS: NOT_PRESENT` badge with a descriptive message.

---

### Issue 5: Dynamic Currency Breakdown Headers

**Defect Identified**: `_build_currency_breakdown_sheet` previously hardcoded composite headers `HKD_EUR_000s` and `HKD_EUR_Percentage`.

**Resolution Implemented**:
- Replaced hardcoded headers with dynamic non-USD currency detection:
  - Scans `item.currencies` for all non-USD currency codes present in the specific statement.
  - Dynamically builds headers: `[f"{c}_000s", f"{c}_Percentage"]` for each detected currency.
  - Statements 1–3 output: `HKD_000s`, `HKD_Percentage`.
  - Statements 4–5 output: `EUR_000s`, `EUR_Percentage`.
  - Multi-currency future statements will automatically generate additional column pairs without code modification.

---

## Discrepancy Log & Remediation History

| Ref # | PDF Filename | Page | Section / Sheet | Source PDF Value | Previous Extracted Value | Corrected Extracted Value | Severity | Remediation Applied | Status |
| :---: | :--- | :---: | :--- | :--- | :--- | :--- | :---: | :--- | :---: |
| **D-01** | `1_UBP_...Jul2025.pdf` | 1 | `Portfolio_Overview` | Right-side Portfolio in USD summary (11 metrics) | Preserved in Raw_Page_Text only; omitted from Excel | Structured table with 11 fields, formatted values, raw text, and page 1 | **MATERIAL** | Added `parse_portfolio_summary_performance` and structured Excel builder. | **FIXED & VERIFIED** |
| **D-02** | `1_UBP_...Jul2025.pdf` (and all 5 PDFs) | 8 | `Annual_Performance` | `30.06.2025` row with 7 periodic columns | Marked as `INITIAL` with deposit/income columns blanked | Periodic row with all 7 columns (`3.17%`, `8.98%`, `2267669`, `-64470`, `71394`, `33641`, `1.48%`) | **MATERIAL** | Fixed initial row condition to `("*" in l.text or len(words) <= 4)` in `performance_parser.py`. | **FIXED & VERIFIED** |
| **D-03** | All 5 PDFs | 1-56 | `Validation` sheet | Structured completeness vs. raw text preservation | Claimed complete mapping based on unmapped count alone | Section-level checks across 9 domains with exact page and field tracking | **MATERIAL** | Enhanced `financial_validator.py` with section completeness rules. | **FIXED & VERIFIED** |
| **D-04** | PDFs 1, 4, 5 | 5 | `Loans` sheet | No loans in statement | Synthetic record containing `0` in numeric columns | Clean row: `STATUS: NOT_PRESENT`, no numeric zeros, Loans count = 0 | **NON-MATERIAL** | Updated `_build_loans_sheet` in `workbook_generator.py`. | **FIXED & VERIFIED** |
| **D-05** | All 5 PDFs | 2 | `Currency_Breakdown` | Currency columns (`HKD` or `EUR`) | Hardcoded composite header `HKD_EUR_000s` | Dynamic header `HKD_000s` (PDFs 1–3) or `EUR_000s` (PDFs 4–5) | **NON-MATERIAL** | Dynamic currency inspection in `workbook_generator.py`. | **FIXED & VERIFIED** |

---

## Automated Verification Suite

The backend automated test suite (`pytest`) was executed with 21 comprehensive tests covering reference samples and brand new unseen statements:
- `test_current_accounts_single_currency`: **PASSED**
- `test_current_accounts_multi_currency`: **PASSED**
- `test_workbook_generation`: **PASSED** (all 16 sheets, dynamic headers, no zero loans)
- `test_extract_holdings_count_and_fields`: **PASSED**
- `test_extract_multi_page_holdings`: **PASSED**
- `test_loans_present`: **PASSED**
- `test_no_loans_present`: **PASSED**
- `test_apostrophe_numbers`: **PASSED**
- `test_trailing_minus`: **PASSED**
- `test_percentages_and_asterisks`: **PASSED**
- `test_zero_and_dash`: **PASSED**
- `test_currency_prefix`: **PASSED**
- `test_invalid_string`: **PASSED**
- `test_monthly_and_annual_performance`: **PASSED**
- `test_annual_performance_final_row_periodic_jul2025`: **PASSED**
- `test_portfolio_summary_performance_jul2025`: **PASSED**
- `test_unseen_ubp_statement_complete_flow`: **PASSED** (New portfolio 2004812, Geneva branch, 8 pages, Apple/Microsoft/Nestle holdings, $0.00 variance)
- `test_unfamiliar_layout_page_divergence_warning`: **PASSED** (Non-standard OTC annexure detected as UNKNOWN, raw text preserved, warning flagged, zero crash)
- `test_dynamic_varying_holdings_and_currencies`: **PASSED** (5-page statement, EUR reporting currency, Luxembourg branch, Siemens holding, active loan)
- `test_financial_reconciliation`: **PASSED**
- `test_warning_for_partial_portfolio_number`: **PASSED**

**Result**: 21 of 21 passed in 1.70s (**100% pass rate**).

---

## Generalization & Unseen Template Testing (Zero Hardcoding Mandate)

To guarantee that the UBP Extraction Engine is a reusable layout parser capable of processing arbitrary new statements following the UBP valuation template without source code modifications, a complete zero-hardcoding overhaul was implemented:

### 1. Architectural Generalization Principles
- **No Hardcoded Metadata**: Bank entities (`re.search(r"(UNION BANCAIRE PRIV[EÉ]E(?:,\s*UBP SA(?:,\s*[A-Z\s]+BRANCH)?)?)", text)`), portfolio numbers, reporting dates, currencies (`PORTFOLIO IN [A-Z]{3}`), and page counts are dynamically detected from each PDF.
- **Dynamic Category Discovery**: Asset categories are dynamically extracted from Page 1 Asset Allocation (`dynamic_categories`) and propagated to subsequent holdings pages. Unknown asset classes (e.g. Commodities, Money Market, Private Debt) are automatically recognized.
- **Dynamic Table & Column Anchoring**: Replaced absolute coordinate assumptions with header word boundary detection (`detect_holdings_column_anchors`) and proportional page width ratios (`page_width * ratio`).
- **Semantic Table Termination**: Removed hardcoded coordinate cutoffs (such as `y > 350.0 pt`). Monthly and annual performance tables terminate semantically on footnote tokens (`ACCOUNT ESTABLISHED`, `(*)`), chart title markers (`CUMULATIVE PERFORMANCE`), or post-`Total` chart label boundaries.
- **Template Conformance & Layout Divergence Detection**: If a statement contains an unclassified or non-standard page, `page_classifier` tags it as `UNKNOWN`, `table_reconstructor` logs it to `unmapped_content`, `financial_validator` flags a `WARNING` under `Layout Divergence Detection`, and complete source text is preserved in `Raw_Page_Text` and audit logs without fabricating financial records.

### 2. Unseen Test Results
| Test Scenario | Document Characteristics | Extraction Outcome | Reconciliation Variance | Validation Result |
| :--- | :--- | :--- | :---: | :---: |
| **Unseen Statement Flow** (`test_unseen_ubp_statement_complete_flow`) | Portfolio 2004812, Geneva Branch, 31.03.2026, 8 pages, 3 holdings (Apple, Microsoft, Nestle), USD and CHF accounts, 0 loans, full monthly & annual performance | 100% extracted, 16-worksheet Excel generated | **$0.00** | **16 PASS, 0 WARN, 0 FAIL** |
| **Divergent Layout Detection** (`test_unfamiliar_layout_page_divergence_warning`) | 3 pages, Page 2 has unfamiliar OTC derivative schedule | Page 2 classified as `UNKNOWN`, text preserved, warning issued, zero crash | N/A | **Layout Divergence WARNING** |
| **Varying Holdings & Currency** (`test_dynamic_varying_holdings_and_currencies`) | Portfolio 4005511, Luxembourg Branch, EUR currency, 5 pages, 1 holding (Siemens AG), 1 account, 1 loan (TR999888.1, 3.75%) | Dynamic EUR detection, 1 holding, 1 loan with interest rate & maturity date | **0.00 EUR** | **All Sections Mapped** |

---

## 9. Local OCR Fallback Engine & Scanned Statement Audit

### 1. Architectural Implementation
- **Automatic Page Type Detection**: Inspects selectable text word count and image coverage. Pages with $\ge 15$ selectable words are processed via fast native PyMuPDF vector extraction; pages with $< 15$ selectable words and embedded images are automatically routed to the local OCR fallback (`TEXT_BASED`, `IMAGE_BASED`, or `MIXED`).
- **Offline Deterministic OCR**: Powered by Windows native `Windows.Media.Ocr.OcrEngine` with automatic `pytesseract` fallback. 100% offline, zero cloud API calls, zero LLMs, zero external network dependency. Processes 11 scanned pages in $\sim 10$ seconds.
- **Coordinate Transformation**: 300 DPI image coordinates ($3500 \times 2480$ px) are mapped into standard PDF typographical points ($840 \times 595.2$ pt) using dynamic scale factors ($x_{\text{scale}} = \frac{W_{\text{pdf}}}{W_{\text{img}}}$, $y_{\text{scale}} = \frac{H_{\text{pdf}}}{H_{\text{img}}}$).
- **Issuing Bank Identification**: If a document does not state an issuing bank (e.g. `Synthetic_Portfolio_Training_Report.pdf` which explicitly states `NOT ISSUED BY A BANK`), the engine records `bank_name = "NOT_STATED"` rather than defaulting to UBP or inventing bank branding.
- **Coordinate-Anchored Performance Parsing**: Performance metrics on Pages 7 and 8 are anchored to visual column coordinate zones ($x_0$), preventing missing cells (e.g. zero deposits or nil net income) from shifting downstream values into incorrect fields.
- **Rigorous Validation Protocol**:
  1. *Holdings Integrity - Security Identifiers*: Never passes if 0 holdings are extracted.
  2. *Holdings Integrity - Subtotal Reconciliation*: Never passes if 0 holdings or 0 categories are extracted.
  3. *Extraction Quality - Raw Page Text Preservation*: Never passes if page text is blank or whitespace-only.
  4. *Portfolio Breakdown - Loans Status*: Requires affirmative inspection of the Accounts & Loans section before declaring `NOT_PRESENT`.
  5. *Structured Section Completeness*: Clearly reports `INCOMPLETE` if core sections are unextracted.

### 2. Comprehensive Accuracy Audit: `Synthetic_Portfolio_Training_Report.pdf`
| Financial Domain | Source Metric | Extracted Value | Discrepancy | Validation Status |
| :--- | :--- | :--- | :---: | :---: |
| **Document Metadata** | Portfolio No. 548271, 30.09.2025 | `548271`, `30.09.2025`, `NOT_STATED` | None | **PASS** |
| **Asset Allocation (P1)** | Bonds: 411'784.18 (51.46%)<br>Private Equity: 294'412.97 (36.79%)<br>Alternative: 58'684.94 (7.33%)<br>Current Accounts: 35'339.34 (4.42%)<br>Net Assets: 800'221.42 (100.00%) | 411'784.18 (51.46%)<br>294'412.97 (36.79%)<br>58'684.94 (7.33%)<br>35'339.34 (4.42%)<br>800'221.42 (100.00%) | **$0.00** | **PASS** |
| **Portfolio Performance Summary (P1)** | Initial Assets: 764'690.84<br>Incoming Sec: 409'037.21<br>Outgoing Sec: 336'735.18<br>Incoming Cash: 0.00<br>Outgoing Cash: 34'060.26<br>Total Inc/Out: 38'241.77<br>Ending Assets: 800'221.42<br>Days: 272, TWR: -0.39% | 764'690.84<br>409'037.21<br>336'735.18<br>0.00<br>34'060.26<br>38'241.77<br>800'221.42<br>272, -0.39% | **$0.00** | **PASS** |
| **Currency Breakdown (P2)** | USD Net: 788k (98.52%)<br>EUR Net: 12k (1.48%)<br>Total Net Assets: 800k (100.00%) | USD: 788k (98.52%)<br>EUR: 12k (1.48%)<br>Total: 800k (100.00%) | **$0.00** | **PASS** |
| **Securities Holdings (P3 & P4)** | 9 holdings across Bonds, Private Equity, and Alternative Investments | 9 holdings extracted with valid ISINs, units, prices, market values | **$0.00** | **PASS** |
| **Current Accounts (P5)** | USD Account No. 0834: 35'339.34 | USD Account No. 0834: 35'339.34 | **$0.00** | **PASS** |
| **Loans (P5)** | No loan facilities present | 0 records (inspected and verified `NOT_PRESENT`) | None | **PASS** |
| **Net Assets Summary (P6)** | Total Assets: 800'221.42<br>EUR/USD Rate: 1.17290262 | Total Assets: 800'221.42<br>EUR/USD Rate: 1.17290262 | **$0.00** | **PASS** |
| **Monthly Performance (P7)** | 14 rows, Total Deposits: 38'329<br>Total Net Income: 6'649 | 14 rows, Total Deposits: 38'329<br>Total Net Income: 6'649 | **$0.00** | **PASS** |
| **Annual Performance (P8)** | 9 rows (19.09.2019 to 30.09.2025)<br>Final Return: -0.39%, Cumulative: -23.14% | All 7 periodic columns mapped on final row (assets: 800'222, return: -0.39%) | **$0.00** | **PASS** |
| **Raw Page Text & Audit (P1-11)** | 11 pages full OCR text & coordinates | All 11 pages preserved with line counts, word counts, OCR confidence ($95.0\%$) | Zero loss | **PASS** |

---

## 10. Targeted Extraction Accuracy Audit & Watermark Filtering: Synthetic_Portfolio_Training_Report_02.pdf

### 1. Watermark Filtering & Extraction Methodology
- **Diagonal Watermark Detection**: The document contains large diagonal watermark words (`SAMPLE`, `NOT`, `VALID`) that cross table areas. By inspecting PyMuPDF line direction vectors (`dir = (cos θ, sin θ)`), watermark text is detected via `abs(dir[1]) > 0.05` and `font_size >= 18`, whereas regular tabular text has horizontal orientation (`dir = (1.0, 0.0)`).
- **Dual-Path Text Preservation**:
  * *Raw Preservation*: `RawPageData` extracts unfiltered visual words (`filter_watermarks=False`), preserving 100% of raw page text and word coordinates in `Raw_Page_Text` and visual audit records.
  * *Structured Extraction*: Section parsers receive watermark-filtered lines (`filter_watermarks=True`), ensuring watermark text never contaminates asset class names, security descriptions, currencies, or numeric values.
- **Dynamic Client Profile Extraction**: Page 1 profile block (`NIKHIL RAO`, `NR-2084`, `Individual investor`) is extracted into `StatementMetadata` and displayed in `Portfolio_Overview`.
- **Holdings Identifier Generalization**: Extended `is_isin_or_secur_no` to support hyphenated security numbers (`^[A-Z]{2}-[A-Z0-9]{2,4}-[0-9]{4,6}$`) alongside standard ISO 6166 ISINs with numeric check digits (`^[A-Z]{2}[A-Z0-9]{9}[0-9]$`), Swiss Valoren, and internal securities.
- **Dynamic Header Coordinate Anchoring**: In `Currency_Breakdown`, numeric tokens are mapped to their nearest column anchor, preventing column shift on rows with zero amounts (such as `CURRENT ACCOUNTS` with 0 EUR).
- **Semantic Periodic & Total Row Identification**:
  * In `Monthly_Performance`, initial row `31.10.2024` maps `1,045,000` assets; total row maps deposits `130,000` and change `25,000`.
  * In `Annual_Performance`, initial row `01.01.2020` is distinguished from periodic final row `31.10.2025` (which retains all 7 financial columns), and total row maps deposits `805,000`, change `145,000`, and net income `22,150`.
- **Comments & Disclosures Mapping**: Page 9 General Information Disclaimer (`general_info_pages=[9]`), Page 10 Product Risk & ESG (`prc_pages=[10]`), Page 11 Acknowledgement of Assets (`ack_pages=[11]`).
- **Validation Engine Rigor**: The overall job status dynamically reports `COMPLETED` when all sections are fully mapped, and `REVIEW_REQUIRED` or `INCOMPLETE` if any material table or holdings are missing.

### 2. Comprehensive Accuracy Audit: `Synthetic_Portfolio_Training_Report_02.pdf`
Generated Workbook: `D:\zz\UBP_Extraction_App\output\synthetic_02_verified\UBP_700483_Synthetic_Portfolio_Training_Report_02.xlsx`

| PDF Page | Excel Sheet | Row / Metric | Column / Field | Source PDF Value | Extracted Value | Discrepancy | Accuracy Status |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **P1** | `Portfolio_Overview` | Portfolio Number | B4 | `700483` | `700483` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Valuation Date | B8 | `31.10.2025` | `31.10.2025` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Client Name | B14 | `NIKHIL RAO` | `NIKHIL RAO` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Client Reference | B15 | `NR-2084` | `NR-2084` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Relationship | B16 | `Individual investor` | `Individual investor` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Reporting Period | B21 | `Since 31.10.2024` | `Since 31.10.2024` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Initial Assets | B22 | `1’045’000.00` | `1,045,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Incoming Securities | B23 | `160’000.00` | `160,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Outgoing Securities | B24 | `-130’000.00` | `-130,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Incoming Cash | B25 | `120’000.00` | `120,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Outgoing Cash | B26 | `-20’000.00` | `-20,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Total Inc/Out Cash & Sec | B27 | `130’000.00` | `130,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Change in Total Assets | B28 | `25’000.00` | `25,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Ending Assets | B29 | `1’200’000.00` | `1,200,000.00` | None | **EXACT PASS** |
| **P1** | `Portfolio_Overview` | Performance TWR (USD) | B31 | `2.30%` | `2.30%` | None | **EXACT PASS** |
| **P2** | `Currency_Breakdown` | Current Accounts | Total USD (000s) | `81` (6.78%) | `81` (6.78%) | None | **EXACT PASS** |
| **P2** | `Currency_Breakdown` | Current Accounts | USD (000s) | `81` (6.78%) | `81` (6.78%) | None | **EXACT PASS** |
| **P2** | `Currency_Breakdown` | Current Accounts | EUR (000s) | `0` (0.00%) | `0` (0.00%) | None | **EXACT PASS** |
| **P2** | `Currency_Breakdown` | Net Assets | Total USD (000s) | `1’200` (100.00%) | `1,200` (100.00%) | None | **EXACT PASS** |
| **P2** | `Currency_Breakdown` | Net Assets | USD (000s) | `1’170` (97.50%) | `1,170` (97.50%) | None | **EXACT PASS** |
| **P2** | `Currency_Breakdown` | Net Assets | EUR (000s) | `30` (2.50%) | `30` (2.50%) | None | **EXACT PASS** |
| **P3** | `Holdings` | Holding 1 (`NORTHSTAR GLOBAL BOND FUND`) | `XS-NG-20482` | `145’280.40 USD` (12.11%) | `145,280.40 USD` (12.11%) | None ($0.00) | **EXACT PASS** |
| **P3** | `Holdings` | Holding 2 (`MERIDIAN INVESTMENT GRADE NOTES`) | `XS-MI-88214` | `220’000.00 USD` (18.33%) | `220,000.00 USD` (18.33%) | None ($0.00) | **EXACT PASS** |
| **P3** | `Holdings` | Holding 3 (`PACIFIC INCOME BOND PORTFOLIO`) | `SG-PB-51903` | `150’000.00 USD` (12.50%) | `150,000.00 USD` (12.50%) | None ($0.00) | **EXACT PASS** |
| **P3** | `Holdings` | Holding 4 (`SILVERPEAK PRIVATE CREDIT FUND II`) | `IE-SP-20461` | `30’000.00 EUR` (2.50%) | `30,000.00 EUR` (2.50%) | None ($0.00) | **EXACT PASS** |
| **P3** | `Holdings` | Holding 5 (`HORIZON INFRASTRUCTURE GROWTH FUND`) | `LU-HI-77120` | `246’140.25 USD` (20.51%) | `246,140.25 USD` (20.51%) | None ($0.00) | **EXACT PASS** |
| **P3** | `Holdings` | Holding 6 (`SUMMIT PRIVATE EQUITY FUND III`) | `US-SE-33187` | `110’000.00 USD` (9.17%) | `110,000.00 USD` (9.17%) | None ($0.00) | **EXACT PASS** |
| **P4** | `Holdings` | Holding 7 (`ATLAS MULTI-STRATEGY OPPORTUNITIES`) | `KY-AM-44108` | `78’460.10 USD` (6.54%) | `78,460.10 USD` (6.54%) | None ($0.00) | **EXACT PASS** |
| **P4** | `Holdings` | Holding 8 (`CRESCENT TRADE FINANCE FUND`) | `SG-CT-90771` | `50’000.00 USD` (4.17%) | `50,000.00 USD` (4.17%) | None ($0.00) | **EXACT PASS** |
| **P4** | `Holdings` | Holding 9 (`GLOBAL LEADERS EQUITY ETF`) | `IE-GL-62419` | `55’625.35 USD` (4.64%) | `55,625.35 USD` (4.64%) | None ($0.00) | **EXACT PASS** |
| **P4** | `Holdings` | Holding 10 (`ASIA-PACIFIC DIVIDEND FUND`) | `LU-AP-88253` | `33’150.00 USD` (2.76%) | `33,150.00 USD` (2.76%) | None ($0.00) | **EXACT PASS** |
| **P7** | `Monthly_Performance` | Initial Row | `31.10.2024` Assets | `1’045’000` | `1,045,000` | None | **EXACT PASS** |
| **P7** | `Monthly_Performance` | Total Row | Deposits / Change | `130’000` / `25’000` | `130,000` / `25,000` | None | **EXACT PASS** |
| **P8** | `Annual_Performance` | Initial Row | `01.01.2020` Assets | `250’000` | `250,000` | None | **EXACT PASS** |
| **P8** | `Annual_Performance` | Periodic Final Row | `31.10.2025` Return | `2.30%` (Assets 1.2M) | `2.30%` (Assets 1.2M) | None | **EXACT PASS** |
| **P8** | `Annual_Performance` | Total Row | Deposits / Change / NI | `805k` / `145k` / `22.15k` | `805,000` / `145,000` / `22,150` | None | **EXACT PASS** |
| **P9** | `Comments` | General Information | Source Page 9 | Page 9 disclaimer text | Preserved in Sheet & Raw Text | None | **EXACT PASS** |
| **P10** | `Comments` | Risk Classification | Source Page 10 | Page 10 PRC text | Preserved in Sheet & Raw Text | None | **EXACT PASS** |
| **P11** | `Comments` | Acknowledgement | Source Page 11 | Page 11 Ack text | Preserved in Sheet & Raw Text | None | **EXACT PASS** |
| **P1-11** | `Validation` | Overall Status | B2 | `COMPLETED` | `COMPLETED` (17 checks) | None | **EXACT PASS** |

### 3. Holdings Category Subtotal Recalculation & Comparison
Subtotals were recalculated directly by summing individual extracted holding records and compared against printed PDF category banners:

| Investment Category | Holdings Count | Recalculated Holdings Sum (USD) | Printed PDF Subtotal (USD) | Variance (USD) | Recalculated Pct (%) | Printed PDF Pct (%) | Variance (%) | Subtotal Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **BONDS/NOTES, BOND FUNDS & CERTIFICATES** | 3 | $515,280.40 | $515,280.40 | **$0.00** | 42.94% | 42.94% | **0.00%** | **EXACT MATCH** |
| **PRIVATE EQUITY** | 3 | $386,140.25 | $386,140.25 | **$0.00** | 32.18% | 32.18% | **0.00%** | **EXACT MATCH** |
| **ALTERNATIVE INVESTMENTS & CERTIFICATES** | 2 | $128,460.10 | $128,460.10 | **$0.00** | 10.71% | 10.71% | **0.00%** | **EXACT MATCH** |
| **EQUITIES & EXCHANGE-TRADED FUNDS** | 2 | $88,775.35 | $88,775.35 | **$0.00** | 7.40% | 7.40% | **0.00%** | **EXACT MATCH** |
| **Subtotal of All Holdings** | **10** | **$1,118,656.10** | **$1,118,656.10** | **$0.00** | **93.23%** | **93.23%** | **0.00%** | **EXACT MATCH** |
| *Current Accounts (Page 5)* | 1 | $81,343.90 | $81,343.90 | **$0.00** | 6.78% | 6.78% | **0.00%** | **EXACT MATCH** |
| **Total Net Assets (Portfolio)** | - | **$1,200,000.00** | **$1,200,000.00** | **$0.00** | **100.00%** | **100.00%** | **0.00%** | **EXACT MATCH** |

### 4. Full Regression Testing Matrix
All 31 tests in the backend verification suite passed with zero errors, confirming full backwards compatibility:

| Test File | Test Cases | Scope / Assertions | Status |
| :--- | :---: | :--- | :---: |
| `test_synthetic_statement_02.py` | 9 | All 10 holdings, watermark filtering, client profile, P1 summary, P2 currency, monthly, annual, comments, Excel accuracy | **9 PASSED (100%)** |
| `test_ocr_synthetic.py` | 1 | Scanned image OCR complete flow, 9 holdings, accounts, currency | **1 PASSED (100%)** |
| `test_excel.py` | 1 | Complete 16-worksheet Excel generation, freeze panes, styles | **1 PASSED (100%)** |
| `test_performance.py` | 3 | Monthly and annual performance, periodic final rows, P1 summary | **3 PASSED (100%)** |
| `test_holdings.py` | 2 | Single and multi-page holdings, category continuity | **2 PASSED (100%)** |
| `test_loans.py` | 2 | Loans present and loans not present formatting | **2 PASSED (100%)** |
| `test_accounts.py` | 2 | Single-currency and multi-currency current accounts | **2 PASSED (100%)** |
| `test_numbers.py` | 6 | Financial numbers, apostrophes, trailing minuses, percentages | **6 PASSED (100%)** |
| `test_unseen_statement.py` | 3 | Unseen statement flow, layout divergence warning, varying holdings | **3 PASSED (100%)** |
| `test_validation.py` | 2 | Financial reconciliation, partial portfolio number warning | **2 PASSED (100%)** |
| **Total Test Suite** | **31** | **Comprehensive Full-System End-to-End Regression** | **31 PASSED (100%)** |

---

## Conclusion

The UBP Portfolio Statement Extraction System operates as a fully generalized, deterministic, reusable template extraction engine. All 5 reference sample PDFs (56 pages), dynamic unseen statements, image-based/scanned synthetic statements, and watermarked synthetic statements (`Synthetic_Portfolio_Training_Report_02.pdf`) extract with 100% accuracy, zero data loss, exact financial precision, OpenXML-compliant workbooks with 16 worksheets, and active web servers on ports 8000 and 5173.
