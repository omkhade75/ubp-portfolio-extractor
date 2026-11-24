import os
import re
from decimal import Decimal
from typing import Optional, List, Dict, Any
import openpyxl

from app.models.schemas import StatementExtractionResult
from app.excel.formatting import (
    HEADER_FONT, TITLE_FONT, SECTION_FONT, DATA_FONT, BOLD_DATA_FONT,
    PASS_FONT, WARNING_FONT, FAIL_FONT,
    HEADER_FILL, SUBTOTAL_FILL, PASS_FILL, WARN_FILL, FAIL_FILL,
    ALIGN_LEFT, ALIGN_LEFT_WRAP, ALIGN_CENTER, ALIGN_RIGHT,
    CELL_BORDER, HEADER_BORDER, TOTAL_BORDER,
    FMT_AMOUNT, FMT_INTEGER, FMT_PERCENT, FMT_PERCENT_PLAIN, FMT_PRICE,
    clean_excel_string, style_header_row, autofit_columns
)

def safe_append(ws, row: List[Any]):
    """Appends a row after sanitizing string elements against XML control characters."""
    ws.append([clean_excel_string(c) for c in row])

def generate_ubp_excel_workbook(res: StatementExtractionResult, output_dir: str) -> str:
    """
    Generates a structured, professional, openpyxl-based financial workbook
    conforming to Taurus standards and Section 15 specifications.
    Generates 16 dedicated worksheets without silent data loss.
    """
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    meta = res.metadata
    port_str = meta.portfolio_number or "UnknownPort"
    safe_fn = os.path.splitext(meta.filename)[0]
    out_filename = f"UBP_{port_str}_{safe_fn}.xlsx"

    if output_dir.lower().endswith(".xlsx"):
        out_path = output_dir
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    else:
        os.makedirs(output_dir, exist_ok=True)
        out_path = os.path.join(output_dir, out_filename)

    # 1. Portfolio_Overview
    _build_portfolio_overview_sheet(wb, res)

    # 2. Asset_Allocation
    _build_asset_allocation_sheet(wb, res)

    # 3. Currency_Breakdown
    _build_currency_breakdown_sheet(wb, res)

    # 4. Holdings
    _build_holdings_sheet(wb, res)

    # 5. Current_Accounts
    _build_current_accounts_sheet(wb, res)

    # 6. Loans
    _build_loans_sheet(wb, res)

    # 7. Transactions
    _build_transactions_sheet(wb, res)

    # 8. Net_Assets_Summary
    _build_net_assets_summary_sheet(wb, res)

    # 9. Exchange_Rates
    _build_exchange_rates_sheet(wb, res)

    # 10. Monthly_Performance
    _build_monthly_performance_sheet(wb, res)

    # 11. Annual_Performance
    _build_annual_performance_sheet(wb, res)

    # 12. Comments
    _build_comments_sheet(wb, res)

    # 13. Counts
    _build_counts_sheet(wb, res)

    # 14. Validation
    _build_validation_sheet(wb, res)

    # 15. Unmapped_Content
    _build_unmapped_content_sheet(wb, res)

    # 16. Raw_Page_Text
    _build_raw_page_text_sheet(wb, res)

    wb.save(out_path)
    res.excel_path = out_path
    return out_path

# ==============================================================================
# SHEET BUILDERS
# ==============================================================================

