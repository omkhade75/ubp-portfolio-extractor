# Generic Financial Table Reconstruction Engine & Synthetic Verification Report

## 1. Architecture Summary (Strictly Deterministic)

The UBP Portfolio Statement Extraction System has been upgraded from positional coordinate cutoffs and UBP-specific wording checks to a **deterministic, header-driven table reconstruction engine** using PyMuPDF coordinates, multi-line header clustering, strict single-token ownership, ISO 4217 currency validation, spatial region splitting, `Decimal` arithmetic, Pydantic models, and OpenPyXL.

- **Zero AI / LLM Dependencies**: Verified via source scan across `backend/app/**/*.py` (`NO_AI_API_REFERENCES_FOUND`).
- **No Fixture Hardcoding**: All parsing rules operate dynamically on header text geometry, semantic synonym tables, ISO 4217 codes, and section boundary headings rather than portfolio numbers, security names, amounts, or dates.

---

## 2. Generic Defects Fixed

| Section / Module | Root Cause Identified | Generic Solution Implemented |
| :--- | :--- | :--- |
| **Header & Column Engine** (`table_header_engine.py`) | Hardcoded pixel cutoffs (`x < 360`, etc.) broke whenever tables shifted column positions or renamed headers (e.g., `SECURITY NO.` at `x=312`, `AVG. COST`, `CCY`, `MARKET VALUE IN USD`). | Added `TableColumnMap`, `build_table_column_map`, `assign_words_to_columns` (strict single-token ownership), multi-line header phrase stacking, synonym matching (`HOLDINGS_SYNONYMS`, `ACCOUNTS_SYNONYMS`, `LOANS_SYNONYMS`, `PERFORMANCE_SYNONYMS`), and `is_valid_iso_currency` against `ISO_4217_CURRENCIES`. |
| **Holdings Parser** (`holdings_parser.py`) | Security IDs left of `360` leaked into `security_name`, shifted `yield` into `isin_secur_no`, missed `ESG AA / A` inline format and continuation credit ratings, and split space-separated ESG score lines (`078 078`) as spurious holdings. | Rewrote `parse_holdings_pages` and `_build_holding_item` around `detect_holdings_table_map` + strict token ownership; preserves `SourceValueState` (`EXPLICIT_ZERO` vs `SOURCE_BLANK` vs `SOURCE_DASH`); handles inline and columnar ESG ratings and continuation ratings/dates without splitting ESG continuation rows. |
| **Currency Breakdown** (`summary_parser.py`) | `len(clean) == 3 and clean.isalpha()` misclassified `"AMT"` as an ISO currency, dumping `USD`, `EUR`, and `HKD` amounts into `"AMT"`. | Replaced with `is_valid_iso_currency`; merged `"<CCY> AMT"` header spans; tracks `unit_scale` (`THOUSANDS`/`UNITS`) and ordered `detected_currencies`; maps values by header center proximity. |
| **Net Assets & Exchange Rates** (`summary_parser.py`) | Full-width line parsing mixed side-by-side left/right columns (`SUMMARY OF NET ASSETS` at `x<450` and `EXCHANGE RATES USED` at `x>=450`), mapped single-column Net Assets rows into `_pct` instead of `_usd`, and matched header page numbers (`Page 5 / 8`) as footer cutoff. | Added spatial two-column splitter when section headings share vertical coordinates; restricts footer cutoff detection to bottom 30% of page (`y0 >= 0.70 * ph`); maps 1-column Net Assets figures to `*_usd` (`pct=None`) and 2-column rows to `(usd, pct)`; validates ISO pairs in Exchange Rates. |
| **Accounts & Loans** (`accounts_parser.py`, `loans_parser.py`, `page_classifier.py`) | Accounts did not stop on `"LOAN FACILITIES"`; Loans only matched `"FIXED LOAN"`/`"TR..."`; stacked 2-line page-top headers missed `"VALUE IN USD"`; headerless synthetic PDFs dropped numeric account numbers/loan rates. | Classifies `"LOAN FACILITIES"`, `"CREDIT FACILITIES"`, and `"BORROWINGS"` dynamically; stops Accounts immediately on any loan heading; captures 2-line stacked local/page-top headers; handles missing `% ASSETS` header when valuation + `%` occupy right zone; retains headerless positional fallback for headerless fixtures. |
| **Metadata & Watermarks** (`pdf_inspector.py`, `word_extractor.py`) | Hardcoded UBP bank regex and `Report edited on`; missed `SYNTHETIC PRIVATE BANK`, `Portfolio reference SYN-4101`, `Report prepared 01.07.2025`, and `SINCE ... TO ...` period; diagonal watermarks risked table pollution. | Filters rotated/oversized watermarks (`TEST`, `BANK`, `STATEMENT`, `NOT A REAL BANK STATEMENT`, `SYNTHETIC DATA`); extracts generic institution headers from left top band + `institution_provenance`; supports `Portfolio reference`, `Report prepared`, and `SINCE ... TO ...` reporting periods across raw text and left-side visual lines. |
| **Performance** (`performance_parser.py`) | Fixed `x` cutoffs (`x < 750`) misassigned columns when headers were left-aligned (e.g., `RETURN ON N.I.` at `x=748`), and missed stacked second header lines without `"AND WITHDRAWALS"`. | Uses `build_table_column_map(..., PERFORMANCE_SYNONYMS)` with stacked header continuation capture and `assign_words_to_columns`, plus headerless fallback. |
| **Validator & Excel Export** (`financial_validator.py`, `workbook_generator.py`, `schemas.py`, `table_reconstructor.py`) | Portfolio ID check warned on `< 6` chars (`SYN-4101` fallback edge); Currency Breakdown sheet hardcoded leading `USD` columns even if absent; empty `Exchange_Rates` had no status marker; lacked structural column-separation checks. | Added structural checks (`Column Boundary & Identifier Separation`, `Currency Breakdown Consistency`, `Accounts vs Loans Section Separation`), propagated `section_confidence` & `detected_column_maps`, added `Institution Provenance` and `Reporting Period` in `Portfolio_Overview`, preserved dynamic currency ordering in `Currency_Breakdown`, and emitted explicit `STATUS: NOT_PRESENT` when exchange rates are absent. |

