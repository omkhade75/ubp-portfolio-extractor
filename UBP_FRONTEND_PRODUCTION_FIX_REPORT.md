# UBP Portfolio Extractor — Production Frontend Fix & E2E Verification Report

**Project Workspace:** `D:\zz\UBP_Extraction_App\`  
**Production URL:** [https://ubp-portfolio-extractor.onrender.com](https://ubp-portfolio-extractor.onrender.com)  
**Git Commit Deployed:** `e2ceffc` (`main`)  
**Date:** November 27, 2026  
**Status:** **RESOLVED & VERIFIED IN LIVE PRODUCTION**

---

## 1. Root Cause Analysis

### Defect 1: CSS Asset 404 (`index-DTUJkkxJ.css`) & Stale UI Labels (`Local Processing`, `No External Processing`)
1. **Uncontrolled HTTP Caching on HTML Entrypoint (`backend/app/main.py`)**:
   - FastAPI previously mounted `frontend/dist` directly using default `StaticFiles(directory=..., html=True)`. That handler emitted `ETag` and `Last-Modified` headers without a `Cache-Control` directive on `/` (`index.html`).
   - Across Docker rebuilds on Render, each clean `vite build` generates fresh content-hashed asset filenames (for example, `index-DTUJkkxJ.css` → `index-Dv4PwctF.css` → `index-BCq5D8XP.css`) and removes obsolete hashes from `frontend/dist/assets`.
   - Open/reloaded browser tabs holding cached copies of an older `index.html` and JS bundle (`index-1R4iswpa.js`) displayed stale header labels (`Local Processing`, `No AI / No External Processing`) while requesting `/assets/index-DTUJkkxJ.css` from the newly deployed container—causing **HTTP 404 Not Found** (`{"detail":"Not Found"}`) and rendering unstyled HTML.
2. **Remaining Misleading Text in Dropzone (`UploadZone.tsx`)**:
   - Even after updating header badges in `Home.tsx`, line 83 of `UploadZone.tsx` still read *"Supports individual PDFs, multiple files, or zipped bundles. Deterministic local extraction."* and `Home.tsx` checked only `"PROCESSING" || "PENDING"` rather than `"QUEUED"`.

### Defect 2: Browser Warning — `"File chooser dialog can only be shown with a user activation."`
1. **Nested Clickable Wrapper Over `<input type="file">`**:
   - In `UploadZone.tsx`, `<input type="file" className="hidden" />` was nested **inside** `<div onClick={() => !disabled && fileInputRef.current?.click()}>`.
   - Under unstyled HTML (caused by CSS 404) or any event bubbling scenario, Tailwind's `.hidden` class failed to hide the `<input>` element. Clicking the visible native file input opened the OS picker and simultaneously bubbled the click to the parent `<div>`, triggering a second programmatic `fileInputRef.current?.click()` after user activation was consumed/blocked.
   - Without `e.stopPropagation()` on `<input>`, keyboard accessibility, or sibling structural isolation, native input clicks collided with React's delegated click handler.

---

## 2. Implemented Fixes & Files Modified

Working backend domain modules (`job_store.py`, `financial_validator.py`, `holdings_parser.py`, `performance_parser.py`, `number_parser.py`, `workbook_generator.py`) were **preserved untouched**.

| File | Change Summary |
|---|---|
| `backend/app/main.py` | Mounted `/assets` via `ImmutableAssetsStaticFiles` (`Cache-Control: public, max-age=31536000, immutable`). Served `index.html` with `Cache-Control: no-cache, no-store, must-revalidate`, `Pragma: no-cache`, `Expires: 0`. Enforced strict HTTP 404 on missing `/api/*`, `/assets/*`, and file-extension requests instead of SPA HTML fallback. Updated OpenAPI app description. |
| `frontend/src/components/UploadZone.tsx` | Moved `<input type="file">` outside the clickable dropzone container as an accessible sibling (`sr-only` + inline visually-hidden CSS + `onClick={(e) => e.stopPropagation()}`). Added explicit `<button type="button" onClick={handleBrowseClick}>browse</button>` and `triggerFilePicker()` calling `input.click()` synchronously inside the user click/keydown frame. Updated caption to *"Deterministic server-side extraction."* |
| `frontend/src/pages/Home.tsx` | Updated header badges to truthful server-side labels: `Isolated Server-Side Processing`, `Python Financial Extraction Engine`, `Deterministic Processing / No External AI Calls`. Fixed `isProcessing` check (`!["COMPLETED", "FAILED", "CANCELLED"].includes(jobStatus.status)`) and allowed resetting from error banners. |
| `.dockerignore` | Added `frontend/node_modules` and `frontend/dist` so Docker always performs a clean Linux `npm install && npm run build`. |
| `backend/tests/test_static_serving_and_cache.py` | Added automated FastAPI tests verifying `no-cache` headers on `/`, `immutable` HTTP 200 on every CSS/JS asset referenced in built `dist/index.html`, truthful UI strings compiled in bundle, and strict 404 (never HTML) on stale hashes like `/assets/index-DTUJkkxJ.css`. |

---

## 3. Clean Frontend Build & Backend Test Results

### Clean Frontend Production Build (`tsc && vite build`)
```
dist/index.html                   0.88 kB │ gzip:  0.53 kB
dist/assets/index-BCq5D8XP.css   25.45 kB │ gzip:  5.63 kB
dist/assets/index-DO5ptz87.js   207.41 kB │ gzip: 60.17 kB
✓ built in 2.48s
```
- Built `dist/index.html` references exact existing bundles `/assets/index-DO5ptz87.js` and `/assets/index-BCq5D8XP.css`.

### Backend Test Suite (`python -m pytest tests -v`)
- **Result:** **51 passed in 16.64s** (`0` failures, `0` skipped), including:
  - `test_static_serving_and_cache.py::test_index_html_has_no_cache_headers_and_valid_asset_references` (**PASSED**)
  - `test_static_serving_and_cache.py::test_missing_hashed_asset_returns_strict_404_not_html` (**PASSED**)
  - `test_job_lifecycle_persistence.py` (3/3 **PASSED**)
  - All holdings, numbers, performance, OCR synthetic, data fidelity, and Excel generation tests (**PASSED**)

---

## 4. Live Render Deployment Verification

Verified directly against `https://ubp-portfolio-extractor.onrender.com` after Docker rollout of commit `e2ceffc`:

### Browser Network Results (Playwright Chromium E2E Session)
| Resource / Endpoint | Status | Content-Type | Cache-Control |
|---|---|---|---|
| `GET https://ubp-portfolio-extractor.onrender.com/` | **200 OK** | `text/html; charset=utf-8` | `no-cache, no-store, must-revalidate` |
| `GET .../assets/index-BCq5D8XP.css` | **200 OK** | `text/css; charset=utf-8` | `public, max-age=31536000, immutable` |
| `GET .../assets/index-DO5ptz87.js` | **200 OK** | `application/javascript` | `public, max-age=31536000, immutable` |
| `GET .../assets/index-DTUJkkxJ.css` *(stale probe via curl)* | **404 Not Found** | `application/json` | `{"detail":"Not Found"}` *(never HTML)* |
| `POST /api/upload` (2 live runs) | **200 OK** | `application/json` | Dynamic |
| `GET /api/jobs/{id}` *(73 live polls)* | **200 OK** | `application/json` | Dynamic (`0` non-200 polls) |

### Browser Console & Computed Styling Results
- **Console Errors:** `0`
- **Console Warnings:** `0` (verified **0 occurrences** of `"File chooser dialog can only be shown with a user activation."`)
- **Uncaught Page Errors:** `0`
- **Non-200 Requests in Browser Session:** `0`
- **Computed Styling:**
  - `document.body` background: `oklch(0.984 0.003 247.858)` (`bg-slate-50`)
  - Dropzone border: `dashed` (`1.6px`)
  - `<input type="file">` bounding box: `1px × 1px` (`sr-only` hidden visually)
  - Truthful Header Badges rendered:
    1. `Isolated Server-Side Processing`
    2. `Python Financial Extraction Engine`
    3. `Deterministic Processing / No External AI Calls`
  - Dropzone caption rendered: `"Supports individual PDFs, multiple files, or zipped bundles. Deterministic server-side extraction."`

### Live Synthetic Upload & Download Test Results

#### Upload #1: `Synthetic_Portfolio_Test_01.pdf` (via real mouse click on `browse` → native `filechooser`)
- **File Chooser Activation:** Native Playwright `filechooser` event fired cleanly from user click on `browse` button (`isMultiple: true`, `0` browser warnings).
- **Job ID:** `435d78d7-f072-4c9f-94ae-e15884117574` → reached `COMPLETED` (`100%`).
- **Extracted UI Summary:** `TOTAL PDFS: 1` | `TOTAL PAGES: 11` | `HOLDINGS: 12` | `ACCOUNTS: 3` | `LOANS: 0` | `PERF RECORDS: 19`
- **Excel Download (`/api/jobs/435d78d7.../download/0`):** **HTTP 200 OK**, `30,780 bytes` (`.xlsx`)
- **ZIP Bundle Download (`/api/jobs/435d78d7.../download-all`):** **HTTP 200 OK**, `57,907 bytes` (`.zip`)

#### Upload #2: `Synthetic_Portfolio_Test_02.pdf` (via `Reset / New Upload` → Drag-and-Drop `DragEvent('drop')`)
- **Drag-and-Drop Delivery:** Dispatched `dragover` and `drop` with real PDF `File` object onto the dropzone container.
- **Job ID:** `13283afe-8aa0-4d55-986d-b1d86fa49efe` → reached `COMPLETED` (`100%`).
- **Extracted UI Summary:** `TOTAL PDFS: 1` | `TOTAL PAGES: 12` | `HOLDINGS: 13` | `ACCOUNTS: 5` | `LOANS: 0` | `PERF RECORDS: 20`
- **Excel Download (`/api/jobs/13283afe.../download/0`):** **HTTP 200 OK**, `31,782 bytes` (`.xlsx`)
- **ZIP Bundle Download (`/api/jobs/13283afe.../download-all`):** **HTTP 200 OK**, `66,158 bytes` (`.zip`)
