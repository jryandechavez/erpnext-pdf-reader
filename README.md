# Sales Order PDF Import

Portable Frappe/ERPNext v15 custom app that adds an **Import Purchase Order PDF**
button to Sales Order. The importer reads the customer PO, matches each PDF
description to an enabled Item, and fills Item Code, Quantity, UOM, and Rate.

## Install on the ERPNext server

Run these commands as the Linux user that owns the Bench. `--skip-assets` lets
Bench register the app before Frappe tries to resolve its asset path; build the
assets explicitly after installation.

```bash
cd /path/to/frappe-bench
bench --site your-site.example backup --with-files
bench get-app --skip-assets --branch main sales_order_pdf_import \
  https://github.com/jryandechavez/erpnext-pdf-reader.git
bench --site your-site.example install-app sales_order_pdf_import
bench --site your-site.example migrate
bench build --app sales_order_pdf_import
bench --site your-site.example clear-cache
bench restart
bench --site your-site.example list-apps
```

### Recover from an interrupted `get-app`

If the repository and Python package were installed but the asset build stopped
before the app was registered, do not download it again. Add the app to
`sites/apps.txt`, ensuring it starts on a new line:

```bash
cd /path/to/frappe-bench
printf '\n' >> sites/apps.txt
grep -qxF sales_order_pdf_import sites/apps.txt || \
  printf '%s\n' sales_order_pdf_import >> sites/apps.txt
bench build --app sales_order_pdf_import
bench --site your-site.example install-app sales_order_pdf_import
bench --site your-site.example migrate
bench --site your-site.example clear-cache
bench restart
```

If a previous manual append produced `hrmssales_order_pdf_import`, repair it
before continuing:

```bash
sed -i 's/^hrmssales_order_pdf_import$/hrms\nsales_order_pdf_import/' sites/apps.txt
```

The server must have `pypdf` installed; Bench installs it from this app's
`pyproject.toml`. This sample PDF contains selectable text, so no OCR service is
required. Image-only PDFs are rejected with a clear message rather than silently
creating incorrect rows.

## Use

Open a new or draft Sales Order and choose **Import Purchase Order PDF**. Select
the PDF and confirm the preview. Only uniquely matched items are added. Unmatched
or ambiguous lines stay in the preview for manual resolution. As soon as the PDF
is parsed successfully, its Order No. overwrites the Sales Order `po_no` field,
including when that field already has a value or the preview is later closed.

The preview shows sequential row numbers and extracted, matched, and mismatched
counts. Choose **Download Extracted CSV** to download every row, or **Download
Mismatched Items** to download only unmatched rows that will not be inserted. Both
CSV files include quantity, PDF UOM, UOM used, rate, amount, status, and message.
While matched rows are being inserted, all dialog actions are disabled, the main
button displays `Adding X of Y...`, and a progress indicator reports each completed
Sales Order line. Completion and partial-failure messages remain visible.

The supplied Tic and Terry/TBG sample layout is supported. Lines beginning with
`Line Dimensions` are intentionally ignored.
`Ship-to Address`, totals, header dimensions, acknowledgement certificate details,
and the input-tax disclaimer are hard description boundaries and are never included
in an Item description. On multi-page PDFs, repeated page footers are skipped and
parsing resumes with the Item table on the next page.

## Matching safety

PDF descriptions are normalized and compared with `Item.item_name`, the plain-text
version of `Item.description`, `Item.item_code`, and the Item document `name`. The
PDF `No.` column is used only to detect row boundaries and is not imported or
included in the CSV. An exact normalized description wins. Fuzzy matches must score
at least 0.78; the highest-scoring enabled Item is selected deterministically.
Exact-match priority follows `item_name`, `description`, `item_code`, then `name`.
Exact enabled matches are queried before the fuzzy-search candidate limit, so broad
description words cannot hide an exact Item Code or document name.
Description and UOM matching are case-insensitive, so values such as `kg`, `Kg`,
and `KG` resolve to the same configured UOM.

The preview displays the matched Item, PDF UOM, UOM used by ERPNext, and match
result. If an Item matches but its PDF UOM has no configured conversion, the line
remains importable using the Item's stock UOM. The PDF quantity and rate are kept,
and the preview shows a warning so the user can review the units and pricing.

## Tests

```bash
bench --site your-site.example run-tests --app sales_order_pdf_import
```
