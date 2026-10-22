from .base import Entity, Field

PHONE = r"^[0-9+\-\s()]{7,15}$"

CATEGORIES = ["Starters", "Mains", "Sides", "Desserts", "Beverages"]
ROLES = ["Manager", "Chef", "Waiter", "Cashier", "Cleaner"]
SHIFTS = ["Morning", "Evening", "Night"]
TABLE_STATUS = ["free", "occupied", "reserved"]
MEMBERSHIPS = ["none", "silver", "gold"]
UNITS = ["kg", "g", "l", "ml", "pcs"]

menu = Entity(
    "menu", "menu_items", "Menu", "menu item",
    [
        Field("name"),
        Field("category", kind="choice", choices=CATEGORIES),
        Field("price", kind="float", minimum=0, money=True),
        Field("cost", kind="float", minimum=0, money=True),
        Field("available", kind="bool", required=False),
    ],
    search=["name", "category"], filters=["category"], order="name",
)

staff = Entity(
    "staff", "staff", "Staff", "staff member",
    [
        Field("name"),
        Field("role", kind="choice", choices=ROLES),
        Field("shift", kind="choice", choices=SHIFTS),
        Field("phone", pattern=PHONE),
        Field("salary", kind="float", minimum=0, money=True),
        Field("hire_date", kind="date"),
    ],
    search=["name", "role", "phone"], filters=["role", "shift"], order="name",
)

tables = Entity(
    "tables", "tables", "Tables", "table",
    [
        Field("table_no", label="Table no", kind="int", minimum=1),
        Field("capacity", kind="int", minimum=1),
        Field("status", kind="choice", choices=TABLE_STATUS),
    ],
    search=["table_no", "status"], filters=["status"], order="table_no",
)

customers = Entity(
    "customers", "customers", "Customers", "customer",
    [
        Field("name"),
        Field("phone", required=False, pattern=PHONE),
        Field("membership", kind="choice", choices=MEMBERSHIPS),
    ],
    search=["name", "phone"], filters=["membership"], order="name",
)

inventory = Entity(
    "inventory", "inventory", "Inventory", "ingredient",
    [
        Field("ingredient"),
        Field("unit", kind="choice", choices=UNITS),
        Field("stock_qty", label="Stock", kind="float", minimum=0),
        Field("reorder_level", label="Reorder level", kind="float", minimum=0),
        Field("unit_cost", label="Unit cost", kind="float", minimum=0, money=True),
        Field("expiry_date", label="Expiry date", kind="date", required=False),
    ],
    search=["ingredient"], filters=["unit"], order="ingredient",
)

ENTITIES = {e.slug: e for e in [menu, staff, tables, customers, inventory]}
