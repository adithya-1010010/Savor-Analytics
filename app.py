import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template,
                   request, url_for)

import config
import database
from database import get_db
from models import orders as order_model
from models.base import friendly_error
from models.entities import ENTITIES
from services import analytics, csv_io, reports

ENTITY_NAMES = ",".join(ENTITIES)
IO_NAMES = ",".join(csv_io.NAMES)


def ensure_db(path):
    """Create and fill the database the first time the app runs."""
    fresh = not os.path.exists(path) or os.path.getsize(path) == 0
    conn = database.connect(path)
    database.init_schema(conn)
    if fresh:
        import seed
        seed.seed_db(conn)
    conn.close()


def parse_date(text, default):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return default


def create_app(db_path=None):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=config.SECRET_KEY, DB_PATH=db_path or config.DB_PATH,
                      MAX_CONTENT_LENGTH=5_000_000, MAX_FORM_MEMORY_SIZE=5_000_000)
    app.teardown_appcontext(database.close_db)
    ensure_db(app.config["DB_PATH"])

    # ---- template helpers ----
    @app.template_filter("fmt")
    def fmt(value, field):
        if value is None or value == "":
            return "-"
        if field.kind == "bool":
            return "Yes" if value else "No"
        if field.money:
            return f"{value:,.2f}"
        if field.kind == "float":
            return f"{value:g}"
        return value

    @app.template_filter("money")
    def money(value):
        return f"{value:,.2f}"

    @app.context_processor
    def helpers():
        def page_url(n):
            args = request.args.to_dict()
            args["page"] = n
            return url_for(request.endpoint, **{**(request.view_args or {}), **args})

        def sort_url(col):
            args = request.args.to_dict()
            flip = args.get("sort") == col and args.get("dir", "asc") == "asc"
            args.update(sort=col, dir="desc" if flip else "asc")
            args.pop("page", None)
            return url_for(request.endpoint, **{**(request.view_args or {}), **args})

        return {"page_url": page_url, "sort_url": sort_url, "entities": ENTITIES,
                "order_statuses": order_model.STATUSES}

    def list_url(slug):
        return url_for("orders_list") if slug == "orders" else url_for("entity_list", slug=slug)

    # ---- dashboard ----
    def dashboard_data():
        today = date.today()
        start = parse_date(request.args.get("start"), today - timedelta(days=29))
        end = parse_date(request.args.get("end"), today)
        if start > end:
            start, end = end, start
        return analytics.dashboard(get_db(), start, end, today)

    @app.route("/")
    def dashboard():
        data = dashboard_data()
        return render_template("dashboard.html", data=data)

    @app.route("/api/dashboard")
    def dashboard_api():
        return jsonify(dashboard_data())

    # ---- generic list / add / edit / delete for the five simple tables ----
    @app.route(f"/<any({ENTITY_NAMES}):slug>/")
    def entity_list(slug):
        ent, db = ENTITIES[slug], get_db()
        q = request.args.get("q", "").strip()
        filters = {n: request.args.get(n, "") for n in ent.filters}
        sort = request.args.get("sort", "")
        direction = request.args.get("dir", "asc")
        low = slug == "inventory" and request.args.get("low") == "1"
        where = "stock_qty <= reorder_level" if low else None
        page = max(1, request.args.get("page", 1, type=int))

        rows, total = ent.list(db, q, filters, sort, direction, page, config.PER_PAGE, where)
        pages = max(1, -(-total // config.PER_PAGE))
        if page > pages:
            page = pages
            rows, total = ent.list(db, q, filters, sort, direction, page, config.PER_PAGE, where)

        wastage = []
        if slug == "inventory":
            wastage = db.execute(
                "SELECT w.logged_at, i.ingredient, i.unit, w.qty, w.reason FROM wastage_log w "
                "JOIN inventory i ON i.id = w.inventory_id ORDER BY w.id DESC LIMIT 8").fetchall()
        return render_template("list.html", ent=ent, slug=slug, rows=rows, total=total,
                               page=page, pages=pages, q=q, filters=filters, low=low,
                               sort=sort, direction=direction, wastage=wastage)

    def entity_form(slug, rid):
        ent, db = ENTITIES[slug], get_db()
        record = None
        if rid is not None:
            record = ent.get(db, rid)
            if record is None:
                abort(404)
        errors = {}
        if request.method == "POST":
            clean, errors = ent.validate(request.form)
            if not errors:
                try:
                    if rid is None:
                        ent.insert(db, clean)
                    else:
                        ent.update(db, rid, clean)
                except sqlite3.IntegrityError as e:
                    errors["_"] = friendly_error(e)
                else:
                    flash(f"Saved {ent.singular}.", "success")
                    return redirect(url_for("entity_list", slug=slug))
            values = request.form
        else:
            values = dict(record) if record else {"available": 1}
        return render_template("form.html", ent=ent, slug=slug, record=record,
                               values=values, errors=errors)

    @app.route(f"/<any({ENTITY_NAMES}):slug>/new", methods=["GET", "POST"])
    def entity_new(slug):
        return entity_form(slug, None)

    @app.route(f"/<any({ENTITY_NAMES}):slug>/<int:rid>/edit", methods=["GET", "POST"])
    def entity_edit(slug, rid):
        return entity_form(slug, rid)

    @app.post(f"/<any({ENTITY_NAMES}):slug>/<int:rid>/delete")
    def entity_delete(slug, rid):
        ent = ENTITIES[slug]
        try:
            ent.delete(get_db(), rid)
        except sqlite3.IntegrityError:
            flash(f"Can't delete this {ent.singular}: it is used by other records "
                  "(orders, for example).", "danger")
        else:
            flash(f"Deleted {ent.singular}.", "success")
        return redirect(url_for("entity_list", slug=slug))

    # ---- inventory extras ----
    def positive_qty():
        try:
            qty = float(request.form.get("qty", ""))
        except ValueError:
            return None
        return qty if qty > 0 else None

    @app.post("/inventory/<int:rid>/restock")
    def inventory_restock(rid):
        qty, db = positive_qty(), get_db()
        if qty is None:
            flash("Enter a quantity above zero.", "danger")
        elif db.execute("UPDATE inventory SET stock_qty = stock_qty + ? WHERE id = ?",
                        (qty, rid)).rowcount == 0:
            abort(404)
        else:
            flash("Stock updated.", "success")
        return redirect(url_for("entity_list", slug="inventory"))

    @app.post("/inventory/<int:rid>/waste")
    def inventory_waste(rid):
        qty, db = positive_qty(), get_db()
        item = db.execute("SELECT stock_qty FROM inventory WHERE id = ?", (rid,)).fetchone()
        if item is None:
            abort(404)
        if qty is None:
            flash("Enter a quantity above zero.", "danger")
        elif qty > item["stock_qty"]:
            flash("You can't write off more than is in stock.", "danger")
        else:
            reason = request.form.get("reason", "").strip() or "not given"
            db.execute("BEGIN")
            db.execute("UPDATE inventory SET stock_qty = stock_qty - ? WHERE id = ?", (qty, rid))
            db.execute("INSERT INTO wastage_log (inventory_id, qty, reason, logged_at) "
                       "VALUES (?, ?, ?, ?)",
                       (rid, qty, reason, datetime.now().strftime("%Y-%m-%d %H:%M")))
            db.execute("COMMIT")
            flash("Wastage logged.", "success")
        return redirect(url_for("entity_list", slug="inventory"))

    # ---- orders ----
    @app.route("/orders/")
    def orders_list():
        q = request.args.get("q", "").strip()
        status = request.args.get("status", "")
        start, end = request.args.get("start", ""), request.args.get("end", "")
        page = max(1, request.args.get("page", 1, type=int))
        rows, total = order_model.list_orders(get_db(), q, status, start, end, page, config.PER_PAGE)
        pages = max(1, -(-total // config.PER_PAGE))
        return render_template("orders.html", rows=rows, total=total, page=page, pages=pages,
                               q=q, status=status, start=start, end=end)

    @app.route("/orders/new", methods=["GET", "POST"])
    def order_new():
        db = get_db()
        pairs = [("", "1")] * 3
        if request.method == "POST":
            pairs = list(zip(request.form.getlist("menu_item_id"), request.form.getlist("qty")))
            try:
                oid = order_model.create_order(
                    db, request.form.get("table_id", type=int),
                    request.form.get("customer_id", type=int),
                    request.form.get("staff_id", type=int), pairs)
            except order_model.OrderError as e:
                flash(str(e), "danger")
            else:
                flash("Order placed.", "success")
                return redirect(url_for("order_view", oid=oid))
        return render_template(
            "order_form.html", pairs=pairs, form=request.form,
            tables=db.execute("SELECT * FROM tables ORDER BY table_no").fetchall(),
            customers=db.execute("SELECT id, name FROM customers ORDER BY name").fetchall(),
            staff=db.execute("SELECT id, name FROM staff WHERE role IN ('Waiter', 'Manager') "
                             "ORDER BY name").fetchall(),
            menu=db.execute("SELECT id, name, price FROM menu_items WHERE available = 1 "
                            "ORDER BY category, name").fetchall())

    @app.route("/orders/<int:oid>")
    def order_view(oid):
        order, items = order_model.get_order(get_db(), oid)
        if order is None:
            abort(404)
        return render_template("order_detail.html", order=order, items=items)

    @app.post("/orders/<int:oid>/status")
    def order_status(oid):
        try:
            order_model.set_status(get_db(), oid, request.form.get("status", ""))
        except order_model.OrderError as e:
            flash(str(e), "danger")
        else:
            flash("Status updated.", "success")
        return redirect(url_for("order_view", oid=oid))

    @app.post("/orders/<int:oid>/delete")
    def order_delete(oid):
        order_model.delete_order(get_db(), oid)
        flash(f"Deleted order {oid}.", "success")
        return redirect(url_for("orders_list"))

    # ---- CSV import / export ----
    @app.route(f"/<any({IO_NAMES}):slug>/export.csv")
    def export_view(slug):
        body = csv_io.export_csv(get_db(), slug)
        return Response(body, mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={slug}.csv"})

    def import_page(slug, report=None, text=""):
        required, optional = csv_io.columns_info(slug)
        title = "Orders" if slug == "orders" else ENTITIES[slug].title
        return render_template("import.html", slug=slug, title=title, report=report, text=text,
                               required=required, optional=optional, back=list_url(slug))

    @app.route(f"/<any({IO_NAMES}):slug>/import", methods=["GET", "POST"])
    def import_view(slug):
        report, text = None, ""
        if request.method == "POST":
            file = request.files.get("file")
            if not file or not file.filename:
                flash("Choose a CSV file first.", "danger")
            else:
                try:
                    text = file.read().decode("utf-8-sig")
                except UnicodeDecodeError:
                    flash("That file isn't UTF-8 text.", "danger")
                else:
                    report = csv_io.run_import(get_db(), slug, text, commit=False)
        return import_page(slug, report, text)

    @app.post(f"/<any({IO_NAMES}):slug>/import/confirm")
    def import_confirm(slug):
        text = request.form.get("csv_text", "")
        report = csv_io.run_import(get_db(), slug, text, commit=True)
        if report["committed"]:
            flash(f"Imported {report['good']} rows.", "success")
            return redirect(list_url(slug))
        flash("Nothing was imported.", "danger")
        return import_page(slug, report, text)

    # ---- reports ----
    @app.route("/reports/")
    def reports_index():
        return render_template("reports.html", reports=reports.REPORTS)

    @app.route("/reports/<name>")
    def report_view(name):
        if name not in reports.REPORTS:
            abort(404)
        report = reports.build(get_db(), name, request.args)
        if request.args.get("format") == "csv":
            return Response(reports.to_csv(report), mimetype="text/csv",
                            headers={"Content-Disposition": f"attachment; filename={name}.csv"})
        return render_template("report.html", report=report, name=name)

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
