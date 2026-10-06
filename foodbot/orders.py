import sqlite3

from foodbot import db
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km
from foodbot.services.eta import estimate_eta


class OrderError(Exception):
    pass


FLOW = {
    "PENDING": {"ACCEPTED", "REJECTED", "CANCELLED"},
    "ACCEPTED": {"PREPARING"},
    "PREPARING": {"OUT_FOR_DELIVERY"},
    "OUT_FOR_DELIVERY": {"DELIVERED"},
}


def add_item(tg_id, item_id, qty=1, replace=False):
    it = catalogue.ITEMS[item_id]
    conn = db.connect()
    try:
        with conn:
            cur = conn.execute("SELECT restaurant_id FROM cart WHERE telegram_id=? LIMIT 1", (tg_id,)).fetchone()
            if cur and cur["restaurant_id"] != it.restaurant_id:
                if not replace:
                    return "conflict"
                conn.execute("DELETE FROM cart WHERE telegram_id=?", (tg_id,))
            conn.execute(
                "INSERT INTO cart(telegram_id, restaurant_id, item_id, qty) VALUES(?,?,?,?) "
                "ON CONFLICT(telegram_id, item_id) DO UPDATE SET qty=MIN(10, qty+excluded.qty)",
                (tg_id, it.restaurant_id, item_id, qty),
            )
        return "ok"
    finally:
        conn.close()


def change_qty(tg_id, item_id, delta):
    conn = db.connect()
    try:
        with conn:
            conn.execute("UPDATE cart SET qty=MIN(10, qty+?) WHERE telegram_id=? AND item_id=?", (delta, tg_id, item_id))
            conn.execute("DELETE FROM cart WHERE telegram_id=? AND qty<=0", (tg_id,))
    finally:
        conn.close()


def clear_cart(tg_id):
    conn = db.connect()
    with conn:
        conn.execute("DELETE FROM cart WHERE telegram_id=?", (tg_id,))
    conn.close()


def cart_summary(tg_id):
    conn = db.connect()
    rows = conn.execute(
        "SELECT item_id, restaurant_id, qty FROM cart WHERE telegram_id=? ORDER BY rowid", (tg_id,)
    ).fetchall()
    conn.close()
    if not rows:
        return None
    rest = catalogue.RESTAURANTS.get(rows[0]["restaurant_id"])
    user = db.get_user(tg_id)
    issues, lines, subtotal = [], [], 0
    for r in rows:
        it = catalogue.ITEMS.get(r["item_id"])
        if not it or not it.available:
            issues.append("An item in your cart is no longer available.")
            continue
        amount = it.price * r["qty"]
        subtotal += amount
        lines.append({"item_id": it.id, "name": it.name, "qty": r["qty"], "unit": it.price, "amount": amount})
    if rest is None:
        issues.append("Restaurant not found.")
        return {"issues": issues, "lines": lines}
    if not rest.open_at():
        issues.append(f"{rest.name} is currently closed (open {rest.hours_label}).")
    dist = None
    eta = (0, 0)
    if not user or user["latitude"] is None:
        issues.append("Share your location first.")
    else:
        dist = haversine_km(user["latitude"], user["longitude"], rest.lat, rest.lon)
        if dist > rest.radius_km:
            issues.append(f"You are outside {rest.name}'s delivery area.")
        eta = estimate_eta(dist, rest.prep_min)
    if subtotal < rest.min_order:
        issues.append(f"{rest.name} has a minimum order of ₹{rest.min_order} (your items: ₹{subtotal}).")
    return {
        "rest": rest, "lines": lines, "subtotal": subtotal, "fee": rest.delivery_fee,
        "total": subtotal + rest.delivery_fee, "dist": dist, "eta": eta, "issues": issues,
    }


def create_order(tg_id, key):
    conn = db.connect()
    existing = conn.execute("SELECT id FROM orders WHERE confirmation_key=?", (key,)).fetchone()
    conn.close()
    if existing:
        return existing["id"], False
    user = db.get_user(tg_id)
    if not user or user["pending_key"] != key:
        raise OrderError("This checkout has expired. Please open your cart again.")
    s = cart_summary(tg_id)
    if not s or s["issues"] or not s["lines"]:
        raise OrderError((s or {}).get("issues", ["Your cart is empty."])[0] if s else "Your cart is empty.")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        dup = conn.execute("SELECT id FROM orders WHERE confirmation_key=?", (key,)).fetchone()
        if dup:
            conn.execute("ROLLBACK")
            return dup["id"], False
        ts = db.now()
        cur = conn.execute(
            "INSERT INTO orders(customer_id, customer_name, restaurant_id, status, subtotal, delivery_fee, total,"
            " latitude, longitude, address, landmark, eta_min, eta_max, payment_method, confirmation_key,"
            " created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tg_id, user["name"], s["rest"].id, "PENDING", s["subtotal"], s["fee"], s["total"],
             user["latitude"], user["longitude"], user["address"], user["landmark"],
             s["eta"][0], s["eta"][1], "COD", key, ts, ts),
        )
        oid = cur.lastrowid
        for ln in s["lines"]:
            conn.execute(
                "INSERT INTO order_items(order_id, item_id, item_name, quantity, unit_price) VALUES(?,?,?,?,?)",
                (oid, ln["item_id"], ln["name"], ln["qty"], ln["unit"]),
            )
        conn.execute("INSERT INTO order_log(order_id, status, note, at) VALUES(?,?,?,?)", (oid, "PENDING", None, ts))
        conn.execute("DELETE FROM cart WHERE telegram_id=?", (tg_id,))
        conn.execute("UPDATE users SET pending_key=NULL, awaiting=NULL, landmark=NULL WHERE telegram_id=?", (tg_id,))
        conn.execute("COMMIT")
        return oid, True
    except sqlite3.IntegrityError:
        conn.execute("ROLLBACK")
        row = conn.execute("SELECT id FROM orders WHERE confirmation_key=?", (key,)).fetchone()
        if row:
            return row["id"], False
        raise
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def get_order(order_id):
    conn = db.connect()
    order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    items = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    conn.close()
    return order, items


def transition(order_id, new_status, note=None):
    conn = db.connect()
    try:
        with conn:
            row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not row:
                raise OrderError("Order not found.")
            if new_status not in FLOW.get(row["status"], set()):
                raise OrderError(f"Cannot move order from {row['status']} to {new_status}.")
            ts = db.now()
            conn.execute("UPDATE orders SET status=?, updated_at=? WHERE id=?", (new_status, ts, order_id))
            conn.execute("INSERT INTO order_log(order_id, status, note, at) VALUES(?,?,?,?)",
                         (order_id, new_status, note, ts))
        return row
    finally:
        conn.close()


def recent_orders(limit=10):
    conn = db.connect()
    rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return rows