def _build_portfolio_overview_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Portfolio_Overview")
    meta = res.metadata
    
    ws["A1"] = "UBP Portfolio Statement Extraction Summary"
    ws["A1"].font = TITLE_FONT
    ws.row_dimensions[1].height = 28

    has_fails = any(c.level == "FAIL" for c in res.validation_checks)
    has_missing_holdings = len(res.holdings) == 0 and "HOLDINGS" in meta.detected_sections
    status_str = "REVIEW_REQUIRED" if has_fails or has_missing_holdings else "COMPLETED"

    metadata_rows = [
        ("Bank Name", meta.bank_name),
        ("Portfolio Number (Extracted from PDF)", meta.portfolio_number_extracted or "NOT_PRINTED_IN_SOURCE_DOCUMENT"),
        ("Portfolio Number (Filename Fallback)", meta.portfolio_number_fallback or "N/A"),
        ("Portfolio Identifier Source", meta.portfolio_identifier_source or "EXTRACTED_FROM_PDF"),
        ("Portfolio Name", meta.portfolio_name or ""),
        ("Valuation Date", meta.valuation_date or ""),
        ("Report Edited Date", meta.report_edited_date or ""),
        ("Reporting Currency", meta.report_currency),
        ("Total Source Pages", meta.total_pages),
        ("Original File", meta.filename),
        ("Extraction Status", status_str),
    ]
    if meta.client_name:
        metadata_rows.append(("Client Name", meta.client_name))
    if meta.client_reference:
        metadata_rows.append(("Client Reference", meta.client_reference))
    if meta.relationship_type:
        metadata_rows.append(("Relationship", meta.relationship_type))
    perf = res.portfolio_summary_performance
    port_esg_prev = meta.portfolio_esg_previous or meta.portfolio_previous_esg_rating
    port_esg_curr = meta.portfolio_esg_current or meta.portfolio_current_esg_rating
    port_esg_page = meta.portfolio_esg_source_page or (perf.source_page if perf and (port_esg_prev or port_esg_curr) else None)

    if port_esg_prev or port_esg_curr:
        metadata_rows.append(("Portfolio ESG Rating (Previous)", port_esg_prev or ""))
        metadata_rows.append(("Portfolio ESG Rating (Current)", port_esg_curr or ""))
        if port_esg_page:
            metadata_rows.append(("Portfolio ESG Source Page", port_esg_page))

    for idx, (lbl, val) in enumerate(metadata_rows, start=3):
        ws.cell(row=idx, column=1, value=lbl).font = BOLD_DATA_FONT
        ws.cell(row=idx, column=1).border = CELL_BORDER
        c_val = ws.cell(row=idx, column=2, value=val)
        c_val.font = DATA_FONT
        c_val.border = CELL_BORDER

    # Structured Section for Page 1 Right-Side Portfolio in USD Summary
    perf = res.portfolio_summary_performance
    start_row = len(metadata_rows) + 5
    ws.cell(row=start_row, column=1, value="PORTFOLIO PERFORMANCE & ASSET FLOW SUMMARY (USD)").font = HEADER_FONT
    ws.row_dimensions[start_row].height = 24

    perf_headers = ["Metric / Flow Description", "Extracted Value", "Raw Source Value", "Source Page"]
    for c_idx, h_text in enumerate(perf_headers, start=1):
        cell = ws.cell(row=start_row + 1, column=c_idx, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER if c_idx in [3, 4] else (ALIGN_RIGHT if c_idx == 2 else ALIGN_LEFT)
        cell.border = CELL_BORDER

    perf_items = []
    if perf:
        raw = perf.raw_values
        perf_items = [
            ("Reporting Period", perf.reporting_period, "TEXT", raw.get("reporting_period", perf.reporting_period or "")),
            ("Initial Assets", float(perf.initial_assets) if perf.initial_assets is not None else None, "AMOUNT", raw.get("initial_assets", "")),
            ("Total Incoming Securities", float(perf.total_incoming_securities) if perf.total_incoming_securities is not None else None, "AMOUNT", raw.get("total_incoming_securities", "")),
            ("Total Outgoing Securities", float(perf.total_outgoing_securities) if perf.total_outgoing_securities is not None else None, "AMOUNT", raw.get("total_outgoing_securities", "")),
            ("Total Incoming Cash", float(perf.total_incoming_cash) if perf.total_incoming_cash is not None else None, "AMOUNT", raw.get("total_incoming_cash", "")),
            ("Total Outgoing Cash", float(perf.total_outgoing_cash) if perf.total_outgoing_cash is not None else None, "AMOUNT", raw.get("total_outgoing_cash", "")),
            ("Total of Inc/Out Cash & Sec", float(perf.total_inc_out_cash_sec) if perf.total_inc_out_cash_sec is not None else None, "AMOUNT", raw.get("total_inc_out_cash_sec", "")),
            ("Change in Total Assets", float(perf.change_in_total_assets) if perf.change_in_total_assets is not None else None, "AMOUNT", raw.get("change_in_total_assets", "")),
            (f"Assets as of {perf.valuation_date or meta.valuation_date or ''}".strip(), float(perf.ending_assets) if perf.ending_assets is not None else None, "AMOUNT", raw.get("ending_assets", "")),
            ("Number of Days", f"{perf.number_of_days} D" if perf.number_of_days is not None else None, "TEXT", raw.get("number_of_days", "")),
            ("Performance TWR (USD)", float(perf.performance_twr_pct) / 100.0 if perf.performance_twr_pct is not None else None, "PERCENT", raw.get("performance_twr_pct", "")),
        ]
    else:
        perf_items = [
            ("Status", "NOT_PRESENT", "TEXT", "Not present on overview page")
        ]

    for p_idx, (lbl, val, val_type, raw_val) in enumerate(perf_items, start=start_row + 2):
        c1 = ws.cell(row=p_idx, column=1, value=lbl)
        c1.font = BOLD_DATA_FONT
        c1.border = CELL_BORDER

        c2 = ws.cell(row=p_idx, column=2, value=val)
        c2.font = DATA_FONT
        c2.border = CELL_BORDER
        if val_type == "AMOUNT":
            c2.number_format = FMT_AMOUNT
            c2.alignment = ALIGN_RIGHT
        elif val_type == "PERCENT":
            c2.number_format = FMT_PERCENT
            c2.alignment = ALIGN_RIGHT
        else:
            c2.alignment = ALIGN_LEFT

        c3 = ws.cell(row=p_idx, column=3, value=raw_val)
        c3.font = DATA_FONT
        c3.border = CELL_BORDER
        c3.alignment = ALIGN_RIGHT

        c4 = ws.cell(row=p_idx, column=4, value=perf.source_page if perf else 1)
        c4.font = DATA_FONT
        c4.border = CELL_BORDER
        c4.alignment = ALIGN_CENTER

    # Structured Section for Portfolio ESG Rating
    esg_start_row = start_row + len(perf_items) + 3
    ws.cell(row=esg_start_row, column=1, value="PORTFOLIO ESG RATING (PREVIOUS - CURRENT)").font = HEADER_FONT
    ws.row_dimensions[esg_start_row].height = 24

    esg_headers = ["Field_Name", "Extracted_Rating", "Source_Page"]
    for c_idx, h_text in enumerate(esg_headers, start=1):
        cell = ws.cell(row=esg_start_row + 1, column=c_idx, value=h_text)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = ALIGN_CENTER if c_idx == 3 else ALIGN_LEFT
        cell.border = CELL_BORDER

    esg_items = [
        ("Portfolio_ESG_Previous", port_esg_prev if port_esg_prev else None, port_esg_page if port_esg_prev else None),
        ("Portfolio_ESG_Current", port_esg_curr if port_esg_curr else None, port_esg_page if port_esg_curr else None),
    ]

    for e_idx, (lbl, val, spage) in enumerate(esg_items, start=esg_start_row + 2):
        c1 = ws.cell(row=e_idx, column=1, value=lbl)
        c1.font = BOLD_DATA_FONT
        c1.border = CELL_BORDER

        c2 = ws.cell(row=e_idx, column=2, value=val)
        c2.font = DATA_FONT
        c2.border = CELL_BORDER
        c2.alignment = ALIGN_LEFT

        c3 = ws.cell(row=e_idx, column=3, value=spage)
        c3.font = DATA_FONT
        c3.border = CELL_BORDER
        c3.alignment = ALIGN_CENTER

    ws.freeze_panes = "A3"
    autofit_columns(ws)

def _build_asset_allocation_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Asset_Allocation")
    headers = ["Investment_Category", "Value_USD", "Percentage", "Raw_Value", "Raw_Percentage", "Source_Page"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for item in res.asset_allocation:
        row = [
            item.investment_category,
            float(item.value_usd) if item.value_usd is not None else None,
            float(item.percentage) / 100.0 if item.percentage is not None else None,
            item.raw_value,
            item.raw_percentage,
            item.source_page
        ]
        safe_append(ws, row)
        r_idx = ws.max_row
        ws.cell(r_idx, 2).number_format = FMT_AMOUNT
        ws.cell(r_idx, 3).number_format = FMT_PERCENT
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)

def _build_currency_breakdown_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Currency_Breakdown")
    # Dynamically detect non-USD currencies present in this specific statement
    non_usd_currencies = []
    for item in res.currency_breakdown:
        for c in item.currencies.keys():
            if c != "USD" and c not in non_usd_currencies:
                non_usd_currencies.append(c)

    headers = ["Asset_Class", "Total_000s_USD", "Total_Percentage", "USD_000s", "USD_Percentage"]
    for c in non_usd_currencies:
        headers.extend([f"{c}_000s", f"{c}_Percentage"])
    headers.extend(["Source_Page", "Raw_Text"])

    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for item in res.currency_breakdown:
        usd_d = item.currencies.get("USD")
        row = [
            item.asset_class,
            float(item.total_in_thousands) if item.total_in_thousands is not None else None,
            float(item.total_percentage) / 100.0 if item.total_percentage is not None else None,
            float(usd_d.amount_in_thousands) if usd_d and usd_d.amount_in_thousands is not None else None,
            float(usd_d.percentage) / 100.0 if usd_d and usd_d.percentage is not None else None,
        ]
        for c in non_usd_currencies:
            cd = item.currencies.get(c)
            row.append(float(cd.amount_in_thousands) if cd and cd.amount_in_thousands is not None else None)
            row.append(float(cd.percentage) / 100.0 if cd and cd.percentage is not None else None)
        row.extend([item.source_page, item.raw_text])

        safe_append(ws, row)
        r_idx = ws.max_row
        ws.cell(r_idx, 2).number_format = FMT_AMOUNT
        ws.cell(r_idx, 3).number_format = FMT_PERCENT
        ws.cell(r_idx, 4).number_format = FMT_AMOUNT
        ws.cell(r_idx, 5).number_format = FMT_PERCENT
        col_offset = 6
        for _ in non_usd_currencies:
            ws.cell(r_idx, col_offset).number_format = FMT_AMOUNT
            ws.cell(r_idx, col_offset + 1).number_format = FMT_PERCENT
            col_offset += 2
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)

