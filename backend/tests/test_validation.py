import pytest
from app.extraction.table_reconstructor import extract_ubp_statement
from app.config import SAMPLE_PDFS_DIR

def test_financial_reconciliation():
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    checks = res.validation_checks
    assert any(c.name == "Page Coverage" and c.level == "PASS" for c in checks)
    assert any(c.name == "Subtotal Reconciliation" and c.level == "PASS" for c in checks)
    assert any(c.name == "Net Assets Balance Equation" and c.level == "PASS" for c in checks)

def test_warning_for_partial_portfolio_number():
    f = str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf")
    res = extract_ubp_statement(f)
    checks = res.validation_checks
    port_check = next(c for c in checks if c.name == "Portfolio Identifier")
    assert port_check.level == "WARNING"
    assert "could not be fully extracted" in port_check.message
