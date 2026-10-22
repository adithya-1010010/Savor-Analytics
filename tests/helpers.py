import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402


def small_db():
    """Empty database with a tiny, known data set. Returns (conn, path)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = database.connect(path)
    database.init_schema(conn)
    conn.executescript("""
        INSERT INTO tables (table_no, capacity, status) VALUES (1, 4, 'free'), (2, 2, 'free');
        INSERT INTO staff (name, role, shift, phone, salary, hire_date) VALUES
            ('Asha', 'Waiter', 'Morning', '9000000001', 1500, '2024-01-01'),
            ('Ben', 'Waiter', 'Evening', '9000000002', 1500, '2024-01-01');
        INSERT INTO customers (name, phone, membership) VALUES ('Cara', NULL, 'gold');
        INSERT INTO inventory (ingredient, unit, stock_qty, reorder_level, unit_cost) VALUES
            ('Rice', 'kg', 10, 2, 1.0), ('Chicken', 'kg', 1, 2, 6.0);
        INSERT INTO menu_items (name, category, price, cost, available) VALUES
            ('Biryani', 'Mains', 10.0, 3.0, 1),
            ('Soup', 'Starters', 4.0, 1.0, 1),
            ('Old Special', 'Mains', 9.0, 3.0, 0);
        INSERT INTO recipes (menu_item_id, inventory_id, qty_per_item) VALUES
            (1, 1, 0.5), (1, 2, 0.25);
    """)
    return conn, path


def add_order(conn, day, hour, staff_id, items, status="paid", table_id=1):
    from models.orders import insert_order
    return insert_order(conn, table_id, None, staff_id, status,
                        f"{day} {hour:02d}:30:00", items)
