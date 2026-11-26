import pytest
from decimal import Decimal
from app.processing.number_parser import parse_financial_number, clean_financial_string, format_financial_decimal, SourceValueState

def test_apostrophe_numbers():
    fn = parse_financial_number("2’267’669.27")
    assert fn.is_valid
    assert fn.value == Decimal("2267669.27")
    assert not fn.is_negative

    fn2 = parse_financial_number("2'267'669.27")
    assert fn2.is_valid
    assert fn2.value == Decimal("2267669.27")

def test_trailing_minus():
    fn = parse_financial_number("64’470.32-")
    assert fn.is_valid
    assert fn.value == Decimal("-64470.32")
    assert fn.is_negative

    fn2 = parse_financial_number("2’364.96-")
    assert fn2.is_valid
    assert fn2.value == Decimal("-2364.96")
    assert fn2.is_negative

def test_percentages_and_asterisks():
    fn = parse_financial_number("20.90%")
    assert fn.is_valid
    assert fn.value == Decimal("20.90")
    assert fn.is_percentage

    fn_neg = parse_financial_number("-0.33%")
    assert fn_neg.is_valid
    assert fn_neg.value == Decimal("-0.33")
    assert fn_neg.is_negative
    assert fn_neg.is_percentage

    fn_ast = parse_financial_number("1’227.62*")
    assert fn_ast.is_valid
    assert fn_ast.value == Decimal("1227.62")
    assert fn_ast.has_asterisk

def test_zero_and_dash():
    fn = parse_financial_number("0.00")
    assert fn.is_valid
    assert fn.value == Decimal("0.00")
    assert fn.state == SourceValueState.EXPLICIT_ZERO

    fn_dash = parse_financial_number("-")
    assert fn_dash.is_valid
    assert fn_dash.value is None
    assert fn_dash.is_dash
    assert fn_dash.state == SourceValueState.SOURCE_DASH

    fn_blank = parse_financial_number("")
    assert fn_blank.is_valid
    assert fn_blank.value is None
    assert fn_blank.state == SourceValueState.SOURCE_BLANK

def test_currency_prefix():
    fn = parse_financial_number("USD 247’821.91")
    assert fn.is_valid
    assert fn.value == Decimal("247821.91")
    assert fn.currency == "USD"

def test_invalid_string():
    fn = parse_financial_number("NOT_A_NUMBER", allow_blank=False)
    assert not fn.is_valid
    assert fn.value is None
    assert fn.error is not None
