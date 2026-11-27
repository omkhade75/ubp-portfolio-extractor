# GENERIC FINANCIAL EXTRACTION ENGINE — OCR, ESG & HOLDINGS ACCEPTANCE REPORT

**Project:** UBP Wealth Management Portfolio Statement Extraction System  
**Workspace:** `D:\zz\UBP_Extraction_App\`  
**Engine Architecture:** Deterministic Offline Local Processing (No LLMs, No Cloud OCR, No External APIs)  
**Date:** 2026-11-27  

---

## 1. ROOT CAUSE ANALYSIS

| Defect ID | Description | Root Cause |
|---|---|---|
| **Defect 1: Phantom ESG Holding** | Standalone line `ESG 078 / 078` created an artificial 14th holding with blank name, identifier `078`, blank units/values. | In `_extract_identifier_from_words`, the 3-digit score `078` matched the fallback numeric check inside the `SECURITY_ID` column. Furthermore, `_is_primary_line` lacked positive structural checks (valid security description, units, or financial values), treating lines with zero financial content as primary holding rows. |
| **Defect 2: OCR Security Identifiers** | On image-only page 5, Tesseract produced `XSSYNO0001081` and `XSSYNO0001090` (extraneous `O` inserted), and Windows OCR produced `XSSYNOOOI090` (letter confusions `O`->`0`, `I`->`1`). | Lack of format-guided character confusion normalization for ISINs / synthetic codes. Font kerning between alpha prefix `XSSYN` and digits created a boundary misclassification (`O`), and glyph similarity between `O`/`0` and `I`/`1` in numeric suffixes was not normalized against expected column patterns. |
| **Defect 3: Portfolio ESG Ratings Not Separated** | Page 1 string `PORTFOLIO ESG (PREVIOUS / CURRENT)` with value `BBB+ / A (AVERAGE)` was placed entirely into current ESG rating, leaving previous ESG empty. | `parse_portfolio_esg_generic` required symmetrical qualifiers (either both ratings having parentheses or neither having parentheses). `BBB+` had no parentheses while `A (AVERAGE)` had parentheses, causing the regex to fall through and return `(None, 'BBB+ / A (AVERAGE)')`. |

---

## 2. SHARED MODULES MODIFIED

1. **`backend/app/extraction/identifier_engine.py` (New Shared Engine)**
   - Implements multi-format validation: ISO 6166 ISIN, Swiss Valoren, CUSIP, UBP Internal, and Synthetic hyphenated codes.
   - Implements format-guided character confusion handling (`O`->`0`, `I`->`1`, `l`->`1`, `S`->`5`, `B`->`8`, `Z`->`2`).
   - Removes extraneous boundary artifact `O` inserted between alpha prefix and numeric payload (`XSSYNO0001081` -> `XSSYN0001081`).
   - Maintains full provenance: `raw_identifier`, `normalized_identifier`, `status` (`PASS`, `NORMALIZED`, `REVIEW_REQUIRED`), `provenance`, and `confidence`.

2. **`backend/app/extraction/holdings_parser.py`**
   - Implemented `is_primary_holding_line(l, col_map)` at module level:
     - Rejects any line containing `\bESG\b`, date-only patterns, credit rating only lines, or watermark noise.
     - Enforces **Primary Row Structural Substance**: a row must possess at least one of (a) valid security description (>=2 chars), (b) valid units, or (c) valid market value / price evidence.
   - Integrated `_extract_identifier_from_words` with `normalize_security_identifier`, rejecting 3-digit ESG scores (`078`) and ESG lines.
   - Enhanced continuation line processing: attaches inline ESG ratings (`ESG 078 / 078`, `ESG AA / A`, `ESG BBB+ / A`, `ESG AA (LEADER) / AA (LEADER)`) to parent holding records cleanly.
   - Populates `raw_identifier`, `identifier_status`, `identifier_provenance`, and `identifier_confidence` on `HoldingItem`.

3. **`backend/app/extraction/summary_parser.py`**
   - Upgraded `parse_portfolio_esg_generic`:
     - Robust delimiter parsing on `/` or `|` outside parentheses (`BBB+ / A (AVERAGE)` -> `BBB+`, `A (AVERAGE)`).
     - Handles asymmetrical qualifiers, numeric scores (`078 / 078`), and standard codes (`AA / A`).
     - Supports consecutive line layout where rating appears immediately below header.
     - Populates `portfolio_esg_previous`, `portfolio_esg_current`, `portfolio_esg_source_page`, and `portfolio_esg_provenance = "EXTRACTED"`.

4. **`backend/app/extraction/table_reconstructor.py`**
   - Propagates `portfolio_esg_previous`, `portfolio_esg_current`, `portfolio_esg_source_page`, and `portfolio_esg_provenance` to `StatementMetadata`.

5. **`backend/app/models/schemas.py`**
   - Added `portfolio_esg_provenance` to `StatementMetadata` and `PortfolioSummaryPerformance`.
   - Added `raw_identifier`, `identifier_status`, `identifier_provenance`, and `identifier_confidence` to `HoldingItem`.

6. **`backend/app/excel/workbook_generator.py`**
   - Portfolio Overview worksheet: Formats `Portfolio_ESG_Previous`, `Portfolio_ESG_Current`, `Portfolio_ESG_Source_Page`, and `Portfolio_ESG_Provenance`.
   - Preserves all 16 standardized worksheets:
     `Portfolio_Overview`, `Asset_Allocation`, `Currency_Breakdown`, `Holdings`, `Current_Accounts`, `Loans`, `Transactions`, `Net_Assets_Summary`, `Exchange_Rates`, `Monthly_Performance`, `Annual_Performance`, `Comments`, `Counts`, `Validation`, `Unmapped_Content`, `Raw_Page_Text`.

---

## 3. SYNTHETIC TEST COMPARISON & ACCURACY

### Synthetic Test 01 (11 Pages)
- **Holdings Extracted:** 12 (expected: 12).
- **Accounts & Loans:** 2 accounts, 1 loan.
- **Currencies:** USD, EUR, HKD.
- **ESG Extracted:** Fully preserved and matched.
- **Status:** **PASS** (100% regression parity).

### Synthetic Test 02 (12 Pages) — Before vs After

| Metric | Before Hardening | After Hardening | Status |
|---|---|---|---|
| **Total Holdings Count** | 14 (1 phantom holding created from `ESG 078 / 078`) | **13** (exact genuine financial holdings) | **PASS** |
| **Phantom Holding #9** | Present (`Name: ''`, `ID: '078'`) | **ELIMINATED** | **PASS** |
| **Cobalt Alpine Property Fund ESG** | `None / None` | **`078 / 078`** (continuation attached) | **PASS** |
| **Silver Fern European Growth ESG** | `A / AA` | **`A / AA`** (continuation attached) | **PASS** |
| **Page 5 OCR ID 1 (Juniper)** | `CUSP-TEST-OI (REVIEW_REQUIRED)` | **`CUSP-TEST-01`** (normalized) | **PASS** |
| **Page 5 OCR ID 2 (Callable Note)** | `XSSYNO0001081` | **`XSSYN0001081`** (normalized) | **PASS** |
| **Page 5 OCR ID 3 (Equity-Linked)** | `XSSYNO0001090` / `XSSYNOOOI090` | **`XSSYN0001090`** (normalized) | **PASS** |
| **Portfolio ESG Previous** | `None` (empty) | **`BBB+`** | **PASS** |
| **Portfolio ESG Current** | `BBB+ / A (AVERAGE)` (unsplit) | **`A (AVERAGE)`** | **PASS** |
| **Current Accounts** | 3 (USD, EUR, CHF) | **3** (USD, EUR, CHF) | **PASS** |
| **Loans** | 2 (`LN-TEST-5202-A`, `LN-TEST-5202-B`) | **2** (`LN-TEST-5202-A`, `LN-TEST-5202-B`) | **PASS** |
| **Currencies** | 4 (USD, EUR, CHF, HKD) | **4** (USD, EUR, CHF, HKD) | **PASS** |
| **Exchange Rates** | 3 (EUR/USD, CHF/USD, USD/HKD) | **3** (EUR/USD, CHF/USD, USD/HKD) | **PASS** |
| **Monthly Performance Rows** | 14 rows | **14 rows** | **PASS** |
| **Annual Performance Rows** | 7 rows | **7 rows** | **PASS** |
| **USD 25 Flow Discrepancy** | Preserved | **Preserved without falsification** | **PASS** |

---

## 4. REGRESSION VERIFICATION ACROSS TEST SUITE

The entire backend test suite was executed locally:
- **Total Tests Executed:** 70
- **Passed:** 70 (100%)
- **Failed:** 0
- **Execution Time:** ~21.5 seconds

### Verified Reference Statements:
1. `Statement 1 (Jan 2026)`: LU2001707251 holdings, single/multi-currency accounts, period-aligned flows -> **PASS**
2. `Statement 2 (Oct 2025)`: Multi-page continuation lines, zero phantom holdings -> **PASS**
3. `Statement 3 (Jul 2025)`: Loans extraction, missing portfolio number warning fallback -> **PASS**
4. `Statement 4 (Apr 2025)`: Alternative investments column mapping, cash flows -> **PASS**
5. `Statement 5 (Feb 2025)`: Cross-section net assets reconciliation, zero-vs-blank fidelity -> **PASS**
6. `Synthetic Portfolio Test 01`: Full 11-page extraction, 12 holdings, USD/EUR/HKD breakdown -> **PASS**
7. `Synthetic Portfolio Test 02`: Full 12-page extraction, 13 holdings, OCR identifiers, ESG separation -> **PASS**

---

## 5. FRONTEND VERIFICATION

- **TypeScript Compilation (`tsc`):** Clean (0 errors).
- **Vite Production Build:** Success (`dist/index.html`, `dist/assets/index-BCq5D8XP.css`, `dist/assets/index-DO5ptz87.js`).
- **Build Duration:** 2.15 seconds.

---

## 6. FINAL ACCEPTANCE DECISION

**STATUS: ACCEPTED**  
All three defects identified in Synthetic Test 02 have been completely resolved using reusable, deterministic financial document parsing and OCR normalization logic. No hardcoded document numbers, security names, or test filenames exist in production code.
