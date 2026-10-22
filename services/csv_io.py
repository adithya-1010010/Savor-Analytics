import csv
import io
import sqlite3
from datetime import datetime

from models.base import friendly_error
from models.entities import ENTITIES
from models.orders import STATUSES, insert_order

ORDER_COLUMNS = ["id", "table_id", "customer_id", "staff_id", "status", "order_time", "items", "total"]
ORDER_REQUIRED = ["table_id", "staff_id", "status", "order_time", "items"]
NAMES = list(ENTITIES) + ["orders"]


class RowError(Exception):
    pass


def columns_info(name):
    """(required columns, optional columns) for an import file."""
    if name == "orders":
        return ORDER_REQUIRED, [c for c in ORDER_COLUMNS if c not in ORDER_REQUIRED]
    ent = ENTITIES[name]
    return ([f.name for f in ent.fields if f.required],
            ["id"] + [f.name for f in ent.fields if not f.required])


def export_csv(conn, name):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    if name == "orders":
        w.writerow(ORDER_COLUMNS)
        rows = conn.execute(
            "SELECT o.*, (SELECT group_concat(menu_item_id || ':' || qty || ':' || price, ';') "
            "FROM order_items WHERE order_id = o.id) AS items FROM orders o ORDER BY o.id")
        for r in rows:
            w.writerow([r[c] for c in ORDER_COLUMNS])
    else:
        ent = ENTITIES[name]
        w.writerow(["id"] + ent.columns)
        for r in conn.execute(f"SELECT * FROM {ent.table} ORDER BY id"):
            w.writerow([r["id"]] + ["" if r[c] is None else r[c] for c in ent.columns])
    return out.getvalue()


def _int(raw, label, required=True):
    text = (raw or "").strip()
    if not text:
        if required:
            raise RowError(f"{label} is required.")
        return None
    try:
        return int(text)
    except ValueError:
        raise RowError(f"{label} must be a whole number.")


def _entity_row(conn, ent, raw):
    clean, errors = ent.validate(raw)
    if errors:
        raise RowError(" ".join(errors.values()))
    ent.upsert(conn, _int(raw.get("id"), "Id", required=False), clean)
    return clean


def _order_row(conn, raw):
    table_id = _int(raw.get("table_id"), "Table id")
    staff_id = _int(raw.get("staff_id"), "Staff id")
    customer_id = _int(raw.get("customer_id"), "Customer id", required=False)
    order_id = _int(raw.get("id"), "Id", required=False)

    status = (raw.get("status") or "").strip().lower()
    if status not in STATUSES:
        raise RowError(f"Status must be one of: {', '.join(STATUSES)}.")

    when = (raw.get("order_time") or "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            when = datetime.strptime(when, fmt).strftime("%Y-%m-%d %H:%M:%S")
            break
        except ValueError:
            continue
    else:
        raise RowError("Order time must look like 2026-03-27 19:30:00.")

    items = []
    for part in (raw.get("items") or "").split(";"):
        part = part.strip()
        if not part:
            continue
        bits = part.split(":")
        if len(bits) not in (2, 3):
            raise RowError(f"Item '{part}' should look like menu_id:qty or menu_id:qty:price.")
        try:
            mid, qty = int(bits[0]), int(bits[1])
            price = float(bits[2]) if len(bits) == 3 else None
        except ValueError:
            raise RowError(f"Item '{part}' has a value that isn't a number.")
        if qty < 1:
            raise RowError("Item quantities must be at least 1.")
        if price is None:
            found = conn.execute("SELECT price FROM menu_items WHERE id = ?", (mid,)).fetchone()
            if found is None:
                raise RowError(f"Menu item {mid} doesn't exist.")
            price = found["price"]
        items.append((mid, qty, price))
    if not items:
        raise RowError("An order needs at least one item.")

    if order_id is not None:
        conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    insert_order(conn, table_id, customer_id, staff_id, status, when, items, order_id)
    return {"table_id": table_id, "customer_id": customer_id, "staff_id": staff_id,
            "status": status, "order_time": when, "items": len(items)}


def run_import(conn, name, text, commit=False):
    """Validate (and optionally save) a CSV. Rows are tried one by one inside a
    single transaction; if any row fails nothing is saved."""
    result = {"header_errors": [], "row_errors": [], "good": 0, "preview": [],
              "columns": [], "committed": False}
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    header = reader.fieldnames
    if not header:
        result["header_errors"].append("The file is empty.")
        return result
    header = [h.strip().lower() for h in header]
    reader.fieldnames = header

    required, optional = columns_info(name)
    allowed = required + optional + (["total"] if name == "orders" else [])
    missing = [c for c in required if c not in header]
    unknown = [c for c in header if c not in allowed]
    if missing:
        result["header_errors"].append("Missing column(s): " + ", ".join(missing))
    if unknown:
        result["header_errors"].append("Unknown column(s): " + ", ".join(unknown))
    if len(set(header)) != len(header):
        result["header_errors"].append("Some column names appear twice.")
    if result["header_errors"]:
        return result

    handler = (lambda raw: _order_row(conn, raw)) if name == "orders" \
        else (lambda raw: _entity_row(conn, ENTITIES[name], raw))

    conn.execute("BEGIN")
    try:
        for line, raw in enumerate(reader, start=2):
            if None in raw:
                result["row_errors"].append((line, "Too many columns in this row."))
                continue
            if not any((v or "").strip() for v in raw.values()):
                continue
            conn.execute("SAVEPOINT one_row")
            try:
                clean = handler(raw)
            except (RowError, sqlite3.IntegrityError) as e:
                conn.execute("ROLLBACK TO one_row")
                msg = friendly_error(e) if isinstance(e, sqlite3.IntegrityError) else str(e)
                result["row_errors"].append((line, msg))
            else:
                result["good"] += 1
                if len(result["preview"]) < 8:
                    result["preview"].append(clean)
            finally:
                conn.execute("RELEASE one_row")
        if result["preview"]:
            result["columns"] = list(result["preview"][0].keys())
        if commit and result["good"] and not result["row_errors"]:
            conn.execute("COMMIT")
            result["committed"] = True
        else:
            conn.execute("ROLLBACK")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return result
