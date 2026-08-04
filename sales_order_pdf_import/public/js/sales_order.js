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
          if (result.message.order_no) {
            await frm.set_value("po_no", result.message.order_no);
          }
          show_import_preview(frm, result.message);
        },
      });
    }, __("Tools"));
  },
});

function isImportableRow(row) {
  return [
    "matched",
    "matched_uom_fallback",
    "matched_manual",
    "matched_manual_uom_fallback",
  ].includes(row.status);
}

function renderMatchStatus(row) {
  if (["matched", "matched_manual"].includes(row.status)) {
    const label = row.status === "matched_manual" ? __("Manually Matched") : __("Matched");
    return `<span class="indicator-pill green">${label}</span>`;
  }
  if (["matched_uom_fallback", "matched_manual_uom_fallback"].includes(row.status)) {
    return `<span class="indicator-pill yellow">${frappe.utils.escape_html(row.message)}</span>`;
  }
  return `<span class="indicator-pill orange">${frappe.utils.escape_html(
    row.message || __("Unmatched")
  )}</span>`;
}

function renderItemMatch(row, index) {
  const canMap = !["matched", "matched_uom_fallback"].includes(row.status);
  const button = canMap
    ? `<br><button type="button" class="btn btn-xs btn-default manual-item-map" data-row-index="${index}">${__(
      isImportableRow(row) ? "Change Item" : "Select Item"
    )}</button>`
    : "";
  return `${frappe.utils.escape_html(row.item_code || "-")}<br>
    <small>${frappe.utils.escape_html(row.item_name || "")}</small>${button}`;
}

