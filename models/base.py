import math
import sqlite3
from datetime import datetime
import re


class Field:
    def __init__(self, name, label=None, kind="text", required=True, choices=None,
                 minimum=None, pattern=None, money=False):
        self.name = name
        self.label = label or name.replace("_", " ").capitalize()
        self.kind = kind
        self.required = required
        self.choices = choices or []
        self.minimum = minimum
        self.pattern = pattern
        self.money = money

    def parse(self, raw):
        """Return (value, error). error is None when the value is fine."""
        text = "" if raw is None else str(raw).strip()
        lab = self.label

        if self.kind == "bool":
            low = text.lower()
            if low in ("1", "true", "yes", "on", "y"):
                return 1, None
            if low in ("", "0", "false", "no", "off", "n"):
                return 0, None
            return None, f"{lab} must be yes or no."

        if text == "":
            if self.required:
                return None, f"{lab} is required."
            return None, None

        if self.kind == "int":
            try:
                value = int(text)
            except ValueError:
                return None, f"{lab} must be a whole number."
        elif self.kind == "float":
            try:
                value = float(text)
            except ValueError:
                return None, f"{lab} must be a number."
            if not math.isfinite(value):
                return None, f"{lab} must be a number."
        elif self.kind == "date":
            try:
                datetime.strptime(text, "%Y-%m-%d")
            except ValueError:
                return None, f"{lab} must be a date like 2026-03-27."
            return text, None
        elif self.kind == "choice":
            for c in self.choices:
                if c.lower() == text.lower():
                    return c, None
            return None, f"{lab} must be one of: {', '.join(self.choices)}."
        else:
            if len(text) > 100:
                return None, f"{lab} is too long (100 characters max)."
            if self.pattern and not re.match(self.pattern, text):
                return None, f"{lab} doesn't look right."
            return text, None

        if self.minimum is not None and value < self.minimum:
            return None, f"{lab} must be at least {self.minimum}."
        return value, None


def friendly_error(exc):
    msg = str(exc)
    if msg.startswith("UNIQUE"):
        col = msg.split(":")[-1].strip().split(".")[-1].replace("_", " ")
        return f"That {col} already exists."
    if "FOREIGN KEY" in msg:
        return "A linked record doesn't exist, or this record is still used by other records."
    if "CHECK" in msg:
        return "A value is outside the allowed range."
    return msg


class Entity:
    """Describes one table and does the basic CRUD on it."""

    def __init__(self, slug, table, title, singular, fields, search,
                 filters=(), order="id"):
        self.slug = slug
        self.table = table
        self.title = title
        self.singular = singular
        self.fields = fields
        self.search = search
        self.filters = list(filters)
        self.order = order

    @property
    def columns(self):
        return [f.name for f in self.fields]

    def field(self, name):
        return next(f for f in self.fields if f.name == name)

    def validate(self, raw):
        clean, errors = {}, {}
        for f in self.fields:
            value, err = f.parse(raw.get(f.name))
            if err:
                errors[f.name] = err
            else:
                clean[f.name] = value
        return clean, errors

    def list(self, conn, q="", filters=None, sort="", direction="asc",
             page=1, per_page=15, extra_where=None):
        where, params = [], []
        if q:
            where.append("(" + " OR ".join(f"{c} LIKE ?" for c in self.search) + ")")
            params += [f"%{q}%"] * len(self.search)
        for name, value in (filters or {}).items():
            if value and name in self.filters:
                where.append(f"{name} = ?")
                params.append(value)
        if extra_where:
            where.append(extra_where)
        clause = (" WHERE " + " AND ".join(where)) if where else ""

        col = sort if sort in self.columns or sort == "id" else self.order
        way = "DESC" if direction == "desc" else "ASC"
        total = conn.execute(f"SELECT COUNT(*) FROM {self.table}{clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM {self.table}{clause} ORDER BY {col} {way}, id LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()
        return rows, total

    def get(self, conn, rid):
        return conn.execute(f"SELECT * FROM {self.table} WHERE id = ?", (rid,)).fetchone()

    def insert(self, conn, clean):
        cols = ", ".join(self.columns)
        marks = ", ".join("?" for _ in self.columns)
        cur = conn.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({marks})",
                           [clean[c] for c in self.columns])
        return cur.lastrowid

    def update(self, conn, rid, clean):
        sets = ", ".join(f"{c} = ?" for c in self.columns)
        conn.execute(f"UPDATE {self.table} SET {sets} WHERE id = ?",
                     [clean[c] for c in self.columns] + [rid])

    def delete(self, conn, rid):
        conn.execute(f"DELETE FROM {self.table} WHERE id = ?", (rid,))

    def upsert(self, conn, rid, clean):
        """Insert, or update when a row with this id already exists."""
        if rid is None:
            return self.insert(conn, clean)
        cols = ["id"] + self.columns
        marks = ", ".join("?" for _ in cols)
        updates = ", ".join(f"{c} = excluded.{c}" for c in self.columns)
        conn.execute(
            f"INSERT INTO {self.table} ({', '.join(cols)}) VALUES ({marks}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            [rid] + [clean[c] for c in self.columns],
        )
        return rid
