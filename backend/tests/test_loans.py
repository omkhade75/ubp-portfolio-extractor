import pytest
from decimal import Decimal
from app.extraction.table_reconstructor import extract_ubp_statement
from app.config import SAMPLE_PDFS_DIR

def test_loans_present():
    f = str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf")
    res = extract_ubp_statement(f)
    assert len(res.loans) == 2
    l1 = res.loans[0]
    assert l1.currency == "USD"
    assert l1.amount == Decimal("-100580.25")
    assert l1.interest_rate == Decimal("5.150000")
    assert l1.maturity_date == "15.01.26"
    assert l1.accrued_interest == Decimal("-1107.92")

    l2 = res.loans[1]
    assert l2.amount == Decimal("-202457.50")
    assert l2.interest_rate == Decimal("5.080000")
    assert l2.maturity_date == "17.02.26"
    assert l2.accrued_interest == Decimal("-1257.04")

def test_no_loans_present():
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    assert len(res.loans) == 0
