from __future__ import annotations

import re
from difflib import SequenceMatcher

import frappe
from frappe.utils import strip_html

MATCH_THRESHOLD = 0.78
AMBIGUITY_GAP = 0.05


def normalize(value: str) -> str:
    value = strip_html(value or "").casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def match_item(description: str) -> dict:
    normalized = normalize(description)
    terms = [term for term in normalized.split() if len(term) >= 4][:4]
    if not terms:
        return {
            "status": "unmatched",
            "item_code": None,
            "message": "No confident Item match",
        }

    # LOWER makes candidate retrieval case-insensitive even if the database uses
    # a case-sensitive collation. Final similarity scoring is also normalized.
    clauses = []
    values = {}
    for index, term in enumerate(terms):
        key = f"term_{index}"
        clauses.append(
            f"(LOWER(item_name) LIKE %({key})s OR LOWER(description) LIKE %({key})s)"
        )
        values[key] = f"%{term}%"
    candidates = frappe.db.sql(
        f"""
        SELECT name, item_name, description, stock_uom
        FROM `tabItem`
        WHERE disabled = 0 AND ({" OR ".join(clauses)})
        LIMIT 100
        """,
        values,
        as_dict=True,
    )
    scored = []
    for item in candidates:
        item_values = [normalize(item.item_name), normalize(item.description)]
        score = max(
            SequenceMatcher(None, normalized, value).ratio()
            for value in item_values
            if value
        )
        scored.append((score, item))
    scored.sort(key=lambda value: value[0], reverse=True)

    if not scored or scored[0][0] < MATCH_THRESHOLD:
        return {
            "status": "unmatched",
            "item_code": None,
            "message": "No confident Item match",
        }
    if len(scored) > 1 and scored[0][0] - scored[1][0] < AMBIGUITY_GAP:
        return {
            "status": "ambiguous",
            "item_code": None,
            "message": "Multiple similar Items found",
        }
    best_score, best = scored[0]
    return {
        "status": "matched",
        "item_code": best.name,
        "item_name": best.item_name,
        "stock_uom": best.stock_uom,
        "match_score": round(best_score, 3),
        "message": "Matched",
    }
