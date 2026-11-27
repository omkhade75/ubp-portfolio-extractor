import re
from typing import List, Tuple, Optional, Dict, Any
from decimal import Decimal
import pymupdf

from app.models.schemas import PerformanceRow
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines, VisualLine, ExtractedWord
from app.extraction.table_header_engine import (
    PERFORMANCE_SYNONYMS,
    TableColumnMap,
    build_table_column_map,
    assign_words_to_columns,
)


def _is_performance_header_line(tu: str) -> bool:
    return (
        ("PERIOD" in tu and ("PERFORMANCE" in tu or "ASSETS" in tu or "DEPOSITS" in tu))
        or ("END-OF-PER" in tu)
        or ("(GLOBAL)" in tu)
        or ("WITHDRAWALS" in tu)
        or (tu.strip() in ("ASSETS WITHDRAWALS ASSETS", "ASSETS AND WITHDRAWALS", "WITHDRAWALS ASSETS", "ASSETS"))
        or ("DEPOSITS" in tu and "CHANGE" in tu)
    )


def _map_words_to_performance_columns(
    row_words: List[ExtractedWord],
    col_map: Optional[TableColumnMap] = None,
) -> Tuple[Any, Any, Any, Any, Any, Any, Any]:
    """
    Deterministically maps words in a monthly or annual performance row to the
    standard 7 column positions using dynamically reconstructed header boundaries
    with fallback to coordinate anchors if header detection was incomplete.
    """
    fn_perf = fn_cum = fn_assets = fn_dep = fn_chg = fn_ni = fn_rni = None

    if col_map and len(col_map.ordered_columns) >= 5:
        assigned, _ = assign_words_to_columns(row_words, col_map)

        def _first_num(key: str) -> Any:
            for w in assigned.get(key, []):
                fn = parse_financial_number(w.text)
                if fn.is_valid and fn.value is not None:
                    return fn
            return None

        fn_perf = _first_num("PERFORMANCE_PCT")
        fn_cum = _first_num("CUMULATIVE_PCT")
        fn_assets = _first_num("END_OF_PERIOD_ASSETS")
        fn_dep = _first_num("DEPOSITS_WITHDRAWALS")
        fn_chg = _first_num("CHANGE_IN_ASSETS")
        fn_ni = _first_num("NET_INCOME")
        fn_rni = _first_num("RETURN_ON_NI_PCT")
        return fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni

    # Exact 7-token row positional fallback
    if len(row_words) == 7:
        t0 = parse_financial_number(row_words[0].text)
        t1 = parse_financial_number(row_words[1].text)
        t6 = parse_financial_number(row_words[6].text)
        if (
            (t0.is_percentage or "%" in row_words[0].text)
            and (t1.is_percentage or "%" in row_words[1].text)
            and (t6.is_percentage or "%" in row_words[6].text)
        ):
            return (
                t0,
                t1,
                parse_financial_number(row_words[2].text),
                parse_financial_number(row_words[3].text),
                parse_financial_number(row_words[4].text),
                parse_financial_number(row_words[5].text),
                t6,
            )

    for w in row_words:
        fn = parse_financial_number(w.text)
        if not fn.is_valid or fn.value is None:
            continue
        x = w.x0
        if x < 205 and fn_perf is None and (fn.is_percentage or "%" in w.text):
            fn_perf = fn
        elif x < 275 and fn_cum is None and (fn.is_percentage or "%" in w.text):
            fn_cum = fn
        elif x < 375 and fn_assets is None:
            fn_assets = fn
        elif x < 475 and fn_dep is None:
            fn_dep = fn
        elif x < 620 and fn_chg is None:
            fn_chg = fn
        elif x < 745 and fn_ni is None:
            fn_ni = fn
        elif x >= 745 and fn_rni is None:
            fn_rni = fn

    return fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni


def _map_total_row(
    num_words: List[ExtractedWord],
    col_map: Optional[TableColumnMap],
) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[Decimal]]:
    """Maps summary TOTAL row tokens (deposits/withdrawals, change in assets, net income) by header interval."""
    dep_val: Optional[Decimal] = None
    chg_val: Optional[Decimal] = None
    ni_val: Optional[Decimal] = None

    if col_map and len(col_map.ordered_columns) >= 5:
        assigned, _ = assign_words_to_columns(num_words, col_map)
        for w in assigned.get("DEPOSITS_WITHDRAWALS", []):
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None and dep_val is None:
                dep_val = fn.value
        for w in assigned.get("CHANGE_IN_ASSETS", []):
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None and chg_val is None:
                chg_val = fn.value
        for w in assigned.get("NET_INCOME", []):
            fn = parse_financial_number(w.text)
            if fn.is_valid and fn.value is not None and ni_val is None:
                ni_val = fn.value
        if dep_val is not None or chg_val is not None or ni_val is not None:
            return dep_val, chg_val, ni_val

    for w in num_words:
        fn = parse_financial_number(w.text)
        if not fn.is_valid or fn.value is None:
            continue
        if w.x0 < 500 and dep_val is None:
            dep_val = fn.value
        elif w.x0 < 640 and chg_val is None:
            chg_val = fn.value
        elif w.x0 >= 640 and ni_val is None:
            ni_val = fn.value
    return dep_val, chg_val, ni_val


