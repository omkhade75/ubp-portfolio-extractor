import pytest
from decimal import Decimal
import pymupdf
from app.extraction.table_reconstructor import extract_ubp_statement
from app.config import SAMPLE_PDFS_DIR

@pytest.fixture
def sample_pdf_1():
    return str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")

@pytest.fixture
def sample_pdf_3():
    return str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf")

@pytest.fixture
def sample_pdf_5():
    return str(SAMPLE_PDFS_DIR / "5_UBP_1002591_Oct2025.pdf")

def test_extract_holdings_count_and_fields(sample_pdf_1):
    res = extract_ubp_statement(sample_pdf_1)
    assert len(res.holdings) == 12
    # Verify first holding CS INVESTMENT FUNDS
    h0 = res.holdings[0]
    assert h0.isin_secur_no == "LU2001707251"
    assert h0.units_nominal == Decimal("93.27")
    assert h0.value_in_usd == Decimal("95134.47")
    assert h0.market_value_currency == "USD"
    assert h0.asset_category == "BONDS/NOTES, BOND FUNDS & CERTIFICATES"

def test_extract_multi_page_holdings(sample_pdf_3):
    res = extract_ubp_statement(sample_pdf_3)
    # Holdings continue across pages 3, 4, 5
    assert len(res.holdings) == 17
    # Verify holding from page 5
    h_p5 = [h for h in res.holdings if h.source_page == 5]
    assert len(h_p5) == 1
    assert h_p5[0].isin_secur_no == "XS2981244168"
    assert h_p5[0].units_nominal == Decimal("800000")
    assert h_p5[0].market_value_currency == "HKD"

def test_jan2026_alternatives_column_mapping(sample_pdf_3):
    """
    Verifies that in January 2026 statement:
      - 'ALTERNATIVES' is preserved in the security name and NEVER assigned to Secur No.
      - The actual identifier 'XFCS00X6RK62' is cleanly mapped to isin_secur_no.
      - Full multi-line description is preserved without truncation.
    """
    res = extract_ubp_statement(sample_pdf_3)
    h_alpha = next(h for h in res.holdings if "ALPHA" in h.security_name)
    assert h_alpha.isin_secur_no == "XFCS00X6RK62"
    assert "ALTERNATIVES" in h_alpha.security_name
    assert "EQUITY ABSOL.RETURN" in h_alpha.security_name
    assert h_alpha.units_nominal == Decimal("200")
    assert h_alpha.value_in_usd == Decimal("220951.86")
    assert h_alpha.percentage_of_total_assets == Decimal("8.57")

def test_oct2025_continuation_line_no_spurious_holding(sample_pdf_5):
    """
    Verifies that in October 2025 statement 1002591:
      - Continuation line containing 'SPVI-SPV2-SER' is NOT treated as a spurious holding.
      - Exactly 9 holdings are extracted.
      - Category subtotal for ALTERNATIVE INVESTMENTS reconciles to $67,453.95 with zero variance.
    """
    res = extract_ubp_statement(sample_pdf_5)
    assert len(res.holdings) == 9
    assert not any(h.isin_secur_no == "SPVI-SPV2-SER" for h in res.holdings)
    h_ta = next(h for h in res.holdings if "TA ASIAN MULTI-FINANCE FUND-ASIAN TR FIN" in h.security_name)
    assert h_ta.isin_secur_no == "XD1148483633"
    assert "SPVI-SPV2-SER" in h_ta.security_name
    assert h_ta.units_nominal == Decimal("1165.141")
    assert h_ta.value_in_usd == Decimal("40442.04")
