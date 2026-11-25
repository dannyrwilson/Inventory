"""Duplicate detection and merging."""
import re

from db import now

SCHEMA = """
CREATE TABLE IF NOT EXISTS dup_ignore (
    item_a INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    item_b INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    PRIMARY KEY (item_a, item_b)
);
"""

FILL_FIELDS = ["description", "part_number", "manufacturer", "barcode", "value", "min_quantity",
               "url", "category_id", "location_id"]


def norm_name(name):
    """'Nuts, M3 (hex)' and 'm3 hex nut' -> same key."""
    s = (name or "").lower().replace("×", "x")
    toks = re.findall(r"[a-z0-9]+", s)
    out = []
    for t in toks:
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return " ".join(sorted(out))


def norm_code(code):
    return re.sub(r"[^a-z0-9]", "", (code or "").lower())


def keys_for(row):
    keys = []
    n = norm_name(row.get("name"))
    if n:
        keys.append(("name", n))
    pn = norm_code(row.get("part_number"))
    if len(pn) >= 3:
        keys.append(("part", pn))
    bc = (row.get("barcode") or "").strip()
    if bc:
        keys.append(("barcode", bc))
    return keys


REASONS = {"name": "Same name", "part": "Same part number", "barcode": "Same barcode"}


class Dupes:
    def __init__(self, db):
        self.db = db
        db.conn.executescript(SCHEMA)

    # ------------------------------------------------------------ detection
    def _ignored(self):
        return {(r["item_a"], r["item_b"]) for r in self.db.q("SELECT item_a, item_b FROM dup_ignore")}

    def groups(self):
        """Returns [{ids, reasons}] for every group of 2+ items that look like the same thing."""
        rows = self.db.q("SELECT id, name, part_number, barcode FROM items ORDER BY id")
        ignored = self._ignored()
        buckets = {}
        for r in rows:
            for k in keys_for(r):
                buckets.setdefault(k, []).append(r["id"])
        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        reasons = {}
        for (kind, _), ids in buckets.items():
            if len(ids) < 2:
                continue
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    if (min(a, b), max(a, b)) in ignored:
                        continue
                    ra, rb = find(a), find(b)
                    if ra != rb:
                        parent[rb] = ra
                    reasons.setdefault(frozenset((a, b)), set()).add(kind)
        groups = {}
        for x in list(parent):
            groups.setdefault(find(x), []).append(x)
        out = []
        for ids in groups.values():
            if len(ids) < 2:
                continue
            ids.sort()
            why = set()
            for pair, kinds in reasons.items():
                if pair <= set(ids):
                    why |= kinds
            out.append({"ids": ids, "reasons": [REASONS[k] for k in ("barcode", "part", "name") if k in why]})
        return out

    def keeper(self, ids):
        """Pick the item with the most information (photos, filled fields), oldest on ties."""
        best, best_score = None, None
        for i in ids:
            r = self.db.one("SELECT *, (SELECT COUNT(*) FROM photos p WHERE p.item_id=items.id) AS pc, "
                            "(SELECT COUNT(*) FROM links l WHERE l.item_a=items.id OR l.item_b=items.id) AS lc "
                            "FROM items WHERE id=?", (i,))
            if not r:
                continue
            filled = sum(1 for f in FILL_FIELDS + ["tags", "notes", "compatible_with"] if r.get(f) not in (None, ""))
            score = (r["pc"] * 3 + r["lc"] * 2 + filled, -r["id"])
            if best_score is None or score > best_score:
                best, best_score = i, score
        return best

    def hidden_ids(self):
        """Non-keeper members of each group: hidden from the main item list."""
        hidden = set()
        for g in self.groups():
            k = self.keeper(g["ids"])
            hidden.update(i for i in g["ids"] if i != k)
        return hidden

    def find_existing(self, data, exclude_id=None):
        """Item that a new/edited item would duplicate, or None."""
        mine = set(keys_for(data))
        if not mine:
            return None
        hits = [r["id"] for r in self.db.q("SELECT id, name, part_number, barcode FROM items")
                if r["id"] != exclude_id and mine & set(keys_for(r))]
        if not hits:
            return None
        hidden = self.hidden_ids() if len(hits) > 1 else set()
        visible = [h for h in hits if h not in hidden]
        return (visible or hits)[0]

    def ignore(self, ids):
        ids = sorted(set(int(i) for i in ids))
        with self.db.tx() as c:
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    c.execute("INSERT OR IGNORE INTO dup_ignore(item_a, item_b) VALUES (?,?)", (a, b))

    # --------------------------------------------------------------- merging
    def merge(self, keep_id, other_ids):
        db = self.db
        other_ids = [int(o) for o in other_ids if int(o) != int(keep_id)]
        keep = db.one("SELECT * FROM items WHERE id=?", (keep_id,))
        if not keep or not other_ids:
            return False
        others = [db.one("SELECT * FROM items WHERE id=?", (o,)) for o in other_ids]
        others = [o for o in others if o]
        t = now()
        with db.tx() as c:
            qty = keep["quantity"]
            updates = {}
            tags = [x for x in (keep["tags"] or "").split(",") if x]
            compat = [x for x in (keep["compatible_with"] or "").split(",") if x]
            notes = [keep["notes"]] if keep["notes"] else []
            for o in others:
                qty += o["quantity"]
                for f in FILL_FIELDS:
                    if keep[f] in (None, "") and updates.get(f) in (None, "") and o[f] not in (None, ""):
                        updates[f] = o[f]
                tags += [x for x in (o["tags"] or "").split(",") if x]
                compat += [x for x in (o["compatible_with"] or "").split(",") if x]
                if o["notes"] and o["notes"] not in notes:
                    notes.append(o["notes"])
                if o["favorite"]:
                    updates["favorite"] = 1
                # photos (skip copies of a photo the keeper already has)
                have = {r[0] for r in c.execute("SELECT filename FROM photos WHERE item_id=?", (keep_id,))}
                for p in c.execute("SELECT id, filename FROM photos WHERE item_id=?", (o["id"],)).fetchall():
                    if p["filename"] in have:
                        c.execute("DELETE FROM photos WHERE id=?", (p["id"],))
                    else:
                        c.execute("UPDATE photos SET item_id=? WHERE id=?", (keep_id, p["id"]))
                        have.add(p["filename"])
                # links: repoint, drop ones that would clash or point at itself
                c.execute("UPDATE OR IGNORE links SET item_a=? WHERE item_a=?", (keep_id, o["id"]))
                c.execute("UPDATE OR IGNORE links SET item_b=? WHERE item_b=?", (keep_id, o["id"]))
                c.execute("DELETE FROM links WHERE item_a=? OR item_b=?", (o["id"], o["id"]))
                c.execute("UPDATE stock_log SET item_id=? WHERE item_id=?", (keep_id, o["id"]))
                c.execute("DELETE FROM items WHERE id=?", (o["id"],))
                if db.fts:
                    c.execute("DELETE FROM items_fts WHERE rowid=?", (o["id"],))
            c.execute("DELETE FROM links WHERE item_a=item_b")
            updates["quantity"] = qty
            updates["tags"] = ",".join(dict.fromkeys(tags))
            updates["compatible_with"] = ",".join(dict.fromkeys(compat))
            updates["notes"] = "\n".join(notes)
            updates["updated_at"] = t
            c.execute("UPDATE items SET " + ",".join(f"{k}=?" for k in updates) + " WHERE id=?",
                      list(updates.values()) + [keep_id])
            c.execute("""UPDATE items SET primary_photo_id=(SELECT id FROM photos WHERE item_id=? ORDER BY id LIMIT 1)
                         WHERE id=? AND (primary_photo_id IS NULL OR primary_photo_id NOT IN
                         (SELECT id FROM photos WHERE item_id=?))""", (keep_id, keep_id, keep_id))
            c.execute("INSERT INTO stock_log(item_id, delta, quantity_after, reason, created_at) VALUES (?,?,?,?,?)",
                      (keep_id, qty - keep["quantity"], qty, f"Merged {len(others)} duplicate(s)", t))
        db.reindex(keep_id)
        return True
