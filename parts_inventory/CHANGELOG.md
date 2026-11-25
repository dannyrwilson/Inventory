## 1.2.0
- Scan a whole picking/organizer box: AI reads every compartment label and adds each as an item
  with stock 1 (review list, rename, skip, or +1 items you already have; choose a location).

## 1.1.0
- AI photo identification now uses OpenAI by default (`openai_api_key`, model `gpt-5-mini`).
  Claude remains available with `ai_provider: anthropic`.

## 1.0.0
- Initial release: items, photos, nested locations, categories, linked items, full-text search,
  stock history, QR labels and scanning, CSV/JSON export, CSV import, optional AI photo identification.
