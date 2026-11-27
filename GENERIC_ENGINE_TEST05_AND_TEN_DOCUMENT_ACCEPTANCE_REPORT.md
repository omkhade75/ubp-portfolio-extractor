# MASTER ENGINEERING ACCEPTANCE REPORT
## GENERIC FINANCIAL PDF EXTRACTION ENGINE — ALTERNATE HEADER TERMINOLOGY, MULTI-LINE HOLDINGS & TEN-DOCUMENT RECONCILIATION

**Project:** UBP Portfolio Statement Extraction System  
**Workspace:** `D:\zz\UBP_Extraction_App\`  
**Target Reference Document:** `Synthetic_Portfolio_Test_05.pdf` (Portfolio `SYN-8505`)  
**Regression Corpus:** 5 Original UBP PDFs + 5 Synthetic Portfolio Documents (10 Total Statements)  
**Status:** **ACCEPTED — 100% Deterministic Python, Zero AI/LLM Dependencies, 82/82 Automated Tests Passing, 0 FAIL Validation Checks Across All 10 Documents**

---

## 1. EXECUTIVE SUMMARY

The generic financial document extraction engine has been successfully upgraded and validated across the complete portfolio statement suite, including the new challenging test document: `Synthetic_Portfolio_Test_05.pdf` (Portfolio `SYN-8505`).

`Synthetic_Portfolio_Test_05.pdf` introduced structural variations and alternate terminology within the supported portfolio statement family:
1. **Alternate Table Terminology**: Column headers used different synonyms (`POSITION / NOMINAL`, `INSTRUMENT DESCRIPTION`, `REFERENCE CODE`, `DISTRIBUTION / YIELD`, `COST PRICE`, `CLOSING PRICE`, `DENOM. CCY`, `VALUATION AMOUNT`, `USD EQUIVALENT`, `% PORTFOLIO`).
2. **Vertically Separated Holding Rows (Case B)**: The instrument description was printed on line 1, while units, reference code, yield, prices, currency, and market valuations were printed on line 2 (with embedded inline ESG ratings).
3. **Category Subtotals with Numeric Values**: Subtotals like `BONDS / NOTES 480000 32.00%` placed a 6-digit figure directly inside the category line, which previously triggered false-positive Valoren security identification.
4. **Summary & Performance Layout Variations**: Performance TWR percentages and title-cased cash flow labels (`Initial assets`, `Incoming cash`, etc.) required robust geometry and case-insensitive token parsing.
5. **Accounts & Loans Layout Alignment**: Separation of narrow 3-character ISO currency columns, numeric balance/principal amounts, and alphanumeric account descriptions/loan references.

All corrections have been implemented strictly in **shared, reusable extraction engines** without filename-specific branching, hardcoded portfolio references, or coordinate overrides.

---

## 2. STRICT TECHNOLOGY COMPLIANCE AUDIT

| Requirement | Implementation Standard | Status |
| :--- | :--- | :--- |
| **No LLM / AI APIs** | Zero dependencies on OpenAI, Gemini, Claude, or cloud AI services | **100% COMPLIANT** |
| **Deterministic Code** | PyMuPDF (`fitz`), openpyxl, Python Decimal, regex, geometric analysis | **100% COMPLIANT** |
| **No Hardcoded Values** | No document names, dates, amounts, portfolio IDs in extraction logic | **100% COMPLIANT** |
| **Format Conformance** | 16 dedicated worksheets generated for every extracted workbook | **100% COMPLIANT** |
| **Data Integrity** | Numbers preserved as Python `Decimal`, zero floating-point drift | **100% COMPLIANT** |

---

## 3. ROOT CAUSE INVESTIGATION & SHARED ENGINE FIXES

### 3.1 Table Header Engine & Synonym Expansion (`table_header_engine.py`)
- **Problem**: Header columns in Test 05 used alternate terminology (`DISTRIBUTION / YIELD`, `COST PRICE`, `CLOSING PRICE`, `DENOM. CCY`, `VALUATION AMOUNT`, `USD EQUIVALENT`, `REFERENCE CODE`, `% PORTFOLIO`).
- **Correction**: Expanded `HOLDINGS_SYNONYMS`, `ACCOUNTS_SYNONYMS`, and `LOANS_SYNONYMS` dictionaries to map these alternate terms deterministically to standard semantic column keys (`YIELD_RATING`, `AVERAGE_COST`, `MARKET_PRICE`, `MARKET_CURRENCY`, `MARKET_VALUE`, `REPORTING_VALUE`, `SECURITY_ID`, `PERCENTAGE`).
- **Boundary Optimization**: Preserved narrow boundaries for ISO currencies and computed safe midpoints between `BALANCE`/`PRINCIPAL` and description columns (`min(max(prev.hx1 + 4.0, col.hx0 - 30.0), (prev.hx1 + col.hx0) / 2.0)`).

### 3.2 Holdings Parser Multi-Line Symmetry (`holdings_parser.py`)
- **Problem**: Multi-line holdings tables fall into two structural variations:
  - **Case A**: Primary financial anchor on line 1 (units, identifier, values), description continuation on line 2.
  - **Case B**: Description on line 1, financial anchor on line 2 (units, identifier, values, ESG).
- **Correction**:
  - Implemented `is_case_b_pair(desc_l, fin_l, col_map)` which evaluates whether a description line and financial line form a vertically separated holding pair.
  - In `is_category_header`, numeric category amounts (e.g., `480000`) are excluded before testing Valoren regexes.
  - In `_build_holding_item`, `fin_line` is dynamically selected to provide financial numbers, while description words across all holding lines are gathered cleanly.

### 3.3 Accounts & Loans Semantic Token Assignment (`accounts_parser.py`, `loans_parser.py`)
- **Problem**: When numeric balances/principals or text descriptions landed near column boundaries, tokens were misassigned.
- **Correction**:
  - In `accounts_parser.py` and `loans_parser.py`, words assigned to `BALANCE`/`PRINCIPAL` that contain letters are reassigned to `ACCOUNT_DESCRIPTION`/`LOAN_REFERENCE`.
  - Leading words in `ACCOUNT_DESCRIPTION`/`LOAN_REFERENCE` that parse as financial numbers (when `amt_val is None`) are cleanly assigned as the numeric balance/principal.

### 3.4 Summary Performance Geometry & Case-Insensitive Cash Flows (`summary_parser.py`)
- **Problem**: On page 1 of Test 05, `mid_x = page.rect.width * 0.45` picked up the asset allocation table's `12.00%` into the right panel. Title-cased labels (`Initial assets`) failed uppercase string splits.
- **Correction**:
  - Adjusted `mid_x` to `page.rect.width * 0.49`.
  - Used case-insensitive regex splitting (`re.split(..., flags=re.IGNORECASE)`) for cash-flow metrics.
  - Extracted TWR % strictly from text *following* the `PERFORMANCE TWR` label.

---

## 4. TEN-DOCUMENT REGRESSION & RECONCILIATION MATRIX

All 10 documents were extracted and verified using the unified engine. Every statement generates 16 structured worksheets with zero validation failures:

| Document Filename | Portfolio ID | Valuation Date | Net Assets (USD) | TWR % | Holdings | Accounts | Loans | Sheets | FAIL Checks | Reconciliation Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `1_UBP_1002590_Jul2025.pdf` | `1002590` | 30.06.2025 | 2,267,669.27 | 3.17% | 12 | 1 | 0 | 16 | 0 | **RECONCILED (EXACT)** |
| `2_UBP_1002590_Oct2025.pdf` | `1002590` | 30.09.2025 | 2,279,848.49 | 5.77% | 16 | 1 | 1 | 16 | 0 | **RECONCILED (EXACT)** |
| `3_UBP_1002590_Jan2026.pdf` | `1002590` | 31.12.2025 | 2,577,594.26 | 7.96% | 17 | 2 | 2 | 16 | 0 | **RECONCILED (EXACT)** |
| `4_UBP_1002591_Jul2025.pdf` | `1002591` | 30.06.2025 | 858,466.51 | -2.33% | 9 | 1 | 0 | 16 | 0 | **RECONCILED (EXACT)** |
| `5_UBP_1002591_Oct2025.pdf` | `1002591` | 30.09.2025 | 919,794.74 | -0.39% | 9 | 1 | 0 | 16 | 0 | **RECONCILED (EXACT)** |
| `Synthetic_Portfolio_Test_01.pdf` | `SYN-4101` | 30.06.2025 | 1,080,000.00 | 2.10% | 12 | 2 | 1 | 16 | 0 | **RECONCILED (EXACT)** |
| `Synthetic_Portfolio_Test_02.pdf` | `SYN-5202` | 31.10.2025 | 1,420,000.00 | 3.45% | 13 | 3 | 2 | 16 | 0 | **RECONCILED (EXACT)** |
| `Synthetic_Portfolio_Test_03.pdf` | `SYN-6303` | 30.09.2025 | 1,815,000.00 | 3.05% | 12 | 3 | 1 | 16 | 0 | **RECONCILED (EXACT)** |
| `Synthetic_Portfolio_Test_04.pdf` | `SYN-7404` | 31.12.2025 | 2,120,000.00 | 4.12% | 14 | 4 | 2 | 16 | 0 | **RECONCILED (EXACT)** |
| `Synthetic_Portfolio_Test_05.pdf` | `SYN-8505` | 30.06.2026 | 1,500,000.00 | 3.10% | 12 | 4 | 2 | 16 | 0 | **RECONCILED (EXACT)** |

---

## 5. DETAILED VERIFICATION: `Synthetic_Portfolio_Test_05.pdf` (SYN-8505)

### 5.1 Portfolio Overview & Cash Flows
- **Portfolio Number**: `SYN-8505`
- **Valuation Date**: `30.06.2026`
- **Initial Assets**: `USD 1,455,000.00`
- **Ending Assets**: `USD 1,500,000.00`
- **Total Incoming Cash**: `USD 60,000.00`
- **Total Outgoing Cash**: `USD -20,000.00`
- **Total Incoming Securities**: `USD 20,000.00`
- **Total Outgoing Securities**: `USD -15,000.00`
- **Net Asset Flows**: `USD 45,000.00`
- **Net Asset Change**: `USD 45,000.00`
- **Performance TWR %**: `3.10%`
- **Portfolio ESG Rating**: `Previous: A (AVERAGE)`, `Current: AA (LEADER)`

### 5.2 Holdings Records (12 Positions)
1. `XS8505000017` | Maple Ridge Sovereign Bond 2033 | Units: `1,800` | Yield: `3.55%` | Cost: `99.10` | Price: `100.00 USD` | Val: `USD 180,000.00` (`12.00%`)
2. `XS8505000025` | Highland Corporate Credit Fund - Class I | Units: `1,600` | Yield: `4.20%` | Cost: `98.00` | Price: `100.00 USD` | Val: `USD 160,000.00` (`10.67%`)
3. `CH-VAL-8505003` | Meridian Municipal Bond Portfolio | Units: `1,400` | Yield: `3.10%` | Cost: `99.50` | Price: `100.00 USD` | Val: `USD 140,000.00` (`9.33%`)
4. `XS8505000041` | Sapphire Global Equity Fund - Class A | Units: `2,000` | Yield: `1.45%` | Cost: `95.00` | Price: `100.00 USD` | Val: `USD 200,000.00` (`13.33%`)
5. `US-TEST-8505-A` | Cedar Emerging Markets ETF | Units: `1,200` | Yield: `—` | Cost: `98.00` | Price: `100.00 USD` | Val: `USD 120,000.00` (`8.00%`)
6. `XS8505000058` | Northwind Growth Partnership - EUR Class | Units: `1,000` | Yield: `7.20%` | Cost: `90.00` | Price: `100.00 EUR` | Val: `USD 110,000.00` (`7.33%`)
7. `PB-TEST-8505-PE` | Westlake Infrastructure Co-Investment | Units: `900` | Yield: `—` | Cost: `100.00` | Price: `100.00 USD` | Val: `USD 90,000.00` (`6.00%`)
8. `CH-VAL-8505007` | Alpine Renewable Property Fund - CHF | Units: `60,000` | Yield: `5.10%` | Cost: `99.00` | Price: `100.00 CHF` | Val: `USD 60,000.00` (`4.00%`)
9. `XS8505000082` | Harbor Systematic Macro Strategy | Units: `1,000` | Yield: `6.10%` | Cost: `98.00` | Price: `100.00 USD` | Val: `USD 100,000.00` (`6.67%`)
10. `XS8505000090` | Redstone Multi-Strategy Fund | Units: `800` | Yield: `5.25%` | Cost: `97.00` | Price: `100.00 USD` | Val: `USD 80,000.00` (`5.33%`)
11. `XS8505000108` | Euro Dual-Currency Callable Note - 2029 | Units: `72,727.27` | Yield: `—` | Cost: `100.00` | Price: `100.00 EUR` | Val: `USD 80,000.00` (`5.33%`)
12. `XS8505000116` | Hong Kong Equity Participation Note - Series 4 | Units: `468,000` | Yield: `3.40%` | Cost: `100.00` | Price: `100.00 HKD` | Val: `USD 60,000.00` (`4.00%`)

### 5.3 Current Accounts (4 Accounts)
- `ACC-001` | USD | Balance: `100,000.00` | Description: `CURRENT ACCOUNT 8505-USD` | Reporting USD: `100,000.00`
- `ACC-002` | EUR | Balance: `30,000.00` | Description: `CURRENT ACCOUNT 8505-EUR` | Reporting USD: `33,000.00`
- `ACC-003` | CHF | Balance: `20,000.00` | Description: `CURRENT ACCOUNT 8505-CHF` | Reporting USD: `22,000.00`
- `ACC-004` | HKD | Balance: `39,000.00` | Description: `CURRENT ACCOUNT 8505-HKD` | Reporting USD: `5,000.00`

### 5.4 Loan Facilities (2 Loans)
- `LOAN-001` | USD | Principal: `-25,000.00` | Reference: `LN-TEST-8505-A` | Maturity: `31.12.2027` | Rate: `4.7500%` | USD Equivalent: `-25,000.00`
- `LOAN-002` | CHF | Principal: `-13,636.36` | Reference: `LN-TEST-8505-B` | Maturity: `30.06.2028` | Rate: `5.1500%` | USD Equivalent: `-15,000.00`

### 5.5 Balance Reconciliation Equation
$$\text{Holdings Total (USD 1,380,000.00)} + \text{Accounts Total (USD 160,000.00)} + \text{Loans Total (USD -40,000.00)} = \text{Net Assets (USD 1,500,000.00)}$$
- Difference: **$0.00** (Exact reconciliation).

---

## 6. AUTOMATED TEST SUITE EXECUTION

The complete Pytest regression suite was executed:
```text
pytest -q
82 passed in 27.22s (100% pass rate, 0 failures)
```
Key tests executed:
- `test_nine_document_full_reconciliation` (All 10 documents parameterized)
- `test_synthetic_05_alternative_terminology_and_multi_line_holdings`
- `test_synthetic_04_structured_products_and_zero_column_alignment`
- `test_accounts_loans_net_assets_and_exchange_rates`
- `test_multiline_continuation_preservation`
- `test_market_price_dates_and_markers`
- `test_jan2026_alternatives_column_mapping`

---

## 7. GENERATED WORKBOOK ARTIFACT PATHS

All 10 workbooks are generated and available for user inspection in both target directories:
1. `D:\zz\UBP_Extraction_App\test_outputs_audit\UBP_SYN-8505_Synthetic_Portfolio_Test_05.xlsx`
2. `D:\UserData\Downloads\UBP_SYN-8505_Synthetic_Portfolio_Test_05.xlsx`
3. `D:\UserData\Downloads\UBP_SYN-7404_Synthetic_Portfolio_Test_04.xlsx`
4. `D:\UserData\Downloads\UBP_SYN-6303_Synthetic_Portfolio_Test_03.xlsx`
5. `D:\UserData\Downloads\UBP_SYN-5202_Synthetic_Portfolio_Test_02.xlsx`
6. `D:\UserData\Downloads\UBP_SYN-4101_Synthetic_Portfolio_Test_01.xlsx`
7. `D:\UserData\Downloads\1_UBP_1002590_Jul2025.xlsx`
8. `D:\UserData\Downloads\2_UBP_1002590_Oct2025.xlsx`
9. `D:\UserData\Downloads\3_UBP_1002590_Jan2026.xlsx`
10. `D:\UserData\Downloads\4_UBP_1002591_Jul2025.xlsx`
11. `D:\UserData\Downloads\5_UBP_1002591_Oct2025.xlsx`

Every workbook contains all 16 required worksheets with freeze panes, auto-fit columns, standard accounting number formats, and zero truncation.
