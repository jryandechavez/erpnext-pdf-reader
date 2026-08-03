from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

ITEM_START = re.compile(r"^(A\d{8})\s+(.+)$", re.IGNORECASE)
ROW_VALUES = re.compile(
    r"^(?P<description>.*?)\s+(?P<qty>\d+(?:\.\d+)?)\s+"
    r"(?P<uom>[A-Za-z][A-Za-z0-9]*)\s+(?P<rate>[\d,]+(?:\.\d+)?)"
    r"(?:\s+.*)?\s+(?P<amount>[\d,]+(?:\.\d+)?)$"
)


def _number(value: str) -> float:
    try:
        return float(Decimal(value.replace(",", "")))
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid number: {value}")


def parse_purchase_order(text: str) -> dict:
    """Parse the observed TBG purchase-order text layout.

    Wrapped description lines are accumulated until ``Line Dimensions`` or the
    next product number. Values always come from the product's first line.
    """
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    order_match = re.search(r"Order No\.\s+(\S+)", text, re.IGNORECASE)
    rows = []
    current = None

    def finish():
        nonlocal current
        if current:
            current["description"] = " ".join(current.pop("description_parts")).strip()
            rows.append(current)
            current = None

    for line in lines:
        if not line:
            continue
        if line.lower().startswith("line dimensions"):
            finish()
            continue
        start = ITEM_START.match(line)
        if start:
            finish()
            source_code, remainder = start.groups()
            values = ROW_VALUES.match(remainder)
            if not values:
                continue
            current = {
                "source_code": source_code.upper(),
                "description_parts": [values.group("description")],
                "qty": _number(values.group("qty")),
                "uom": values.group("uom").upper(),
                "rate": _number(values.group("rate")),
                "amount": _number(values.group("amount")),
            }
            continue
        if current and not re.match(r"^(Total|Ship-to|Header Dimensions)", line, re.I):
            current["description_parts"].append(line)
    finish()
    return {"order_no": order_match.group(1) if order_match else None, "rows": rows}