def _build_holdings_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Holdings")
    headers = [
        "Holding_ID", "Asset_Category", "Security_Name", "ISIN_Secur_No",
        "Units_Nominal", "Net_Average_Cost", "Cost_Currency",
        "Market_Price", "Market_Price_Currency", "Market_Price_Date",
        "Total_Market_Value", "Market_Value_Currency",
        "Accrued_Interest", "Accrued_Interest_USD",
        "Value_in_USD", "Percentage_Total_Assets",
        "Yield", "Duration", "Rating",
        "Price_Marker", "Previous_ESG_Rating", "Current_ESG_Rating",
        "Source_Page"
    ]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for h in res.holdings:
        row = [
            h.id,
            h.asset_category,
            h.security_name,
            h.isin_secur_no,
            float(h.units_nominal) if h.units_nominal is not None else None,
            float(h.net_avg_cost) if h.net_avg_cost is not None else None,
            h.net_avg_cost_currency,
            float(h.market_price) if h.market_price is not None else None,
            h.market_price_currency,
            h.market_price_date,
            float(h.total_market_value) if h.total_market_value is not None else None,
            h.market_value_currency,
            float(h.accrued_interest) if h.accrued_interest is not None else None,
            float(h.accrued_interest_usd) if h.accrued_interest_usd is not None else None,
            float(h.value_in_usd) if h.value_in_usd is not None else None,
            float(h.percentage_of_total_assets) / 100.0 if h.percentage_of_total_assets is not None else None,
            float(h.yield_val) if h.yield_val is not None else None,
            h.duration,
            h.rating,
            h.price_marker,
            h.previous_esg_rating or h.esg_rating_previous,
            h.current_esg_rating or h.esg_rating_current,
            h.source_page
        ]
        safe_append(ws, row)
        r_idx = ws.max_row
        ws.cell(r_idx, 5).number_format = FMT_AMOUNT
        ws.cell(r_idx, 6).number_format = FMT_AMOUNT
        ws.cell(r_idx, 8).number_format = FMT_PRICE
        ws.cell(r_idx, 11).number_format = FMT_AMOUNT
        ws.cell(r_idx, 13).number_format = FMT_AMOUNT
        ws.cell(r_idx, 14).number_format = FMT_AMOUNT
        ws.cell(r_idx, 15).number_format = FMT_AMOUNT
        ws.cell(r_idx, 16).number_format = FMT_PERCENT
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)