function show_import_preview(frm, data) {
  const rows = data.rows || [];
  const body = rows.map((row, index) => {
    return `<tr data-row-index="${index}">
      <td class="text-right">${index + 1}</td>
      <td>${frappe.utils.escape_html(row.description)}</td>
      <td class="item-match">${renderItemMatch(row, index)}</td>
      <td class="text-right">${frappe.utils.escape_html(String(row.qty))}</td>
      <td>${frappe.utils.escape_html(row.uom)}</td>
      <td class="uom-used">${frappe.utils.escape_html(row.import_uom || "-")}</td>
      <td class="text-right">${format_currency(row.rate, frm.doc.currency)}</td>
      <td class="match-result">${renderMatchStatus(row)}</td>
    </tr>`;
  }).join("");

  const initialMatched = rows.filter(isImportableRow);
  const initialMismatched = rows.filter((row) => !isImportableRow(row));
  let mismatchButton;

  const dialog = new frappe.ui.Dialog({
    title: __("Purchase Order PDF Preview"),
    size: "extra-large",
    fields: [{
      fieldtype: "HTML",
      fieldname: "preview",
      options: `<p>${__("Order")}: <b>${frappe.utils.escape_html(data.order_no || __("Not found"))}</b></p>
        <p>${__("Extracted")}: <b>${rows.length}</b> &nbsp; ${__("Matched")}: <b class="matched-count">${initialMatched.length}</b> &nbsp; ${__("Mismatched")}: <b class="mismatched-count">${initialMismatched.length}</b></p>
        <div class="table-responsive"><table class="table table-bordered">
        <thead><tr><th>${__("No.")}</th><th>${__("PDF Description")}</th><th>${__("Item Match")}</th><th>${__("Qty")}</th><th>${__("PDF UOM")}</th><th>${__("UOM Used")}</th><th>${__("Rate")}</th><th>${__("Result")}</th></tr></thead>
        <tbody>${body}</tbody></table></div>`,
    }],
    primary_action_label: __("Add {0} Matched Items", [initialMatched.length]),
    primary_action: async () => {
      const matched = rows.filter(isImportableRow);
      if (!matched.length) return;
      const primaryButton = dialog.get_primary_btn();
      const actionButtons = dialog.$wrapper.find(".modal-footer button");
      const originalLabel = __("Add {0} Matched Items", [matched.length]);
      let added = 0;

      actionButtons.prop("disabled", true);
      frappe.show_progress(__("Adding Sales Order Items"), 0, matched.length);
      try {
        for (const [index, source] of matched.entries()) {
          primaryButton.text(__("Adding {0} of {1}...", [index + 1, matched.length]));
          const row = frm.add_child("items");
          await frappe.model.set_value(row.doctype, row.name, "item_code", source.item_code);
          await frappe.model.set_value(row.doctype, row.name, {
            qty: source.qty,
            uom: source.import_uom,
            rate: source.rate,
          });
          added = index + 1;
          frappe.show_progress(
            __("Adding Sales Order Items"),
            added,
            matched.length,
            __("Added {0} of {1}", [added, matched.length])
          );
        }
        frm.refresh_field("items");
        dialog.hide();
        frappe.show_alert({ message: __(
          "Added {0} item(s). Review totals before saving.", [matched.length]
        ), indicator: "green" }, 7);
      } catch (error) {
        frm.refresh_field("items");
        frappe.msgprint({
          title: __("Item Import Stopped"),
          indicator: "red",
          message: __(
            "Added {0} of {1} items before an error occurred: {2}",
            [
              added,
              matched.length,
              frappe.utils.escape_html(error.message || String(error)),
            ]
          ),
        });
      } finally {
        frappe.hide_progress();
        if (dialog.display) {
          actionButtons.prop("disabled", false);
          const mismatchedCount = rows.filter((row) => !isImportableRow(row)).length;
          mismatchButton.prop("disabled", !mismatchedCount);
          primaryButton.text(originalLabel);
        }
      }
    },
  });
  if (!initialMatched.length) dialog.get_primary_btn().prop("disabled", true);
  dialog.show();

  const downloadButton = $(
    `<button class="btn btn-default btn-sm">${__("Download Extracted CSV")}</button>`
  );
  downloadButton.on("click", () => downloadExtractedCsv(data, false));
  dialog.get_primary_btn().before(downloadButton);

  mismatchButton = $(
    `<button class="btn btn-default btn-sm">${__(
      "Download Mismatched Items ({0})",
      [initialMismatched.length]
    )}</button>`
  );
  mismatchButton.on("click", () => downloadExtractedCsv(data, true));
  mismatchButton.prop("disabled", !initialMismatched.length);
  dialog.get_primary_btn().before(mismatchButton);

  const refreshCounts = () => {
    const matchedCount = rows.filter(isImportableRow).length;
    const mismatchedCount = rows.length - matchedCount;
    dialog.$wrapper.find(".matched-count").text(matchedCount);
    dialog.$wrapper.find(".mismatched-count").text(mismatchedCount);
    dialog.get_primary_btn()
      .text(__("Add {0} Matched Items", [matchedCount]))
      .prop("disabled", !matchedCount);
    mismatchButton
      .text(__("Download Mismatched Items ({0})", [mismatchedCount]))
      .prop("disabled", !mismatchedCount);
  };

  dialog.$wrapper.on("click", ".manual-item-map", function () {
    const index = Number($(this).attr("data-row-index"));
    const row = rows[index];
    frappe.prompt(
      [{
        fieldname: "item_code",
        fieldtype: "Link",
        label: __("ERPNext Item"),
        options: "Item",
        default: row.item_code || "",
        reqd: 1,
        get_query: () => ({ filters: { disabled: 0 } }),
      }],
      async (values) => {
        const response = await frappe.call({
          method: "sales_order_pdf_import.api.get_manual_item_match",
          args: { item_code: values.item_code, pdf_uom: row.uom },
          freeze: true,
          freeze_message: __("Validating selected Item..."),
        });
        Object.assign(row, response.message);
        const tableRow = dialog.$wrapper.find(`tr[data-row-index="${index}"]`);
        tableRow.find(".item-match").html(renderItemMatch(row, index));
        tableRow.find(".uom-used").text(row.import_uom || "-");
        tableRow.find(".match-result").html(renderMatchStatus(row));
        refreshCounts();
        frappe.show_alert({
          message: __("Row {0} mapped to Item {1}.", [index + 1, row.item_code]),
          indicator: "green",
        });
      },
      __("Map PDF Row {0} to an Item", [index + 1]),
      __("Map Item")
    );
  });
}

function downloadExtractedCsv(data, mismatchedOnly) {
  const headers = [
    "No.",
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
  const values = (data.rows || [])
    .map((row, index) => ({ row, number: index + 1 }))
    .filter(({ row }) => !mismatchedOnly || !isImportableRow(row))
    .map(({ row, number }) => [
      number,
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
  const fileType = mismatchedOnly ? "mismatched-items" : "extracted-items";
  const link = document.createElement("a");
  link.href = url;
  link.download = `${orderNo}-${fileType}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
