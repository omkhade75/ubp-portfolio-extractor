import re
from typing import List, Tuple, Optional
from decimal import Decimal
import pymupdf

from app.models.schemas import PerformanceRow
from app.processing.number_parser import parse_financial_number
from app.extraction.word_extractor import extract_visual_words_and_lines, ExtractedWord

def _map_words_to_performance_columns(row_words: List[ExtractedWord]):
    """
    Deterministically maps words in a monthly or annual performance row to
    their standard 7 column positions:
      0: performance_pct (Period)
      1: cumulative_performance_pct (Global)
      2: end_of_period_assets
      3: period_deposits_withdrawals
      4: change_in_total_assets
      5: net_income
      6: return_on_net_income_pct
    Uses column x-coordinate anchors so that missing/blank columns (e.g. 0 deposits or blank net income)
    never shift downstream columns into the wrong fields.
    """
    fn_perf = None
    fn_cum = None
    fn_assets = None
    fn_dep = None
    fn_chg = None
    fn_ni = None
    fn_rni = None

    # If exactly 7 words and all parse cleanly with standard percentages at 0, 1, 6
    if len(row_words) == 7:
        t0 = parse_financial_number(row_words[0].text)
        t1 = parse_financial_number(row_words[1].text)
        t6 = parse_financial_number(row_words[6].text)
        if (t0.is_percentage or "%" in row_words[0].text) and (t1.is_percentage or "%" in row_words[1].text) and (t6.is_percentage or "%" in row_words[6].text):
            return (
                t0,
                t1,
                parse_financial_number(row_words[2].text),
                parse_financial_number(row_words[3].text),
                parse_financial_number(row_words[4].text),
                parse_financial_number(row_words[5].text),
                t6
            )

    # Coordinate-anchored column mapping
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
        elif x < 750 and fn_ni is None:
            fn_ni = fn
        elif x >= 750 and fn_rni is None:
            fn_rni = fn

    return fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni

def parse_monthly_performance_page(page: pymupdf.Page, page_num: int) -> Tuple[List[PerformanceRow], Optional[str]]:
    """
    Parses History of Monthly Performances table.
    Filters out chart labels below table.
    Returns (list_of_rows, chart_raw_text).
    """
    _, lines = extract_visual_words_and_lines(page)
    rows: List[PerformanceRow] = []
    chart_lines: List[str] = []

    table_started = False
    table_ended = False
    has_total_row = False

    for l in lines:
        t = l.text.strip()
        if "HISTORY OF MONTHLY PERFORMANCES" in t.upper():
            table_started = True
            continue

        if not table_started:
            continue

        # Header lines
        if "PERIOD PERFORMANCE" in t.upper() or "AND WITHDRAWALS" in t.upper():
            continue

        # When chart area or footnote is reached dynamically
        if (
            "CUMULATIVE PERFORMANCE" in t.upper()
            or "ACCOUNT ESTABLISHED" in t.upper()
            or t.startswith("(*)")
            or (has_total_row and (l.y > page.rect.height * 0.38 or re.match(r"^[\-\d\.\,\']+\s*%$", t)))
            or l.y > page.rect.height * 0.70
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

        # Check initial row: e.g. 01.07.2024 0.00% 2’205’057 or 31.10.2024 0.00% 1,045,000 0 0 0 0.00%
        if re.match(r"^\d{2}\.\d{2}\.\d{4}$", first_w):
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:])
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
                raw_text=l.text
            ))
            continue

        # Check monthly row: e.g. 07.2024 -0.33% -0.33% 2’197’796 0 7’261- 34’712 1.57%
        if re.match(r"^\d{2}\.\d{4}$", first_w):
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:])

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
                raw_text=l.text
            ))
            continue

        # Check total row: e.g. 78’128- 140’740 104’430 or TOTAL / CLOSING 130,000 25,000
        is_tot = "TOTAL" in t.upper() or "CLOSING" in t.upper()
        num_vals = [parse_financial_number(w.text) for w in words if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None]
        if (is_tot and len(num_vals) >= 2) or (len(num_vals) >= 2 and not re.search(r"\d{2}\.\d{4}", t) and not re.search(r"\d{2}\.\d{2}\.\d{4}", t)):
            has_total_row = True
            dep_val = None
            chg_val = None
            ni_val = None
            for w in words:
                fn = parse_financial_number(w.text)
                if not fn.is_valid or fn.value is None:
                    continue
                if w.x0 < 500 and dep_val is None:
                    dep_val = fn.value
                elif w.x0 < 640 and chg_val is None:
                    chg_val = fn.value
                elif w.x0 >= 640 and ni_val is None:
                    ni_val = fn.value
            rows.append(PerformanceRow(
                period="Total",
                period_deposits_withdrawals=dep_val,
                change_in_total_assets=chg_val,
                net_income=ni_val,
                is_total_row=True,
                row_type="TOTAL",
                source_page=page_num,
                raw_text=l.text
            ))
            continue

    chart_raw = "\n".join(chart_lines)
    return rows, chart_raw