def _build_current_accounts_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Current_Accounts")
    headers = ["Account_ID", "Currency", "Amount", "Account_Name", "Account_Number", "Market_Value", "Value_in_USD", "Percentage_Assets", "Source_Page"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for a in res.current_accounts:
        row = [
            a.id,
            a.currency,
            float(a.amount) if a.amount is not None else None,
            a.account_name,
            a.account_number,
            float(a.market_value) if a.market_value is not None else None,
            float(a.market_value_usd) if a.market_value_usd is not None else None,
            float(a.percentage_assets) / 100.0 if a.percentage_assets is not None else None,
            a.source_page
        ]
        safe_append(ws, row)
        r_idx = ws.max_row
        ws.cell(r_idx, 3).number_format = FMT_AMOUNT
        ws.cell(r_idx, 6).number_format = FMT_AMOUNT
        ws.cell(r_idx, 7).number_format = FMT_AMOUNT
        ws.cell(r_idx, 8).number_format = FMT_PERCENT
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)

def _build_loans_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Loans")
    headers = [
        "Loan_ID", "Currency", "Original_Amount", "Description", "Loan_Reference",
        "Maturity_Date", "Interest_Rate_Pct", "Market_Value", "Accrued_Interest",
        "USD_Equivalent", "Percentage_Assets", "Source_Page"
    ]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    if not res.loans:
        # Explicit NOT_PRESENT status without fake records containing zero amounts
        safe_append(ws, ["STATUS: NOT_PRESENT", "", None, "No loan or liability positions exist in this portfolio statement.", "", "", None, None, None, None, None, "N/A"])
        r_idx = ws.max_row
        ws.cell(r_idx, 1).font = BOLD_DATA_FONT
        for c_idx in range(1, len(headers) + 1):
            if c_idx > 1:
                ws.cell(r_idx, c_idx).font = DATA_FONT
            ws.cell(r_idx, c_idx).border = CELL_BORDER
    else:
        for l in res.loans:
            row = [
                l.id,
                l.currency,
                float(l.amount) if l.amount is not None else None,
                l.description,
                l.loan_reference,
                l.maturity_date,
                float(l.interest_rate) / 100.0 if l.interest_rate is not None else None,
                float(l.market_value) if l.market_value is not None else None,
                float(l.accrued_interest) if l.accrued_interest is not None else None,
                float(l.usd_equivalent) if l.usd_equivalent is not None else None,
                float(l.percentage_assets) / 100.0 if l.percentage_assets is not None else None,
                l.source_page
            ]
            safe_append(ws, row)
            r_idx = ws.max_row
            ws.cell(r_idx, 3).number_format = FMT_AMOUNT
            ws.cell(r_idx, 7).number_format = FMT_PERCENT
            ws.cell(r_idx, 8).number_format = FMT_AMOUNT
            ws.cell(r_idx, 9).number_format = FMT_AMOUNT
            ws.cell(r_idx, 10).number_format = FMT_AMOUNT
            ws.cell(r_idx, 11).number_format = FMT_PERCENT
            for c_idx in range(1, len(headers) + 1):
                ws.cell(r_idx, c_idx).border = CELL_BORDER
                ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    if res.loans:
        ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)

