from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

ITEM_START = re.compile(r"^(A\d{8})\s+(.+)$", re.IGNORECASE)
DESCRIPTION_END = re.compile(
    r"^(?:Total\s+PHP|Ship-to Address|Header Dimensions|"
    r"Acknowledgement Certificate No\.:|"
    r"THIS DOCUMENT IS NOT VALID FOR CLAIM OF INPUT TAX)",
    re.IGNORECASE,
)
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

    Wrapped description lines are accumulated until ``Line Dimensions``, the
    next product number, or a totals/address/footer boundary. Values always come
    from the product's first line.
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
        if DESCRIPTION_END.match(line):
            finish()
            break
        if line.lower().startswith("line dimensions"):
            finish()
            continue
        start = ITEM_START.match(line)
        if start:
            finish()
            _, remainder = start.groups()
            values = ROW_VALUES.match(remainder)
            if not values:
                continue
            current = {
                "description_parts": [values.group("description")],
                "qty": _number(values.group("qty")),
                "uom": values.group("uom").upper(),
                "rate": _number(values.group("rate")),
                "amount": _number(values.group("amount")),
            }
            continue
        if current:
            current["description_parts"].append(line)
    finish()
    return {"order_no": order_match.group(1) if order_match else None, "rows": rows}
