"""Optional photo identification using OpenAI (default) or the Claude API."""
import base64
import io
import json
import logging

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
        "search_keywords": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["name", "description", "category", "manufacturer", "part_number",
                 "barcode", "quantity", "unit", "tags", "search_keywords", "confidence"],
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
- search_keywords: 3-8 words someone might use to search for this item, including synonyms.
- confidence: how sure you are about the identification."""


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
            text += "\nExisting categories: " + ", ".join(categories[:80])
        if hint:
            text += "\nUser hint: " + hint[:500]
        return text

    def identify(self, image_paths, categories=(), hint=""):
        images = [prepare_image(p) for p in image_paths[:4]]
        text = self._prompt(categories, hint)
        data = (self._identify_openai if self.provider == "openai" else self._identify_anthropic)(images, text)
        data["model"] = data.get("model") or self.model
        return data

    def _identify_openai(self, images, text):
        content = [{"type": "input_image", "image_url": f"data:image/jpeg;base64,{b}", "detail": "high"}
                   for b in images]
        content.append({"type": "input_text", "text": text})
        resp = self.client.responses.create(
            model=self.model,
            instructions=SYSTEM,
            input=[{"role": "user", "content": content}],
            text={"format": {"type": "json_schema", "name": "inventory_item",
                             "schema": SCHEMA, "strict": True}},
        )
        if getattr(resp, "status", "completed") == "incomplete":
            raise RuntimeError("The AI response was cut off; try again.")
        out = resp.output_text
        if not out:
            raise RuntimeError("The AI declined to identify this photo.")
        data = json.loads(out)
        data["model"] = resp.model
        return data

    def _identify_anthropic(self, images, text):
        import anthropic
        content = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b}}
                   for b in images]
        content.append({"type": "text", "text": text})
        kwargs = dict(
            model=self.model,
            max_tokens=16000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "low",
                           "format": {"type": "json_schema", "schema": SCHEMA}},
        )
        try:
            # Server-side refusal fallback: if the main model declines, the API
            # retries on a suitable fallback model within the same request.
            resp = self.client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        except anthropic.BadRequestError as e:
            log.info("Retrying without fallbacks: %s", e.message)
            resp = self.client.messages.create(**kwargs)
        if resp.stop_reason == "refusal":
            raise RuntimeError("The AI declined to identify this photo.")
        if resp.stop_reason == "max_tokens":
            raise RuntimeError("The AI response was cut off; try again.")
        data = json.loads(next((b.text for b in resp.content if b.type == "text"), ""))
        data["model"] = resp.model
        return data


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
