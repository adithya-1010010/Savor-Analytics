"""Fills the database with sample data and writes the sample CSV files.

    python seed.py          wipe data/restaurant.db and start again
"""
import os
import random
from datetime import datetime, timedelta

import config
import database
from models.entities import ENTITIES
from models.orders import insert_order
from services import csv_io

# name, unit, stock, reorder level, unit cost
INGREDIENTS = [
    ("Tomato", "kg", 40, 10, 1.2), ("Onion", "kg", 50, 12, 0.8), ("Potato", "kg", 60, 15, 0.7),
    ("Garlic", "kg", 8, 2, 3.5), ("Spinach", "kg", 12, 4, 2.0), ("Mushroom", "kg", 2.5, 3, 4.5),
    ("Bell pepper", "kg", 14, 4, 2.8), ("Lettuce", "kg", 10, 3, 2.2), ("Chicken", "kg", 45, 12, 6.5),
    ("Lamb", "kg", 5, 6, 11.0), ("Fish fillet", "kg", 18, 6, 9.0), ("Prawns", "kg", 2.5, 3, 12.0),
    ("Paneer", "kg", 15, 4, 7.0), ("Eggs", "pcs", 300, 80, 0.25), ("Rice", "kg", 80, 20, 1.4),
    ("Pasta", "kg", 25, 8, 2.1), ("Flour", "kg", 60, 15, 0.9), ("Bread buns", "pcs", 120, 40, 0.4),
    ("Mozzarella", "kg", 16, 5, 8.0), ("Butter", "kg", 12, 4, 6.0), ("Cream", "l", 15, 5, 3.5),
    ("Milk", "l", 40, 12, 1.0), ("Sugar", "kg", 30, 8, 1.1), ("Chocolate", "kg", 2, 3, 9.5),
    ("Coffee beans", "kg", 9, 3, 14.0), ("Tea leaves", "kg", 0.8, 1, 16.0),
    ("Cooking oil", "l", 35, 10, 2.0), ("Lemons", "pcs", 150, 40, 0.2),
    ("Ice cream", "l", 18, 6, 5.0), ("Mango pulp", "kg", 10, 3, 4.0),
]
PERISHABLE = {"Tomato", "Spinach", "Mushroom", "Lettuce", "Chicken", "Lamb", "Fish fillet",
              "Prawns", "Paneer", "Cream", "Milk", "Ice cream", "Mango pulp", "Mozzarella"}

