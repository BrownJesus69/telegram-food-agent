import sqlite3
from datetime import datetime, timezone

import config

DB_PATH = config.DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    telegram_id INTEGER PRIMARY KEY,
    name TEXT, latitude REAL, longitude REAL, address TEXT,
    awaiting TEXT, landmark TEXT, pending_key TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS cart(
    telegram_id INTEGER NOT NULL,
    restaurant_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    qty INTEGER NOT NULL,
    PRIMARY KEY(telegram_id, item_id)
);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    customer_name TEXT,
    restaurant_id TEXT NOT NULL,
    status TEXT NOT NULL,
    subtotal INTEGER NOT NULL,
    delivery_fee INTEGER NOT NULL,
    total INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT,
    landmark TEXT,
    eta_min INTEGER, eta_max INTEGER,
    payment_method TEXT NOT NULL DEFAULT 'COD',
    confirmation_key TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS order_items(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    item_name TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price INTEGER NOT NULL,
    FOREIGN KEY(order_id) REFERENCES orders(id)
);
CREATE TABLE IF NOT EXISTS order_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL, status TEXT NOT NULL, note TEXT, at TEXT NOT NULL
);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = connect()
    with conn:
        conn.executescript(SCHEMA)
    conn.close()


def upsert_user(tg_id, name):
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO users(telegram_id, name, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at",
            (tg_id, name, now()),
        )
    conn.close()


def get_user(tg_id):
    conn = connect()
    row = conn.execute("SELECT * FROM users WHERE telegram_id=?", (tg_id,)).fetchone()
    conn.close()
    return row


def set_location(tg_id, lat, lon, address):
    conn = connect()
    with conn:
        conn.execute(
            "UPDATE users SET latitude=?, longitude=?, address=?, updated_at=? WHERE telegram_id=?",
            (lat, lon, address, now(), tg_id),
        )
    conn.close()


ALLOWED_FIELDS = {"awaiting", "landmark", "pending_key"}


def set_field(tg_id, **kwargs):
    for k in kwargs:
        if k not in ALLOWED_FIELDS:
            raise ValueError(k)
    sets = ", ".join(f"{k}=?" for k in kwargs)
    conn = connect()
    with conn:
        conn.execute(f"UPDATE users SET {sets} WHERE telegram_id=?", (*kwargs.values(), tg_id))
    conn.close()