def parse_monthly_performance_page(
    page: pymupdf.Page, page_num: int
) -> Tuple[List[PerformanceRow], Optional[str]]:
    """
    Header-driven parser for History of Monthly Performances table.
    Filters out chart labels and disclosure footnotes below table.
    Returns (list_of_rows, chart_raw_text).
    """
    _, lines = extract_visual_words_and_lines(page)
    rows: List[PerformanceRow] = []
    chart_lines: List[str] = []

    pw = page.rect.width
    table_started = False
    table_ended = False
    has_total_row = False
    header_lines: List[VisualLine] = []
    col_map: Optional[TableColumnMap] = None

    for l in lines:
        t = l.text.strip()
        tu = t.upper()
        if "HISTORY OF MONTHLY PERFORMANCES" in tu:
            table_started = True
            continue

        if not table_started:
            continue

        # Header lines (single or multi-line stacked headers before first data row)
        if not rows and _is_performance_header_line(tu):
            header_lines.append(l)
            col_map = build_table_column_map(header_lines, PERFORMANCE_SYNONYMS, "PERFORMANCE", pw)
            continue

        # Chart area or footnotes
        if (
            "CUMULATIVE PERFORMANCE" in tu
            or "ACCOUNT ESTABLISHED" in tu
            or "SUMMARY RECORDS" in tu
            or "MUST NOT BE DOUBLE-COUNTED" in tu
            or "HISTORICAL PERFORMANCE" in tu
            or t.startswith("(*)")
            or (has_total_row and (l.y > page.rect.height * 0.45 or re.match(r"^[\-\d\.\,\']+\s*%$", t)))
            or l.y > page.rect.height * 0.72
        ):
            table_ended = True
            chart_lines.append(t)
            continue

        if table_ended:
            chart_lines.append(t)
            continue

        words = l.words
        if not words:
            continue

        first_w = words[0].text.strip()

        # Initial row: e.g. 01.07.2024 0.00% 1'050'000
        if re.match(r"^\d{2}\.\d{2}\.\d{4}$", first_w):
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:], col_map)
            rows.append(PerformanceRow(
                period=first_w,
                performance_pct=fn_perf.value if fn_perf and fn_perf.is_valid else None,
                cumulative_performance_pct=fn_cum.value if fn_cum and fn_cum.is_valid else Decimal("0.00"),
                end_of_period_assets=fn_assets.value if fn_assets and fn_assets.is_valid else None,
                period_deposits_withdrawals=fn_dep.value if fn_dep and fn_dep.is_valid else None,
                change_in_total_assets=fn_chg.value if fn_chg and fn_chg.is_valid else None,
                net_income=fn_ni.value if fn_ni and fn_ni.is_valid else None,
                return_on_net_income_pct=fn_rni.value if fn_rni and fn_rni.is_valid else None,
                is_initial_row=True,
                row_type="INITIAL",
                source_page=page_num,
                raw_text=l.text,
            ))
            continue

        # Monthly row: e.g. 07.2024 ...
        if re.match(r"^\d{2}\.\d{4}$", first_w):
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:], col_map)
            rows.append(PerformanceRow(
                period=first_w,
                performance_pct=fn_perf.value if fn_perf and fn_perf.is_valid else None,
                cumulative_performance_pct=fn_cum.value if fn_cum and fn_cum.is_valid else None,
                end_of_period_assets=fn_assets.value if fn_assets and fn_assets.is_valid else None,
                period_deposits_withdrawals=fn_dep.value if fn_dep and fn_dep.is_valid else None,
                change_in_total_assets=fn_chg.value if fn_chg and fn_chg.is_valid else None,
                net_income=fn_ni.value if fn_ni and fn_ni.is_valid else None,
                return_on_net_income_pct=fn_rni.value if fn_rni and fn_rni.is_valid else None,
                row_type="MONTHLY",
                source_page=page_num,
                raw_text=l.text,
            ))
            continue

        # Total row: e.g. 78'128- 140'740 104'430 or TOTAL MONTHLY RECORDS 15'000 30'000
        is_tot = "TOTAL" in tu or "CLOSING" in tu
        num_words = [
            w for w in words
            if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
        ]
        if (is_tot and len(num_words) >= 2) or (
            len(num_words) >= 2 and not re.search(r"\d{2}\.\d{4}", t) and not re.search(r"\d{2}\.\d{2}\.\d{4}", t)
        ):
            has_total_row = True
            dep_val, chg_val, ni_val = _map_total_row(num_words, col_map)
            rows.append(PerformanceRow(
                period="Total",
                period_deposits_withdrawals=dep_val,
                change_in_total_assets=chg_val,
                net_income=ni_val,
                is_total_row=True,
                row_type="TOTAL",
                source_page=page_num,
                raw_text=l.text,
            ))
            continue

    chart_raw = "\n".join(chart_lines)
    return rows, chart_raw