---

## 3. Verification Results

All automated checks ran after the final edit with zero failures and zero skipped tests:

1. **Full Backend Test Suite (`python -m pytest tests -v`)**: **60 passed in 17.13s** (0 failed, 0 skipped):
   - Unit tests for generic header engine & strict token ownership (`tests/test_generic_header_engine.py`: 4 passed)
   - Full regression suite for `Synthetic_Portfolio_Test_01.pdf` (`tests/test_synthetic_statement_01_full.py`: 5 passed)
   - `Synthetic_Portfolio_Training_Report_02.pdf` (`tests/test_synthetic_statement_02.py`: 9 passed)
   - OCR Scanned PDF (`tests/test_ocr_synthetic.py`: 1 passed)
   - All 5 original UBP statements + unseen layout/fidelity/persistence/static serving tests (41 passed)
2. **All 5 Original UBP Reference PDFs**:
   - `1_UBP_1002590_Jul2025.pdf`: `port=1002590`, `holds=12`, `cb=6`, `acc=1`, `loans=0`, `rates=1`, `fails=[]`, `warns=[]`
   - `2_UBP_1002590_Oct2025.pdf`: `port=1002590`, `holds=16`, `cb=6`, `acc=1`, `loans=1`, `rates=1`, `fails=[]`, `warns=[]`
   - `3_UBP_1002590_Jan2026.pdf`: `port=1002590`, `holds=17`, `cb=6`, `acc=2`, `loans=2`, `rates=1`, `fails=[]`, `warns=['Portfolio Identifier']` (redacted source ID)
   - `4_UBP_1002591_Jul2025.pdf`: `port=1002591`, `holds=9`, `cb=4`, `acc=1`, `loans=0`, `rates=1`, `fails=[]`, `warns=[]`
   - `5_UBP_1002591_Oct2025.pdf`: `port=1002591`, `holds=9`, `cb=5`, `acc=1`, `loans=0`, `rates=1`, `fails=[]`, `warns=[]`
3. **`Synthetic_Portfolio_Test_01.pdf` End-to-End FastAPI Upload-to-Download (`TestClient`)**:
   - `POST /api/upload` -> `GET /api/jobs/{job_id}` -> `GET /api/jobs/{job_id}/download-all`
   - Result: `status=COMPLETED`, `16` Excel worksheets, `12` holdings rows, `1` loan row (`LN-TEST-4101-A`), `2` exchange rates (`1 EUR = 1.13636364 USD`, `1 USD = 7.80000000 HKD`), `USD/EUR/HKD` currency breakdown columns (no `AMT`), `31` PASS validation checks, `0` WARNING, `0` FAIL.
4. **Frontend Production Build (`npm run build`)**:
   - `tsc && vite build` exited cleanly in `2.45s` (`dist/index.html`, `dist/assets/index-BCq5D8XP.css`, `dist/assets/index-DO5ptz87.js`).

---

## 4. Modified & Created Files

- `backend/app/extraction/table_header_engine.py` (new)
- `backend/app/extraction/word_extractor.py`
- `backend/app/extraction/pdf_inspector.py`
- `backend/app/extraction/page_classifier.py`
- `backend/app/extraction/holdings_parser.py`
- `backend/app/extraction/summary_parser.py`
- `backend/app/extraction/accounts_parser.py`
- `backend/app/extraction/loans_parser.py`
- `backend/app/extraction/performance_parser.py`
- `backend/app/extraction/table_reconstructor.py`
- `backend/app/models/schemas.py`
- `backend/app/processing/financial_validator.py`
- `backend/app/excel/workbook_generator.py`
- `backend/tests/test_generic_header_engine.py` (new)
- `backend/tests/test_synthetic_statement_01_full.py` (new)
