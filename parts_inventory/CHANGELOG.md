## 1.6.0
- NIIMBOT D11 / D11_H label printing from the Pi over Bluetooth (ported from Distill Log; verified
  against its recorded protocol transcripts). Label length + firmware settings, live preview, test print.
- Labels: long names wrap onto two lines; part number or category on the second line; QR code to scan.
- Bigger photo previews while scanning, tap any preview to view full screen and zoom.

## 1.5.0
- Scan multiple photos at once: pick many photos (one part each), AI identifies them in parallel,
  review the list and add them all (stock 1 each, existing items get +1 instead of duplicates).

## 1.4.0
- Duplicate protection: adding an item you already have offers to add stock to it instead.
  Box scans and CSV imports stock existing items rather than creating copies.
- Existing duplicates (same name in any word order, part number or barcode) are hidden from the
  item list and shown in a Duplicates tab with one-tap merge or "Not duplicates".

## 1.3.0
- Built-in two-level category tree (26 groups / 326 sub-categories), pre-loaded on first start.
- Auto-categorize: items saved without a category are sorted in the background; bulk review screen.
- New "Works with" field: AI lists compatibility (boards, voltages, interfaces, connectors) and the
  item page suggests owned parts to link as compatible.

## 1.2.0
- Scan a whole picking/organizer box: AI reads every compartment label and adds each as an item
  with stock 1 (review list, rename, skip, or +1 items you already have; choose a location).

## 1.1.0
- AI photo identification now uses OpenAI by default (`openai_api_key`, model `gpt-5-mini`).
  Claude remains available with `ai_provider: anthropic`.

## 1.0.0
- Initial release: items, photos, nested locations, categories, linked items, full-text search,
  stock history, QR labels and scanning, CSV/JSON export, CSV import, optional AI photo identification.
