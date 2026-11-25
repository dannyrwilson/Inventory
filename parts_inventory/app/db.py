"""SQLite storage layer for Parts Inventory."""
import os
import re
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    parent_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    description TEXT DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    color TEXT DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    location_id INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    quantity REAL NOT NULL DEFAULT 0,
    unit TEXT DEFAULT 'pcs',
    min_quantity REAL,
    part_number TEXT DEFAULT '',
    manufacturer TEXT DEFAULT '',
    barcode TEXT DEFAULT '',
    value REAL,
    tags TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    url TEXT DEFAULT '',
    primary_photo_id INTEGER,
    favorite INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_location ON items(location_id);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);
CREATE INDEX IF NOT EXISTS idx_items_barcode ON items(barcode);
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY,
    item_id INTEGER REFERENCES items(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    width INTEGER, height INTEGER,
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_photos_item ON photos(item_id);
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY,
    item_a INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    item_b INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    relation TEXT NOT NULL DEFAULT 'related',
    note TEXT DEFAULT '',
    created_at INTEGER NOT NULL,
    UNIQUE(item_a, item_b, relation)
);
CREATE INDEX IF NOT EXISTS idx_links_a ON links(item_a);
CREATE INDEX IF NOT EXISTS idx_links_b ON links(item_b);
CREATE TABLE IF NOT EXISTS stock_log (
    id INTEGER PRIMARY KEY,
    item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    delta REAL NOT NULL,
    quantity_after REAL NOT NULL,
    reason TEXT DEFAULT '',
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_log_item ON stock_log(item_id, created_at);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

# Relations are stored directionally (item_a -> item_b). Each has a label as
# seen from A and the inverse label as seen from B.
RELATIONS = {
    "related": ("Related to", "Related to"),
    "part_of": ("Part of", "Has part"),
    "compatible": ("Compatible with", "Compatible with"),
    "replacement": ("Replacement for", "Replaced by"),
    "accessory": ("Accessory for", "Has accessory"),
    "requires": ("Requires", "Required by"),
}

ITEM_FIELDS = [
    "name", "description", "category_id", "location_id", "quantity", "unit",
    "min_quantity", "part_number", "manufacturer", "barcode", "value", "tags",
    "notes", "url", "favorite",
]


def now():
    return int(time.time())


class DB:
    def __init__(self, path):
        self.path = path
        self._local = threading.local()
        self.write_lock = threading.Lock()
        conn = self.conn
        conn.executescript(SCHEMA)
        self.fts = self._init_fts(conn)
        conn.commit()

    @property
    def conn(self):
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = c
        return c

    def _init_fts(self, conn):
        try:
            existed = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE name='items_fts'").fetchone()
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5("
                "name, body, tokenize='unicode61 remove_diacritics 2', prefix='2 3')")
            ver = conn.execute("SELECT value FROM meta WHERE key='fts_ver'").fetchone()
            if not existed or not ver or ver[0] != "2":
                conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('fts_ver', '2')")
                ids = [r[0] for r in conn.execute("SELECT id FROM items")]
                for i in ids:
                    self._reindex(conn, i, fts=True)
            return True
        except sqlite3.OperationalError:
            return False

    # ------------------------------------------------------------------ utils
    def q(self, sql, args=()):
        return [dict(r) for r in self.conn.execute(sql, args)]

    def one(self, sql, args=()):
        r = self.conn.execute(sql, args).fetchone()
        return dict(r) if r else None

    def tx(self):
        return _Tx(self)

    # -------------------------------------------------------------- locations
    def location_path(self, loc_id, _cache=None):
        parts, seen = [], set()
        while loc_id and loc_id not in seen:
            seen.add(loc_id)
            r = self.one("SELECT id, name, parent_id FROM locations WHERE id=?", (loc_id,))
            if not r:
                break
            parts.append(r["name"])
            loc_id = r["parent_id"]
        return " › ".join(reversed(parts))

    def location_descendants(self, loc_id):
        rows = self.q("""
            WITH RECURSIVE d(id) AS (SELECT ? UNION ALL
              SELECT l.id FROM locations l JOIN d ON l.parent_id=d.id)
            SELECT id FROM d""", (loc_id,))
        return [r["id"] for r in rows]

    def list_locations(self):
        rows = self.q("""
            SELECT l.*, (SELECT COUNT(*) FROM items i WHERE i.location_id=l.id) AS item_count,
                   (SELECT filename FROM photos p WHERE p.location_id=l.id ORDER BY id DESC LIMIT 1) AS photo
            FROM locations l ORDER BY name COLLATE NOCASE""")
        for r in rows:
            r["path"] = self.location_path(r["id"])
        return rows

    # ------------------------------------------------------------------ items
    def _reindex(self, conn, item_id, fts=None):
        if not (self.fts if fts is None else fts):
            return
        conn.execute("DELETE FROM items_fts WHERE rowid=?", (item_id,))
        it = conn.execute("""
            SELECT i.*, c.name AS category_name FROM items i
            LEFT JOIN categories c ON c.id=i.category_id WHERE i.id=?""", (item_id,)).fetchone()
        if not it:
            return
        body = " ".join(str(x or "") for x in [
            it["description"], it["part_number"], it["manufacturer"], it["barcode"],
            (it["tags"] or "").replace(",", " "), it["notes"], it["category_name"],
            self.location_path(it["location_id"]),
            # split part numbers like "LM7805-CT" into pieces too
            re.sub(r"[-_/.]", " ", it["part_number"] or ""),
        ])
        # "LM7805" -> also index "LM 7805" so partial numbers match
        split = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ",
                       f'{it["name"]} {it["part_number"] or ""}')
        body += " " + split
        conn.execute("INSERT INTO items_fts(rowid, name, body) VALUES (?,?,?)",
                     (item_id, it["name"], body))

    def reindex(self, item_id):
        self._reindex(self.conn, item_id)

    def reindex_many(self, ids):
        for i in ids:
            self._reindex(self.conn, i)

    def item_row_sql(self):
        return """
            SELECT i.*, c.name AS category_name, c.color AS category_color,
              (SELECT filename FROM photos p WHERE p.id=i.primary_photo_id) AS photo,
              (SELECT COUNT(*) FROM photos p WHERE p.item_id=i.id) AS photo_count
            FROM items i LEFT JOIN categories c ON c.id=i.category_id"""

    def decorate(self, rows):
        cache = {}
        for r in rows:
            lid = r.get("location_id")
            if lid not in cache:
                cache[lid] = self.location_path(lid) if lid else ""
            r["location_path"] = cache[lid]
            r["low"] = bool(r.get("min_quantity") is not None
                            and r["quantity"] <= r["min_quantity"])
            r["tags"] = [t.strip() for t in (r.get("tags") or "").split(",") if t.strip()]
        return rows

    @staticmethod
    def fts_query(text):
        toks = re.findall(r"[\w]+", text.lower(), flags=re.UNICODE)
        if not toks:
            return None
        return " ".join('"%s"*' % t.replace('"', "") for t in toks[:12])

    def search_items(self, q="", location_id=None, category_id=None, low=False,
                     favorite=False, sort="updated", limit=100, offset=0, any_terms=False,
                     _like=False):
        where, args = [], []
        order = {
            "name": "i.name COLLATE NOCASE ASC",
            "quantity": "i.quantity ASC",
            "created": "i.created_at DESC",
            "updated": "i.updated_at DESC",
        }.get(sort, "i.updated_at DESC")
        join = ""
        q = (q or "").strip()
        if q:
            exact = self.q("SELECT id FROM items WHERE barcode=? AND barcode!='' "
                           "OR part_number=? COLLATE NOCASE AND part_number!=''", (q, q))
            fq = self.fts_query(q)
            if self.fts and fq and not _like:
                if any_terms:
                    fq = " OR ".join(fq.split(" "))
                join = "JOIN (SELECT rowid AS rid, bm25(items_fts, 4.0, 1.0) AS score " \
                       "FROM items_fts WHERE items_fts MATCH ?) f ON f.rid=i.id"
                args.append(fq)
                if sort == "relevance" or sort == "updated":
                    order = "f.score ASC"
            else:
                like = f"%{q}%"
                where.append("(i.name LIKE ? OR i.description LIKE ? OR i.part_number LIKE ? "
                             "OR i.tags LIKE ? OR i.notes LIKE ? OR i.manufacturer LIKE ? OR i.barcode LIKE ?)")
                args += [like] * 7
        if location_id:
            ids = self.location_descendants(int(location_id))
            where.append("i.location_id IN (%s)" % ",".join("?" * len(ids)))
            args += ids
        if category_id:
            where.append("i.category_id=?")
            args.append(int(category_id))
        if low:
            where.append("i.min_quantity IS NOT NULL AND i.quantity <= i.min_quantity")
        if favorite:
            where.append("i.favorite=1")
        sql = self.item_row_sql().replace("FROM items i", f"FROM items i {join}")
        if where:
            sql += " WHERE " + " AND ".join(where)
        count_sql = "SELECT COUNT(*) AS n FROM (" + sql + ")"
        total = self.one(count_sql, args)["n"]
        sql += f" ORDER BY {order} LIMIT ? OFFSET ?"
        rows = self.decorate(self.q(sql, args + [int(limit), int(offset)]))
        if q and total == 0 and self.fts and not _like and not any_terms:
            # FTS only matches word prefixes; fall back to substring search
            return self.search_items(q, location_id, category_id, low, favorite, sort,
                                     limit, offset, any_terms, _like=True)
        if q and not offset:
            have = {r["id"] for r in rows}
            extra = [e["id"] for e in exact if e["id"] not in have]
            if extra:
                more = self.decorate(self.q(self.item_row_sql() + " WHERE i.id IN (%s)"
                                            % ",".join("?" * len(extra)), extra))
                rows = more + rows
                total += len(more)
        return rows, total

    def get_item(self, item_id):
        rows = self.decorate(self.q(self.item_row_sql() + " WHERE i.id=?", (item_id,)))
        if not rows:
            return None
        it = rows[0]
        it["photos"] = self.q("SELECT id, filename, width, height, created_at FROM photos "
                              "WHERE item_id=? ORDER BY (id=?) DESC, id ASC",
                              (item_id, it["primary_photo_id"] or 0))
        it["links"] = self.item_links(item_id)
        it["history"] = self.q("SELECT * FROM stock_log WHERE item_id=? ORDER BY id DESC LIMIT 50",
                               (item_id,))
        return it

    def item_links(self, item_id):
        out = []
        for direction, mine, other in (("out", "item_a", "item_b"), ("in", "item_b", "item_a")):
            rows = self.q(f"""
                SELECT l.id AS link_id, l.relation, l.note, i.id, i.name, i.quantity, i.unit,
                       (SELECT filename FROM photos p WHERE p.id=i.primary_photo_id) AS photo
                FROM links l JOIN items i ON i.id=l.{other} WHERE l.{mine}=?""", (item_id,))
            for r in rows:
                labels = RELATIONS.get(r["relation"], (r["relation"], r["relation"]))
                r["label"] = labels[0] if direction == "out" else labels[1]
                r["direction"] = direction
                out.append(r)
        return out

    def clean_item_data(self, data, partial=False):
        out = {}
        for f in ITEM_FIELDS:
            if f not in data:
                continue
            v = data[f]
            if f in ("quantity",):
                v = float(v or 0)
            elif f in ("min_quantity", "value"):
                v = None if v in (None, "") else float(v)
            elif f in ("category_id", "location_id"):
                v = None if v in (None, "", 0, "0") else int(v)
            elif f == "favorite":
                v = 1 if v else 0
            elif f == "tags":
                if isinstance(v, list):
                    v = ",".join(t.strip() for t in v if str(t).strip())
                v = ",".join(dict.fromkeys(t.strip() for t in str(v or "").split(",") if t.strip()))
            else:
                v = str(v or "").strip()
            out[f] = v
        if not partial and not out.get("name"):
            raise ValueError("Name is required")
        if "name" in out and not out["name"]:
            raise ValueError("Name is required")
        return out

    def create_item(self, data, photo_ids=(), reason="Created"):
        d = self.clean_item_data(data)
        t = now()
        d.setdefault("quantity", 0)
        d["created_at"] = d["updated_at"] = t
        cols = ",".join(d)
        with self.tx() as c:
            cur = c.execute(f"INSERT INTO items ({cols}) VALUES ({','.join('?' * len(d))})",
                            list(d.values()))
            item_id = cur.lastrowid
            if d["quantity"]:
                c.execute("INSERT INTO stock_log(item_id, delta, quantity_after, reason, created_at) "
                          "VALUES (?,?,?,?,?)", (item_id, d["quantity"], d["quantity"], reason, t))
            self._attach_photos(c, item_id, photo_ids)
            self._reindex(c, item_id)
        return item_id

    def _attach_photos(self, c, item_id, photo_ids):
        for pid in photo_ids or []:
            c.execute("UPDATE photos SET item_id=? WHERE id=? AND (item_id IS NULL OR item_id=?)",
                      (item_id, int(pid), item_id))
        c.execute("""UPDATE items SET primary_photo_id=(SELECT id FROM photos WHERE item_id=?
                     ORDER BY id LIMIT 1) WHERE id=? AND (primary_photo_id IS NULL OR
                     primary_photo_id NOT IN (SELECT id FROM photos WHERE item_id=?))""",
                  (item_id, item_id, item_id))

    def attach_photos(self, item_id, photo_ids):
        with self.tx() as c:
            self._attach_photos(c, item_id, photo_ids)
            c.execute("UPDATE items SET updated_at=? WHERE id=?", (now(), item_id))

    def update_item(self, item_id, data):
        d = self.clean_item_data(data, partial=True)
        old = self.one("SELECT quantity FROM items WHERE id=?", (item_id,))
        if not old:
            return False
        d["updated_at"] = now()
        with self.tx() as c:
            c.execute("UPDATE items SET " + ",".join(f"{k}=?" for k in d) + " WHERE id=?",
                      list(d.values()) + [item_id])
            if "quantity" in d and d["quantity"] != old["quantity"]:
                c.execute("INSERT INTO stock_log(item_id, delta, quantity_after, reason, created_at) "
                          "VALUES (?,?,?,?,?)", (item_id, d["quantity"] - old["quantity"],
                                                 d["quantity"], "Edited", d["updated_at"]))
            self._reindex(c, item_id)
        return True

    def adjust(self, item_id, delta, reason=""):
        with self.tx() as c:
            r = c.execute("SELECT quantity FROM items WHERE id=?", (item_id,)).fetchone()
            if not r:
                return None
            q = max(0.0, r["quantity"] + float(delta))
            real = q - r["quantity"]
            t = now()
            c.execute("UPDATE items SET quantity=?, updated_at=? WHERE id=?", (q, t, item_id))
            if real:
                c.execute("INSERT INTO stock_log(item_id, delta, quantity_after, reason, created_at) "
                          "VALUES (?,?,?,?,?)", (item_id, real, q, reason or "", t))
        return q

    def delete_item(self, item_id):
        files = [r["filename"] for r in self.q("SELECT filename FROM photos WHERE item_id=?", (item_id,))]
        with self.tx() as c:
            c.execute("DELETE FROM items WHERE id=?", (item_id,))
            if self.fts:
                c.execute("DELETE FROM items_fts WHERE rowid=?", (item_id,))
        return files

    def duplicate_item(self, item_id):
        it = self.one("SELECT * FROM items WHERE id=?", (item_id,))
        if not it:
            return None
        data = {k: it[k] for k in ITEM_FIELDS}
        data["name"] = it["name"] + " (copy)"
        data["quantity"] = 0
        data["barcode"] = ""
        return self.create_item(data)

    def stats(self):
        s = self.one("""SELECT COUNT(*) AS items, COALESCE(SUM(quantity),0) AS units,
            COALESCE(SUM(quantity*COALESCE(value,0)),0) AS total_value,
            SUM(CASE WHEN min_quantity IS NOT NULL AND quantity<=min_quantity THEN 1 ELSE 0 END) AS low
            FROM items""")
        s["locations"] = self.one("SELECT COUNT(*) AS n FROM locations")["n"]
        s["categories"] = self.one("SELECT COUNT(*) AS n FROM categories")["n"]
        s["photos"] = self.one("SELECT COUNT(*) AS n FROM photos")["n"]
        return s

    def activity(self, limit=60):
        return self.q("""SELECT s.*, i.name, i.unit,
              (SELECT filename FROM photos p WHERE p.id=i.primary_photo_id) AS photo
            FROM stock_log s JOIN items i ON i.id=s.item_id ORDER BY s.id DESC LIMIT ?""", (limit,))


class _Tx:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db.write_lock.acquire()
        self.c = self.db.conn
        self.c.execute("BEGIN IMMEDIATE")
        return self.c

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.c.execute("ROLLBACK")
            else:
                self.c.execute("COMMIT")
        finally:
            self.db.write_lock.release()
        return False
