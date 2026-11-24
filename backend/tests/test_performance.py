import pytest
from decimal import Decimal
from app.extraction.table_reconstructor import extract_ubp_statement
from app.config import SAMPLE_PDFS_DIR

def test_monthly_and_annual_performance():
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    assert len(res.monthly_performance) == 14  # initial + 12 months + total
    m0 = res.monthly_performance[0]
    assert m0.is_initial_row
    assert m0.period == "01.07.2024"
    assert m0.end_of_period_assets == Decimal("2205057")

    m_tot = res.monthly_performance[-1]
    assert m_tot.is_total_row
    assert m_tot.period == "Total"
    assert m_tot.period_deposits_withdrawals == Decimal("-78128")
    assert m_tot.change_in_total_assets == Decimal("140740")
    assert m_tot.net_income == Decimal("104430")

    assert len(res.annual_performance) == 12  # initial + 10 years + total
    a_tot = res.annual_performance[-1]
    assert a_tot.is_total_row
    assert a_tot.period_deposits_withdrawals == Decimal("2161505")

def test_annual_performance_final_row_periodic_jul2025():
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    
    # 20.12.2016 should be the only initial row
    initial_rows = [r for r in res.annual_performance if r.is_initial_row]
    assert len(initial_rows) == 1
    assert initial_rows[0].period == "20.12.2016"
    assert initial_rows[0].end_of_period_assets == Decimal("635000")

    # 30.06.2025 must NOT be marked as initial, and must have all 7 financial values
    p_row = next((r for r in res.annual_performance if r.period == "30.06.2025"), None)
    assert p_row is not None
    assert p_row.is_initial_row is False
    assert p_row.is_total_row is False
    assert p_row.performance_pct == Decimal("3.17")
    assert p_row.cumulative_performance_pct == Decimal("8.98")
    assert p_row.end_of_period_assets == Decimal("2267669")
    assert p_row.period_deposits_withdrawals == Decimal("-64470")
    assert p_row.change_in_total_assets == Decimal("71394")
    assert p_row.net_income == Decimal("33641")
    assert p_row.return_on_net_income_pct == Decimal("1.48")

def test_portfolio_summary_performance_jul2025():
    f = str(SAMPLE_PDFS_DIR / "1_UBP_1002590_Jul2025.pdf")
    res = extract_ubp_statement(f)
    
    perf = res.portfolio_summary_performance
    assert perf is not None
    assert perf.initial_assets == Decimal("2260746.02")
    assert perf.total_incoming_securities == Decimal("0.00")
    assert perf.total_outgoing_securities == Decimal("0.00")
    assert perf.total_incoming_cash == Decimal("0.00")
    assert perf.total_outgoing_cash == Decimal("-64470.32")
    assert perf.total_inc_out_cash_sec == Decimal("-64470.32")
    assert perf.change_in_total_assets == Decimal("71393.58")
    assert perf.ending_assets == Decimal("2267669.27")
    assert perf.number_of_days == 180
    assert perf.performance_twr_pct == Decimal("3.17")
    assert perf.source_page == 1
