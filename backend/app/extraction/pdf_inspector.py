import re
from typing import Dict, Any, List, Optional
import pymupdf
from app.models.schemas import StatementMetadata
from app.extraction.word_extractor import get_page_text

def inspect_pdf_document(doc: pymupdf.Document, filename: str) -> StatementMetadata:
    """
    Inspects PDF document structure, rotation, dimensions, and header metadata.
    Dynamically discovers portfolio number, valuation date, and page count.
    Handles partial/redacted portfolio numbers cleanly.
    Identifies issuing bank or records NOT_STATED if no bank branding is found.
    """
    total_pages = len(doc)
    portfolio_number: Optional[str] = None
    portfolio_name: Optional[str] = None
    valuation_date: Optional[str] = None
    report_edited_date: Optional[str] = None
    bank_name: Optional[str] = None
    report_currency = "USD"
    is_synthetic = False
    client_name: Optional[str] = None
    client_reference: Optional[str] = None
    relationship_type: Optional[str] = None

    # Search first 5 pages for metadata
    for pno in range(min(5, total_pages)):
        text = get_page_text(doc[pno])

        if "SYNTHETIC PORTFOLIO" in text.upper():
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

        # Bank Name detection (handles Singapore, Geneva, Zurich, London, Hong Kong, Monaco, Luxembourg, etc.)
        if not bank_name:
            m_bank = re.search(r"(UNION BANCAIRE PRIV[EÉ]E(?:,\s*UBP SA(?:,\s*[A-Z\s]+BRANCH)?)?)", text, re.IGNORECASE)
            if m_bank:
                bank_name = m_bank.group(1).strip()

        # Reporting currency detection: PORTFOLIO IN USD or PERFORMANCES ... IN USD or CURRENCY : USD
        m_curr = re.search(r"PORTFOLIO IN\s+([A-Z]{3})", text, re.IGNORECASE) or re.search(r"PERFORMANCES.*IN\s+([A-Z]{3})", text, re.IGNORECASE) or re.search(r"CURRENCY\s*:\s*([A-Z]{3})", text, re.IGNORECASE)
        if m_curr:
            report_currency = m_curr.group(1).strip().upper()

        # Valuation date pattern: PORTFOLIO VALUATION AS OF 30.06.2025 or VALUATION AS OF 31.03.2026
        if not valuation_date:
            m_val = re.search(r"(?:PORTFOLIO\s+)?VALUATION\s+AS\s+OF\s*:?\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})", text, re.IGNORECASE)
            if m_val:
                valuation_date = m_val.group(1).strip()

        # Report edited date: Report edited on : 01.07.25
        if not report_edited_date:
            m_edit = re.search(r"Report\s+edited\s+on\s*:?\s*([0-9]{2}\.[0-9]{2}\.[0-9]{2,4})", text, re.IGNORECASE)
            if m_edit:
                report_edited_date = m_edit.group(1).strip()

        # Portfolio Number pattern (must be digits, e.g. 1002590, 1002591, 2004812, 548271)
        if not portfolio_number:
            # Pattern 1: Portfolio No. 1002590 or Portfolio No. : 2004812 or PORTFOLIO NO. 548271
            m_port = re.search(r"Portfolio\s+(?:No\.?|Number)\s*:?\s*([0-9]{6,})", text, re.IGNORECASE)
            if m_port:
                portfolio_number = m_port.group(1).strip()
            else:
                # Pattern 2: Portfolio 001 SEE1002590
                m_port2 = re.search(r"Portfolio\s+001\s+SEE\s*([0-9]{6,})", text, re.IGNORECASE)
                if m_port2:
                    portfolio_number = m_port2.group(1).strip()
                else:
                    # Pattern 3: SEE1002590 or Portfolio 2004812
                    m_port3 = re.search(r"(?:SEE|Portfolio)\s*:?\s*([0-9]{6,})", text, re.IGNORECASE)
                    if m_port3:
                        portfolio_number = m_port3.group(1).strip()

    # Per Task 5: If bank is not identified in document, record NOT_STATED
    if not bank_name:
        bank_name = "NOT_STATED"

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
        report_currency=report_currency,
        total_pages=total_pages,
        detected_sections=[],
        client_name=client_name,
        client_reference=client_reference,
        relationship_type=relationship_type
    )
