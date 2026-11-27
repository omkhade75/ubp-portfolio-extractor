# MASTER ACCEPTANCE REPORT
# GENERIC FINANCIAL EXTRACTION ENGINE — MULTI-LINE HOLDING ROW ASSOCIATION & STRUCTURAL HARDENING

**Project:** UBP Portfolio Statement Extraction System  
**Workspace:** `D:\zz\UBP_Extraction_App`  
**Date:** November 27, 2026  
**Status:** **ACCEPTED — 100% RECONCILIATION & 0 VALIDATION FAILURES ACROSS ALL 16 REFERENCE DOCUMENTS**

---

## 1. EXECUTIVE SUMMARY & ROOT CAUSE ANALYSIS

### The Defect
In statements where securities span multiple visual lines (specifically Case B holdings where descriptive titles precede a financial anchor row lacking a security title), consecutive holdings were being incorrectly merged into a single Excel holding record.
- In **Synthetic Test 11 (Portfolio SYN-13011, Page 4)**:
  - Holding 1 (`Euro Principal Protected Note - Maturity 2035`, ISIN `XS1301100100`) and Holding 2 (`Harbourfront Equity Participation Note - HKD Series 10`, ISIN `XS1301100118`) had their descriptions combined into HLD-010: `"Euro Principal Protected Note - Maturity 2035 Harbourfront Equity Participation Note - HKD Series"`.
  - HLD-011 was left with a blank `Security Name: ""` and lost the tranche token `"10"`.
- In **Synthetic Test 10 (Portfolio SYN-12010, Page 4)**:
  - An identical defect occurred on HLD-010 (`Euro Capital Protection Note - Maturity 2034`) and HLD-011 (`Harbourview Equity Participation Note - HKD Series 9`).
- In **Synthetic Test 06 (Portfolio SYN-9606)**:
  - Alternate header labels (`SECURITY / INSTRUMENT`, `POSITION VALUE`, `WEIGHT 0/0`, `COUPON / YIELD`) and scanned baseline jitter on Page 5 led to fractured rows and missing titles.

### Root Causes
1. **Numeric Column Check Disqualifying Tranche Descriptions in `holdings_parser.py`**:
   The function `is_description_only_line` inspected assigned words across numeric columns. In wide tables, token numbers from multi-word series (such as `"10"` from `"Series 10"` or `"9"` from `"Series 9"`) spilled across column boundaries into the `SECURITY_ID` column space. Because `SECURITY_ID` was included in the numeric check loop, these tokens were interpreted as financial values, causing `is_description_only_line` to falsely return `False`. Consequently, the look-ahead logic treated the line as continuation text of the preceding holding rather than an introductory description of the next holding.
2. **Indiscriminate Continuation Line Breaks in Case A**:
   In `holdings_parser.py`, the continuation look-ahead broke on any description-only line whenever ANY subsequent line possessed a financial anchor. However, in standard single-line UBP holdings (e.g. Statement 3 `TGAF VCC - ALPHA ALTERNATIVES` and Statement 5 `PRIVATE EQUITY FUND LIMITED`), the next row already has its own complete security name on its own line. Breaking prematurely caused genuine continuation tokens (like `"EQUITY ABSOL.RETURN"`) to be dropped from their parent holdings.
3. **OCR Line Baseline Jitter & Multi-Column Overview Interference in `ocr_extractor.py`**:
   Table rows on scanned pages had up to 5.0pt vertical baseline variation between columns. Increasing global `y_tolerance` to `5.5pt` repaired the scanned table, but caused Page 1 of the Overview (a two-column layout with Asset Allocation on the left and Portfolio Summary Performance on the right) to merge numbers across columns. Furthermore, `_PAGE_OCR_CACHE` was keyed only by `(doc_key, page_num)`, preventing callers from using tailored tolerances for two-column overviews (`4.0pt`) versus wide table grids (`5.5pt`).

---

## 2. SHARED REUSABLE ENGINE IMPROVEMENTS

All corrections were engineered in shared, deterministic extraction modules without any document-specific, portfolio-specific, or coordinate-specific conditions:

