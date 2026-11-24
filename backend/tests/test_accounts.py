import pytest
from decimal import Decimal
from app.extraction.table_reconstructor import extract_ubp_statement
from app.config import SAMPLE_PDFS_DIR

def test_current_accounts_single_currency():
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    assert len(res.current_accounts) == 1
    acc = res.current_accounts[0]
    assert acc.currency == "USD"
    assert acc.amount == Decimal("241292.33")
    assert acc.account_number == "0001"
    assert acc.percentage_assets == Decimal("10.64")

def test_current_accounts_multi_currency():
    f = str(SAMPLE_PDFS_DIR / "3_UBP_1002590_Jan2026.pdf")
    res = extract_ubp_statement(f)
    assert len(res.current_accounts) == 2
    currencies = {a.currency for a in res.current_accounts}
    assert "HKD" in currencies
    assert "USD" in currencies
    hkd_acc = next(a for a in res.current_accounts if a.currency == "HKD")
    assert hkd_acc.amount == Decimal("26827.20")
    assert hkd_acc.account_number == "0003"
    assert hkd_acc.market_value_usd == Decimal("3448.80")
