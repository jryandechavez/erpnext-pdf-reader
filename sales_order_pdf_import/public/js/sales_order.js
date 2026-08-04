frappe.ui.form.on("Sales Order", {
  refresh(frm) {
    if (frm.doc.docstatus !== 0) return;

    frm.add_custom_button(__("Import Purchase Order PDF"), () => {
      new frappe.ui.FileUploader({
        doctype: frm.doctype,
        docname: frm.doc.name,
        restrictions: {
          allowed_file_types: [".pdf"],
          max_file_size: 10 * 1024 * 1024,
        },
        allow_multiple: false,
        on_success: async (file) => {
          const result = await frappe.call({
            method: "sales_order_pdf_import.api.parse_and_match_pdf",
            args: { file_url: file.file_url },
            freeze: true,
            freeze_message: __("Reading and matching PDF items..."),
          });
          show_import_preview(frm, result.message);
        },
      });
    }, __("Tools"));
  },
});

function show_import_preview(frm, data) {
  const rows = data.rows || [];
  const isImportable = (row) => ["matched", "matched_uom_fallback"].includes(row.status);
  const matched = rows.filter(isImportable);
  const body = rows.map((row) => {
    let status;
    if (row.status === "matched") {
      status = `<span class="indicator-pill green">${__("Matched")}</span>`;
    } else if (row.status === "matched_uom_fallback") {
      status = `<span class="indicator-pill yellow">${frappe.utils.escape_html(row.message)}</span>`;
    } else {
      status = `<span class="indicator-pill orange">${frappe.utils.escape_html(row.message || __("Unmatched"))}</span>`;
    }
    return `<tr>
      <td>${frappe.utils.escape_html(row.description)}</td>
      <td>${frappe.utils.escape_html(row.item_code || "-")}<br>
        <small>${frappe.utils.escape_html(row.item_name || "")}</small></td>
      <td class="text-right">${frappe.utils.escape_html(String(row.qty))}</td>
      <td>${frappe.utils.escape_html(row.uom)}</td>
      <td>${frappe.utils.escape_html(row.import_uom || "-")}</td>
      <td class="text-right">${format_currency(row.rate, frm.doc.currency)}</td>
      <td>${status}</td>
    </tr>`;
  }).join("");

  const dialog = new frappe.ui.Dialog({
    title: __("Purchase Order PDF Preview"),
    size: "extra-large",
    fields: [{
      fieldtype: "HTML",
      fieldname: "preview",
      options: `<p>${__("Order")}: <b>${frappe.utils.escape_html(data.order_no || __("Not found"))}</b></p>
        <div class="table-responsive"><table class="table table-bordered">
        <thead><tr><th>${__("PDF Description")}</th><th>${__("Item Match")}</th><th>${__("Qty")}</th><th>${__("PDF UOM")}</th><th>${__("UOM Used")}</th><th>${__("Rate")}</th><th>${__("Result")}</th></tr></thead>
        <tbody>${body}</tbody></table></div>`,
    }],
    primary_action_label: __("Add {0} Matched Items", [matched.length]),
    primary_action: async () => {
      if (!matched.length) return;
      for (const source of matched) {
        const row = frm.add_child("items");
        await frappe.model.set_value(row.doctype, row.name, "item_code", source.item_code);
        await frappe.model.set_value(row.doctype, row.name, {
          qty: source.qty,
          uom: source.import_uom,
          rate: source.rate,
        });
      }
      frm.refresh_field("items");
      dialog.hide();
      frappe.show_alert({ message: __(
        "Added {0} item(s). Review totals before saving.", [matched.length]
      ), indicator: "green" });
    },
  });
  if (!matched.length) dialog.get_primary_btn().prop("disabled", true);
  dialog.show();

  const downloadButton = $(
    `<button class="btn btn-default btn-sm">${__("Download Extracted CSV")}</button>`
  );
  downloadButton.on("click", () => downloadExtractedCsv(data));
  dialog.get_primary_btn().before(downloadButton);
}

function downloadExtractedCsv(data) {
  const headers = [
    "Source Code",
    "PDF Description",
    "Matched Item Code",
    "Matched Item Name",
    "Quantity",
    "PDF UOM",
    "UOM Used",
    "Rate",
    "Amount",
    "Status",
    "Result",
  ];
  const values = (data.rows || []).map((row) => [
    row.source_code,
    row.description,
    row.item_code,
    row.item_name,
    row.qty,
    row.uom,
    row.import_uom,
    row.rate,
    row.amount,
    row.status,
    row.message,
  ]);
  const escapeCsv = (value) => {
    const safeValue = typeof value === "string" && /^[=+\-@]/.test(value)
      ? `'${value}`
      : value;
    return `"${String(safeValue ?? "").replace(/"/g, '""')}"`;
  };
  const csv = `\uFEFF${[headers, ...values]
    .map((row) => row.map(escapeCsv).join(","))
    .join("\r\n")}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const orderNo = String(data.order_no || "purchase-order")
    .replace(/[^a-z0-9_-]+/gi, "-");
  const link = document.createElement("a");
  link.href = url;
  link.download = `${orderNo}-extracted-items.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