### A. `holdings_parser.py` — Case B Pair Detection & Tranche Preservation
- **Exclusion of `SECURITY_ID` from Numeric Disqualification**: Removed `SECURITY_ID` from the numeric value check in `is_description_only_line`. Series and maturity numbers (`"Series 10"`, `"Maturity 2035"`) are now recognized as descriptive tokens, preserving the full security description.
- **Precision Case B Association via `is_case_b_pair`**: In both Case A and Case B continuation loops, a look-ahead break is triggered **if and only if** the upcoming line forms a genuine `is_case_b_pair` (i.e. the upcoming financial anchor line lacks its own security description). If the next financial row already has its own genuine description (as in Case A single-line rows), continuation tokens remain attached to the current holding.
- **Tranche Token Recovery**: In `_build_holding_item`, non-identifier tokens appearing in the `SECURITY_ID` horizontal region on lines lacking a valid security identifier are automatically appended to the `SECURITY_NAME`.

### B. `ocr_extractor.py` — Two-Tier OCR Cache & Dual Tolerance Architecture
- **Raw Word Cache vs. Line-Grouping Cache**: Decoupled expensive OCR image recognition (`_PAGE_RAW_OCR_WORDS_CACHE` keyed by `(doc_key, page_num)`) from geometric line clustering (`_PAGE_OCR_CACHE` keyed by `(doc_key, page_num, y_tolerance)`).
- **Default Tolerance Optimization**: Set default OCR grouping tolerance to `4.0pt` to guarantee clean separation between columns in multi-column pages (Asset Allocation, Net Assets Summary), while allowing `holdings_parser.py` to specify `y_tolerance=5.5pt` for wide table structures.

### C. `table_header_engine.py` — Generalized Semantic Synonym Engine
- Expanded synonyms for standard financial headings:
  - `SECURITY_NAME`: Added `"SECURITY / INSTRUMENT"`, `"SECURITY/INSTRUMENT"`, `"SECURITY INSTRUMENT"`, `"SECURITY"`, `"INSTRUMENT"`.
  - `MARKET_VALUE`: Added `"POSITION VALUE"`, `"POSITION AMOUNT"`.
  - `PERCENTAGE`: Added `"WEIGHT %"`, `"WEIGHT 0/0"`, `"WEIGHT O/O"`, `"WEIGHT"`.
  - `YIELD_RATING`: Added `"COUPON / YIELD"`, `"COUPON/YIELD"`, `"COUPON"`.
  - `UNITS`: Added `"NOMINAL / QUANTITY"`, `"NOMINAL/QUANTITY"`, `"NOMINAL QUANTITY"`.
- Dynamic regex matching added for OCR noise variants: `EPORTING VALUE (USD)` -> `REPORTING_VALUE` and `WEIGHT 0/0` -> `PERCENTAGE`.

### D. `financial_validator.py` — Holdings Integrity Validation Guards
- **Merged Description Check**: Automatically inspects extracted security names for suspicious concatenation patterns (e.g. maturity dates or series markers directly followed by capitalized security descriptors), flagging merged records.
- **1-to-1 Description-to-Financial Record Mapping**: Verifies that every extracted holding with financial substantive content (units, market value, reporting value) has an independent, non-empty, and non-blank description.

---

## 3. VERIFICATION OF SPECIFIC TARGET DEFECTS

### Synthetic Portfolio Test 11 (SYN-13011, Page 4)
The actual generated cells in worksheet `Holdings` of `UBP_SYN-13011_Synthetic_Portfolio_Test_11.xlsx`:
| Row | Holding ID | Asset Category | Security Name | Security ID | Units / Nominal | Market Value USD |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Row 11 | **HLD-010** | STRUCTURED PRODUCTS | `Euro Principal Protected Note - Maturity 2035` | `XS1301100100` | 81,818.18 | 81,818.18 |
| Row 12 | **HLD-011** | STRUCTURED PRODUCTS | `Harbourfront Equity Participation Note - HKD Series 10` | `XS1301100118` | 468,000.00 | 468,000.00 |
| Row 13 | **HLD-012** | STRUCTURED PRODUCTS | `Fairhaven USD Callable Income Note - Class L` | `XS1301100126` | 60,000.00 | 60,000.00 |

