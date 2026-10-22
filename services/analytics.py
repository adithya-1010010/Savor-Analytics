from datetime import date

import pandas as pd


def _orders(conn, start, end):
    return pd.read_sql(
        "SELECT o.id, o.order_time, o.total, s.name AS staff FROM orders o "
        "JOIN staff s ON s.id = o.staff_id "
        "WHERE o.status != 'cancelled' AND date(o.order_time) BETWEEN ? AND ?",
        conn, params=(start.isoformat(), end.isoformat()))


def _lines(conn, start, end):
    return pd.read_sql(
        "SELECT m.name AS item, m.category, oi.qty, oi.price FROM order_items oi "
        "JOIN orders o ON o.id = oi.order_id JOIN menu_items m ON m.id = oi.menu_item_id "
        "WHERE o.status != 'cancelled' AND date(o.order_time) BETWEEN ? AND ?",
        conn, params=(start.isoformat(), end.isoformat()))


def _series(s):
    return {"labels": [str(i) for i in s.index], "values": [round(float(v), 2) for v in s.values]}


def dashboard(conn, start, end, today=None):
    today = today or date.today()
    orders = _orders(conn, start, end)
    lines = _lines(conn, start, end)

    n_orders = len(orders)
    revenue = float(orders["total"].sum()) if n_orders else 0.0

    # revenue per day, with zero-revenue days filled in
    days = pd.date_range(start, end).strftime("%Y-%m-%d")
    if n_orders:
        daily = orders.groupby(orders["order_time"].str[:10])["total"].sum()
    else:
        daily = pd.Series(dtype=float)
    daily = daily.reindex(days, fill_value=0)

    # orders per hour of the day
    if n_orders:
        hours = orders["order_time"].str[11:13].astype(int)
        per_hour = hours.value_counts().sort_index()
        per_hour = per_hour.reindex(range(hours.min(), hours.max() + 1), fill_value=0)
        per_hour.index = [f"{h:02d}:00" for h in per_hour.index]
    else:
        per_hour = pd.Series(dtype=int)

    if len(lines):
        lines = lines.assign(revenue=lines["qty"] * lines["price"])
        categories = lines.groupby("category")["revenue"].sum().sort_values(ascending=False)
        top = lines.groupby("item")["qty"].sum().sort_values(ascending=False).head(8)
    else:
        categories = pd.Series(dtype=float)
        top = pd.Series(dtype=int)

    if n_orders:
        by_staff = (orders.groupby("staff").agg(orders=("id", "count"), revenue=("total", "sum"))
                    .sort_values("revenue", ascending=False))
    else:
        by_staff = pd.DataFrame(columns=["orders", "revenue"])

    today_revenue = conn.execute(
        "SELECT COALESCE(SUM(total), 0) FROM orders WHERE status != 'cancelled' "
        "AND date(order_time) = ?", (today.isoformat(),)).fetchone()[0]
    low_stock = conn.execute(
        "SELECT COUNT(*) FROM inventory WHERE stock_qty <= reorder_level").fetchone()[0]

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "kpis": {
            "today_revenue": round(today_revenue, 2),
            "orders": n_orders,
            "avg_order": round(revenue / n_orders, 2) if n_orders else 0,
            "low_stock": low_stock,
            "top_item": top.index[0] if len(top) else "-",
        },
        "daily": _series(daily),
        "categories": _series(categories),
        "top_items": {"labels": list(top.index), "values": [int(v) for v in top.values]},
        "hours": {"labels": list(per_hour.index), "values": [int(v) for v in per_hour.values]},
        "staff": {
            "labels": list(by_staff.index),
            "orders": [int(v) for v in by_staff["orders"]],
            "revenue": [round(float(v), 2) for v in by_staff["revenue"]],
        },
    }
