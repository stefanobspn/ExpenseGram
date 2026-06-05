# tests/test_parser.py
from src.core.parser import parse_transaction, parse_amount


def test_parse_amount():
    assert parse_amount("15k") == 15000.0
    assert parse_amount("+3.5m") == 3500000.0
    assert parse_amount("50000") == 50000.0
    assert parse_amount("-100") == 100.0
    assert parse_amount("abc") is None
    assert parse_amount("") is None


def test_parse_expense_simple():
    res = parse_transaction("50000 cash food")
    assert res is not None
    assert res["amount"] == 50000.0
    assert res["type"] == "expense"
    assert res["account"] == "cash"
    assert res["category"] == "food"
    assert res["description"] == ""


def test_parse_expense_k_multiplier():
    res = parse_transaction("-15k bank food lunch out")
    assert res is not None
    assert res["amount"] == 15000.0
    assert res["type"] == "expense"
    assert res["account"] == "bank"
    assert res["category"] == "food"
    assert res["description"] == "lunch out"


def test_parse_income_m_multiplier():
    res = parse_transaction("+3.5m bank salary June pay check")
    assert res is not None
    assert res["amount"] == 3500000.0
    assert res["type"] == "income"
    assert res["account"] == "bank"
    assert res["category"] == "salary"
    assert res["description"] == "June pay check"


def test_parse_decimal_values():
    res = parse_transaction("2.5k visa transport bus")
    assert res is not None
    assert res["amount"] == 2500.0
    assert res["account"] == "visa"
    assert res["category"] == "transport"
    assert res["description"] == "bus"


def test_invalid_formats():
    assert parse_transaction("food lunch") is None
    assert parse_transaction("15k") is None
    assert parse_transaction("15k cash") is None  # Needs category too
    assert parse_transaction("+-15k cash food") is None
    assert parse_transaction("15xyz cash food") is None
    assert parse_transaction("") is None