def parse_annual_performance_page(
    page: pymupdf.Page, page_num: int
) -> Tuple[List[PerformanceRow], Optional[str]]:
    """
    Header-driven parser for History of Annual Performances table.
    Filters out chart labels and disclosure footnotes below table.
    Returns (list_of_rows, chart_raw_text).
    """
    _, lines = extract_visual_words_and_lines(page)
    rows: List[PerformanceRow] = []
    chart_lines: List[str] = []

    pw = page.rect.width
    table_started = False
    table_ended = False
    has_total_row = False
    header_lines: List[VisualLine] = []
    col_map: Optional[TableColumnMap] = None

    for l in lines:
        t = l.text.strip()
        tu = t.upper()
        if "HISTORY OF ANNUAL PERFORMANCES" in tu or "HISTORY OF YEARLY PERFORMANCES" in tu:
            table_started = True
            continue

        if not table_started:
            continue

        if not rows and _is_performance_header_line(tu):
            header_lines.append(l)
            col_map = build_table_column_map(header_lines, PERFORMANCE_SYNONYMS, "PERFORMANCE", pw)
            continue

        if (
            "PERFORMANCE PERFORMANCE" in tu
            or "CUMULATIVE PERFORMANCE" in tu
            or "ACCOUNT ESTABLISHED" in tu
            or "HISTORICAL PERFORMANCE" in tu
            or t.startswith("(*)")
            or (has_total_row and (l.y > page.rect.height * 0.45 or re.match(r"^[\-\d\.\,\']+\s*%$", t)))
            or l.y > page.rect.height * 0.72
        ):
            table_ended = True
            chart_lines.append(t)
            continue

        if table_ended:
            chart_lines.append(t)
            continue

        words = l.words
        if not words:
            continue

        first_w = words[0].text.strip()
        has_initial = any(r.is_initial_row for r in rows)

        if re.match(r"^\d{2}\.\d{2}\.\d{4}$", first_w) and not has_initial:
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:], col_map)
            rows.append(PerformanceRow(
                period=first_w,
                performance_pct=fn_perf.value if fn_perf and fn_perf.is_valid else None,
                cumulative_performance_pct=fn_cum.value if fn_cum and fn_cum.is_valid else Decimal("0.00"),
                end_of_period_assets=fn_assets.value if fn_assets and fn_assets.is_valid else None,
                period_deposits_withdrawals=fn_dep.value if fn_dep and fn_dep.is_valid else None,
                change_in_total_assets=fn_chg.value if fn_chg and fn_chg.is_valid else None,
                net_income=fn_ni.value if fn_ni and fn_ni.is_valid else None,
                return_on_net_income_pct=fn_rni.value if fn_rni and fn_rni.is_valid else None,
                is_initial_row=True,
                row_type="INITIAL",
                source_page=page_num,
                raw_text=l.text,
            ))
            continue

        if re.match(r"^\d{4}$", first_w) or (re.match(r"^\d{2}\.\d{2}\.\d{4}$", first_w) and has_initial):
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:], col_map)
            rows.append(PerformanceRow(
                period=first_w,
                performance_pct=fn_perf.value if fn_perf and fn_perf.is_valid else None,
                cumulative_performance_pct=fn_cum.value if fn_cum and fn_cum.is_valid else None,
                end_of_period_assets=fn_assets.value if fn_assets and fn_assets.is_valid else None,
                period_deposits_withdrawals=fn_dep.value if fn_dep and fn_dep.is_valid else None,
                change_in_total_assets=fn_chg.value if fn_chg and fn_chg.is_valid else None,
                net_income=fn_ni.value if fn_ni and fn_ni.is_valid else None,
                return_on_net_income_pct=fn_rni.value if fn_rni and fn_rni.is_valid else None,
                row_type="ANNUAL",
                source_page=page_num,
                raw_text=l.text,
            ))
            continue

        is_tot = "TOTAL" in tu or "CLOSING" in tu
        num_words = [
            w for w in words
            if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None
        ]
        if (
            (is_tot and len(num_words) >= 2 and "REPORTING CURRENCY" not in tu and not tu.startswith("PERIOD:"))
            or (
                len(num_words) >= 2
                and not re.search(r"\d{2}\.\d{4}", t)
                and not re.search(r"\d{2}\.\d{2}\.\d{4}", t)
                and not re.match(r"^\d{4}$", first_w)
                and "REPORTING CURRENCY" not in tu
                and not tu.startswith("PERIOD:")
            )
        ):
            has_total_row = True
            dep_val, chg_val, ni_val = _map_total_row(num_words, col_map)
            rows.append(PerformanceRow(
                period="Total",
                period_deposits_withdrawals=dep_val,
                change_in_total_assets=chg_val,
                net_income=ni_val,
                is_total_row=True,
                row_type="TOTAL",
                source_page=page_num,
                raw_text=l.text,
            ))
            continue

    chart_raw = "\n".join(chart_lines)
    return rows, chart_raw
