import pytest
from decimal import Decimal
import openpyxl
from app.extraction.table_reconstructor import extract_ubp_statement
from app.excel.workbook_generator import generate_ubp_excel_workbook
from app.config import SAMPLE_PDFS_DIR

@pytest.fixture
def statement_1():
    return str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")

@pytest.fixture
def statement_2():
    return str(SAMPLE_PDFS_DIR / "2_UBP_1002590_Oct2025.pdf")

@pytest.fixture
def statement_4():
    return str(SAMPLE_PDFS_DIR / "4_UBP_1002591_Jul2025.pdf")

@pytest.fixture
def statement_5():
    return str(SAMPLE_PDFS_DIR / "5_UBP_1002591_Oct2025.pdf")

def test_holding_blank_vs_explicit_zero_fidelity(statement_4, statement_5):
    """
    Issue 1 Test:
    Verifies that holdings with explicit 0.00 market price/value but blank
    percentage-of-assets in original PDF (IE00BMY47228) are extracted with:
      - market_price: Decimal('0.00'), state='EXPLICIT_ZERO'
      - value_in_usd: Decimal('0.00'), state='EXPLICIT_ZERO'
      - percentage_of_total_assets: None, state='SOURCE_BLANK'
    """
    for stmt_path in [statement_4, statement_5]:
        res = extract_ubp_statement(stmt_path)
        zero_holding = next(
            (h for h in res.holdings if "IE00BMY47228" in (h.isin_secur_no or "") and h.market_price == Decimal("0.00")),
            None
        )
        assert zero_holding is not None, f"Zero holding IE00BMY47228 not found in {stmt_path}"
        assert zero_holding.market_price == Decimal("0.00")
        assert zero_holding.market_price_state == "EXPLICIT_ZERO"
        assert zero_holding.value_in_usd == Decimal("0.00")
        assert zero_holding.value_in_usd_state == "EXPLICIT_ZERO"
        assert zero_holding.percentage_of_total_assets is None
        assert zero_holding.percentage_state == "SOURCE_BLANK"

        # Verify Missing vs Zero validation check passes
        mvz_check = next((c for c in res.validation_checks if c.name == "Missing vs Zero Fields Integrity"), None)
        assert mvz_check is not None
        assert mvz_check.level == "PASS"
        assert mvz_check.details["explicit_zeros"] >= 1
        assert mvz_check.details["source_blanks"] >= 1

def test_excel_cell_blank_for_unpopulated_percentage(tmp_path, statement_4):
    """
    Issue 1 Excel Test:
    Verifies that the generated Excel workbook for Statement 4 writes None (empty cell)
    into the Percentage_Total_Assets column for IE00BMY47228, NEVER 0 or 0.00%.
    """
    res = extract_ubp_statement(statement_4)
    out_xlsx = generate_ubp_excel_workbook(res, str(tmp_path))
    
    wb = openpyxl.load_workbook(out_xlsx, data_only=True)
    ws = wb["Holdings"]
    headers = [cell.value for cell in ws[1]]
    isin_col = headers.index("ISIN_Secur_No") + 1
    pct_col = headers.index("Percentage_Total_Assets") + 1
    price_col = headers.index("Market_Price") + 1

    found_zero_holding = False
    for r in range(2, ws.max_row + 1):
        isin = ws.cell(r, isin_col).value
        price = ws.cell(r, price_col).value
        pct = ws.cell(r, pct_col).value
        if isin == "IE00BMY47228" and (price == 0 or price == 0.0):
            found_zero_holding = True
            # Percentage MUST be None (blank cell), not 0 or 0.0
            assert pct is None, f"Expected empty cell for blank percentage, got: {pct}"

    assert found_zero_holding, "Zero holding IE00BMY47228 row not found in Excel"

def test_period_aligned_monthly_flow_statement_1(statement_1):
    """
    Issue 2 Test: Statement 1
    Page 1 reports flow of -64,470.32 for period SINCE 01.01.2025 to 30.06.2025.
    Monthly table contains 2024 history (with -13,658 in 12.2024).
    Validator must filter strictly to 2025 months (01.2025 to 06.2025, sum = -64,470.00).
    Difference is 0.32 USD <= 1.00 USD rounding tolerance -> ROUNDING_DIFFERENCE (level: PASS).
    """
    res = extract_ubp_statement(statement_1)
    flow_check = next((c for c in res.validation_checks if c.name == "Portfolio Flow vs Performance Flow"), None)
    assert flow_check is not None
    assert flow_check.level == "PASS"
    assert flow_check.details["reconciliation_status"] == "ROUNDING_DIFFERENCE"
    assert flow_check.details["reporting_period"] == "01.2025 - 06.2025"
    assert Decimal(flow_check.details["difference"]) == Decimal("0.32")
    assert flow_check.details["page1_portfolio_flow"] == "-64470.32"
    assert flow_check.details["monthly_performance_flow"] == "-64470"

def test_period_aligned_monthly_flow_statement_4(statement_4):
    """
    Issue 2 Test: Statement 4
    Page 1 reports flow 0.00. Monthly performance sum in 2025 is 0.00.
    Status is MATCH (level: PASS).
    """
    res = extract_ubp_statement(statement_4)
    flow_check = next((c for c in res.validation_checks if c.name == "Portfolio Flow vs Performance Flow"), None)
    assert flow_check is not None
    assert flow_check.level == "PASS"
    assert flow_check.details["reconciliation_status"] == "MATCH"
    assert flow_check.details["reporting_period"] == "01.2025 - 06.2025"
    assert flow_check.details["page1_portfolio_flow"] == "0.00"
    assert flow_check.details["monthly_performance_flow"] == "0"

def test_period_aligned_monthly_flow_discrepancy_preserved(statement_2):
    """
    Issue 2 Test: Statement 2
    Page 1 reports flow -108,426.38. Monthly performance in 2025 sum is -108,526.00.
    Difference is 99.62 USD > 1.00 USD.
    Status is SOURCE_DISCREPANCY (level: INFO), preserving both source figures.
    """
    res = extract_ubp_statement(statement_2)
    flow_check = next((c for c in res.validation_checks if c.name == "Portfolio Flow vs Performance Flow"), None)
    assert flow_check is not None
    assert flow_check.level == "INFO"
    assert flow_check.details["reconciliation_status"] == "SOURCE_DISCREPANCY"
    assert flow_check.details["reporting_period"] == "01.2025 - 09.2025"
    assert Decimal(flow_check.details["discrepancy"]) == Decimal("99.62")
    assert flow_check.details["page1_portfolio_flow"] == "-108426.38"
    assert flow_check.details["monthly_performance_flow"] == "-108526"
