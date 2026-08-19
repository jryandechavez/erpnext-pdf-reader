from __future__ import annotations

import re
from difflib import SequenceMatcher

import frappe
from frappe.utils import strip_html

MATCH_THRESHOLD = 0.78


def normalize(value: str) -> str:
    value = strip_html(value or "").casefold()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = " ".join(value.split())
    # Treat compact and spaced number-unit forms as equivalent: 5kg == 5 kg,
    # 30pcs == 30 pcs, and 4-5kg == 4-5 kg after punctuation normalization.
    return re.sub(r"(?<=\d)\s+(?=[a-z])", "", value)


def match_item(description: str) -> dict:
    normalized = normalize(description)
    terms = [term for term in normalized.split() if len(term) >= 2][:4]
    if not terms:
        return {
            "status": "unmatched",
            "item_code": None,
            "message": "No confident Item match",
        }

    remembered = frappe.db.sql(
        """
        SELECT item.name, item.item_code, item.item_name, item.description,
               item.stock_uom
        FROM `tabSales Order PDF Item Mapping` mapping
        INNER JOIN `tabItem` item ON item.name = mapping.item
        WHERE mapping.disabled = 0
          AND item.disabled = 0
          AND mapping.normalized_description = %(description)s
        LIMIT 1
        """,
        {"description": normalized},
        as_dict=True,
    )
    if remembered:
        result = _match_result(remembered[0], 1.0)
        result.update(status="matched_remembered", message="Remembered match")
        return result

    # Run exact case-insensitive matching before the limited fuzzy candidate
    # query. This prevents a broad word such as "vegetable" from filling the
    # candidate limit and hiding an exact Item Code or document name.
    exact_text = strip_html(description or "").strip().casefold()
    exact_matches = frappe.db.sql(
        """
        SELECT name, item_code, item_name, description, stock_uom
        FROM `tabItem`
        WHERE disabled = 0 AND (
            LOWER(TRIM(item_name)) = %(exact)s
            OR LOWER(TRIM(description)) = %(exact)s
            OR LOWER(TRIM(item_code)) = %(exact)s
            OR LOWER(TRIM(name)) = %(exact)s
        )
        ORDER BY CASE
            WHEN LOWER(TRIM(item_name)) = %(exact)s THEN 1
            WHEN LOWER(TRIM(description)) = %(exact)s THEN 2
            WHEN LOWER(TRIM(item_code)) = %(exact)s THEN 3
            WHEN LOWER(TRIM(name)) = %(exact)s THEN 4
            ELSE 5
        END, name ASC
        LIMIT 1
        """,
        {"exact": exact_text},
        as_dict=True,
    )
    if exact_matches:
        return _match_result(exact_matches[0], 1.0)

    # LOWER makes candidate retrieval case-insensitive even if the database uses
    # a case-sensitive collation. Final similarity scoring is also normalized.
    clauses = []
    values = {}
    for index, term in enumerate(terms):
        key = f"term_{index}"
        clauses.append(
            f"(LOWER(item_name) LIKE %({key})s "
            f"OR LOWER(description) LIKE %({key})s "
            f"OR LOWER(item_code) LIKE %({key})s "
            f"OR LOWER(name) LIKE %({key})s)"
        )
        values[key] = f"%{term}%"
    relevance = " + ".join(
        f"(CASE WHEN {clause} THEN 1 ELSE 0 END)" for clause in clauses
    )
    candidates = frappe.db.sql(
        f"""
        SELECT name, item_code, item_name, description, stock_uom
        FROM `tabItem`
        WHERE disabled = 0 AND ({" OR ".join(clauses)})
        ORDER BY ({relevance}) DESC, name ASC
        LIMIT 100
        """,
        values,
        as_dict=True,
    )
    scored = []
    for item in candidates:
        # This is the requested exact-match priority. Any exact normalized match
        # wins over all fuzzy matches; duplicate exact matches resolve by Item
        # name because the query order is deterministic.
        item_values = [
            normalize(item.item_name),
            normalize(item.description),
            normalize(item.item_code),
            normalize(item.name),
        ]
        exact_priority = next(
            (
                index
                for index, value in enumerate(item_values)
                if value and value == normalized
            ),
            len(item_values),
        )
        score = max(
            SequenceMatcher(None, normalized, value).ratio()
            for value in item_values
            if value
        )
        scored.append((exact_priority, score, item))
    scored.sort(
        key=lambda value: (
            value[0] == 4,
            value[0],
            -value[1],
            normalize(value[2].name),
        )
    )

    if not scored or (scored[0][0] == 4 and scored[0][1] < MATCH_THRESHOLD):
        return {
            "status": "unmatched",
            "item_code": None,
            "message": "No confident Item match",
        }
    _, best_score, best = scored[0]
    return _match_result(best, best_score)


def _match_result(item, score: float) -> dict:
    return {
        "status": "matched",
        "item_code": item.item_code or item.name,
        "item_name": item.item_name,
        "stock_uom": item.stock_uom,
        "match_score": round(score, 3),
        "message": "Matched",
    }