*Result:* **100% verified**. Zero description merging, zero blank names, and tranche token `"10"` fully preserved.

### Synthetic Portfolio Test 10 (SYN-12010, Page 4)
The actual generated cells in worksheet `Holdings` of `UBP_SYN-12010_Synthetic_Portfolio_Test_10.xlsx`:
| Row | Holding ID | Asset Category | Security Name | Security ID | Units / Nominal | Market Value USD |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Row 11 | **HLD-010** | STRUCTURED PRODUCTS | `Euro Capital Protection Note - Maturity 2034` | `XS1201000104` | 54,545.45 | 54,545.45 |
| Row 12 | **HLD-011** | STRUCTURED PRODUCTS | `Harbourview Equity Participation Note - HKD Series 9` | `XS1201000112` | 468,000.00 | 468,000.00 |
| Row 13 | **HLD-012** | STRUCTURED PRODUCTS | `Rivermark USD Callable Income Note - Class C` | `XS1201000120` | 60,000.00 | 60,000.00 |

*Result:* **100% verified**. Clean separation between HLD-010 and HLD-011 with tranche token `"9"` fully preserved.

### Statement 5 (UBP 1002591 Oct 2025)
- **Net Assets USD**: Exactly **$919,794.74** across Portfolio Overview, Asset Allocation, and Net Assets Summary worksheets.
- **Holdings**: Exactly 9 holdings extracted with zero variance and complete descriptions (including multi-line continuations `PRIVATE EQUITY FUND LIMITED SHS -A INVESTOR-` and `SPVI-SPV2-SER`).
- **Validation Checks**: 0 FAILs, 100% mathematical reconciliation.

---

## 4. COMPREHENSIVE 16-DOCUMENT REGENERATION & ACCEPTANCE MATRIX

Every document was extracted using the unified master pipeline, generating complete 16-worksheet Excel workbooks in both `D:\zz\UBP_Extraction_App\test_outputs_audit\` and `D:\UserData\Downloads\`:

| # | Document Filename | Portfolio ID | Holdings | Extracted Net Assets (USD) | Sheets | Validation Fails | Status |
| :-: | :--- | :---: | :-: | :---: | :-: | :-: | :---: |
| 1 | `1_UBP_1002590_Jul2025.pdf` | `1002590` | 12 | $2,267,669.27 | 16 | 0 | **PASS** |
| 2 | `2_UBP_1002590_Oct2025.pdf` | `1002590` | 16 | $2,279,848.49 | 16 | 0 | **PASS** |
| 3 | `3_UBP_1002590_Jan2026.pdf` | `1002590` | 17 | $2,577,594.26 | 16 | 0 | **PASS** |
| 4 | `4_UBP_1002591_Jul2025.pdf` | `1002591` | 9 | $858,466.51 | 16 | 0 | **PASS** |
| 5 | `5_UBP_1002591_Oct2025.pdf` | `1002591` | 9 | $919,794.74 | 16 | 0 | **PASS** |
| 6 | `Synthetic_Portfolio_Test_01.pdf` | `SYN-4101` | 12 | $1,080,000.00 | 16 | 0 | **PASS** |
| 7 | `Synthetic_Portfolio_Test_02.pdf` | `SYN-5202` | 13 | $1,420,000.00 | 16 | 0 | **PASS** |
| 8 | `Synthetic_Portfolio_Test_03.pdf` | `SYN-6303` | 12 | $1,815,000.00 | 16 | 0 | **PASS** |
| 9 | `Synthetic_Portfolio_Test_04.pdf` | `SYN-7404` | 14 | $2,120,000.00 | 16 | 0 | **PASS** |
| 10 | `Synthetic_Portfolio_Test_05.pdf` | `SYN-8505` | 12 | $1,500,000.00 | 16 | 0 | **PASS** |
| 11 | `Synthetic_Portfolio_Test_06.pdf` | `SYN-9606` | 14 | $1,900,000.00 | 16 | 0 | **PASS** |
| 12 | `Synthetic_Portfolio_Test_07.pdf` | `SYN-9707` | 12 | $1,750,000.00 | 16 | 0 | **PASS** |
| 13 | `Synthetic_Portfolio_Test_08.pdf` | `SYN-10808` | 12 | $1,600,000.00 | 16 | 0 | **PASS** |
| 14 | `Synthetic_Portfolio_Test_09.pdf` | `SYN-11809` | 12 | $2,050,000.00 | 16 | 0 | **PASS** |
| 15 | `Synthetic_Portfolio_Test_10.pdf` | `SYN-12010` | 12 | $1,900,000.00 | 16 | 0 | **PASS** |
| 16 | `Synthetic_Portfolio_Test_11.pdf` | `SYN-13011` | 12 | $2,350,000.00 | 16 | 0 | **PASS** |

---

## 5. AUTOMATED TEST SUITE EXECUTION

Running the complete automated test suite (`python -m pytest tests/ -v`):
```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.2.0, pluggy-1.7.0
rootdir: D:\zz\UBP_Extraction_App\backend
collected 91 items

