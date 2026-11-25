# Parts Inventory for Home Assistant

A photo-first inventory web app for all your parts. It runs as a **Home Assistant add-on** on your
Raspberry Pi (HA OS) and shows up in the HA sidebar.

- 📸 **Snap to stock**: tap the camera, take a photo, and either create a new item or add stock to one you already have
- ✨ **AI identification (optional)**: Claude looks at the photo and fills in the name, description, category, part number and tags, and suggests matching items you already own
- 🔎 **Fast search**: SQLite full-text search across names, part numbers (`7805` finds `LM7805`), tags, notes, categories and locations
- 🔗 **Linked items**: part of / has part, compatible with, replacement for, accessory, requires, related
- 📍 **Nested locations**: Garage › Shelf A › Bin 3, with photos of each spot
- 🏷️ **QR labels**: print labels for items and bins, then scan them in the app to jump straight to that item
- ➕➖ **Quick stock steppers**, low-stock alerts, history and activity log
- 📱 **Feels native**: iOS-style UI, dark mode, swipe-to-dismiss sheets, haptics, installable PWA
- 💾 **SQLite in `/data`**, so it's included in Home Assistant backups. CSV import and export, plus a full JSON export

## Install on Home Assistant OS

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**.
2. Open the **⋮** menu → **Repositories**, add `https://github.com/dannyrwilson/Inventory` and close the dialog.
3. Find **Parts Inventory** in the store and click **Install**. The first build on a Pi takes a few minutes.
4. Turn on **Show in sidebar** and click **Start**.
5. Open **Inventory** from the sidebar. It also works in the Home Assistant Companion app on your phone, where the camera button opens the phone camera.

> The repository must be reachable by Home Assistant. If it's private, either make it public or
> copy the `parts_inventory` folder into `/addons/` on the Pi (Samba or SSH add-on) and install it
> from **Local add-ons**.

### Optional: AI photo identification

On the add-on's **Configuration** tab:

| Option | Description |
| --- | --- |
| `anthropic_api_key` | Your Anthropic API key (console.anthropic.com). Leave it empty to disable AI. |
| `ai_model` | Default: `claude-opus-5-5`. Use `claude-haiku-5-5` for cheaper and faster identification. |
| `password` | Only needed if you enable the direct port (below). |

Restart the add-on after changing options. Photos are only sent to Anthropic when AI is enabled.

### Optional: direct access (without the HA sidebar)

On the **Configuration** tab, under **Network**, set a host port for `8099/tcp`. **Set a `password`
first**, because direct access bypasses Home Assistant's login. Then open `http://<pi-ip>:<port>/`.
Access through the HA sidebar never asks for this password.

## Using it

- **Camera button** (centre of the tab bar): take a photo. If it contains one of your QR labels or a known
  barcode, you jump straight to that item with +/− buttons. Otherwise you can create a new item from the
  photo (with AI if configured) or add stock to an existing item. **Long-press** the camera button for the
  photo library, scan-only, or a new item with no photo.
- **Item page**: tap +/− to adjust stock. Tap the number to set an exact count. Use *Link* to connect related
  parts and *Label* to print a QR label. Long-press a linked item to unlink it.
- **Places**: build your location tree and add a photo of each shelf or bin. You can print labels for a
  location and for everything in it.
- **More**: categories, activity, inventory value, and CSV/JSON import and export.

## Development

```bash
pip install -r parts_inventory/requirements.txt
DATA_DIR=./devdata python parts_inventory/app/server.py   # http://localhost:8099
```

Stack: Python (Flask + Waitress), SQLite with FTS5, Pillow, and plain JavaScript (no build step).
QR decoding uses the browser's BarcodeDetector where available, with vendored jsQR as the fallback.
