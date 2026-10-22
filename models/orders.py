import sqlite3
from datetime import datetime

STATUSES = ["open", "served", "paid", "cancelled"]


class OrderError(Exception):
    pass


def insert_order(conn, table_id, customer_id, staff_id, status, order_time,
                 items, order_id=None):
    """Write an order and its lines. items = [(menu_item_id, qty, price)].
    Does not touch stock and does not open a transaction."""
    total = round(sum(qty * price for _, qty, price in items), 2)
    cur = conn.execute(
        "INSERT INTO orders (id, table_id, customer_id, staff_id, status, order_time, total) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (order_id, table_id, customer_id, staff_id, status, order_time, total),
    )
    oid = cur.lastrowid
    conn.executemany(
        "INSERT INTO order_items (order_id, menu_item_id, qty, price) VALUES (?, ?, ?, ?)",
        [(oid, m, q, p) for m, q, p in items],
    )
    return oid


def _ingredient_needs(conn, items):
    """items = {menu_item_id: qty}. Returns {inventory_id: amount needed}."""
    needs = {}
    for mid, qty in items.items():
        rows = conn.execute(
            "SELECT inventory_id, qty_per_item FROM recipes WHERE menu_item_id = ?", (mid,)
        ).fetchall()
        for r in rows:
            needs[r["inventory_id"]] = needs.get(r["inventory_id"], 0) + r["qty_per_item"] * qty
    return needs


def create_order(conn, table_id, customer_id, staff_id, raw_items, now=None):
    """Place an order: check stock, save the order, deduct ingredients.
    raw_items is a list of (menu_item_id, qty) as typed in the form.
    All or nothing - raises OrderError and changes nothing if anything is wrong."""
    if not table_id or not staff_id:
        raise OrderError("Pick a table and a staff member.")

    wanted = {}
    for mid, qty in raw_items:
        if str(mid).strip() == "":
            continue
        try:
            mid, qty = int(mid), int(qty)
        except (TypeError, ValueError):
            raise OrderError("Quantities must be whole numbers.")
        if qty < 1:
            raise OrderError("Quantities must be at least 1.")
        wanted[mid] = wanted.get(mid, 0) + qty
    if not wanted:
        raise OrderError("Add at least one item.")

    lines = []
    for mid, qty in wanted.items():
        item = conn.execute("SELECT id, name, price, available FROM menu_items WHERE id = ?",
                            (mid,)).fetchone()
        if item is None:
            raise OrderError("One of the menu items doesn't exist.")
        if not item["available"]:
            raise OrderError(f"{item['name']} is not available right now.")
        lines.append((mid, qty, item["price"]))

    now = now or datetime.now()
    conn.execute("BEGIN IMMEDIATE")
    try:
        needs = _ingredient_needs(conn, wanted)
        short = []
        for inv_id, need in needs.items():
            inv = conn.execute("SELECT ingredient, unit, stock_qty FROM inventory WHERE id = ?",
                               (inv_id,)).fetchone()
            if need > inv["stock_qty"] + 1e-9:
                short.append(f"{inv['ingredient']} (need {need:g} {inv['unit']}, "
                             f"have {inv['stock_qty']:g})")
        if short:
            raise OrderError("Not enough stock: " + ", ".join(short) + ".")

        oid = insert_order(conn, table_id, customer_id or None, staff_id, "open",
                           now.strftime("%Y-%m-%d %H:%M:%S"), lines)
        for inv_id, need in needs.items():
            conn.execute("UPDATE inventory SET stock_qty = MAX(0, stock_qty - ?) WHERE id = ?",
                         (need, inv_id))
        conn.execute("UPDATE tables SET status = 'occupied' WHERE id = ?", (table_id,))
        conn.execute("COMMIT")
        return oid
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        raise OrderError("That table, customer or staff member doesn't exist.")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _restore_stock(conn, order_id):
    rows = conn.execute(
        "SELECT r.inventory_id, SUM(r.qty_per_item * oi.qty) AS amount "
        "FROM order_items oi JOIN recipes r ON r.menu_item_id = oi.menu_item_id "
        "WHERE oi.order_id = ? GROUP BY r.inventory_id", (order_id,)).fetchall()
    for r in rows:
        conn.execute("UPDATE inventory SET stock_qty = stock_qty + ? WHERE id = ?",
                     (r["amount"], r["inventory_id"]))


def set_status(conn, order_id, status):
    """Change an order's status. Cancelling puts the ingredients back."""
    if status not in STATUSES:
        raise OrderError("Unknown status.")
    order = conn.execute("SELECT status, table_id FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        raise OrderError("Order not found.")
    if order["status"] == "cancelled":
        raise OrderError("Cancelled orders can't be changed.")

    conn.execute("BEGIN")
    try:
        if status == "cancelled":
            _restore_stock(conn, order_id)
        conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        if status in ("paid", "cancelled"):
            conn.execute(
                "UPDATE tables SET status = 'free' WHERE id = ? AND NOT EXISTS "
                "(SELECT 1 FROM orders WHERE table_id = ? AND id != ? "
                "AND status IN ('open', 'served'))",
                (order["table_id"], order["table_id"], order_id))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def delete_order(conn, order_id):
    """Remove an order and its lines. Stock is left alone."""
    conn.execute("DELETE FROM orders WHERE id = ?", (order_id,))


ORDER_SELECT = (
    "SELECT o.*, t.table_no, c.name AS customer, s.name AS staff, "
    "(SELECT SUM(qty) FROM order_items WHERE order_id = o.id) AS n_items "
    "FROM orders o JOIN tables t ON t.id = o.table_id "
    "LEFT JOIN customers c ON c.id = o.customer_id "
    "JOIN staff s ON s.id = o.staff_id"
)


def list_orders(conn, q="", status="", start="", end="", page=1, per_page=15):
    where, params = [], []
    if q:
        where.append("(c.name LIKE ? OR s.name LIKE ? OR CAST(t.table_no AS TEXT) = ? "
                     "OR CAST(o.id AS TEXT) = ?)")
        params += [f"%{q}%", f"%{q}%", q, q]
    if status:
        where.append("o.status = ?")
        params.append(status)
    if start:
        where.append("date(o.order_time) >= ?")
        params.append(start)
    if end:
        where.append("date(o.order_time) <= ?")
        params.append(end)
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    count_sql = ("SELECT COUNT(*) FROM orders o JOIN tables t ON t.id = o.table_id "
                 "LEFT JOIN customers c ON c.id = o.customer_id "
                 "JOIN staff s ON s.id = o.staff_id" + clause)
    total = conn.execute(count_sql, params).fetchone()[0]
    rows = conn.execute(
        ORDER_SELECT + clause + " ORDER BY o.order_time DESC, o.id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page]).fetchall()
    return rows, total


def get_order(conn, order_id):
    order = conn.execute(ORDER_SELECT + " WHERE o.id = ?", (order_id,)).fetchone()
    if order is None:
        return None, []
    items = conn.execute(
        "SELECT oi.qty, oi.price, m.name FROM order_items oi "
        "JOIN menu_items m ON m.id = oi.menu_item_id WHERE oi.order_id = ? ORDER BY oi.id",
        (order_id,)).fetchall()
    return order, items