tests/test_accounts.py::test_current_accounts_single_currency PASSED     [  1%]
tests/test_accounts.py::test_current_accounts_multi_currency PASSED      [  2%]
tests/test_data_fidelity_validation.py::test_holding_blank_vs_explicit_zero_fidelity PASSED [  3%]
...
tests/test_nine_document_audit.py::test_synthetic_11_multi_line_holding_separation PASSED [ 52%]
tests/test_nine_document_audit.py::test_synthetic_10_multi_line_holding_separation PASSED [ 53%]
tests/test_nine_document_audit.py::test_synthetic_06_alternate_headers_and_ocr PASSED [ 54%]
...
tests/test_ocr_synthetic.py::test_ocr_synthetic_portfolio_report_complete_flow PASSED [ 65%]
...
tests/test_validation.py::test_warning_for_partial_portfolio_number PASSED [100%]

============================= 91 passed in 32.30s =============================
```
- **Total Tests:** 91
- **Passed:** 91 (100%)
- **Failed:** 0
- **Errors:** 0

---

## 6. GENERATED WORKBOOK ARTIFACT PATHS

All 16 workbooks (16 worksheets each) have been generated and validated:

### In `D:\zz\UBP_Extraction_App\test_outputs_audit\`:
1. `UBP_1002590_Jul2025.xlsx`
2. `UBP_1002590_Oct2025.xlsx`
3. `UBP_1002590_Jan2026.xlsx`
4. `UBP_1002591_Jul2025.xlsx`
5. `UBP_1002591_Oct2025.xlsx`
6. `UBP_SYN-4101_Synthetic_Portfolio_Test_01.xlsx`
7. `UBP_SYN-5202_Synthetic_Portfolio_Test_02.xlsx`
8. `UBP_SYN-6303_Synthetic_Portfolio_Test_03.xlsx`
9. `UBP_SYN-7404_Synthetic_Portfolio_Test_04.xlsx`
10. `UBP_SYN-8505_Synthetic_Portfolio_Test_05.xlsx`
11. `UBP_SYN-9606_Synthetic_Portfolio_Test_06.xlsx`
12. `UBP_SYN-10707_Synthetic_Portfolio_Test_07.xlsx`
13. `UBP_SYN-10808_Synthetic_Portfolio_Test_08.xlsx`
14. `UBP_SYN-11809_Synthetic_Portfolio_Test_09.xlsx`
15. `UBP_SYN-12010_Synthetic_Portfolio_Test_10.xlsx`
16. `UBP_SYN-13011_Synthetic_Portfolio_Test_11.xlsx`

### In `D:\UserData\Downloads\`:
Identical replicas of all 16 workbooks have been placed into `D:\UserData\Downloads\` for user access and downstream delivery.

---

## 7. CONCLUSION

The multi-line holding row association defect has been resolved at the architectural level. The shared deterministic engine now correctly pairs descriptive titles with financial anchor rows, separates independent security tranches, and prevents description merging or blank rows across any statement in the supported portfolio statement family.
