import os
from typing import List, Dict, Any, Optional
import pymupdf

from app.models.schemas import (
    StatementExtractionResult,
    StatementMetadata,
    RawPageData,
    UnmappedContentItem
)
from app.extraction.pdf_inspector import inspect_pdf_document
from app.extraction.page_classifier import classify_statement_page
from app.extraction.summary_parser import (
    parse_asset_allocation_page,
    parse_portfolio_summary_performance,
    parse_portfolio_esg_generic,
    parse_currency_breakdown_page,
    parse_net_assets_summary_page
)
from app.extraction.holdings_parser import parse_holdings_pages
from app.extraction.accounts_parser import parse_current_accounts_page
from app.extraction.loans_parser import parse_loans_page
from app.extraction.performance_parser import (
    parse_monthly_performance_page,
    parse_annual_performance_page
)
from app.extraction.disclosure_parser import parse_disclosures
from app.extraction.word_extractor import extract_visual_words_and_lines, get_page_text
from app.extraction.ocr_extractor import detect_page_type, extract_page_with_ocr
from app.processing.financial_validator import run_financial_validation

def extract_ubp_statement(
    file_path: str,
    progress_callback: Optional[Any] = None
) -> StatementExtractionResult:
    """
    Deterministic master extractor for UBP portfolio valuation statements.
    Processes all pages, classifies sections, extracts structured entities,
    and runs independent financial validations.
    Supports progress_callback(stage, phase, percentage).
    """
    filename = os.path.basename(file_path)
    doc = pymupdf.open(file_path)
    total_pages = len(doc)

    if progress_callback:
        progress_callback("INSPECTING", f"Inspecting {filename} ({total_pages} pages)", 10)

    # 1. Document metadata inspection
    metadata = inspect_pdf_document(doc, filename)

    if progress_callback:
        progress_callback("CLASSIFYING", f"Classifying document structure ({total_pages} pages)", 25)

    # 2. Page classification and raw text record
    classified_pages: Dict[int, str] = {}
    raw_pages: List[RawPageData] = []
    detected_sections = set()

    for pno in range(total_pages):
        page = doc[pno]
        page_type, needs_ocr = detect_page_type(page)

        # Extract visual words for raw audit preservation (all words including watermarks)
        raw_vis_words, _ = extract_visual_words_and_lines(page, filter_watermarks=False)
        page_text = get_page_text(page)
        lines = page_text.splitlines()
        words = page_text.split()

        avg_conf = None
        if needs_ocr:
            _, _, _, avg_conf, _ = extract_page_with_ocr(page, pno + 1)

        section_type = classify_statement_page(page, pno + 1, total_pages, page_text=page_text)
        classified_pages[pno] = section_type
        detected_sections.add(section_type)

        word_coords = [
            {
                "word": w.text,
                "bbox": [round(w.x0, 2), round(w.y0, 2), round(w.x1, 2), round(w.y1, 2)],
                "block": w.block_no,
                "line": w.line_no,
                "word_no": w.word_no,
                "confidence": getattr(w, "confidence", 100.0)
            }
            for w in raw_vis_words
        ]

        raw_pages.append(RawPageData(
            page_number=pno + 1,
            section_name=section_type,
            rotation=page.rotation,
            width=page.rect.width,
            height=page.rect.height,
            line_count=len(lines),
            word_count=len(words),
            text=page_text,
            word_coordinates=word_coords,
            page_type=page_type,
            ocr_applied=needs_ocr,
            ocr_confidence=avg_conf
        ))

    metadata.detected_sections = sorted(list(detected_sections))

    # 3. Section-by-section extraction
    portfolio_summary_perf = None
    asset_allocation = []
    currency_breakdown = []
    holdings = []
    current_accounts = []
    loans = []
    net_assets_summary = None
    exchange_rates = []
    monthly_perf = []
    annual_perf = []
    unmapped_content: List[UnmappedContentItem] = []

    # Identify page indices for each section
    overview_pages = [p for p, s in classified_pages.items() if s == "OVERVIEW_ASSET_ALLOCATION"]
    curr_breakdown_pages = [p for p, s in classified_pages.items() if s == "CURRENCY_BREAKDOWN"]
    holdings_pages = [p for p, s in classified_pages.items() if s == "HOLDINGS"]
    accounts_loans_pages = [p for p, s in classified_pages.items() if s == "ACCOUNTS_AND_LOANS"]
    summary_pages = [p for p, s in classified_pages.items() if s == "NET_ASSETS_SUMMARY"]
    monthly_pages = [p for p, s in classified_pages.items() if s == "MONTHLY_PERFORMANCE"]
    annual_pages = [p for p, s in classified_pages.items() if s == "ANNUAL_PERFORMANCE"]

    if progress_callback:
        progress_callback("EXTRACTING", f"Extracting tables & securities holdings ({len(holdings_pages)} pages)", 50)

    # Extract Asset Allocation & Portfolio Performance Summary (Overview)
    for pno in overview_pages:
        alloc_items = parse_asset_allocation_page(doc[pno], pno + 1)
        asset_allocation.extend(alloc_items)
        if portfolio_summary_perf is None:
            portfolio_summary_perf = parse_portfolio_summary_performance(doc[pno], pno + 1)
            if portfolio_summary_perf:
                if portfolio_summary_perf.portfolio_previous_esg_rating:
                    metadata.portfolio_previous_esg_rating = portfolio_summary_perf.portfolio_previous_esg_rating
                    metadata.portfolio_esg_previous = portfolio_summary_perf.portfolio_previous_esg_rating
                if portfolio_summary_perf.portfolio_current_esg_rating:
                    metadata.portfolio_current_esg_rating = portfolio_summary_perf.portfolio_current_esg_rating
                    metadata.portfolio_esg_current = portfolio_summary_perf.portfolio_current_esg_rating
                if portfolio_summary_perf.portfolio_esg_source_page:
                    metadata.portfolio_esg_source_page = portfolio_summary_perf.portfolio_esg_source_page

        if not metadata.portfolio_esg_previous and not metadata.portfolio_esg_current:
            _, ov_lines = extract_visual_words_and_lines(doc[pno])
            mid_x_left = doc[pno].rect.width * 0.50
            for ov_l in ov_lines:
                if "PORTFOLIO ESG RATING" in ov_l.text.upper() or "ESG RATING" in ov_l.text.upper():
                    left_words = [w for w in ov_l.words if w.x0 < mid_x_left]
                    left_text = " ".join(w.text for w in left_words).strip()
                    p_p, p_c = parse_portfolio_esg_generic(left_text if "PORTFOLIO ESG" in left_text.upper() else ov_l.text)
                    if p_p or p_c:
                        metadata.portfolio_esg_previous = p_p
                        metadata.portfolio_esg_current = p_c
                        metadata.portfolio_previous_esg_rating = p_p
                        metadata.portfolio_current_esg_rating = p_c
                        metadata.portfolio_esg_source_page = pno + 1
                        break

    # Extract Currency Breakdown
    for pno in curr_breakdown_pages:
        curr_items = parse_currency_breakdown_page(doc[pno], pno + 1)
        currency_breakdown.extend(curr_items)

    # Extract Holdings (with cross-page continuity and dynamically discovered categories)
    dynamic_categories = [a.investment_category for a in asset_allocation if a.investment_category]
    if holdings_pages:
        h_items, _ = parse_holdings_pages(doc, holdings_pages, dynamic_categories=dynamic_categories)
        holdings.extend(h_items)

    # Extract Current Accounts and Loans
    for pno in accounts_loans_pages:
        acc_items, _, _ = parse_current_accounts_page(doc[pno], pno + 1)
        current_accounts.extend(acc_items)
        loan_items, _, _ = parse_loans_page(doc[pno], pno + 1)
        loans.extend(loan_items)

    # Extract Net Assets Summary & Exchange Rates
    for pno in summary_pages:
        summary_data, rates = parse_net_assets_summary_page(doc[pno], pno + 1)
        if summary_data:
            net_assets_summary = summary_data
        exchange_rates.extend(rates)

    # Extract Monthly Performance
    for pno in monthly_pages:
        m_rows, _ = parse_monthly_performance_page(doc[pno], pno + 1)
        monthly_perf.extend(m_rows)

    # Extract Annual Performance
    for pno in annual_pages:
        a_rows, _ = parse_annual_performance_page(doc[pno], pno + 1)
        annual_perf.extend(a_rows)

    if progress_callback:
        progress_callback("NORMALIZING", "Normalizing financial data & disclosures", 70)

    # Extract Comments and Disclosures
    comments_disclosures = parse_disclosures(doc, classified_pages)

    # Detect unknown / unfamiliar layout pages and preserve in unmapped content
    unknown_pages = [p for p, s in classified_pages.items() if s == "UNKNOWN"]
    for pno in unknown_pages:
        unmapped_content.append(UnmappedContentItem(
            page_number=pno + 1,
            raw_text=raw_pages[pno].text[:300] if pno < len(raw_pages) else "",
            reason="Unfamiliar or non-standard page layout: section heading does not match standard UBP report templates."
        ))

    # Create extraction result object
    result = StatementExtractionResult(
        metadata=metadata,
        portfolio_summary_performance=portfolio_summary_perf,
        asset_allocation=asset_allocation,
        currency_breakdown=currency_breakdown,
        holdings=holdings,
        current_accounts=current_accounts,
        loans=loans,
        net_assets_summary=net_assets_summary,
        exchange_rates=exchange_rates,
        monthly_performance=monthly_perf,
        annual_performance=annual_perf,
        comments_disclosures=comments_disclosures,
        unmapped_content=unmapped_content,
        raw_pages=raw_pages,
        validation_checks=[]
    )

    if progress_callback:
        progress_callback("VALIDATING", "Running cross-section financial validation", 85)

    # 4. Financial Validation
    validation_checks = run_financial_validation(result)
    result.validation_checks = validation_checks

    return result
