import frappe
from frappe import _
from frappe.model.document import Document

from sales_order_pdf_import.matcher import normalize


class SalesOrderPDFItemMapping(Document):
    def validate(self):
        self.normalized_description = normalize(self.pdf_description)
        if not self.normalized_description:
            frappe.throw(_("PDF Description is required."))
        if self.item and frappe.db.get_value("Item", self.item, "disabled"):
            frappe.throw(_("Item {0} is disabled.").format(self.item))
