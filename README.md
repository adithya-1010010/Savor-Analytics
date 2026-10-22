# Savor Analytics

A restaurant management web app built with Flask and SQLite. It manages the menu, staff, tables, customers, inventory and orders, and shows sales charts and printable reports.

## Setup

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000. The first run creates `data/restaurant.db` and fills it with about 60 days of sample orders. To wipe it and start again, run `python seed.py`. That also rewrites the sample CSV files in `data/sample/`.

The charts use Chart.js and the layout uses Bootstrap, both loaded from a CDN. Without internet the pages still work and the dashboard shows tables instead of charts.

## What's in it

- **Menu, staff, tables, customers, inventory**: list, add, edit, delete. Every list has search, filters, sortable columns and pagination.
- **Orders**: pick a table, a waiter and the items. The order total is worked out from menu prices, and the ingredients used (set per menu item in the `recipes` table) are taken out of stock. If anything is short, the order is refused and nothing changes. Cancelling an order puts the ingredients back.
- **Inventory**: low-stock flag, restock, and wastage logging.
- **CSV import and export**: every table can be exported. Import checks the header and every row first and shows the problems by line number. Nothing is saved unless every row is fine. Exported files can be imported again.
- **Dashboard**: today's revenue, order count, average order, low-stock count, top item, and five charts, with a date range filter. Cancelled orders are left out.
- **Reports**: daily sales, low stock, top sellers, staff performance. Each can be printed or downloaded as CSV.

## Orders CSV format

Items go in one cell as `menu_id:qty:price`, separated by semicolons, for example `3:2:12.0;7:1:4.5`. The price is optional and defaults to the current menu price. Importing orders doesn't change stock. If the `id` already exists, that order is replaced.

## Tests

```
pytest
```

(`python -m unittest discover -s tests -t .` also works.) The tests cover CSV import edge cases, order totals, stock deduction and rollback, every page's status code, and the dashboard numbers against a small known data set and against plain SQL.

## Layout

```
app.py            routes
config.py         paths and constants
database.py       connection helper
schema.sql        tables
seed.py           sample data and CSVs
models/           base.py (generic CRUD), entities.py (the five simple tables), orders.py
services/         analytics.py, reports.py, csv_io.py
templates/        pages
static/           css and the dashboard script
data/sample/      sample CSVs
tests/
```

## Differences from plan.md

- Two extra tables: `recipes` (ingredients per menu item, needed to deduct stock) and `wastage_log`.
- The five simple tables share one generic model in `models/base.py` instead of five separate files.
- The optional matplotlib PNG export isn't included.
