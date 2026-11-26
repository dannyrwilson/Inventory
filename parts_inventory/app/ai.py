"""Optional photo identification using OpenAI (default) or the Claude API."""
import base64
import io
import json
import logging
import time

from PIL import Image, ImageOps

log = logging.getLogger("inventory.ai")

SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Short, specific inventory name"},
        "description": {"type": "string"},
        "category": {"type": "string"},
        "manufacturer": {"type": "string"},
        "part_number": {"type": "string"},
        "barcode": {"type": "string"},
        "quantity": {"type": "number"},
        "unit": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "compatible_with": {"type": "array", "items": {"type": "string"}},
        "search_keywords": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["name", "description", "category", "manufacturer", "part_number",
                 "barcode", "quantity", "unit", "tags", "compatible_with", "search_keywords", "confidence"],
    "additionalProperties": False,
}

SYSTEM = """You identify physical parts, components, tools and supplies from photos for a \
personal workshop inventory system. Look carefully at markings, labels, packaging text, \
part numbers, logos and form factor.

Return:
- name: concise but specific (e.g. "M3 x 10mm socket head cap screw", "LM7805 5V linear regulator, TO-220").
- description: one or two sentences with useful specs (size, rating, material, thread, voltage).
- category: reuse one of the existing categories when it fits; otherwise propose a short new one.
- manufacturer, part_number, barcode: only what is actually visible or certain; empty string otherwise.
- quantity: how many of the item you can count in the photo (1 if unsure; count packs as 1 unless contents are visible).
- unit: "pcs" unless something else is clearly better (m, ft, g, ml, roll, box, pack).
- tags: 2-6 short lowercase tags.
- compatible_with: what this part works with, fits or is meant for: boards and platforms (ESP32,
  Arduino, Raspberry Pi), voltages / cell counts (3.3V logic, 5V, 2-4S LiPo), interfaces and
  protocols (I2C, SPI, UART, PWM, Zigbee), connectors and standards (XT60, JST-PH 2.0, M3 thread,
  1.75mm filament, 608 bearing), or specific devices / printers / drones. 2-8 short entries;
  empty list if nothing sensible applies.
- search_keywords: 3-8 words someone might use to search for this item, including synonyms.
- confidence: how sure you are about the identification."""


BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label_text": {"type": "string", "description": "Label text exactly as written"},
                    "position": {"type": "string", "description": "Where in the box, e.g. 'row 1, col 3'"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                    "manufacturer": {"type": "string"},
                    "part_number": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "compatible_with": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["label_text", "position", "name", "description", "category",
                             "manufacturer", "part_number", "tags", "compatible_with"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

BATCH_SYSTEM = """You read organizer / picking boxes for a personal workshop inventory. The photo \
shows a box, case or drawer with many compartments, each usually with its own label (printed, \
handwritten, or a sticker). Your job is to list EVERY labelled compartment.

Work systematically: go row by row, left to right, top to bottom, so nothing is missed or listed twice.
For each labelled compartment return:
- label_text: the label exactly as written (keep abbreviations like "M3x10 SHCS").
- position: its place in the box, e.g. "row 1, col 3".
- name: a clear, specific inventory name expanded from the label (e.g. "M3 x 10mm socket head cap screw").
  If the label is unreadable but the contents are obvious, name the contents and put "?" in label_text.
- description: short specs implied by the label or visible contents; empty string if nothing to add.
- category: reuse one of the existing categories when it fits; otherwise a short new one. Use one
  category for the whole box when the parts are all the same kind.
- manufacturer, part_number: only if written on the label; empty string otherwise.
- tags: 1-4 short lowercase tags.
- compatible_with: 0-5 short entries for what it fits / works with (e.g. "M3 thread", "XT60",
  "3.3V logic", "ESP32"), only when the label makes it clear; otherwise an empty list.
Skip empty, unlabelled compartments unless their contents are clearly identifiable."""


CATEGORY_SCHEMA = {
    "type": "object",
    "properties": {
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "category": {"type": "string"}},
                "required": ["id", "category"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["assignments"],
    "additionalProperties": False,
}

CATEGORY_SYSTEM = """You organise a personal workshop / electronics parts inventory.
The inventory uses a two-level category tree written as "Group › Sub-category".
Assign exactly one category to every item you are given, returning its id unchanged.

Rules:
- Pick the single most specific matching entry from the category list and copy it exactly,
  e.g. "Sensors › Temperature", "Fasteners & Fixings › Nuts", "Cables & Connectors › XT60 Connectors".
- Only if nothing fits, keep an existing group and add a short new sub-category in the same style
  ("Group › New Sub-category"). Never invent a new group when an existing one is close.
- Use the same category for the same kind of part every time."""

SHARED_CATEGORY_RULE = """
Category: choose the most specific entry from the category list, written exactly as \
"Group › Sub-category" (e.g. "Sensors › Temperature"). Only if nothing fits, use an existing \
group with a short new sub-category."""

SYSTEM += SHARED_CATEGORY_RULE
BATCH_SYSTEM += SHARED_CATEGORY_RULE


LIST_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_text": {"type": "string"},
                    "name": {"type": "string"},
                    "quantity": {"type": "number"},
                    "unit": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                    "manufacturer": {"type": "string"},
                    "part_number": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "compatible_with": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["source_text", "name", "quantity", "unit", "description", "category",
                             "manufacturer", "part_number", "tags", "compatible_with"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

LIST_SYSTEM = """You turn a person's parts list (typed notes, a pasted shopping or order list, \
or a photo of a handwritten / printed list or screenshot) into inventory items.

For every part mentioned return one item:
- source_text: the original line or fragment, as written.
- name: a clear, specific inventory name expanded from shorthand
  (e.g. "10x m3x10 shcs" -> "M3 x 10mm socket head cap screw", "esp32 wroom" -> "ESP32-WROOM-32 module").
- quantity: the count given (10x, x10, (10), "ten", "pack of 10" -> 10); 1 if none is given.
- unit: "pcs" unless the list says otherwise (m, ft, g, ml, roll, pack, box).
- description: short specs implied by the text; empty string if nothing to add.
- manufacturer, part_number: only if written; empty string otherwise.
- tags: 1-4 short lowercase tags.
- compatible_with: 0-5 short entries for what it fits / works with, only when clear.
Ignore headings, prices, shipping lines, order numbers, dates and anything that isn't a part.
Merge exact repeats of the same part into one item with the quantities added together."""
LIST_SYSTEM += SHARED_CATEGORY_RULE


def prepare_image(path, max_side=1568):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


DEFAULT_MODELS = {"openai": "gpt-5-mini", "anthropic": "claude-opus-5-5"}


class Identifier:
    def __init__(self, provider, api_key, model=""):
        self.provider = (provider or "openai").strip().lower()
        if self.provider not in DEFAULT_MODELS:
            self.provider = "openai"
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip() or DEFAULT_MODELS[self.provider]
        self._client = None
        self._reasoning_ok = True

    @property
    def enabled(self):
        return bool(self.api_key)

    @property
    def client(self):
        if self._client is None:
            if self.provider == "openai":
                import openai
                self._client = openai.OpenAI(api_key=self.api_key, timeout=120.0)
            else:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key, timeout=120.0)
        return self._client

    @staticmethod
    def _prompt(categories, hint):
        text = "Identify this item for my inventory."
        if categories:
            text += "\nCategory list:\n" + "\n".join(categories)
        if hint:
            text += "\nUser hint: " + hint[:500]
        return text

    def identify(self, image_paths, categories=(), hint=""):
        """Identify a single item (possibly from several angles)."""
        text = self._prompt(categories, hint)
        data, model = self._call(image_paths[:4], text, SYSTEM, SCHEMA, "inventory_item")
        data["model"] = model
        return data

    def identify_box(self, image_paths, categories=(), hint=""):
        """Read every labelled compartment in an organizer / picking box."""
        text = "List every labelled compartment in this box."
        if categories:
            text += "\nCategory list:\n" + "\n".join(categories)
        if hint:
            text += "\nUser hint: " + hint[:500]
        # bigger images so small labels stay legible
        data, model = self._call(image_paths[:3], text, BATCH_SYSTEM, BATCH_SCHEMA,
                                 "box_contents", max_side=2048, timeout=300.0)
        return data.get("items") or [], model

    def parse_list(self, text="", image_paths=(), categories=()):
        """Parts list (text and/or photos of a list) -> items."""
        prompt = "Turn this into inventory items."
        if categories:
            prompt += "\nCategory list:\n" + "\n".join(categories)
        if text.strip():
            prompt += "\n\nThe list:\n" + text.strip()
        data, model = self._call(list(image_paths)[:4], prompt, LIST_SYSTEM, LIST_SCHEMA, "parts_list",
                                 max_side=2048, timeout=240.0)
        return data.get("items") or [], model

    def categorize(self, items, categories=()):
        """Text-only: assign a category to each item. items: [{id, name, ...}]"""
        lines = []
        for it in items:
            extra = " | ".join(x for x in [it.get("description"), it.get("part_number"),
                                           it.get("manufacturer"), it.get("tags")] if x)
            lines.append(f'{it["id"]}: {it["name"]}' + (f" ({extra[:200]})" if extra else ""))
        text = ("Category list:\n" + ("\n".join(categories) if categories else "(none yet)") +
                "\n\nItems:\n" + "\n".join(lines))
        data, _ = self._call([], text, CATEGORY_SYSTEM, CATEGORY_SCHEMA, "categories", timeout=150.0)
        valid = {it["id"] for it in items}
        return {a["id"]: a["category"].strip() for a in data.get("assignments", [])
                if a.get("id") in valid and a.get("category", "").strip()}

    def _call(self, image_paths, text, system, schema, name, max_side=1568, timeout=120.0):
        if self.provider == "openai":
            return self._call_openai(image_paths, text, system, schema, name, max_side, timeout)
        return self._call_anthropic(image_paths, text, system, schema, min(max_side, 1568), timeout)

    def _call_openai(self, image_paths, text, system, schema, name, max_side, timeout):
        content = [{"type": "input_image", "detail": "high",
                    "image_url": "data:image/jpeg;base64," + prepare_image(p, max_side)}
                   for p in image_paths]
        content.append({"type": "input_text", "text": text})
        import openai
        kwargs = dict(
            model=self.model,
            instructions=system,
            input=[{"role": "user", "content": content}],
            text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
        )
        client = self.client.with_options(timeout=timeout)
        t0 = time.time()
        if self._reasoning_ok:
            try:
                # reading labels / sorting parts doesn't need deep thinking; low is several times faster
                resp = client.responses.create(reasoning={"effort": "low"}, **kwargs)
            except openai.BadRequestError as e:
                if "reasoning" not in str(e).lower():
                    raise
                self._reasoning_ok = False  # non-reasoning model (e.g. gpt-4.1)
                resp = client.responses.create(**kwargs)
        else:
            resp = client.responses.create(**kwargs)
        log.info("AI %s: %s in %.1fs (status %s)", name, resp.model, time.time() - t0, getattr(resp, "status", "?"))
        if getattr(resp, "status", "completed") == "incomplete":
            raise RuntimeError("The AI response was cut off; try again.")
        out = resp.output_text
        if not out:
            raise RuntimeError("The AI declined to identify this photo.")
        return json.loads(out), resp.model

    def _call_anthropic(self, image_paths, text, system, schema, max_side, timeout):
        import anthropic
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                                "data": prepare_image(p, max_side)}}
                   for p in image_paths]
        content.append({"type": "text", "text": text})
        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        )
        client = self.client.with_options(timeout=timeout)
        try:
            # Server-side refusal fallback: if the main model declines, the API
            # retries on a suitable fallback model within the same request.
            resp = client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        except anthropic.BadRequestError as e:
            log.info("Retrying without fallbacks: %s", e.message)
            resp = client.messages.create(**kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError("The AI declined to identify this photo.")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("The AI response was cut off; try again.")
        return json.loads(next((b.text for b in resp.content if b.type == "text"), "")), resp.model


def friendly_error(e):
    try:
        import openai
        if isinstance(e, openai.AuthenticationError):
            return "Invalid OpenAI API key (check the add-on configuration)."
        if isinstance(e, openai.PermissionDeniedError):
            return "OpenAI key lacks permission for this model."
        if isinstance(e, openai.NotFoundError):
            return "Model not found — check the ai_model option."
        if isinstance(e, openai.RateLimitError):
            return "Rate limited or out of OpenAI credit, try again shortly."
        if isinstance(e, openai.APIConnectionError):
            return "Could not reach OpenAI (network)."
        if isinstance(e, openai.APIStatusError):
            return f"OpenAI error ({e.status_code})."
    except ImportError:
        pass
    try:
        import anthropic
    except ImportError:
        return str(e)
    if isinstance(e, anthropic.AuthenticationError):
        return "Invalid Anthropic API key (check the add-on configuration)."
    if isinstance(e, anthropic.PermissionDeniedError):
        return "API key lacks permission for this model."
    if isinstance(e, anthropic.NotFoundError):
        return "Model not found — check the ai_model option."
    if isinstance(e, anthropic.RateLimitError):
        return "Rate limited by the AI service, try again shortly."
    if isinstance(e, anthropic.APIConnectionError):
        return "Could not reach the AI service (network)."
    if isinstance(e, anthropic.APIStatusError):
        return f"AI service error ({e.status_code})."
    return str(e)