# name, category, price, cost, recipe (ingredient -> amount per portion)
MENU = [
    ("Tomato Soup", "Starters", 4.5, 1.2, {"Tomato": 0.25, "Cream": 0.03, "Butter": 0.01}),
    ("Veg Spring Rolls", "Starters", 5.0, 1.4, {"Flour": 0.08, "Bell pepper": 0.05, "Cooking oil": 0.05}),
    ("Chicken Wings", "Starters", 7.5, 2.8, {"Chicken": 0.25, "Cooking oil": 0.05}),
    ("Garlic Bread", "Starters", 3.5, 0.8, {"Bread buns": 1, "Butter": 0.03, "Garlic": 0.01}),
    ("Prawn Cocktail", "Starters", 9.0, 4.0, {"Prawns": 0.15, "Lettuce": 0.05, "Lemons": 1}),
    ("Caesar Salad", "Starters", 6.5, 2.0, {"Lettuce": 0.2, "Eggs": 1, "Chicken": 0.08}),
    ("Butter Chicken", "Mains", 12.0, 4.2, {"Chicken": 0.3, "Butter": 0.03, "Cream": 0.05, "Tomato": 0.15}),
    ("Paneer Tikka Masala", "Mains", 11.0, 3.6, {"Paneer": 0.2, "Tomato": 0.15, "Onion": 0.1, "Cream": 0.04}),
    ("Grilled Fish", "Mains", 14.0, 5.5, {"Fish fillet": 0.25, "Lemons": 1, "Potato": 0.15}),
    ("Lamb Rogan Josh", "Mains", 15.5, 6.8, {"Lamb": 0.28, "Onion": 0.1, "Tomato": 0.1}),
    ("Mushroom Risotto", "Mains", 11.5, 3.2, {"Rice": 0.15, "Mushroom": 0.12, "Butter": 0.02}),
    ("Spaghetti Carbonara", "Mains", 12.5, 3.5, {"Pasta": 0.15, "Eggs": 2, "Cream": 0.05}),
    ("Margherita Pizza", "Mains", 10.0, 3.0, {"Flour": 0.2, "Mozzarella": 0.12, "Tomato": 0.1}),
    ("Chicken Burger", "Mains", 9.5, 3.1, {"Bread buns": 1, "Chicken": 0.15, "Lettuce": 0.03, "Tomato": 0.03}),
    ("Prawn Curry", "Mains", 16.0, 7.2, {"Prawns": 0.2, "Onion": 0.1, "Tomato": 0.1}),
    ("Veg Biryani", "Mains", 10.5, 2.9, {"Rice": 0.2, "Bell pepper": 0.05, "Onion": 0.08}),
    ("French Fries", "Sides", 4.0, 0.9, {"Potato": 0.25, "Cooking oil": 0.05}),
    ("Steamed Rice", "Sides", 3.0, 0.5, {"Rice": 0.15}),
    ("Garden Salad", "Sides", 4.5, 1.2, {"Lettuce": 0.1, "Tomato": 0.08, "Lemons": 0.5}),
    ("Sauteed Spinach", "Sides", 4.5, 1.3, {"Spinach": 0.15, "Garlic": 0.01, "Butter": 0.01}),
    ("Chocolate Brownie", "Desserts", 5.5, 1.6, {"Chocolate": 0.05, "Flour": 0.04, "Sugar": 0.05, "Eggs": 1}),
    ("Ice Cream Sundae", "Desserts", 5.0, 1.5, {"Ice cream": 0.15, "Chocolate": 0.02}),
    ("Cheesecake", "Desserts", 6.0, 2.0, {"Cream": 0.08, "Flour": 0.03, "Sugar": 0.04}),
    ("Masala Tea", "Beverages", 2.5, 0.4, {"Tea leaves": 0.005, "Milk": 0.1, "Sugar": 0.01}),
    ("Cappuccino", "Beverages", 3.5, 0.8, {"Coffee beans": 0.018, "Milk": 0.15}),
    ("Fresh Lime Soda", "Beverages", 3.0, 0.5, {"Lemons": 1, "Sugar": 0.02}),
    ("Mango Lassi", "Beverages", 4.0, 1.1, {"Mango pulp": 0.1, "Milk": 0.15, "Sugar": 0.01}),
    ("Cold Coffee", "Beverages", 4.5, 1.0, {"Coffee beans": 0.02, "Milk": 0.2, "Ice cream": 0.05}),
]
UNAVAILABLE = {"Cheesecake"}

STAFF = [
    ("Meera Nair", "Manager", "Morning", 3200), ("Arjun Das", "Chef", "Morning", 2600),
    ("Rohan Pillai", "Chef", "Evening", 2600), ("Sana Iqbal", "Chef", "Evening", 2400),
    ("Divya Menon", "Waiter", "Morning", 1500), ("Karthik Raj", "Waiter", "Morning", 1500),
    ("Anil Kumar", "Waiter", "Evening", 1500), ("Fatima Khan", "Waiter", "Evening", 1550),
    ("Joseph Mathew", "Waiter", "Evening", 1500), ("Lakshmi Iyer", "Cashier", "Morning", 1700),
    ("Vikram Singh", "Cashier", "Evening", 1700), ("Ravi Shankar", "Cleaner", "Night", 1200),
]
FIRST = ["Aarav", "Isha", "Neha", "Rahul", "Priya", "Sameer", "Tara", "Imran", "Anjali", "Dev",
         "Kavya", "Nikhil", "Pooja", "Suresh", "Zoya", "Harsh", "Ritu", "Manoj", "Asha", "Yash"]
LAST = ["Sharma", "Patel", "Reddy", "Nair", "Gupta", "Joshi", "Bose", "Menon", "Verma", "Kapoor"]


