# src/core/parser.py
import re
from typing import Optional, Dict, Any

# Regex to match the amount token: e.g., -15k, +3.5m, 50000, 1.2K
AMOUNT_PATTERN = re.compile(r"^([+-]?)(\d+(?:\.\d+)?)([kmKM]?)$")


def parse_amount(token: str) -> Optional[float]:
    """
    Parses a single amount token like '15k', '+3.5m', '50000' or '-100'
    and returns its positive float value.
    """
    token = token.strip()
    match = AMOUNT_PATTERN.match(token)
    if not match:
        return None

    sign, val_str, multiplier = match.groups()
    try:
        val = float(val_str)
    except ValueError:
        return None

    multiplier = multiplier.lower()
    if multiplier == "k":
        val *= 1_000
    elif multiplier == "m":
        val *= 1_000_000

    return val


def parse_transaction(text: str) -> Optional[Dict[str, Any]]:
    """
    Parses a transaction shorthand string.
    Format: [sign][amount][multiplier] [account] [category] [description...]

    Examples:
    - "-15k cash food lunch" -> {
        'amount': 15000.0,
        'type': 'expense',
        'account': 'cash',
        'category': 'food',
        'description': 'lunch'
      }
    - "50000 bank transport taxi" -> {
        'amount': 50000.0,
        'type': 'expense',
        'account': 'bank',
        'category': 'transport',
        'description': 'taxi'
      }
    """
    text = text.strip()
    if not text:
        return None

    tokens = text.split()
    if len(tokens) < 3:
        return None  # Shorthand requires at least amount, account, and category

    amount_token = tokens[0]
    account_token = tokens[1].lower()
    category_token = tokens[2].lower()
    description = " ".join(tokens[3:]) if len(tokens) > 3 else ""

    match = AMOUNT_PATTERN.match(amount_token)
    if not match:
        return None

    sign, val_str, multiplier = match.groups()

    tx_type = "income" if sign == "+" else "expense"

    try:
        val = float(val_str)
    except ValueError:
        return None

    multiplier = multiplier.lower()
    if multiplier == "k":
        val *= 1_000
    elif multiplier == "m":
        val *= 1_000_000

    return {
        "amount": val,
        "type": tx_type,
        "account": account_token,
        "category": category_token,
        "description": description,
    }
