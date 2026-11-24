from typing import List, Dict
import pymupdf
from app.models.schemas import CommentsDisclosuresData
from app.extraction.word_extractor import get_page_text

def parse_disclosures(doc: pymupdf.Document, classified_pages: Dict[int, str]) -> CommentsDisclosuresData:
    """
    Extracts all non-financial but critical audit and regulatory content:
      - General information disclaimer
      - Product Risk Classification (PRC) & ESG definitions
      - Acknowledgement of assets
      - Notes and footnotes
    """
    general_info_parts: List[str] = []
    prc_parts: List[str] = []
    ack_parts: List[str] = []
    all_disclaimers: List[str] = []
    source_pages: List[int] = []
    general_info_pages: List[int] = []
    prc_pages: List[int] = []
    ack_pages: List[int] = []

    for pno, section_type in classified_pages.items():
        page = doc[pno]
        page_num = pno + 1
        text = get_page_text(page).strip()

        if section_type == "DISCLAIMER_GENERAL":
            source_pages.append(page_num)
            general_info_pages.append(page_num)
            general_info_parts.append(text)
            all_disclaimers.append(f"[Page {page_num} - General Information]\n{text}")

        elif section_type == "DISCLAIMER_RISK_ESG":
            source_pages.append(page_num)
            prc_pages.append(page_num)
            prc_parts.append(text)
            all_disclaimers.append(f"[Page {page_num} - Product Risk & ESG]\n{text}")

        elif section_type == "ACKNOWLEDGEMENT_OF_ASSETS":
            source_pages.append(page_num)
            ack_pages.append(page_num)
            ack_parts.append(text)
            all_disclaimers.append(f"[Page {page_num} - Acknowledgement of Assets]\n{text}")

    return CommentsDisclosuresData(
        general_information="\n\n".join(general_info_parts),
        product_risk_classification="\n\n".join(prc_parts),
        acknowledgement_of_assets="\n\n".join(ack_parts),
        disclaimers=all_disclaimers,
        source_pages=source_pages,
        general_info_pages=general_info_pages,
        prc_pages=prc_pages,
        ack_pages=ack_pages
    )
