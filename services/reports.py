import csv
import io
from datetime import date, datetime, timedelta


def _day(text, default):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


def _money(x):
    return f"{x:,.2f}"


def daily_sales(conn, args, today):
    day = _day(args.get("day"), today)
    rows = conn.execute(
        "SELECT o.id, substr(o.order_time, 12, 5) AS t, tb.table_no, s.name AS staff, "
        "o.status, o.total FROM orders o JOIN tables tb ON tb.id = o.table_id "
        "JOIN staff s ON s.id = o.staff_id WHERE date(o.order_time) = ? "
        "ORDER BY o.order_time", (day.isoformat(),)).fetchall()
    valid = [r for r in rows if r["status"] != "cancelled"]
    revenue = sum(r["total"] for r in valid)
    return {
        "title": "Daily sales",
        "subtitle": day.isoformat(),
        "params": "day", "values": {"day": day.isoformat()},
        "summary": [("Orders", len(valid)), ("Cancelled", len(rows) - len(valid)),
                    ("Revenue", _money(revenue)),
                    ("Average order", _money(revenue / len(valid)) if valid else "0.00")],
        "columns": ["Order", "Time", "Table", "Staff", "Status", "Total"],
        "rows": [[r["id"], r["t"], r["table_no"], r["staff"], r["status"], _money(r["total"])]
                 for r in rows],
    }


def low_stock(conn, args, today):
    rows = conn.execute(
        "SELECT ingredient, unit, stock_qty, reorder_level, expiry_date FROM inventory "
        "WHERE stock_qty <= reorder_level ORDER BY stock_qty - reorder_level, ingredient").fetchall()
    return {
        "title": "Low stock",
        "subtitle": f"as of {today.isoformat()}",
        "params": None, "values": {},
        "summary": [("Items to reorder", len(rows))],
        "columns": ["Ingredient", "Unit", "In stock", "Reorder level", "Short by", "Expiry"],
        "rows": [[r["ingredient"], r["unit"], f"{r['stock_qty']:g}", f"{r['reorder_level']:g}",
                  f"{r['reorder_level'] - r['stock_qty']:g}", r["expiry_date"] or "-"]
                 for r in rows],
    }


def _range(args, today):
    end = _day(args.get("end"), today)
    start = _day(args.get("start"), end - timedelta(days=29))
    if start > end:
        start, end = end, start
    return start, end


def top_sellers(conn, args, today):
    start, end = _range(args, today)
    rows = conn.execute(
        "SELECT m.name, m.category, SUM(oi.qty) AS qty, SUM(oi.qty * oi.price) AS revenue, "
        "SUM(oi.qty * (oi.price - m.cost)) AS profit FROM order_items oi "
        "JOIN orders o ON o.id = oi.order_id JOIN menu_items m ON m.id = oi.menu_item_id "
        "WHERE o.status != 'cancelled' AND date(o.order_time) BETWEEN ? AND ? "
        "GROUP BY m.id ORDER BY qty DESC, revenue DESC LIMIT 10",
        (start.isoformat(), end.isoformat())).fetchall()
    return {
        "title": "Top sellers",
        "subtitle": f"{start} to {end}",
        "params": "range", "values": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": [("Items listed", len(rows))],
        "columns": ["Item", "Category", "Sold", "Revenue", "Profit (est.)"],
        "rows": [[r["name"], r["category"], r["qty"], _money(r["revenue"]), _money(r["profit"])]
                 for r in rows],
    }


def staff_performance(conn, args, today):
    start, end = _range(args, today)
    rows = conn.execute(
        "SELECT s.name, s.role, COUNT(o.id) AS n, COALESCE(SUM(o.total), 0) AS revenue "
        "FROM staff s LEFT JOIN orders o ON o.staff_id = s.id AND o.status != 'cancelled' "
        "AND date(o.order_time) BETWEEN ? AND ? GROUP BY s.id ORDER BY revenue DESC, s.name",
        (start.isoformat(), end.isoformat())).fetchall()
    return {
        "title": "Staff performance",
        "subtitle": f"{start} to {end}",
        "params": "range", "values": {"start": start.isoformat(), "end": end.isoformat()},
        "summary": [("Staff", len(rows)), ("Orders handled", sum(r["n"] for r in rows))],
        "columns": ["Name", "Role", "Orders", "Revenue", "Average order"],
        "rows": [[r["name"], r["role"], r["n"], _money(r["revenue"]),
                  _money(r["revenue"] / r["n"]) if r["n"] else "-"] for r in rows],
    }


REPORTS = {
    "daily-sales": ("Daily sales", "Every order for one day with totals.", daily_sales),
    "low-stock": ("Low stock", "Ingredients at or below their reorder level.", low_stock),
    "top-sellers": ("Top sellers", "The 10 most ordered items in a date range.", top_sellers),
    "staff-performance": ("Staff performance", "Orders and revenue per staff member.",
                          staff_performance),
}


def build(conn, name, args, today=None):
    return REPORTS[name][2](conn, args, today or date.today())


def to_csv(report):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(report["columns"])
    w.writerows(report["rows"])
    return out.getvalue()
