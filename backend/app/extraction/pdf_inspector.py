import re
from typing import Dict, Any, List, Optional
import pymupdf
from app.models.schemas import StatementMetadata
from app.extraction.word_extractor import get_page_text, extract_visual_words_and_lines

def inspect_pdf_document(doc: pymupdf.Document, filename: str) -> StatementMetadata:
    """
    Inspects PDF document structure, rotation, dimensions, and header metadata.
    Dynamically discovers portfolio number, valuation date, reporting period, and page count.
    Handles partial/redacted portfolio numbers cleanly.
    Identifies issuing bank or records NOT_STATED / NOT_PRESENT if no bank branding is found.
    """
    total_pages = len(doc)
    portfolio_number: Optional[str] = None
    portfolio_name: Optional[str] = None
    valuation_date: Optional[str] = None
    report_edited_date: Optional[str] = None
    bank_name: Optional[str] = None
    institution_provenance: str = "NOT_PRESENT"
    report_currency = "USD"
    reporting_period: Optional[str] = None
    is_synthetic = False
    client_name: Optional[str] = None
    client_reference: Optional[str] = None
    relationship_type: Optional[str] = None

    # Search first 5 pages for metadata
    for pno in range(min(5, total_pages)):
        text = get_page_text(doc[pno])

        if "SYNTHETIC PORTFOLIO" in text.upper() or "SYNTHETIC PRIVATE BANK" in text.upper():
            is_synthetic = True

        # Client profile detection (e.g. synthetic reports or customized portfolio reports)
        if not client_reference:
            m_ref = re.search(r"Client\s+reference\s*:?\s*([A-Z0-9\-]+)", text, re.IGNORECASE)
            if m_ref:
                client_reference = m_ref.group(1).strip()
        if not relationship_type:
            m_rel = re.search(r"Relationship\s*:?\s*([^\n\r]+)", text, re.IGNORECASE)
            if m_rel:
                relationship_type = m_rel.group(1).split("PAGE")[0].strip()
        if not client_name:
            m_name = re.search(r"FICTIONAL\s+CLIENT\s+PROFILE\s*\n\s*([^\n\r]+)", text, re.IGNORECASE)
            if m_name:
                cand = m_name.group(1).strip()
                if "TABLE OF CONTENTS" not in cand and "PAGE" not in cand:
                    client_name = cand

        # Bank Name detection (handles UBP branches and generic institutional headers)
        if not bank_name:
            m_bank = re.search(r"(UNION BANCAIRE PRIV[EÉ]E(?:,\s*UBP SA(?:,\s*[A-Z\s]+BRANCH)?)?)", text, re.IGNORECASE)
            if m_bank:
                bank_name = m_bank.group(1).strip()
                institution_provenance = "EXTRACTED"
            elif pno == 0:
                _, top_lines = extract_visual_words_and_lines(doc[pno])
                top_cutoff = doc[pno].rect.height * 0.16
                left_limit = doc[pno].rect.width * 0.65
                blocked_inst = (
                    "NOT A REAL BANK", "NOT STATED", "NO BANK", "WATERMARK",
                    "SYNTHETIC PORTFOLIO", "SAMPLE", "TABLE OF CONTENTS",
                    "VALUATION AS OF", "ASSET ALLOCATION", "PORTFOLIO REFERENCE"
                )
                for hl in top_lines:
                    if hl.y > top_cutoff:
                        continue
                    left_text = " ".join(w.text for w in hl.words if w.x0 < left_limit).strip()
                    if not left_text:
                        continue
                    cand_raw = re.split(r"\b(?:PORTFOLIO\s+IN|VALUATION\s+AS\s+OF|PAGE\s+\d)\b", left_text, flags=re.IGNORECASE)[0].strip()
                    cand_up = cand_raw.upper()
                    if any(b in cand_up for b in blocked_inst):
                        continue
                    if re.search(r"\b(?:PRIVATE\s+BANK|WEALTH\s+MANAGEMENT|ASSET\s+MANAGEMENT|TRUST\s+BANK|BANK)\b", cand_up):
                        cleaned = re.sub(r"\s*[-–—]\s*(?:PORTFOLIO|PRIVATE\s+CLIENT|REPORTING)\s+SERVICES$", "", cand_raw, flags=re.IGNORECASE).strip()
                        if len(cleaned) >= 4:
                            bank_name = cleaned
                            institution_provenance = "EXTRACTED"
                            break

        # Also inspect visual lines on page 0 for dates/references split across wide horizontal spacing
        if pno == 0 and (not report_edited_date or not portfolio_number or not valuation_date):
            _, p0_lines = extract_visual_words_and_lines(doc[pno])
            p0_left_cut = doc[pno].rect.width * 0.50
            for vl in p0_lines:
                vl_left = " ".join(w.text for w in vl.words if w.x0 < p0_left_cut).strip()
                if not report_edited_date:
                    m_ed_v = re.search(r"Report\s+(?:edited\s+on|prepared(?:\s+on)?|date|generated(?:\s+on)?)[ \t]*:?[ \t]*([0-9]{2}\.[0-9]{2}\.[0-9]{2,4})", vl_left, re.IGNORECASE)
                    if m_ed_v:
                        report_edited_date = m_ed_v.group(1).strip()
                if not portfolio_number:
                    m_pt_v = re.search(r"Portfolio[ \t]+(?:reference|ref\.?|id|no\.?|number)[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-]*\d[A-Z0-9\-]*)", vl_left, re.IGNORECASE)
                    if m_pt_v and m_pt_v.group(1).strip() != "001":
                        portfolio_number = m_pt_v.group(1).strip()

        # Reporting currency detection: PORTFOLIO IN USD or PERFORMANCES ... IN USD or CURRENCY : USD or Reporting currency USD
        m_curr = (
            re.search(r"PORTFOLIO\s+IN\s+([A-Z]{3})\b", text, re.IGNORECASE)
            or re.search(r"Reporting\s+currency[ \t]*:?[ \t]*([A-Z]{3})\b", text, re.IGNORECASE)
            or re.search(r"PERFORMANCES.*IN\s+([A-Z]{3})\b", text, re.IGNORECASE)
            or re.search(r"CURRENCY[ \t]*:[ \t]*([A-Z]{3})\b", text, re.IGNORECASE)
        )
        if m_curr:
            report_currency = m_curr.group(1).strip().upper()

        # Reporting period detection (e.g. SINCE 01.01.2025 TO 30.06.2025 or SINCE 01.01.2025)
        if not reporting_period:
            m_rp = re.search(r"(SINCE\s+[0-9]{2}\.[0-9]{2}\.[0-9]{4}(?:\s+TO\s+[0-9]{2}\.[0-9]{2}\.[0-9]{4})?)", text, re.IGNORECASE)
            if m_rp:
                reporting_period = re.sub(r"\s+", " ", m_rp.group(1).strip().upper())

        # Valuation date pattern: PORTFOLIO VALUATION AS OF 30.06.2025 or Valuation date 30.06.2025
        if not valuation_date:
            m_val = (
                re.search(r"(?:PORTFOLIO\s+)?VALUATION\s+AS\s+OF[ \t]*:?[ \t]*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text, re.IGNORECASE)
                or re.search(r"Valuation\s+date[ \t]*:?[ \t]*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text, re.IGNORECASE)
            )
            if m_val:
                valuation_date = m_val.group(1).strip()

        # Report edited / prepared date: Report edited on : 01.07.25 or Report prepared 01.07.2025
        if not report_edited_date:
            m_edit = re.search(r"Report\s+(?:edited\s+on|prepared(?:\s+on)?|date|generated(?:\s+on)?)[ \t]*:?[ \t]*([0-9]{2}\.[0-9]{2}\.[0-9]{2,4})", text, re.IGNORECASE)
            if m_edit:
                report_edited_date = m_edit.group(1).strip()

        # Portfolio Number / Reference pattern (numeric e.g. 1002590 or alphanumeric e.g. SYN-4101)
        if not portfolio_number:
            m_port = (
                re.search(r"Portfolio[ \t]+(?:No\.?|Number)[ \t]*:?[ \t]*([0-9]{6,})", text, re.IGNORECASE)
                or re.search(r"Portfolio[ \t]+(?:reference|ref\.?|id)[ \t]*:?[ \t]*([A-Z0-9][A-Z0-9\-]*\d[A-Z0-9\-]*)", text, re.IGNORECASE)
                or re.search(r"Portfolio[ \t]+001[ \t]+SEE[ \t]*([0-9]{6,})", text, re.IGNORECASE)
                or re.search(r"(?:SEE|Portfolio)[ \t]*:?[ \t]*([0-9]{6,}|[A-Z]{2,6}-[0-9]{3,})", text, re.IGNORECASE)
            )
            if m_port:
                cand_port = m_port.group(1).strip()
                if cand_port != "001" and len(cand_port) >= 4:
                    portfolio_number = cand_port

    # Per Task 5: If bank is not identified in document, record NOT_STATED
    if not bank_name:
        bank_name = "NOT_STATED"
        institution_provenance = "NOT_PRESENT"

    # Note if statement has blank portfolio number (e.g. File 3 where it literally prints 'Portfolio No. ' and 'Portfolio 001 SEE')
    # If not found in document text, extract from filename as fallback
    portfolio_number_extracted = portfolio_number
    portfolio_number_fallback = None
    identifier_source = "EXTRACTED_FROM_PDF"

    if not portfolio_number:
        m_fn = re.search(r"UBP_([0-9]{6,})", filename)
        if m_fn:
            portfolio_number_fallback = m_fn.group(1)
            portfolio_number = portfolio_number_fallback
            identifier_source = "INFERRED_FROM_FILENAME"

    if is_synthetic:
        port_name = f"Synthetic Portfolio {portfolio_number}" if portfolio_number else "Synthetic Portfolio"
    else:
        port_name = f"Portfolio {portfolio_number}" if portfolio_number else "UBP Portfolio"

    if identifier_source == "INFERRED_FROM_FILENAME":
        port_name += " (Inferred from filename fallback)"

    return StatementMetadata(
        filename=filename,
        portfolio_number=portfolio_number,
        portfolio_number_extracted=portfolio_number_extracted,
        portfolio_number_fallback=portfolio_number_fallback,
        portfolio_identifier_source=identifier_source,
        portfolio_name=port_name,
        valuation_date=valuation_date,
        report_edited_date=report_edited_date,
        bank_name=bank_name,
        institution_provenance=institution_provenance,
        report_currency=report_currency,
        reporting_period=reporting_period,
        total_pages=total_pages,
        detected_sections=[],
        client_name=client_name,
        client_reference=client_reference,
        relationship_type=relationship_type
    )
