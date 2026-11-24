import pymupdf
from typing import List, Dict, Optional
from app.extraction.word_extractor import get_page_text

PAGE_SECTION_TYPES = {
    "OVERVIEW_ASSET_ALLOCATION": "Portfolio Overview & Asset Allocation",
    "CURRENCY_BREAKDOWN": "Currency Breakdown",
    "HOLDINGS": "Current Portfolio / Holdings",
    "ACCOUNTS_AND_LOANS": "Current Accounts & Loans",
    "NET_ASSETS_SUMMARY": "Summary of Net Assets & Exchange Rates",
    "MONTHLY_PERFORMANCE": "Monthly Performance",
    "ANNUAL_PERFORMANCE": "Annual Performance",
    "DISCLAIMER_GENERAL": "Disclaimer & General Information",
    "DISCLAIMER_RISK_ESG": "Product Risk Classification & ESG",
    "ACKNOWLEDGEMENT_OF_ASSETS": "Acknowledgement of Assets",
    "UNKNOWN": "Other Content"
}

def classify_statement_page(page: pymupdf.Page, page_num: int, total_pages: int, page_text: Optional[str] = None) -> str:
    """
    Deterministically classifies a statement page into its standard semantic report section
    based on section headings, column labels, and textual fingerprints.
    Works independently of bank branding (UBP, synthetic demo, or other portfolio templates).
    """
    if page_text is None:
        page_text = get_page_text(page)
    text = page_text.upper()

    # 1. Overview / Asset Allocation & Portfolio Summary
    # Identified dynamically by section headings, table of contents, and valuation headers (not fixed page index)
    is_overview = (
        ("PORTFOLIO IN " in text or "PORTFOLIO OVERVIEW" in text or "ASSET ALLOCATION" in text)
        and ("VALUATION AS OF" in text or "TABLE OF CONTENTS" in text or "PORTFOLIO VALUATION" in text or "PERFORMANCE TWR" in text)
    )
    if is_overview:
        return "OVERVIEW_ASSET_ALLOCATION"

    if "BREAKDOWN OF NET ASSETS BY CURRENCY" in text or "CURRENCY BREAKDOWN" in text or "BREAKDOWN BY CURRENCY" in text:
        return "CURRENCY_BREAKDOWN"
    
    if "SUMMARY OF NET ASSETS" in text or "EXCHANGE RATES USED" in text:
        return "NET_ASSETS_SUMMARY"

    if "HISTORY OF MONTHLY PERFORMANCES" in text or "MONTHLY PERFORMANCES" in text:
        return "MONTHLY_PERFORMANCE"

    if "HISTORY OF ANNUAL PERFORMANCES" in text or "HISTORY OF YEARLY PERFORMANCES" in text or "ANNUAL PERFORMANCES" in text:
        return "ANNUAL_PERFORMANCE"

    if "PRODUCT RISK CLASSIFICATION" in text or "PRC 001" in text or "PRC" in text:
        return "DISCLAIMER_RISK_ESG"

    if "ACKNOWLEDGEMENT OF ASSETS" in text or "RECONCILIATION STATEMENT" in text or "RECONCILIA" in text:
        return "ACKNOWLEDGEMENT_OF_ASSETS"

    if any(d in text for d in ["DISCLAIMER", "COMMENTS AND DISCLOSURES", "GENERAL INFORMATION", "IMPORTANT INFORMATION"]):
        return "DISCLAIMER_GENERAL"

    # Accounts and Loans page
    if "CURRENT ACCOUNTS" in text or "LOANS" in text:
        if "ASSET ALLOCATION" not in text:
            return "ACCOUNTS_AND_LOANS"

    # Holdings page: dynamically detected by table column headers or asset category listings
    if "CURRENT PORTFOLIO" in text or "UNITS/NOMINAL" in text or "UNITS / NOMINAL" in text:
        return "HOLDINGS"
    if ("SECURITY NUMBER" in text or "ISIN" in text) and ("MARKET PRICE" in text or "MARKET VALUE" in text):
        if "ASSET ALLOCATION" not in text and "BREAKDOWN OF NET ASSETS" not in text and "CURRENCY BREAKDOWN" not in text:
            return "HOLDINGS"
    if any(h in text for h in ["BONDS/NOTES", "EQUITIES, EQUITY", "ALTERNATIVE INVESTMENTS", "STRUCTURED PRODUCTS", "PRIVATE EQUITY"]):
        if "ASSET ALLOCATION" not in text and "BREAKDOWN OF NET ASSETS" not in text and "CURRENCY BREAKDOWN" not in text:
            return "HOLDINGS"

    return "UNKNOWN"