def seed_db(conn, now=None, days=60, rng_seed=42):
    """Fill an empty database. `now` is a datetime; orders run up to it."""
    now = now or datetime.now()
    rng = random.Random(rng_seed)
    today = now.date()
    conn.execute("BEGIN")

    inv_ids = {}
    for name, unit, stock, reorder, cost in INGREDIENTS:
        if name in PERISHABLE:
            expiry = (today + timedelta(days=rng.randint(2, 12))).isoformat()
        else:
            expiry = (today + timedelta(days=rng.randint(90, 300))).isoformat()
        cur = conn.execute(
            "INSERT INTO inventory (ingredient, unit, stock_qty, reorder_level, unit_cost, expiry_date) "
            "VALUES (?, ?, ?, ?, ?, ?)", (name, unit, stock, reorder, cost, expiry))
        inv_ids[name] = cur.lastrowid

    menu_ids, prices, weights = {}, {}, {}
    for name, cat, price, cost, recipe in MENU:
        cur = conn.execute(
            "INSERT INTO menu_items (name, category, price, cost, available) VALUES (?, ?, ?, ?, ?)",
            (name, cat, price, cost, 0 if name in UNAVAILABLE else 1))
        mid = cur.lastrowid
        menu_ids[name], prices[mid] = mid, price
        if name not in UNAVAILABLE:
            weights[mid] = rng.uniform(0.4, 2.0)
        for ing, amount in recipe.items():
            conn.execute("INSERT INTO recipes (menu_item_id, inventory_id, qty_per_item) VALUES (?, ?, ?)",
                         (mid, inv_ids[ing], amount))

    waiters = []
    for name, role, shift, salary in STAFF:
        hired = datetime(2019, 1, 1) + timedelta(days=rng.randint(0, 2300))
        cur = conn.execute(
            "INSERT INTO staff (name, role, shift, phone, salary, hire_date) VALUES (?, ?, ?, ?, ?, ?)",
            (name, role, shift, str(rng.randint(9000000000, 9999999999)), salary,
             hired.strftime("%Y-%m-%d")))
        if role == "Waiter":
            waiters.append(cur.lastrowid)

    table_ids = []
    for no, cap in enumerate([2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 8, 8], start=1):
        table_ids.append(conn.execute(
            "INSERT INTO tables (table_no, capacity, status) VALUES (?, ?, 'free')",
            (no, cap)).lastrowid)

    customer_ids, used = [], set()
    while len(customer_ids) < 40:
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        if name in used:
            continue
        used.add(name)
        membership = rng.choices(["none", "silver", "gold"], [60, 25, 15])[0]
        customer_ids.append(conn.execute(
            "INSERT INTO customers (name, phone, membership) VALUES (?, ?, ?)",
            (name, str(rng.randint(9000000000, 9999999999)), membership)).lastrowid)

    hours = list(range(10, 22))
    hour_weights = [1, 2, 5, 6, 3, 1, 1, 3, 6, 6, 3, 1]
    menu_pool = list(weights)
    pool_weights = [weights[m] for m in menu_pool]
    for back in range(days - 1, -1, -1):
        day = today - timedelta(days=back)
        count = rng.randint(14, 22) if day.weekday() >= 5 else rng.randint(8, 14)
        for _ in range(count):
            when = datetime(day.year, day.month, day.day, rng.choices(hours, hour_weights)[0],
                            rng.randint(0, 59), rng.randint(0, 59))
            if when > now:
                continue
            if back == 0 and when > now - timedelta(minutes=60):
                status = rng.choice(["open", "served"])
            else:
                status = "cancelled" if rng.random() < 0.03 else "paid"
            picked = set()
            for _ in range(rng.choice([1, 2, 2, 3, 3, 4])):
                picked.add(rng.choices(menu_pool, pool_weights)[0])
            items = [(m, rng.choice([1, 1, 1, 2, 3]), prices[m]) for m in sorted(picked)]
            customer = rng.choice(customer_ids) if rng.random() < 0.5 else None
            insert_order(conn, rng.choice(table_ids), customer, rng.choice(waiters), status,
                         when.strftime("%Y-%m-%d %H:%M:%S"), items)

    conn.execute("UPDATE tables SET status = 'occupied' WHERE id IN "
                 "(SELECT table_id FROM orders WHERE status IN ('open', 'served'))")
    conn.execute("COMMIT")


def write_sample_csvs(conn, folder=None):
    folder = folder or config.SAMPLE_DIR
    os.makedirs(folder, exist_ok=True)
    for name in csv_io.NAMES:
        fname = {"menu": "menu_items"}.get(name, name)
        with open(os.path.join(folder, f"{fname}.csv"), "w", newline="") as f:
            f.write(csv_io.export_csv(conn, name))


def reset(path=None):
    path = path or config.DB_PATH
    if os.path.exists(path):
        os.remove(path)
    conn = database.connect(path)
    database.init_schema(conn)
    seed_db(conn)
    write_sample_csvs(conn)
    conn.close()


if __name__ == "__main__":
    reset()
    print("Database and sample CSVs written to", os.path.join(config.BASE_DIR, "data"))
