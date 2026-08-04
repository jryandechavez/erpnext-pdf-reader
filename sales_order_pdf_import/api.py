from __future__ import annotations

from io import BytesIO

import frappe
from frappe import _
from pypdf import PdfReader

from sales_order_pdf_import.parser import parse_purchase_order
from sales_order_pdf_import.matcher import match_item


@frappe.whitelist()
def parse_and_match_pdf(file_url: str) -> dict:
    """Read an uploaded File and return a non-mutating import preview."""
    if not file_url or not file_url.lower().split("?")[0].endswith(".pdf"):
        frappe.throw(_("Please upload a PDF file."))

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    if not file_doc.has_permission("read"):
        frappe.throw(_("You do not have permission to read this file."), frappe.PermissionError)
    if (file_doc.file_size or 0) > 10 * 1024 * 1024:
        frappe.throw(_("The PDF must be 10 MB or smaller."))

    content = file_doc.get_content()
    try:
        reader = PdfReader(BytesIO(content))
        if len(reader.pages) > 20:
            frappe.throw(_("The PDF must have 20 pages or fewer."))
        # Layout mode preserves table columns. Plain pypdf extraction emits each
        # cell separately and loses the relationship between qty/UOM/rate.
        # Form-feed preserves page boundaries so the parser can skip a repeated
        # footer and continue with the Item table on the following page.
        text = "\f".join(
            page.extract_text(
                extraction_mode="layout", layout_mode_space_vertically=False
            )
            or ""
            for page in reader.pages
        )
    except frappe.ValidationError:
        raise
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Sales Order PDF extraction failed")
        frappe.throw(_("The PDF could not be read. It may be damaged or encrypted."))

    if len(text.strip()) < 50:
        frappe.throw(_("This PDF has no readable text. Run OCR on the PDF and upload it again."))

    parsed = parse_purchase_order(text)
    if not parsed["rows"]:
        frappe.throw(_("No item rows were found in this PDF layout."))

    for row in parsed["rows"]:
        row.update(match_item(row["description"]))
        if row["status"] == "matched":
            canonical_uom = _resolve_uom(row["uom"])
            row["import_uom"] = canonical_uom or row["uom"]
            if not canonical_uom or not _item_supports_uom(
                row["item_code"], row["stock_uom"], canonical_uom
            ):
                # A valid Item match is still useful. Import with its stock UOM
                # so ERPNext does not reject the Sales Order for a missing UOM
                # conversion, and make the fallback explicit in the preview.
                row.update(
                    status="matched_uom_fallback",
                    import_uom=row["stock_uom"],
                    message=_(
                        "Matched; no conversion for {0}. Using stock UOM {1}"
                    ).format(row["uom"], row["stock_uom"]),
                )
    return parsed


def _resolve_uom(pdf_uom: str) -> str | None:
    """Return the canonical ERPNext UOM name without case sensitivity."""
    wanted = (pdf_uom or "").strip().casefold()
    return next(
        (
            uom
            for uom in frappe.get_all("UOM", pluck="name")
            if uom.strip().casefold() == wanted
        ),
        None,
    )


def _item_supports_uom(item_code: str, stock_uom: str, pdf_uom: str) -> bool:
    if stock_uom.strip().casefold() == pdf_uom.strip().casefold():
        return True
    return bool(
        frappe.db.exists(
            "UOM Conversion Detail", {"parent": item_code, "uom": pdf_uom}
        )
    )
