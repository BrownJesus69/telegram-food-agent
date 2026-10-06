import json
import sqlite3
from datetime import datetime, timezone

from foodbot import config

DB_PATH = config.DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    telegram_id INTEGER PRIMARY KEY,
    name TEXT, latitude REAL, longitude REAL, address TEXT,
    awaiting TEXT, landmark TEXT, pending_key TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS addresses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    address TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    recipient_name TEXT,
    recipient_phone TEXT,
    deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_addresses_user ON addresses(telegram_id, deleted);
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
CREATE TABLE IF NOT EXISTS order_courier(
    order_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL, vehicle TEXT NOT NULL, phone TEXT NOT NULL, rating REAL NOT NULL,
    assigned_at TEXT NOT NULL,
    pickup_at TEXT, travel_s REAL,
    live_chat_id INTEGER, live_message_id INTEGER, live_stopped INTEGER NOT NULL DEFAULT 0,
    last_edit_at TEXT, milestone INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(order_id) REFERENCES orders(id)
);
CREATE TABLE IF NOT EXISTS order_messages(
    order_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, kind TEXT NOT NULL,
    PRIMARY KEY(order_id, chat_id, kind)
);
CREATE TABLE IF NOT EXISTS order_log(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL, status TEXT NOT NULL, note TEXT, at TEXT NOT NULL
);
"""

# Columns added after the first release; applied to databases created by older versions.
MIGRATIONS = {
    "users": {"active_address_id": "INTEGER", "draft": "TEXT"},
    "orders": {"address_label": "TEXT", "recipient_name": "TEXT", "recipient_phone": "TEXT", "rating": "INTEGER",
               "delivered_at": "TEXT"},
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = connect()
    with conn:
        conn.executescript(SCHEMA)
        for table, cols in MIGRATIONS.items():
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col, ddl in cols.items():
                if col not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        # users from before the address book: turn their single saved location into an address
        legacy = conn.execute(
            "SELECT telegram_id, name, latitude, longitude, address FROM users "
            "WHERE latitude IS NOT NULL AND active_address_id IS NULL"
        ).fetchall()
        for u in legacy:
            ts = now()
            cur = conn.execute(
                "INSERT INTO addresses(telegram_id,label,address,latitude,longitude,recipient_name,created_at,updated_at)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (u["telegram_id"], "Current location", u["address"] or "Shared location", u["latitude"], u["longitude"],
                 u["name"], ts, ts),
            )
            conn.execute("UPDATE users SET active_address_id=? WHERE telegram_id=?", (cur.lastrowid, u["telegram_id"]))
    conn.close()


# ----------------------------------------------------------------------------- users
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


def get_draft(tg_id) -> dict:
    user = get_user(tg_id)
    try:
        return json.loads(user["draft"]) if user and user["draft"] else {}
    except (ValueError, TypeError):
        return {}


def set_draft(tg_id, draft: dict | None):
    conn = connect()
    with conn:
        conn.execute("UPDATE users SET draft=? WHERE telegram_id=?", (json.dumps(draft) if draft else None, tg_id))
    conn.close()


# -------------------------------------------------------------------------- addresses
def list_addresses(tg_id):
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM addresses WHERE telegram_id=? AND deleted=0 ORDER BY id", (tg_id,)
    ).fetchall()
    conn.close()
    return rows


def get_address(address_id, tg_id=None):
    conn = connect()
    sql, args = "SELECT * FROM addresses WHERE id=? AND deleted=0", [address_id]
    if tg_id is not None:
        sql += " AND telegram_id=?"
        args.append(tg_id)
    row = conn.execute(sql, args).fetchone()
    conn.close()
    return row


def get_active_address(tg_id):
    conn = connect()
    row = conn.execute(
        "SELECT a.* FROM users u JOIN addresses a ON a.id=u.active_address_id "
        "WHERE u.telegram_id=? AND a.deleted=0",
        (tg_id,),
    ).fetchone()
    conn.close()
    return row


def location_of(tg_id):
    """(lat, lon) of the active delivery address, or None."""
    a = get_active_address(tg_id)
    return (a["latitude"], a["longitude"]) if a else None


def add_address(tg_id, label, address, lat, lon, recipient_name=None, recipient_phone=None, activate=True):
    """Save an address. Re-using a label (e.g. 'Home') replaces that address instead of duplicating it."""
    ts = now()
    conn = connect()
    try:
        with conn:
            existing = conn.execute(
                "SELECT id FROM addresses WHERE telegram_id=? AND deleted=0 AND lower(label)=lower(?)", (tg_id, label)
            ).fetchone()
            if existing:
                aid = existing["id"]
                conn.execute(
                    "UPDATE addresses SET address=?, latitude=?, longitude=?, recipient_name=?, recipient_phone=?, updated_at=? WHERE id=?",
                    (address, lat, lon, recipient_name, recipient_phone, ts, aid),
                )
            else:
                aid = conn.execute(
                    "INSERT INTO addresses(telegram_id,label,address,latitude,longitude,recipient_name,recipient_phone,created_at,updated_at)"
                    " VALUES(?,?,?,?,?,?,?,?,?)",
                    (tg_id, label, address, lat, lon, recipient_name, recipient_phone, ts, ts),
                ).lastrowid
            if activate:
                conn.execute("UPDATE users SET active_address_id=?, updated_at=? WHERE telegram_id=?", (aid, ts, tg_id))
        return aid
    finally:
        conn.close()


def set_location(tg_id, lat, lon, address):
    """Compatibility shim: store a shared pin as the 'Current location' address and make it active."""
    user = get_user(tg_id)
    return add_address(tg_id, "Current location", address or "Shared location", lat, lon, user["name"] if user else None)


def set_active_address(tg_id, address_id) -> bool:
    if not get_address(address_id, tg_id):
        return False
    conn = connect()
    with conn:
        conn.execute("UPDATE users SET active_address_id=?, updated_at=? WHERE telegram_id=?", (address_id, now(), tg_id))
    conn.close()
    return True


def delete_address(tg_id, address_id) -> bool:
    if not get_address(address_id, tg_id):
        return False
    conn = connect()
    with conn:
        conn.execute("UPDATE addresses SET deleted=1, updated_at=? WHERE id=? AND telegram_id=?", (now(), address_id, tg_id))
        conn.execute(
            "UPDATE users SET active_address_id=NULL WHERE telegram_id=? AND active_address_id=?", (tg_id, address_id)
        )
    conn.close()
    return True


def update_recipient(tg_id, address_id, name, phone) -> bool:
    if not get_address(address_id, tg_id):
        return False
    conn = connect()
    with conn:
        conn.execute(
            "UPDATE addresses SET recipient_name=?, recipient_phone=?, updated_at=? WHERE id=? AND telegram_id=?",
            (name, phone, now(), address_id, tg_id),
        )
    conn.close()
    return True


# ------------------------------------------------------------------------ fulfilment
COURIER_FIELDS = {"pickup_at", "travel_s", "live_chat_id", "live_message_id", "live_stopped", "last_edit_at", "milestone"}


def insert_courier(order_id, name, vehicle, phone, rating):
    conn = connect()
    with conn:
        conn.execute(
            "INSERT OR IGNORE INTO order_courier(order_id,name,vehicle,phone,rating,assigned_at) VALUES(?,?,?,?,?,?)",
            (order_id, name, vehicle, phone, rating, now()),
        )
    conn.close()


def get_courier(order_id):
    conn = connect()
    row = conn.execute("SELECT * FROM order_courier WHERE order_id=?", (order_id,)).fetchone()
    conn.close()
    return row


def update_courier(order_id, **fields):
    for k in fields:
        if k not in COURIER_FIELDS:
            raise ValueError(k)
    sets = ", ".join(f"{k}=?" for k in fields)
    conn = connect()
    with conn:
        conn.execute(f"UPDATE order_courier SET {sets} WHERE order_id=?", (*fields.values(), order_id))
    conn.close()


def save_order_message(order_id, chat_id, message_id, kind):
    conn = connect()
    with conn:
        conn.execute(
            "INSERT INTO order_messages(order_id,chat_id,message_id,kind) VALUES(?,?,?,?) "
            "ON CONFLICT(order_id,chat_id,kind) DO UPDATE SET message_id=excluded.message_id",
            (order_id, chat_id, message_id, kind),
        )
    conn.close()


def order_messages(order_id, kind):
    conn = connect()
    rows = conn.execute("SELECT chat_id, message_id FROM order_messages WHERE order_id=? AND kind=?", (order_id, kind)).fetchall()
    conn.close()
    return rows
