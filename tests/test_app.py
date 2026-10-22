import os
import unittest

from tests.helpers import small_db

import database
from app import create_app
from models import orders as om
from services import csv_io


class CsvImportTests(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = small_db()

    def tearDown(self):
        self.conn.close()
        os.remove(self.path)

    def count(self, table):
        return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_good_file_is_saved(self):
        text = "name,category,price,cost,available\nPizza,Mains,9.5,3,1\nTea,Beverages,2,0.4,\n"
        report = csv_io.run_import(self.conn, "menu", text, commit=True)
        self.assertTrue(report["committed"])
        self.assertEqual(report["good"], 2)
        self.assertEqual(self.count("menu_items"), 5)

    def test_preview_does_not_save(self):
        text = "name,category,price,cost\nPizza,Mains,9.5,3\n"
        report = csv_io.run_import(self.conn, "menu", text, commit=False)
        self.assertEqual(report["good"], 1)
        self.assertFalse(report["committed"])
        self.assertEqual(self.count("menu_items"), 3)

    def test_missing_and_unknown_columns(self):
        report = csv_io.run_import(self.conn, "menu", "name,price,colour\nPizza,9,red\n")
        self.assertEqual(len(report["header_errors"]), 2)

    def test_empty_file(self):
        report = csv_io.run_import(self.conn, "menu", "")
        self.assertEqual(report["header_errors"], ["The file is empty."])

    def test_bad_rows_reported_with_line_numbers_and_nothing_saved(self):
        text = ("name,category,price,cost\n"
                "Good,Mains,5,1\n"
                "Bad price,Mains,abc,1\n"
                "Bad category,Snacks,5,1\n"
                "Negative,Mains,-4,1\n")
        report = csv_io.run_import(self.conn, "menu", text, commit=True)
        self.assertFalse(report["committed"])
        self.assertEqual([line for line, _ in report["row_errors"]], [3, 4, 5])
        self.assertEqual(self.count("menu_items"), 3)

    def test_duplicate_unique_value_is_a_row_error(self):
        text = "table_no,capacity,status\n5,4,free\n5,2,free\n1,4,free\n"
        report = csv_io.run_import(self.conn, "tables", text, commit=True)
        self.assertEqual([line for line, _ in report["row_errors"]], [3, 4])
        self.assertEqual(self.count("tables"), 2)

    def test_blank_lines_and_extra_columns(self):
        text = "name,category,price,cost\nA,Mains,5,1\n,,,\nB,Mains,6,2,99\n"
        report = csv_io.run_import(self.conn, "menu", text)
        self.assertEqual(report["good"], 1)
        self.assertEqual(report["row_errors"][0][0], 4)

    def test_existing_id_updates_the_row(self):
        text = "id,name,category,price,cost\n1,Biryani,Mains,11,3\n"
        csv_io.run_import(self.conn, "menu", text, commit=True)
        price = self.conn.execute("SELECT price FROM menu_items WHERE id = 1").fetchone()[0]
        self.assertEqual(price, 11)
        self.assertEqual(self.count("menu_items"), 3)

    def conn_with_nothing(self):
        # fresh empty database for the round trip
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(os.remove, path)
        conn = database.connect(path)
        self.addCleanup(conn.close)
        database.init_schema(conn)
        self.source = conn
        return conn

    def test_export_then_import_gives_the_same_data(self):
        import seed
        from datetime import datetime
        source = self.conn_with_nothing()
        seed.seed_db(source, now=datetime(2026, 3, 1, 23, 0), days=5)
        target = database.connect(self.path.replace(".db", "_copy.db"))
        self.addCleanup(os.remove, self.path.replace(".db", "_copy.db"))
        self.addCleanup(target.close)
        database.init_schema(target)
        # parents first so foreign keys line up
        for name in ["tables", "staff", "customers", "menu", "inventory", "orders"]:
            text = csv_io.export_csv(source, name)
            report = csv_io.run_import(target, name, text, commit=True)
            self.assertTrue(report["committed"], (name, report["row_errors"][:2]))
        for table in ["menu_items", "staff", "tables", "customers", "inventory", "orders", "order_items"]:
            a = source.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            b = target.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            self.assertEqual(a, b, table)
        a = source.execute("SELECT ROUND(SUM(total), 2) FROM orders").fetchone()[0]
        b = target.execute("SELECT ROUND(SUM(total), 2) FROM orders").fetchone()[0]
        self.assertEqual(a, b)

    def test_order_import_checks_items(self):
        head = "table_id,staff_id,status,order_time,items\n"
        ok = csv_io.run_import(self.conn, "orders", head + "1,1,paid,2026-03-01 12:00,1:2:10;2:1\n", commit=True)
        self.assertTrue(ok["committed"])
        total = self.conn.execute("SELECT total FROM orders").fetchone()[0]
        self.assertEqual(total, 24.0)
        bad = csv_io.run_import(self.conn, "orders", head + "1,1,done,2026-03-01 12:00,1:1\n"
                                "1,1,paid,yesterday,1:1\n1,1,paid,2026-03-01 12:00,99:1\n1,1,paid,2026-03-01 12:00,\n")
        self.assertEqual(len(bad["row_errors"]), 4)


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.conn, self.path = small_db()

    def tearDown(self):
        self.conn.close()
        os.remove(self.path)

    def stock(self, name):
        return self.conn.execute("SELECT stock_qty FROM inventory WHERE ingredient = ?", (name,)).fetchone()[0]

    def test_total_is_quantity_times_price(self):
        oid = om.create_order(self.conn, 1, None, 1, [("1", "2"), ("2", "3")])
        order, items = om.get_order(self.conn, oid)
        self.assertEqual(order["total"], 2 * 10.0 + 3 * 4.0)
        self.assertEqual(len(items), 2)

    def test_same_item_twice_is_merged(self):
        oid = om.create_order(self.conn, 1, None, 1, [("2", "1"), ("2", "2")])
        _, items = om.get_order(self.conn, oid)
        self.assertEqual([(i["name"], i["qty"]) for i in items], [("Soup", 3)])

    def test_stock_is_deducted(self):
        om.create_order(self.conn, 1, None, 1, [("1", "2")])
        self.assertAlmostEqual(self.stock("Rice"), 9.0)
        self.assertAlmostEqual(self.stock("Chicken"), 0.5)

    def test_not_enough_stock_changes_nothing(self):
        # chicken: 1 kg in stock, 5 biryanis need 1.25
        with self.assertRaises(om.OrderError) as ctx:
            om.create_order(self.conn, 1, None, 1, [("1", "5")])
        self.assertIn("Chicken", str(ctx.exception))
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)
        self.assertAlmostEqual(self.stock("Rice"), 10.0)

    def test_bad_input(self):
        for args in [(1, None, 1, []), (1, None, 1, [("1", "0")]), (1, None, 1, [("1", "x")]),
                     (1, None, 1, [("3", "1")]), (1, None, 1, [("42", "1")]), (None, None, 1, [("2", "1")])]:
            with self.assertRaises(om.OrderError):
                om.create_order(self.conn, *args)

    def test_unknown_table_is_a_friendly_error(self):
        with self.assertRaises(om.OrderError):
            om.create_order(self.conn, 99, None, 1, [("2", "1")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0], 0)

    def test_table_status_follows_the_order(self):
        oid = om.create_order(self.conn, 1, None, 1, [("2", "1")])
        table = lambda: self.conn.execute("SELECT status FROM tables WHERE id = 1").fetchone()[0]
        self.assertEqual(table(), "occupied")
        om.set_status(self.conn, oid, "paid")
        self.assertEqual(table(), "free")

    def test_cancel_puts_stock_back(self):
        oid = om.create_order(self.conn, 1, None, 1, [("1", "2")])
        om.set_status(self.conn, oid, "cancelled")
        self.assertAlmostEqual(self.stock("Rice"), 10.0)
        with self.assertRaises(om.OrderError):
            om.set_status(self.conn, oid, "paid")


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import tempfile
        fd, cls.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(cls.path)          # let the app create and seed it
        cls.client = create_app(cls.path).test_client()

    @classmethod
    def tearDownClass(cls):
        os.remove(cls.path)

    def test_pages_load(self):
        for url in ["/", "/menu/", "/staff/", "/tables/", "/customers/", "/inventory/",
                    "/inventory/?low=1", "/orders/", "/orders/new", "/orders/1", "/menu/new",
                    "/menu/1/edit", "/reports/", "/reports/daily-sales", "/reports/low-stock",
                    "/reports/top-sellers", "/reports/staff-performance", "/menu/import",
                    "/orders/import", "/api/dashboard", "/menu/?q=tea&sort=price&dir=desc"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_missing_things_are_404(self):
        for url in ["/menu/9999/edit", "/orders/999999", "/reports/nope", "/nothing/"]:
            self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_exports_are_csv(self):
        for name in ["menu", "staff", "tables", "customers", "inventory", "orders"]:
            r = self.client.get(f"/{name}/export.csv")
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.mimetype.startswith("text/csv"))

    def test_add_validates_and_saves(self):
        bad = self.client.post("/menu/new", data={"name": "", "category": "Mains", "price": "x", "cost": "1"})
        self.assertEqual(bad.status_code, 200)
        self.assertIn(b"Name is required", bad.data)
        self.assertIn(b"Price must be a number", bad.data)
        ok = self.client.post("/menu/new", data={"name": "Test Dish", "category": "Mains",
                                                 "price": "7", "cost": "2", "available": "1"})
        self.assertEqual(ok.status_code, 302)
        self.assertIn(b"Test Dish", self.client.get("/menu/?q=Test+Dish").data)
        dup = self.client.post("/menu/new", data={"name": "Test Dish", "category": "Mains",
                                                  "price": "7", "cost": "2"})
        self.assertIn(b"already exists", dup.data)

    def test_cant_delete_a_staff_member_with_orders(self):
        r = self.client.post("/staff/5/delete", follow_redirects=True)
        self.assertIn(b"delete this staff member", r.data)

    def test_order_flow_and_inventory_actions(self):
        r = self.client.post("/orders/new", data={"table_id": "1", "staff_id": "5",
                                                  "menu_item_id": ["17", ""], "qty": ["2", "1"]})
        self.assertEqual(r.status_code, 302)
        r = self.client.post("/orders/new", data={"table_id": "1", "staff_id": "5",
                                                  "menu_item_id": [""], "qty": ["1"]})
        self.assertIn(b"Add at least one item", r.data)
        self.client.post("/inventory/1/restock", data={"qty": "5"})
        r = self.client.post("/inventory/1/waste", data={"qty": "2", "reason": "spoiled"},
                             follow_redirects=True)
        self.assertIn(b"spoiled", r.data)
        r = self.client.post("/inventory/1/waste", data={"qty": "100000"}, follow_redirects=True)
        self.assertIn(b"more than is in stock", r.data)

    def test_import_through_the_browser(self):
        from io import BytesIO
        csv_bytes = b"table_no,capacity,status\n50,4,free\n51,2,free\n"
        r = self.client.post("/tables/import", data={"file": (BytesIO(csv_bytes), "t.csv")},
                             content_type="multipart/form-data")
        self.assertIn(b"2 row(s) are fine", r.data)
        r = self.client.post("/tables/import/confirm",
                             data={"csv_text": csv_bytes.decode()}, follow_redirects=True)
        self.assertIn(b"Imported 2 rows", r.data)


if __name__ == "__main__":
    unittest.main()
