import os
import sqlite3

from flask import current_app, g

import config


def connect(path=None):
    """Open a connection. Autocommit is on, so code that needs a
    transaction issues BEGIN / COMMIT / ROLLBACK itself."""
    path = path or config.DB_PATH
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn):
    with open(os.path.join(config.BASE_DIR, "schema.sql")) as f:
        conn.executescript(f.read())


def get_db():
    if "db" not in g:
        g.db = connect(current_app.config["DB_PATH"])
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