def _build_transactions_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Transactions")
    headers = ["Date", "Type", "Description", "ISIN_Secur_No", "Currency", "Amount", "Price", "Net_Amount", "Status", "Note"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    notice_row = [
        "N/A",
        "INFORMATION_ONLY",
        "Itemized transaction ledger is not present in this UBP Portfolio Valuation Statement.",
        "N/A",
        "USD",
        None,
        None,
        None,
        "NOT_PRESENT",
        "Periodic aggregate cash flow figures are available in Monthly_Performance and Annual_Performance sheets."
    ]
    safe_append(ws, notice_row)
    r_idx = ws.max_row
    for c_idx in range(1, len(headers) + 1):
        cell = ws.cell(r_idx, c_idx)
        cell.font = DATA_FONT
        cell.border = CELL_BORDER
        if c_idx == 3:
            cell.font = BOLD_DATA_FONT

    ws.freeze_panes = "A2"
    autofit_columns(ws)

def _build_net_assets_summary_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Net_Assets_Summary")
    headers = ["Summary_Field", "Amount_USD", "Percentage", "Source_Page"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    summary = res.net_assets_summary
    if summary:
        rows = [
            ("Assets", summary.assets_usd, summary.assets_pct),
            ("Accrued Interest on Securities", summary.accrued_interest_securities_usd, summary.accrued_interest_securities_pct),
            ("Net Accrued Interest on Deposits and Loans", summary.net_accrued_int_deposits_loans_usd, summary.net_accrued_int_deposits_loans_pct),
            ("Total Assets", summary.total_assets_usd, summary.total_assets_pct),
            ("Commitments", summary.commitments_usd, None),
        ]
        for fld, amt, pct in rows:
            safe_append(ws, [
                fld,
                float(amt) if amt is not None else None,
                float(pct) / 100.0 if pct is not None else None,
                summary.source_page
            ])
            r_idx = ws.max_row
            ws.cell(r_idx, 2).number_format = FMT_AMOUNT
            ws.cell(r_idx, 3).number_format = FMT_PERCENT
            for c_idx in range(1, len(headers) + 1):
                ws.cell(r_idx, c_idx).border = CELL_BORDER
                ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    autofit_columns(ws)

def _build_exchange_rates_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Exchange_Rates")
    headers = ["Base_Currency", "Target_Currency", "Exchange_Rate", "Source_Text", "Source_Page"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for rate in res.exchange_rates:
        safe_append(ws, [
            rate.base_currency,
            rate.target_currency,
            float(rate.rate),
            rate.raw_text,
            rate.source_page
        ])
        r_idx = ws.max_row
        ws.cell(r_idx, 3).number_format = '#,##0.00000000'
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    autofit_columns(ws)

def _build_monthly_performance_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Monthly_Performance")
    headers = [
        "Period", "Performance_Pct", "Cumulative_Performance_Pct",
        "End_of_Period_Assets", "Period_Deposits_Withdrawals",
        "Change_in_Total_Assets", "Net_Income", "Return_on_Net_Income_Pct",
        "Row_Type", "Source_Page"
    ]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for r in res.monthly_performance:
        row_type = "INITIAL" if r.is_initial_row else ("TOTAL" if r.is_total_row else "MONTHLY")
        row = [
            r.period,
            float(r.performance_pct) / 100.0 if r.performance_pct is not None else None,
            float(r.cumulative_performance_pct) / 100.0 if r.cumulative_performance_pct is not None else None,
            float(r.end_of_period_assets) if r.end_of_period_assets is not None else None,
            float(r.period_deposits_withdrawals) if r.period_deposits_withdrawals is not None else None,
            float(r.change_in_total_assets) if r.change_in_total_assets is not None else None,
            float(r.net_income) if r.net_income is not None else None,
            float(r.return_on_net_income_pct) / 100.0 if r.return_on_net_income_pct is not None else None,
            row_type,
            r.source_page
        ]
        safe_append(ws, row)
        r_idx = ws.max_row
        ws.cell(r_idx, 2).number_format = FMT_PERCENT
        ws.cell(r_idx, 3).number_format = FMT_PERCENT
        ws.cell(r_idx, 4).number_format = FMT_AMOUNT
        ws.cell(r_idx, 5).number_format = FMT_AMOUNT
        ws.cell(r_idx, 6).number_format = FMT_AMOUNT
        ws.cell(r_idx, 7).number_format = FMT_AMOUNT
        ws.cell(r_idx, 8).number_format = FMT_PERCENT
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = BOLD_DATA_FONT if (r.is_total_row or r.is_initial_row) else DATA_FONT
        if r.is_total_row:
            for c_idx in range(1, len(headers) + 1):
                ws.cell(r_idx, c_idx).fill = SUBTOTAL_FILL

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)

def _build_annual_performance_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Annual_Performance")
    headers = [
        "Period", "Performance_Pct", "Cumulative_Performance_Pct",
        "End_of_Period_Assets", "Period_Deposits_Withdrawals",
        "Change_in_Total_Assets", "Net_Income", "Return_on_Net_Income_Pct",
        "Row_Type", "Source_Page"
    ]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for r in res.annual_performance:
        if r.is_initial_row:
            row_type = "INITIAL"
        elif r.is_total_row:
            row_type = "TOTAL"
        elif re.match(r"^\d{2}\.\d{2}\.\d{4}$", r.period):
            row_type = "PERIODIC"
        else:
            row_type = "ANNUAL"
        row = [
            r.period,
            float(r.performance_pct) / 100.0 if r.performance_pct is not None else None,
            float(r.cumulative_performance_pct) / 100.0 if r.cumulative_performance_pct is not None else None,
            float(r.end_of_period_assets) if r.end_of_period_assets is not None else None,
            float(r.period_deposits_withdrawals) if r.period_deposits_withdrawals is not None else None,
            float(r.change_in_total_assets) if r.change_in_total_assets is not None else None,
            float(r.net_income) if r.net_income is not None else None,
            float(r.return_on_net_income_pct) / 100.0 if r.return_on_net_income_pct is not None else None,
            row_type,
            r.source_page
        ]
        safe_append(ws, row)
        r_idx = ws.max_row
        ws.cell(r_idx, 2).number_format = FMT_PERCENT
        ws.cell(r_idx, 3).number_format = FMT_PERCENT
        ws.cell(r_idx, 4).number_format = FMT_AMOUNT
        ws.cell(r_idx, 5).number_format = FMT_AMOUNT
        ws.cell(r_idx, 6).number_format = FMT_AMOUNT
        ws.cell(r_idx, 7).number_format = FMT_AMOUNT
        ws.cell(r_idx, 8).number_format = FMT_PERCENT
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = BOLD_DATA_FONT if (r.is_total_row or r.is_initial_row) else DATA_FONT
        if r.is_total_row:
            for c_idx in range(1, len(headers) + 1):
                ws.cell(r_idx, c_idx).fill = SUBTOTAL_FILL

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws)

def _build_comments_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Comments")
    headers = ["Section", "Source_Pages", "Content"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    comments = res.comments_disclosures
    rows = [
        ("General Information Disclaimer", ", ".join(str(p) for p in (comments.general_info_pages or comments.source_pages[:1])), comments.general_information),
        ("Product Risk Classification (PRC)", ", ".join(str(p) for p in (comments.prc_pages or comments.source_pages[1:2])), comments.product_risk_classification),
        ("Acknowledgement of Assets", ", ".join(str(p) for p in (comments.ack_pages or comments.source_pages[2:])), comments.acknowledgement_of_assets),
    ]
    for sec, pgs, content in rows:
        safe_append(ws, [sec, pgs, content])
        r_idx = ws.max_row
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT
            if c_idx == 3:
                ws.cell(r_idx, c_idx).alignment = ALIGN_LEFT_WRAP

    ws.freeze_panes = "A2"
    autofit_columns(ws, max_len_cap=80)

def _build_counts_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Counts")
    headers = ["Entity_Type", "Record_Count", "Description"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    counts = [
        ("Source PDF Pages", len(res.raw_pages), "Total pages processed in source statement"),
        ("Securities Holdings", len(res.holdings), "Itemized securities holding rows extracted"),
        ("Holdings with Price Dates", sum(1 for h in res.holdings if h.market_price_date), "Holdings with market price valuation dates"),
        ("Holdings with Price Markers", sum(1 for h in res.holdings if h.price_marker), "Holdings with market price markers (*, t)"),
        ("Holdings with ESG Ratings", sum(1 for h in res.holdings if h.previous_esg_rating or h.current_esg_rating), "Holdings with structured ESG ratings"),
        ("Current Accounts", len(res.current_accounts), "Cash and current account balances extracted"),
        ("Loans", len(res.loans), "Fixed loan and liabilities rows extracted"),
        ("Asset Allocation Categories", len(res.asset_allocation), "Top-level portfolio allocation items"),
        ("Currency Breakdown Rows", len(res.currency_breakdown), "Multi-currency distribution records"),
        ("Exchange Rates", len(res.exchange_rates), "Spot valuation rates applied in statement"),
        ("Monthly Performance Rows", len(res.monthly_performance), "Historical monthly return records"),
        ("Annual Performance Rows", len(res.annual_performance), "Historical yearly return records"),
        ("Unmapped Items", len(res.unmapped_content), "Rows preserved in unmapped audit table"),
        ("Validation Checks", len(res.validation_checks), "Total automated reconciliation rules executed"),
    ]
    for ent, cnt, desc in counts:
        safe_append(ws, [ent, cnt, desc])
        r_idx = ws.max_row
        ws.cell(r_idx, 2).number_format = FMT_INTEGER
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    autofit_columns(ws)

def _build_validation_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Validation")
    headers = ["Level", "Category", "Check_Name", "Message", "Details"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for c in res.validation_checks:
        safe_append(ws, [
            c.level,
            c.category,
            c.name,
            c.message,
            str(c.details) if c.details else ""
        ])
        r_idx = ws.max_row
        lvl_cell = ws.cell(r_idx, 1)
        if c.level == "PASS":
            lvl_cell.font = PASS_FONT
            lvl_cell.fill = PASS_FILL
        elif c.level == "WARNING":
            lvl_cell.font = WARNING_FONT
            lvl_cell.fill = WARN_FILL
        elif c.level == "FAIL":
            lvl_cell.font = FAIL_FONT
            lvl_cell.fill = FAIL_FILL

        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            if c_idx > 1:
                ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    autofit_columns(ws, max_len_cap=70)

def _build_unmapped_content_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Unmapped_Content")
    headers = ["Page_Number", "Bounding_Box", "Raw_Content", "Audit_Reason"]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    if not res.unmapped_content:
        safe_append(ws, ["N/A", "N/A", "No unmapped content. All source content classified and parsed.", "ZERO_LOSS_VERIFIED"])
        r_idx = ws.max_row
        for c_idx in range(1, len(headers) + 1):
            ws.cell(r_idx, c_idx).border = CELL_BORDER
            ws.cell(r_idx, c_idx).font = DATA_FONT
    else:
        for u in res.unmapped_content:
            safe_append(ws, [u.page_number, str(u.bbox), u.raw_text, u.reason])
            r_idx = ws.max_row
            for c_idx in range(1, len(headers) + 1):
                ws.cell(r_idx, c_idx).border = CELL_BORDER
                ws.cell(r_idx, c_idx).font = DATA_FONT

    ws.freeze_panes = "A2"
    autofit_columns(ws)

def _build_raw_page_text_sheet(wb, res: StatementExtractionResult):
    ws = wb.create_sheet("Raw_Page_Text")
    headers = [
        "Page_Number", "Section_Name", "Dimensions", "Rotation",
        "Page_Type", "OCR_Applied", "OCR_Confidence",
        "Line_Count", "Word_Count", "Full_Extracted_Text"
    ]
    safe_append(ws, headers)
    style_header_row(ws, 1, len(headers))

    for p in res.raw_pages:
        dim_str = f"{p.width} x {p.height}"
        ocr_conf_str = f"{p.ocr_confidence:.1f}%" if p.ocr_confidence is not None else "N/A"
        safe_append(ws, [
            p.page_number,
            p.section_name,
            dim_str,
            p.rotation,
            getattr(p, "page_type", "TEXT_BASED"),
            "YES" if getattr(p, "ocr_applied", False) else "NO",
            ocr_conf_str,
            p.line_count,
            p.word_count,
            p.text
        ])
        r_idx = ws.max_row
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(r_idx, c_idx)
            cell.border = CELL_BORDER
            cell.font = DATA_FONT
            if c_idx == len(headers):
                cell.alignment = ALIGN_LEFT_WRAP

    ws.freeze_panes = "A2"
    autofit_columns(ws, max_len_cap=80)
