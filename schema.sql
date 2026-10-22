CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    price REAL NOT NULL CHECK (price >= 0),
    cost REAL NOT NULL CHECK (cost >= 0),
    available INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    shift TEXT NOT NULL,
    phone TEXT NOT NULL,
    salary REAL NOT NULL CHECK (salary >= 0),
    hire_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_no INTEGER NOT NULL UNIQUE,
    capacity INTEGER NOT NULL CHECK (capacity > 0),
    status TEXT NOT NULL DEFAULT 'free'
);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    membership TEXT NOT NULL DEFAULT 'none'
);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient TEXT NOT NULL UNIQUE,
    unit TEXT NOT NULL,
    stock_qty REAL NOT NULL CHECK (stock_qty >= 0),
    reorder_level REAL NOT NULL CHECK (reorder_level >= 0),
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
    expiry_date TEXT
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES tables(id),
    customer_id INTEGER REFERENCES customers(id),
    staff_id INTEGER NOT NULL REFERENCES staff(id),
    status TEXT NOT NULL DEFAULT 'open',
    order_time TEXT NOT NULL,
    total REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
    qty INTEGER NOT NULL CHECK (qty > 0),
    price REAL NOT NULL
);

-- how much of each ingredient one portion of a menu item uses
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    menu_item_id INTEGER NOT NULL REFERENCES menu_items(id) ON DELETE CASCADE,
    inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    qty_per_item REAL NOT NULL CHECK (qty_per_item > 0),
    UNIQUE (menu_item_id, inventory_id)
);

CREATE TABLE IF NOT EXISTS wastage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
    qty REAL NOT NULL CHECK (qty > 0),
    reason TEXT NOT NULL,
    logged_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_time ON orders(order_time);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
