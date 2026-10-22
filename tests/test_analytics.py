import os
import unittest
from datetime import date

from tests.helpers import add_order, small_db

from services import analytics, reports


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = small_db()
        # day 1: two orders (one by each waiter), day 3: one order, one cancelled order
        add_order(self.conn, "2026-03-01", 12, 1, [(1, 2, 10.0)])              # 20.00
        add_order(self.conn, "2026-03-01", 19, 2, [(1, 1, 10.0), (2, 2, 4.0)]) # 18.00
        add_order(self.conn, "2026-03-03", 12, 1, [(2, 1, 4.0)])               # 4.00
        add_order(self.conn, "2026-03-03", 13, 1, [(1, 5, 10.0)], status="cancelled")
        self.start, self.end = date(2026, 3, 1), date(2026, 3, 3)

    def tearDown(self):
        self.conn.close()
        os.remove(self.path)

    def test_kpis(self):
        d = analytics.dashboard(self.conn, self.start, self.end, today=date(2026, 3, 3))
        k = d["kpis"]
        self.assertEqual(k["orders"], 3)                  # cancelled one is left out
        self.assertEqual(k["avg_order"], round(42 / 3, 2))
        self.assertEqual(k["today_revenue"], 4.0)
        self.assertEqual(k["low_stock"], 1)               # chicken: 1 in stock, reorder at 2
        self.assertEqual(k["top_item"], "Biryani")

    def test_daily_revenue_fills_empty_days(self):
        d = analytics.dashboard(self.conn, self.start, self.end)
        self.assertEqual(d["daily"]["labels"], ["2026-03-01", "2026-03-02", "2026-03-03"])
        self.assertEqual(d["daily"]["values"], [38.0, 0.0, 4.0])

    def test_categories_top_items_hours_staff(self):
        d = analytics.dashboard(self.conn, self.start, self.end)
        self.assertEqual(dict(zip(d["categories"]["labels"], d["categories"]["values"])),
                         {"Mains": 30.0, "Starters": 12.0})
        self.assertEqual(dict(zip(d["top_items"]["labels"], d["top_items"]["values"])),
                         {"Biryani": 3, "Soup": 3})
        self.assertEqual(d["hours"]["labels"][0], "12:00")
        self.assertEqual(d["hours"]["labels"][-1], "19:00")
        self.assertEqual(sum(d["hours"]["values"]), 3)
        self.assertEqual(dict(zip(d["staff"]["labels"], d["staff"]["revenue"])),
                         {"Asha": 24.0, "Ben": 18.0})

    def test_date_range_filter(self):
        d = analytics.dashboard(self.conn, date(2026, 3, 3), date(2026, 3, 3))
        self.assertEqual(d["kpis"]["orders"], 1)

    def test_empty_range(self):
        d = analytics.dashboard(self.conn, date(2025, 1, 1), date(2025, 1, 2))
        self.assertEqual(d["kpis"]["orders"], 0)
        self.assertEqual(d["kpis"]["avg_order"], 0)
        self.assertEqual(d["kpis"]["top_item"], "-")
        self.assertEqual(d["daily"]["values"], [0.0, 0.0])
        self.assertEqual(d["categories"]["labels"], [])
        self.assertEqual(d["staff"]["labels"], [])

    def test_reports(self):
        r = reports.build(self.conn, "daily-sales", {"day": "2026-03-01"})
        self.assertEqual(len(r["rows"]), 2)
        self.assertIn(("Revenue", "38.00"), r["summary"])
        r = reports.build(self.conn, "daily-sales", {"day": "2026-03-03"})
        self.assertIn(("Cancelled", 1), r["summary"])
        r = reports.build(self.conn, "low-stock", {}, date(2026, 3, 3))
        self.assertEqual([row[0] for row in r["rows"]], ["Chicken"])
        r = reports.build(self.conn, "top-sellers", {"start": "2026-03-01", "end": "2026-03-03"})
        self.assertEqual(r["rows"][0][0], "Biryani")
        self.assertEqual(r["rows"][0][3], "30.00")
        self.assertEqual(r["rows"][0][4], "21.00")        # 3 sold * (10 - 3)
        r = reports.build(self.conn, "staff-performance", {"start": "2026-03-01", "end": "2026-03-03"})
        self.assertEqual([(row[0], row[2]) for row in r["rows"]], [("Asha", 2), ("Ben", 1)])
        self.assertTrue(reports.to_csv(r).startswith("Name,Role,Orders"))


class SeededDataTests(unittest.TestCase):
    """The dashboard should agree with plain SQL on the generated data."""

    def test_dashboard_matches_sql(self):
        import seed
        import database
        from datetime import datetime
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, path)
        conn = database.connect(path)
        self.addCleanup(conn.close)
        database.init_schema(conn)
        seed.seed_db(conn, now=datetime(2026, 3, 1, 23, 0), days=20)

        start, end = date(2026, 2, 10), date(2026, 3, 1)
        d = analytics.dashboard(conn, start, end, today=end)
        n, total = conn.execute(
            "SELECT COUNT(*), SUM(total) FROM orders WHERE status != 'cancelled' "
            "AND date(order_time) BETWEEN ? AND ?", (start.isoformat(), end.isoformat())).fetchone()
        self.assertEqual(d["kpis"]["orders"], n)
        self.assertAlmostEqual(sum(d["daily"]["values"]), total, places=1)
        self.assertAlmostEqual(sum(d["categories"]["values"]), total, places=1)
        self.assertEqual(sum(d["hours"]["values"]), n)
        self.assertEqual(sum(d["staff"]["orders"]), n)


if __name__ == "__main__":
    unittest.main()
