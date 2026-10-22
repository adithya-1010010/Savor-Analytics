# Project Plan — Restaurant Management System

## 1. Overview

A Python-based interactive web application for managing a restaurant: menu, staff, tables, customers, inventory, and orders — with analytics dashboards, CSV import/export, and printable reports. Accessible via web browser, demonstrating course concepts end-to-end.

- **Theme:** Restaurant Management System ("Savor Analytics")
- **SDG Alignment:** SDG 2 (Zero Hunger — efficient food service & waste reduction), SDG 12 (Responsible Consumption — inventory/waste control), SDG 8 (Decent Work — staff & earnings analytics)
- **Data:** SQLite database (primary) + sample CSV datasets + CSV import/export

## 2. Learning Objectives Demonstrated

Python data types & structures, functions, OOP (models/services), file I/O, CSV parsing, SQL + SQLite (CRUD, JOINs, aggregation), pandas analysis, Flask routing/templates/forms/sessions, HTML/CSS/JS with Chart.js + Bootstrap, error handling, and testing.

## 3. Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.10+ |
| Web framework | Flask + Jinja2 templates |
| Database | SQLite (stdlib `sqlite3`) |
| Data analysis | pandas |
| Charts | Chart.js (CDN) |
| UI | Bootstrap 5 (CDN), custom CSS |
| Extras | matplotlib (optional PNG chart export), pytest |

## 4. Features (Modules)

1. **Data Management (CRUD)** — menu items, staff, tables, customers, inventory, orders with validation and friendly error messages.
2. **CSV Import/Export** — import each entity from CSV (header validation, preview, per-row error report); export any table to CSV; sample CSVs included.
3. **Analytics Dashboard** — KPIs (today's revenue, order count, avg order value, low-stock alerts, top item) + Chart.js charts: daily revenue line, category-share pie, top-selling bar, orders-by-hour, staff performance; date-range filter.
4. **Inventory Management** — stock levels, reorder alerts, restock action, wastage logging.
5. **Reporting** — daily sales report, low-stock report, top sellers, staff performance; print-friendly HTML + CSV export.
6. **Search / Filter / Pagination** — on all list pages.

## 5. Database Design (SQLite)

```
menu_items(id, name, category, price, cost, available)
staff(id, name, role, shift, phone, salary, hire_date)
tables(id, table_no, capacity, status)
customers(id, name, phone, membership)
inventory(id, ingredient, unit, stock_qty, reorder_level, unit_cost, expiry_date)
orders(id, table_id, customer_id, staff_id, status, order_time, total)
order_items(id, order_id, menu_item_id, qty, price)
```

Relationships: orders → order_items → menu_items (1:N); orders → tables/customers/staff (N:1). Analytics via SQL aggregation + pandas.

## 6. Project Structure

```
restaurant-app/
├── app.py                 # Flask entry point + route registration
├── config.py              # app config (DB path, constants)
├── database.py            # connection helper, schema init, seed loader
├── schema.sql             # SQLite DDL
├── seed.py                # sample data generator (DB + CSV files)
├── models/                # data-access classes (menu.py, staff.py, ...)
├── services/              # analytics.py, reports.py, csv_io.py
├── templates/             # base.html, dashboard.html, *_list.html, *_form.html, reports.html
├── static/                # css/style.css, js/dashboard.js
├── data/                  # restaurant.db + sample/*.csv
├── tests/                 # test_app.py, test_analytics.py
├── requirements.txt
└── plan.md, README.md
```

## 7. Development Phases

| Phase | Tasks | Done When |
|---|---|---|
| 1. Setup | Flask skeleton, config, virtualenv, requirements | `python app.py` serves a page |
| 2. DB + seed | schema.sql, database.py, seed.py, sample CSVs | DB populated, CSVs valid |
| 3. CRUD modules | menu, staff, tables, customers, inventory, orders (list/form/delete) | all entities manageable in UI |
| 4. CSV IO | import w/ validation + error report; export | round-trip import/export works |
| 5. Orders flow | place order → order_items → total calc → stock check | order updates inventory & totals |
| 6. Dashboard | KPIs + 5 Chart.js charts + filters | charts render with real data |
| 7. Reports | 4 report pages, print + CSV export | reports correct & printable |
| 8. Polish | Bootstrap styling, validation, empty states, seed re-set | consistent UI, no broken flows |
| 9. Tests + docs | pytest suite, README, final demo walkthrough | `pytest` passes; README complete |

## 8. Test Plan

Unit tests for CSV import edge cases, order total calculation, stock deduction; route smoke tests (status codes); analytics aggregation sanity checks vs. known seed data.

## 9. Deliverables

- Run with `python app.py` (http://localhost:5000); complete `plan.md` + `README.md`; sample datasets; tests.

## 10. Risks & Mitigations

- **Order/inventory consistency** → transactions in a single DB connection, stock check before insert.
- **Bad CSV uploads** → header validation + per-row error report, no partial commits.
- **Chart.js CDN offline** → fallback to server-rendered summary tables.
