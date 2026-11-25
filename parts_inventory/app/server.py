"""Parts Inventory — Home Assistant add-on web server."""
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import sys
import threading
import time
import uuid

from flask import Flask, Response, abort, jsonify, request, send_from_directory
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import DB, RELATIONS, ITEM_FIELDS, now  # noqa: E402
import ai  # noqa: E402
import taxonomy  # noqa: E402
import dupes  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("inventory")

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE, "..", "..", "devdata"))
PHOTO_DIR = os.path.join(DATA_DIR, "photos")
THUMB_DIR = os.path.join(DATA_DIR, "thumbs")
for d in (DATA_DIR, PHOTO_DIR, THUMB_DIR):
    os.makedirs(d, exist_ok=True)


def load_options():
    opts = {}
    p = os.path.join(DATA_DIR, "options.json")
    if os.path.exists(p):
        try:
            with open(p) as f:
                opts = json.load(f)
        except Exception as e:  # pragma: no cover
            log.warning("Could not read options.json: %s", e)
    opts.setdefault("ai_provider", os.environ.get("AI_PROVIDER", "openai"))
    opts.setdefault("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))
    opts.setdefault("anthropic_api_key", os.environ.get("ANTHROPIC_API_KEY", ""))
    opts.setdefault("ai_model", os.environ.get("AI_MODEL", ""))
    opts.setdefault("auto_categorize", True)
    opts.setdefault("password", os.environ.get("INVENTORY_PASSWORD", ""))
    return opts


OPTS = load_options()
db = DB(os.path.join(DATA_DIR, "inventory.db"))
_provider = (OPTS.get("ai_provider") or "openai").lower()
dup = dupes.Dupes(db)
identifier = ai.Identifier(
    _provider,
    OPTS.get("anthropic_api_key") if _provider == "anthropic" else OPTS.get("openai_api_key"),
    OPTS.get("ai_model"))

secret_path = os.path.join(DATA_DIR, ".secret")
if not os.path.exists(secret_path):
    with open(secret_path, "w") as f:
        f.write(secrets.token_hex(32))
with open(secret_path) as f:
    SECRET = f.read().strip()

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 80 * 1024 * 1024
STATIC = os.path.join(BASE, "static")
INGRESS_IP = "172.30.32.2"


# ------------------------------------------------------------------ helpers
def err(msg, code=400):
    return jsonify({"error": msg}), code


def body():
    return request.get_json(silent=True) or {}


def auth_token():
    pw = OPTS.get("password") or ""
    return hmac.new(SECRET.encode(), pw.encode(), hashlib.sha256).hexdigest()


@app.before_request
def check_auth():
    if not OPTS.get("password"):
        return None
    if request.remote_addr == INGRESS_IP:
        return None  # Home Assistant ingress already authenticated the user
    if request.path in ("/login", "/manifest.webmanifest") or request.path.startswith("/icons/"):
        return None
    if hmac.compare_digest(request.cookies.get("inv_auth", ""), auth_token()):
        return None
    if request.path.startswith("/api/"):
        return err("Unauthorized", 401)
    return send_from_directory(STATIC, "login.html")


@app.post("/login")
def login():
    pw = request.form.get("password", "") or body().get("password", "")
    if not hmac.compare_digest(pw, OPTS.get("password") or ""):
        time.sleep(1)
        return Response("", 302, {"Location": "./?bad=1"})
    resp = Response("", 302, {"Location": "./"})
    resp.set_cookie("inv_auth", auth_token(), max_age=60 * 60 * 24 * 365, httponly=True, samesite="Lax")
    return resp


def save_image(file_storage):
    """Normalize an uploaded image (orientation, size) and make a thumbnail."""
    im = Image.open(file_storage.stream)
    im = ImageOps.exif_transpose(im)
    if im.mode not in ("RGB", "L"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        try:
            bg.paste(im, mask=im.convert("RGBA").split()[-1])
        except Exception:
            bg.paste(im.convert("RGB"))
        im = bg
    im.thumbnail((2400, 2400))
    name = uuid.uuid4().hex + ".jpg"
    im.save(os.path.join(PHOTO_DIR, name), "JPEG", quality=86, optimize=True)
    th = im.copy()
    th.thumbnail((480, 480))
    th.save(os.path.join(THUMB_DIR, name), "JPEG", quality=80, optimize=True)
    return name, im.width, im.height


def store_uploads(item_id=None, location_id=None):
    files = request.files.getlist("photo") or request.files.getlist("photos")
    if not files:
        abort(400, "No photo uploaded")
    out = []
    for f in files:
        try:
            name, w, h = save_image(f)
        except Exception as e:
            log.warning("Bad image upload: %s", e)
            continue
        with db.tx() as c:
            cur = c.execute("INSERT INTO photos(item_id, location_id, filename, width, height, created_at) "
                            "VALUES (?,?,?,?,?,?)", (item_id, location_id, name, w, h, now()))
            out.append({"id": cur.lastrowid, "filename": name})
    if not out:
        abort(400, "Could not read image")
    return out


def remove_files(names):
    for n in set(names):
        # a file can be shared (e.g. one box photo attached to many items)
        if db.one("SELECT 1 FROM photos WHERE filename=? LIMIT 1", (n,)):
            continue
        for d in (PHOTO_DIR, THUMB_DIR):
            try:
                os.remove(os.path.join(d, n))
            except FileNotFoundError:
                pass


def cleanup_orphans():
    cutoff = now() - 86400
    rows = db.q("SELECT id, filename FROM photos WHERE item_id IS NULL AND location_id IS NULL "
                "AND created_at<?", (cutoff,))
    if rows:
        with db.tx() as c:
            c.executemany("DELETE FROM photos WHERE id=?", [(r["id"],) for r in rows])
        remove_files(r["filename"] for r in rows)
        log.info("Removed %d orphan uploads", len(rows))


def split_category(path):
    return [p.strip() for p in str(path or "").replace("›", ">").replace("/", ">").split(">") if p.strip()][:2]


def get_or_create_category(path):
    """Accepts 'Parent › Child', 'Parent > Child' or a single name."""
    parts = split_category(path)
    if not parts:
        return None
    if len(parts) == 1:
        name = parts[0]
        # an existing sub-category with this name wins, then a top-level one
        r = db.one("SELECT id FROM categories WHERE name=? AND parent_id IS NOT NULL ORDER BY id", (name,)) or \
            db.one("SELECT id FROM categories WHERE name=? AND parent_id IS NULL", (name,))
        if r:
            return r["id"]
        with db.tx() as c:
            return c.execute("INSERT INTO categories(name, created_at) VALUES (?,?)", (name, now())).lastrowid
    parent, child = parts
    pr = db.one("SELECT id FROM categories WHERE name=? AND parent_id IS NULL", (parent,))
    if pr:
        pid = pr["id"]
    else:
        with db.tx() as c:
            pid = c.execute("INSERT INTO categories(name, created_at) VALUES (?,?)", (parent, now())).lastrowid
    r = db.one("SELECT id FROM categories WHERE name=? AND parent_id=?", (child, pid))
    if r:
        return r["id"]
    with db.tx() as c:
        return c.execute("INSERT INTO categories(name, parent_id, created_at) VALUES (?,?,?)",
                         (child, pid, now())).lastrowid


def category_paths():
    """Every assignable category as 'Parent › Child' (or 'Parent' when it has no children)."""
    rows = db.q("""SELECT c.name, p.name AS parent,
                     (SELECT COUNT(*) FROM categories k WHERE k.parent_id=c.id) AS kids
                   FROM categories c LEFT JOIN categories p ON p.id=c.parent_id
                   ORDER BY COALESCE(p.name, c.name), c.parent_id IS NOT NULL, c.name""")
    return [f'{r["parent"]} › {r["name"]}' if r["parent"] else r["name"] for r in rows
            if r["parent"] or not r["kids"]]


def category_item_ids(cid):
    return [r["id"] for r in db.q("SELECT id FROM items WHERE category_id IN "
                                  "(SELECT id FROM categories WHERE id=? OR parent_id=?)", (cid, cid))]


def get_or_create_location_path(path):
    parts = [p.strip() for p in str(path or "").replace("›", ">").replace("/", ">").split(">") if p.strip()]
    parent = None
    for p in parts:
        r = db.one("SELECT id FROM locations WHERE name=? COLLATE NOCASE AND parent_id IS ?", (p, parent))
        if r:
            parent = r["id"]
        else:
            with db.tx() as c:
                parent = c.execute("INSERT INTO locations(name, parent_id, created_at) VALUES (?,?,?)",
                                   (p, parent, now())).lastrowid
    return parent


# ------------------------------------------------------ default categories


def add_default_categories():
    """Add any missing groups / sub-categories from the built-in tree."""
    added = 0
    for parent, color, children in taxonomy.TREE:
        pr = db.one("SELECT id, color FROM categories WHERE name=? AND parent_id IS NULL", (parent,))
        with db.tx() as c:
            if pr:
                pid = pr["id"]
                if not pr["color"]:
                    c.execute("UPDATE categories SET color=? WHERE id=?", (color, pid))
            else:
                pid = c.execute("INSERT INTO categories(name, color, created_at) VALUES (?,?,?)",
                                (parent, color, now())).lastrowid
                added += 1
            for child in children:
                if not c.execute("SELECT 1 FROM categories WHERE name=? AND parent_id=?", (child, pid)).fetchone():
                    c.execute("INSERT INTO categories(name, parent_id, created_at) VALUES (?,?,?)",
                              (child, pid, now()))
                    added += 1
    return added


# first run only: deleting them later won't bring them back
if not db.one("SELECT value FROM meta WHERE key='seeded_taxonomy'"):
    add_default_categories()
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('seeded_taxonomy', '1')")


# ------------------------------------------------------- auto-categorize
def categorize_items(ids):
    """Ask the AI for categories for the given item ids. Returns {id: category_name}."""
    out = {}
    cats = category_paths()
    for i in range(0, len(ids), 80):
        chunk = ids[i:i + 80]
        rows = db.q("SELECT id, name, description, part_number, manufacturer, tags FROM items "
                    "WHERE id IN (%s)" % ",".join("?" * len(chunk)), chunk)
        got = identifier.categorize(rows, cats)
        out.update(got)
        cats = sorted(set(cats) | set(got.values()), key=str.lower)  # keep later chunks consistent
    return out


def apply_categories(assignments):
    n = 0
    for item_id, name in assignments.items():
        cid = get_or_create_category(name)
        if cid:
            with db.tx() as c:
                c.execute("UPDATE items SET category_id=? WHERE id=?", (cid, int(item_id)))
            db.reindex(int(item_id))
            n += 1
    return n


class AutoCategorizer:
    """Background worker: items saved without a category get one a few seconds later."""

    def __init__(self):
        self.wake = threading.Event()
        self.tried = set()  # don't retry items the AI already couldn't place
        threading.Thread(target=self.run, daemon=True).start()

    def poke(self):
        if identifier.enabled and OPTS.get("auto_categorize", True):
            self.wake.set()

    def run(self):
        while True:
            self.wake.wait()
            time.sleep(4)  # let bursts (imports, box scans) settle into one request
            self.wake.clear()
            try:
                ids = [r["id"] for r in db.q("SELECT id FROM items WHERE category_id IS NULL "
                                             "ORDER BY id DESC LIMIT 200") if r["id"] not in self.tried]
                if not ids:
                    continue
                self.tried.update(ids)
                n = apply_categories(categorize_items(ids))
                log.info("Auto-categorized %d item(s)", n)
            except Exception as e:
                log.warning("Auto-categorize failed: %s", ai.friendly_error(e))


auto_cat = AutoCategorizer()


@app.after_request
def poke_categorizer(resp):
    if request.method in ("POST", "PUT", "PATCH") and resp.status_code < 300 and \
            (request.path.startswith("/api/items") or request.path == "/api/import.csv"):
        auto_cat.poke()
    return resp


# ------------------------------------------------------------------ static
@app.get("/")
def index():
    resp = send_from_directory(STATIC, "index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/static/<path:p>")
def static_files(p):
    resp = send_from_directory(STATIC, p)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/sw.js")
def sw():
    resp = send_from_directory(STATIC, "sw.js")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(STATIC, "manifest.webmanifest", mimetype="application/manifest+json")


@app.get("/icons/<path:p>")
def icons(p):
    return send_from_directory(os.path.join(STATIC, "icons"), p, max_age=86400 * 30)


@app.get("/photos/<name>")
def photo(name):
    return send_from_directory(PHOTO_DIR, name, max_age=86400 * 365)


@app.get("/thumbs/<name>")
def thumb(name):
    return send_from_directory(THUMB_DIR, name, max_age=86400 * 365)


# --------------------------------------------------------------------- api
@app.get("/api/config")
def config():
    return jsonify({
        "ai_enabled": identifier.enabled,
        "ai_model": identifier.model if identifier.enabled else None,
        "ai_provider": identifier.provider,
        "relations": [{"key": k, "label": v[0], "inverse": v[1]} for k, v in RELATIONS.items()],
        "fts": db.fts,
    })


@app.get("/api/stats")
def stats():
    s = db.stats()
    hidden = dup.hidden_ids()
    s["duplicates"] = len(hidden)
    hide = (" WHERE i.id NOT IN (%s)" % ",".join(map(str, hidden))) if hidden else ""
    s["recent"] = db.decorate(db.q(db.item_row_sql() + hide + " ORDER BY i.updated_at DESC LIMIT 12"))
    s["low_items"] = db.decorate(db.q(db.item_row_sql() + " WHERE i.min_quantity IS NOT NULL AND "
                                      "i.quantity<=i.min_quantity ORDER BY i.quantity ASC LIMIT 12"))
    return jsonify(s)


@app.get("/api/items")
def list_items():
    a = request.args
    # duplicates are hidden from the main list and live in the Duplicates tab
    hidden = dup.hidden_ids() if a.get("duplicates") != "show" else set()
    rows, total = db.search_items(
        q=a.get("q", ""), location_id=a.get("location"), category_id=a.get("category"),
        low=a.get("low") == "1", favorite=a.get("favorite") == "1", sort=a.get("sort", "updated"),
        limit=min(int(a.get("limit", 60)), 500), offset=int(a.get("offset", 0)), exclude=hidden)
    return jsonify({"items": rows, "total": total, "duplicates": len(hidden)})


@app.post("/api/items")
def create_item():
    data = body()
    try:
        existing = dup.find_existing(data)
        if existing and not data.get("allow_duplicate"):
            it = db.get_item(existing)
            return jsonify({"error": f"You already have “{it['name']}”", "duplicate": it}), 409
        if data.get("category_name") and not data.get("category_id"):
            data["category_id"] = get_or_create_category(data["category_name"])
        item_id = db.create_item(data, data.get("photo_ids") or [])
        if existing:
            dup.ignore([item_id, existing])  # user chose "create anyway"
    except ValueError as e:
        return err(str(e))
    return jsonify(db.get_item(item_id)), 201


@app.get("/api/items/<int:item_id>")
def get_item(item_id):
    it = db.get_item(item_id)
    return jsonify(it) if it else err("Not found", 404)


@app.put("/api/items/<int:item_id>")
@app.patch("/api/items/<int:item_id>")
def update_item(item_id):
    data = body()
    try:
        if data.get("category_name") and not data.get("category_id"):
            data["category_id"] = get_or_create_category(data["category_name"])
        if not db.update_item(item_id, data):
            return err("Not found", 404)
    except ValueError as e:
        return err(str(e))
    if data.get("photo_ids"):
        db.attach_photos(item_id, data["photo_ids"])
    return jsonify(db.get_item(item_id))


@app.delete("/api/items/<int:item_id>")
def delete_item(item_id):
    remove_files(db.delete_item(item_id))
    return jsonify({"ok": True})


@app.post("/api/items/<int:item_id>/duplicate")
def duplicate_item(item_id):
    new_id = db.duplicate_item(item_id)
    return jsonify(db.get_item(new_id)) if new_id else err("Not found", 404)


@app.post("/api/items/<int:item_id>/adjust")
def adjust(item_id):
    d = body()
    try:
        delta = float(d.get("delta", 0))
    except (TypeError, ValueError):
        return err("Invalid amount")
    if "set" in d:
        cur = db.one("SELECT quantity FROM items WHERE id=?", (item_id,))
        if not cur:
            return err("Not found", 404)
        delta = float(d["set"]) - cur["quantity"]
    q = db.adjust(item_id, delta, d.get("reason", ""))
    if q is None:
        return err("Not found", 404)
    db.reindex(item_id)
    return jsonify({"quantity": q, "item": db.get_item(item_id)})


@app.post("/api/items/<int:item_id>/photos")
def add_photos(item_id):
    if not db.one("SELECT id FROM items WHERE id=?", (item_id,)):
        return err("Not found", 404)
    out = store_uploads(item_id=item_id)
    db.attach_photos(item_id, [p["id"] for p in out])
    return jsonify(db.get_item(item_id))


@app.post("/api/uploads")
def uploads():
    """Upload photos not yet attached to anything (used by photo-first create)."""
    return jsonify({"photos": store_uploads()})


@app.delete("/api/photos/<int:photo_id>")
def delete_photo(photo_id):
    p = db.one("SELECT * FROM photos WHERE id=?", (photo_id,))
    if not p:
        return err("Not found", 404)
    with db.tx() as c:
        c.execute("DELETE FROM photos WHERE id=?", (photo_id,))
        if p["item_id"]:
            c.execute("""UPDATE items SET primary_photo_id=(SELECT id FROM photos WHERE item_id=?
                         ORDER BY id LIMIT 1) WHERE id=? AND primary_photo_id=?""",
                      (p["item_id"], p["item_id"], photo_id))
    remove_files([p["filename"]])
    return jsonify({"ok": True})


@app.post("/api/photos/<int:photo_id>/primary")
def primary_photo(photo_id):
    p = db.one("SELECT * FROM photos WHERE id=?", (photo_id,))
    if not p or not p["item_id"]:
        return err("Not found", 404)
    with db.tx() as c:
        c.execute("UPDATE items SET primary_photo_id=?, updated_at=? WHERE id=?", (photo_id, now(), p["item_id"]))
    return jsonify(db.get_item(p["item_id"]))


# links
@app.post("/api/items/<int:item_id>/links")
def add_link(item_id):
    d = body()
    target = int(d.get("target_id") or 0)
    rel = d.get("relation") or "related"
    if rel not in RELATIONS:
        return err("Unknown relation")
    if not target or target == item_id:
        return err("Pick a different item")
    if not db.one("SELECT id FROM items WHERE id=?", (target,)):
        return err("Target not found", 404)
    a, b = item_id, target
    if d.get("inverse"):
        a, b = b, a
    try:
        with db.tx() as c:
            c.execute("INSERT INTO links(item_a, item_b, relation, note, created_at) VALUES (?,?,?,?,?)",
                      (a, b, rel, d.get("note", ""), now()))
    except Exception:
        return err("Already linked")
    return jsonify(db.get_item(item_id))


@app.delete("/api/links/<int:link_id>")
def delete_link(link_id):
    with db.tx() as c:
        c.execute("DELETE FROM links WHERE id=?", (link_id,))
    return jsonify({"ok": True})


# locations
@app.get("/api/locations")
def list_locations():
    return jsonify(db.list_locations())


@app.get("/api/locations/<int:loc_id>")
def get_location(loc_id):
    loc = db.one("SELECT * FROM locations WHERE id=?", (loc_id,))
    if not loc:
        return err("Not found", 404)
    loc["path"] = db.location_path(loc_id)
    loc["children"] = db.q("SELECT l.*, (SELECT COUNT(*) FROM items i WHERE i.location_id=l.id) AS item_count "
                           "FROM locations l WHERE parent_id=? ORDER BY name COLLATE NOCASE", (loc_id,))
    loc["photos"] = db.q("SELECT id, filename FROM photos WHERE location_id=? ORDER BY id DESC", (loc_id,))
    return jsonify(loc)


@app.post("/api/locations")
def create_location():
    d = body()
    name = (d.get("name") or "").strip()
    if not name:
        return err("Name is required")
    with db.tx() as c:
        lid = c.execute("INSERT INTO locations(name, parent_id, description, created_at) VALUES (?,?,?,?)",
                        (name, d.get("parent_id") or None, d.get("description", ""), now())).lastrowid
    return jsonify(db.one("SELECT * FROM locations WHERE id=?", (lid,))), 201


@app.put("/api/locations/<int:loc_id>")
def update_location(loc_id):
    d = body()
    name = (d.get("name") or "").strip()
    if not name:
        return err("Name is required")
    parent = d.get("parent_id") or None
    if parent and int(parent) in db.location_descendants(loc_id):
        return err("A location can't be inside itself")
    with db.tx() as c:
        c.execute("UPDATE locations SET name=?, parent_id=?, description=? WHERE id=?",
                  (name, parent, d.get("description", ""), loc_id))
    ids = [r["id"] for r in db.q("SELECT id FROM items WHERE location_id IN (%s)" %
                                 ",".join(str(i) for i in db.location_descendants(loc_id)))]
    db.reindex_many(ids)
    return jsonify(db.one("SELECT * FROM locations WHERE id=?", (loc_id,)))


@app.delete("/api/locations/<int:loc_id>")
def delete_location(loc_id):
    loc = db.one("SELECT * FROM locations WHERE id=?", (loc_id,))
    if not loc:
        return err("Not found", 404)
    files = [r["filename"] for r in db.q("SELECT filename FROM photos WHERE location_id=?", (loc_id,))]
    with db.tx() as c:
        # children and items move up to the parent location
        c.execute("UPDATE locations SET parent_id=? WHERE parent_id=?", (loc["parent_id"], loc_id))
        ids = [r[0] for r in c.execute("SELECT id FROM items WHERE location_id=?", (loc_id,))]
        c.execute("UPDATE items SET location_id=? WHERE location_id=?", (loc["parent_id"], loc_id))
        c.execute("DELETE FROM locations WHERE id=?", (loc_id,))
    db.reindex_many(ids)
    remove_files(files)
    return jsonify({"ok": True})


@app.post("/api/locations/<int:loc_id>/photos")
def location_photo(loc_id):
    if not db.one("SELECT id FROM locations WHERE id=?", (loc_id,)):
        return err("Not found", 404)
    store_uploads(location_id=loc_id)
    return get_location(loc_id)


# categories
@app.get("/api/categories")
def list_categories():
    rows = db.q("""SELECT c.*, p.name AS parent_name, COALESCE(NULLIF(c.color, ''), p.color) AS color,
                     (SELECT COUNT(*) FROM items i WHERE i.category_id=c.id) AS item_count
                   FROM categories c LEFT JOIN categories p ON p.id=c.parent_id
                   ORDER BY COALESCE(p.name, c.name) COLLATE NOCASE, c.parent_id IS NOT NULL,
                            c.name COLLATE NOCASE""")
    totals = {}
    for r in rows:
        r["path"] = f'{r["parent_name"]} › {r["name"]}' if r["parent_name"] else r["name"]
        totals[r["id"]] = totals.get(r["id"], 0) + r["item_count"]
        if r["parent_id"]:
            totals[r["parent_id"]] = totals.get(r["parent_id"], 0) + r["item_count"]
    for r in rows:
        r["total_count"] = totals.get(r["id"], 0)
    return jsonify(rows)


@app.post("/api/categories")
def create_category():
    d = body()
    name = (d.get("name") or "").strip()
    if not name:
        return err("Name is required")
    if d.get("parent_id"):
        parent = db.one("SELECT name FROM categories WHERE id=? AND parent_id IS NULL", (int(d["parent_id"]),))
        if parent:
            name = f'{parent["name"]} › {name}'
    cid = get_or_create_category(name)
    if d.get("color"):
        with db.tx() as c:
            c.execute("UPDATE categories SET color=? WHERE id=?", (d["color"], cid))
    return jsonify(db.one("SELECT * FROM categories WHERE id=?", (cid,))), 201


@app.post("/api/categories/defaults")
def categories_defaults():
    return jsonify({"added": add_default_categories()})


@app.put("/api/categories/<int:cid>")
def update_category(cid):
    d = body()
    name = (d.get("name") or "").strip()
    if not name:
        return err("Name is required")
    try:
        with db.tx() as c:
            c.execute("UPDATE categories SET name=?, color=? WHERE id=?", (name, d.get("color", ""), cid))
    except Exception:
        return err("Could not rename")
    db.reindex_many(category_item_ids(cid))
    return jsonify(db.one("SELECT * FROM categories WHERE id=?", (cid,)))


@app.delete("/api/categories/<int:cid>")
def delete_category(cid):
    ids = category_item_ids(cid)  # sub-categories are deleted too
    with db.tx() as c:
        c.execute("DELETE FROM categories WHERE id=?", (cid,))
    db.reindex_many(ids)
    return jsonify({"ok": True})


@app.get("/api/activity")
def activity():
    return jsonify(db.activity(int(request.args.get("limit", 80))))


@app.get("/api/lookup")
def lookup():
    """Resolve a scanned code: INV:<id>, LOC:<id>, or a barcode/part number."""
    code = (request.args.get("code") or "").strip()
    up = code.upper()
    if up.startswith("INV:") and up[4:].isdigit():
        if db.one("SELECT id FROM items WHERE id=?", (int(up[4:]),)):
            return jsonify({"type": "item", "id": int(up[4:])})
    if up.startswith("LOC:") and up[4:].isdigit():
        if db.one("SELECT id FROM locations WHERE id=?", (int(up[4:]),)):
            return jsonify({"type": "location", "id": int(up[4:])})
    rows = db.q("SELECT id FROM items WHERE (barcode=? AND barcode!='') OR "
                "(part_number=? COLLATE NOCASE AND part_number!='')", (code, code))
    if len(rows) == 1:
        return jsonify({"type": "item", "id": rows[0]["id"]})
    return jsonify({"type": "none", "code": code, "matches": [r["id"] for r in rows]})


# QR codes
@app.get("/api/qr")
def qr():
    import segno
    data = request.args.get("data", "")[:300]
    if not data:
        return err("No data")
    buf = io.BytesIO()
    segno.make(data, error="m").save(buf, kind="svg", scale=8, border=2, xmldecl=False)
    return Response(buf.getvalue(), mimetype="image/svg+xml",
                    headers={"Cache-Control": "max-age=86400"})


# AI
@app.post("/api/ai/identify")
def ai_identify():
    """Identify item(s) in photos. Accepts new uploads and/or existing photo_ids."""
    photo_rows = []
    if request.files:
        photo_rows = store_uploads()
    ids = request.form.get("photo_ids", "")
    for pid in [p for p in ids.split(",") if p.strip().isdigit()]:
        r = db.one("SELECT id, filename FROM photos WHERE id=?", (int(pid),))
        if r:
            photo_rows.append(r)
    if not photo_rows:
        return err("No photo")
    result = {"photos": photo_rows, "suggestion": None, "matches": []}
    if not identifier.enabled:
        result["error"] = "AI is not configured. Add an OpenAI API key in the add-on configuration."
        return jsonify(result)
    cats = category_paths()
    try:
        sug = identifier.identify([os.path.join(PHOTO_DIR, p["filename"]) for p in photo_rows],
                                  cats, request.form.get("hint", ""))
    except Exception as e:
        log.exception("AI identify failed")
        result["error"] = ai.friendly_error(e)
        return jsonify(result)
    result["suggestion"] = sug
    # find existing items that might be the same thing
    seen, matches = set(), []
    queries = [sug.get("part_number"), sug.get("barcode"), sug.get("name"),
               " ".join(sug.get("search_keywords") or [])]
    for qtext in [q for q in queries if q]:
        rows, _ = db.search_items(q=qtext, limit=6, sort="relevance", any_terms=(qtext != sug.get("part_number")))
        for r in rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                matches.append(r)
    result["matches"] = matches[:8]
    return jsonify(result)


def _strong_match(entry):
    """Best existing item for a detected label, only when it's a confident match."""
    pn = (entry.get("part_number") or "").strip()
    if pn:
        r = db.one("SELECT id FROM items WHERE part_number=? COLLATE NOCASE AND part_number!=''", (pn,))
        if r:
            return r["id"]
    for text in (entry.get("label_text"), entry.get("name")):
        if not text or text.strip() == "?":
            continue
        rows, _ = db.search_items(q=text, limit=1, sort="relevance")
        if rows:
            return rows[0]["id"]
    return None


@app.post("/api/ai/identify-box")
def ai_identify_box():
    """Read every labelled compartment of an organizer / picking box."""
    photo_rows = store_uploads() if request.files else []
    ids = request.form.get("photo_ids", "")
    for pid in [p for p in ids.split(",") if p.strip().isdigit()]:
        r = db.one("SELECT id, filename FROM photos WHERE id=?", (int(pid),))
        if r:
            photo_rows.append(r)
    if not photo_rows:
        return err("No photo")
    result = {"photos": photo_rows, "items": []}
    if not identifier.enabled:
        result["error"] = "AI is not configured. Add an OpenAI API key in the add-on configuration."
        return jsonify(result)
    cats = category_paths()
    try:
        found, model = identifier.identify_box(
            [os.path.join(PHOTO_DIR, p["filename"]) for p in photo_rows], cats, request.form.get("hint", ""))
    except Exception as e:
        log.exception("AI box identify failed")
        result["error"] = ai.friendly_error(e)
        return jsonify(result)
    match_ids = {}
    for entry in found:
        mid = _strong_match(entry)
        if mid:
            match_ids[mid] = None
            entry["match_id"] = mid
    if match_ids:
        rows = db.decorate(db.q(db.item_row_sql() + " WHERE i.id IN (%s)" % ",".join("?" * len(match_ids)),
                                list(match_ids)))
        by_id = {r["id"]: r for r in rows}
        for entry in found:
            if entry.get("match_id") in by_id:
                m = by_id[entry["match_id"]]
                entry["match"] = {"id": m["id"], "name": m["name"], "quantity": m["quantity"],
                                  "unit": m["unit"], "location_path": m["location_path"], "photo": m["photo"]}
    result["items"] = found
    result["model"] = model
    return jsonify(result)


@app.post("/api/items/batch")
def create_items_batch():
    """Create many items at once (e.g. everything read from a picking box)."""
    d = body()
    entries = d.get("items") or []
    if not entries:
        return err("Nothing to add")
    location_id = d.get("location_id") or None
    photo_ids = [int(p) for p in d.get("photo_ids") or []]
    created, stocked = [], []
    for e in entries:
        if e.get("add_to_id"):
            # already have it: bump existing stock instead of duplicating
            if db.adjust(int(e["add_to_id"]), float(e.get("quantity") or 1), "Stocked from box scan") is not None:
                db.reindex(int(e["add_to_id"]))
                stocked.append(int(e["add_to_id"]))
            continue
        data = {k: e.get(k) for k in ("name", "description", "part_number", "manufacturer", "tags",
                                      "compatible_with") if e.get(k)}
        if not data.get("name"):
            continue
        notes = []
        if e.get("label_text") and e["label_text"] != "?" and e["label_text"] != data["name"]:
            notes.append(f"Label: {e['label_text']}")
        if e.get("position"):
            notes.append(f"Position: {e['position']}")
        data["notes"] = "\n".join(notes)
        data["quantity"] = float(e.get("quantity") or 1)
        existing = dup.find_existing(data)
        if existing:
            db.adjust(existing, data["quantity"], "Stocked from box scan")
            db.reindex(existing)
            stocked.append(existing)
            continue
        data["location_id"] = location_id
        if e.get("category"):
            data["category_id"] = get_or_create_category(e["category"])
        item_id = db.create_item(data, reason="Box scan")
        if photo_ids:
            # share the box photo: attach a reference copy to each item
            with db.tx() as c:
                for pid in photo_ids:
                    src = c.execute("SELECT filename, width, height FROM photos WHERE id=?", (pid,)).fetchone()
                    if src:
                        cur = c.execute("INSERT INTO photos(item_id, filename, width, height, created_at) "
                                        "VALUES (?,?,?,?,?)", (item_id, src["filename"], src["width"], src["height"], now()))
                        c.execute("UPDATE items SET primary_photo_id=COALESCE(primary_photo_id, ?) WHERE id=?",
                                  (cur.lastrowid, item_id))
        created.append(item_id)
    # keep the box photo on the location too
    if location_id and photo_ids:
        with db.tx() as c:
            for pid in photo_ids:
                c.execute("UPDATE photos SET location_id=? WHERE id=? AND item_id IS NULL", (int(location_id), pid))
    return jsonify({"created": created, "stocked": stocked})


@app.post("/api/ai/categorize")
def ai_categorize():
    """Propose categories. scope: 'uncategorized' (default) or 'all'."""
    if not identifier.enabled:
        return err("AI is not configured. Add an OpenAI API key in the add-on configuration.")
    scope = body().get("scope", "uncategorized")
    sql = "SELECT id FROM items" + ("" if scope == "all" else " WHERE category_id IS NULL") + " ORDER BY id"
    ids = [r["id"] for r in db.q(sql)][:800]
    if not ids:
        return jsonify({"proposals": []})
    try:
        got = categorize_items(ids)
    except Exception as e:
        log.exception("Categorize failed")
        return err(ai.friendly_error(e), 502)
    rows = {r["id"]: r for r in db.q(db.item_row_sql() + " WHERE i.id IN (%s)" % ",".join("?" * len(ids)), ids)}
    props = []
    for item_id, cat in got.items():
        r = rows.get(item_id)
        if r and (r["category_name"] or "").lower() != cat.lower():
            props.append({"id": item_id, "name": r["name"], "photo": r["photo"],
                          "current": r["category_name"], "category": cat})
    return jsonify({"proposals": props})


@app.post("/api/ai/categorize/apply")
def ai_categorize_apply():
    a = {int(x["id"]): x["category"] for x in body().get("assignments", []) if x.get("category")}
    return jsonify({"updated": apply_categories(a)})


# duplicates
@app.get("/api/duplicates")
def list_duplicates():
    out = []
    for g in dup.groups():
        keep = dup.keeper(g["ids"])
        rows = db.decorate(db.q(db.item_row_sql() + " WHERE i.id IN (%s)" % ",".join(map(str, g["ids"]))))
        rows.sort(key=lambda r: (r["id"] != keep, r["id"]))
        out.append({"keep_id": keep, "reasons": g["reasons"], "items": rows})
    return jsonify({"groups": out, "count": sum(len(g["items"]) - 1 for g in out)})


@app.post("/api/duplicates/merge")
def merge_duplicates():
    d = body()
    keep, others = int(d.get("keep_id") or 0), d.get("merge_ids") or []
    if not keep or not others or not dup.merge(keep, others):
        return err("Nothing to merge")
    return jsonify(db.get_item(keep))


@app.post("/api/duplicates/merge-all")
def merge_all_duplicates():
    n = 0
    for g in dup.groups():
        keep = dup.keeper(g["ids"])
        others = [i for i in g["ids"] if i != keep]
        if dup.merge(keep, others):
            n += len(others)
    return jsonify({"merged": n})


@app.post("/api/duplicates/ignore")
def ignore_duplicates():
    ids = body().get("ids") or []
    if len(ids) < 2:
        return err("Pick at least two items")
    dup.ignore(ids)
    return jsonify({"ok": True})


# import / export
EXPORT_COLS = ["id", "name", "description", "category", "location", "quantity", "unit", "min_quantity",
               "part_number", "manufacturer", "barcode", "value", "tags", "notes", "url", "favorite",
               "compatible_with"]


@app.get("/api/export.csv")
def export_csv():
    rows, _ = db.search_items(limit=10 ** 9, sort="name")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(EXPORT_COLS)
    for r in rows:
        w.writerow([r["id"], r["name"], r["description"], r.get("category_name") or "",
                    (r.get("location_path") or "").replace(" › ", " > "), r["quantity"], r["unit"],
                    "" if r["min_quantity"] is None else r["min_quantity"], r["part_number"],
                    r["manufacturer"], r["barcode"], "" if r["value"] is None else r["value"],
                    ",".join(r["tags"]), r["notes"], r["url"], r["favorite"], ",".join(r["compatible"])])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=inventory.csv"})


@app.get("/api/export.json")
def export_json():
    out = {
        "exported_at": now(),
        "locations": db.q("SELECT * FROM locations"),
        "categories": db.q("SELECT * FROM categories"),
        "items": db.q("SELECT * FROM items"),
        "photos": db.q("SELECT * FROM photos"),
        "links": db.q("SELECT * FROM links"),
        "stock_log": db.q("SELECT * FROM stock_log"),
    }
    return Response(json.dumps(out, indent=1), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=inventory.json"})


@app.post("/api/import.csv")
def import_csv():
    f = request.files.get("file")
    if not f:
        return err("No file")
    text = f.read().decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    created = updated = merged = 0
    errors = []
    for n, row in enumerate(reader, start=2):
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        try:
            data = {k: row[k] for k in ITEM_FIELDS if k in row and row[k] != ""}
            if row.get("category"):
                data["category_id"] = get_or_create_category(row["category"])
            if row.get("location"):
                data["location_id"] = get_or_create_location_path(row["location"])
            if "favorite" in data:
                data["favorite"] = data["favorite"] not in ("0", "false", "no")
            rid = row.get("id")
            if rid and rid.isdigit() and db.one("SELECT id FROM items WHERE id=?", (int(rid),)):
                db.update_item(int(rid), data)
                updated += 1
            else:
                existing = dup.find_existing(data)
                if existing:
                    db.adjust(existing, float(data.get("quantity") or 0), "Imported (merged duplicate)")
                    db.reindex(existing)
                    merged += 1
                else:
                    db.create_item(data, reason="Imported")
                    created += 1
        except Exception as e:
            errors.append(f"Row {n}: {e}")
    return jsonify({"created": created, "updated": updated, "merged": merged, "errors": errors[:50]})


@app.errorhandler(400)
def bad_request(e):
    return err(getattr(e, "description", "Bad request"), 400)


@app.errorhandler(413)
def too_large(e):
    return err("Upload too large", 413)


def main():
    cleanup_orphans()
    port = int(os.environ.get("PORT", 8099))
    log.info("Parts Inventory on port %d (data: %s, AI: %s, FTS: %s)", port, DATA_DIR,
             "on" if identifier.enabled else "off", db.fts)
    from waitress import serve
    serve(app, host="0.0.0.0", port=port, threads=8, max_request_body_size=80 * 1024 * 1024)


if __name__ == "__main__":
    main()
