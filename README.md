# Sales Order PDF Import

Portable Frappe/ERPNext v15 custom app that adds an **Import Purchase Order PDF**
button to Sales Order. The importer reads the customer PO, matches each PDF
description to an enabled Item, and fills Item Code, Quantity, UOM, and Rate.

## Install on the ERPNext server

```bash
cd /path/to/frappe-bench
bench get-app https://YOUR-GIT-URL/sales_order_pdf_import.git
bench --site your-site.example install-app sales_order_pdf_import
bench --site your-site.example migrate
bench build --app sales_order_pdf_import
bench restart
```

The server must have `pypdf` installed; Bench installs it from this app's
`pyproject.toml`. This sample PDF contains selectable text, so no OCR service is
required. Image-only PDFs are rejected with a clear message rather than silently
creating incorrect rows.

## Use

Open a new or draft Sales Order and choose **Import Purchase Order PDF**. Select
the PDF and confirm the preview. Only uniquely matched items are added. Unmatched
or ambiguous lines stay in the preview for manual resolution.

The supplied Tic and Terry/TBG sample layout is supported. Lines beginning with
`Line Dimensions` are intentionally ignored.

## Matching safety

Descriptions are normalized and compared with `Item.item_name` and the plain-text
version of `Item.description`. An exact normalized description wins. Fuzzy matches
must score at least 0.78 and must be at least 0.05 better than the runner-up.

## Tests

```bash
bench --site your-site.example run-tests --app sales_order_pdf_import
```