def parse_annual_performance_page(page: pymupdf.Page, page_num: int) -> Tuple[List[PerformanceRow], Optional[str]]:
    """
    Parses History of Annual Performances table.
    Filters out chart labels below table.
    Returns (list_of_rows, chart_raw_text).
    """
    _, lines = extract_visual_words_and_lines(page)
    rows: List[PerformanceRow] = []
    chart_lines: List[str] = []

    table_started = False
    table_ended = False
    has_total_row = False

    for l in lines:
        t = l.text.strip()
        if "HISTORY OF ANNUAL PERFORMANCES" in t.upper() or "HISTORY OF YEARLY PERFORMANCES" in t.upper():
            table_started = True
            continue

        if not table_started:
            continue

        if "PERIOD PERFORMANCE" in t.upper() or "AND WITHDRAWALS" in t.upper():
            continue

        # When chart area or footnote is reached dynamically
        if (
            "PERFORMANCE PERFORMANCE" in t.upper()
            or "CUMULATIVE PERFORMANCE" in t.upper()
            or "ACCOUNT ESTABLISHED" in t.upper()
            or t.startswith("(*)")
            or (has_total_row and (l.y > page.rect.height * 0.38 or re.match(r"^[\-\d\.\,\']+\s*%$", t)))
            or l.y > page.rect.height * 0.70
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

        # Check initial row vs annual rows
        # Initial row is always the very first date row before annual years start (e.g. 20.12.2016 or 01.01.2020)
        has_initial = any(r.is_initial_row for r in rows)
        if re.match(r"^\d{2}\.\d{2}\.\d{4}$", first_w) and not has_initial:
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:])
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
                raw_text=l.text
            ))
            continue

        # Check annual row: e.g. 2016 or periodic final row like 30.06.2025 or 31.10.2025
        if re.match(r"^\d{4}$", first_w) or (re.match(r"^\d{2}\.\d{2}\.\d{4}$", first_w) and has_initial):
            fn_perf, fn_cum, fn_assets, fn_dep, fn_chg, fn_ni, fn_rni = _map_words_to_performance_columns(words[1:])

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
                raw_text=l.text
            ))
            continue

        # Check total row: e.g. 2’161’505 104’765 606’831 or TOTAL 805,000 145,000 22,150
        is_tot = "TOTAL" in t.upper() or "CLOSING" in t.upper()
        num_vals = [parse_financial_number(w.text) for w in words if parse_financial_number(w.text).is_valid and parse_financial_number(w.text).value is not None]
        if (is_tot and len(num_vals) >= 2) or (len(num_vals) >= 2 and not re.search(r"\d{2}\.\d{4}", t) and not re.search(r"\d{2}\.\d{2}\.\d{4}", t) and not re.match(r"^\d{4}$", first_w)):
            has_total_row = True
            dep_val = None
            chg_val = None
            ni_val = None
            for w in words:
                fn = parse_financial_number(w.text)
                if not fn.is_valid or fn.value is None:
                    continue
                if w.x0 < 500 and dep_val is None:
                    dep_val = fn.value
                elif w.x0 < 640 and chg_val is None:
                    chg_val = fn.value
                elif w.x0 >= 640 and ni_val is None:
                    ni_val = fn.value
            rows.append(PerformanceRow(
                period="Total",
                period_deposits_withdrawals=dep_val,
                change_in_total_assets=chg_val,
                net_income=ni_val,
                is_total_row=True,
                row_type="TOTAL",
                source_page=page_num,
                raw_text=l.text
            ))
            continue

    chart_raw = "\n".join(chart_lines)
    return rows, chart_raw
