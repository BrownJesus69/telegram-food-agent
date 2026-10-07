import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

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


MAX_QTY = 10


def clamp_qty(qty) -> int:
    """Quantities arrive in callback data, which a hostile client can forge: always bound them before they touch the cart."""
    try:
        return max(1, min(MAX_QTY, int(qty)))
    except (TypeError, ValueError):
        return 1


def add_item(tg_id, item_id, qty=1, replace=False):
    it = catalogue.ITEMS.get(item_id)
    if it is None or not it.available:
        raise OrderError("That item is no longer available.")
    qty = clamp_qty(qty)
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


def replace_cart(tg_id, lines):
    """Atomically make the cart exactly `lines` ([(item_id, qty)], one restaurant). Returns True if it replaced other items."""
    items = [(catalogue.ITEMS[i], max(1, min(10, int(q)))) for i, q in lines]
    if not items or len({it.restaurant_id for it, _ in items}) != 1:
        raise OrderError("A cart can only hold items from one restaurant.")
    conn = db.connect()
    try:
        with conn:
            had = conn.execute("SELECT COUNT(*) AS n FROM cart WHERE telegram_id=?", (tg_id,)).fetchone()["n"]
            conn.execute("DELETE FROM cart WHERE telegram_id=?", (tg_id,))
            for it, qty in items:
                conn.execute("INSERT INTO cart(telegram_id, restaurant_id, item_id, qty) VALUES(?,?,?,?)",
                             (tg_id, it.restaurant_id, it.id, qty))
        return bool(had)
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
    addr = db.get_active_address(tg_id)
    issues, lines, subtotal = [], [], 0
    for r in rows:
        it = catalogue.ITEMS.get(r["item_id"])
        if not it or not it.available:
            issues.append("An item in your cart is no longer available.")
            continue
        qty = clamp_qty(r["qty"])               # backstop: whatever is in the table, an order line is 1..10 units
        amount = it.price * qty
        subtotal += amount
        lines.append({"item_id": it.id, "name": it.name, "qty": qty, "unit": it.price, "amount": amount})
    if rest is None:
        issues.append("Restaurant not found.")
        return {"issues": issues, "lines": lines}
    if not rest.open_at():
        issues.append(f"{rest.name} is currently closed (open {rest.hours_label}).")
    dist = None
    eta = (0, 0)
    if not addr:
        issues.append("Choose a delivery address first.")
    else:
        dist = haversine_km(addr["latitude"], addr["longitude"], rest.lat, rest.lon)
        if dist > rest.radius_km:
            issues.append(
                f"{rest.name} doesn't deliver to {addr['label']} ({dist:.1f} km away, limit {rest.radius_km:g} km). "
                "Change the address or search again."
            )
        eta = estimate_eta(dist, rest.prep_min)
    if subtotal < rest.min_order:
        issues.append(f"{rest.name} has a minimum order of ₹{rest.min_order} (your items: ₹{subtotal}).")
    return {
        "rest": rest, "lines": lines, "subtotal": subtotal, "fee": rest.delivery_fee,
        "total": subtotal + rest.delivery_fee, "dist": dist, "eta": eta, "issues": issues, "address": addr,
    }


def create_order(tg_id, key):
    conn = db.connect()
    existing = conn.execute("SELECT id FROM orders WHERE confirmation_key=? AND customer_id=?", (key, tg_id)).fetchone()
    conn.close()
    if existing:
        return existing["id"], False
    user = db.get_user(tg_id)
    if not user or user["pending_key"] != key:
        raise OrderError("This checkout has expired. Please open your cart again.")
    s = cart_summary(tg_id)
    addr = s.get("address") if s else None
    if not s or s["issues"] or not s["lines"] or not addr:
        raise OrderError((s or {}).get("issues", ["Your cart is empty."])[0] if s else "Your cart is empty.")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        dup = conn.execute("SELECT id FROM orders WHERE confirmation_key=? AND customer_id=?", (key, tg_id)).fetchone()
        if dup:
            conn.execute("ROLLBACK")
            return dup["id"], False
        ts = db.now()
        cur = conn.execute(
            "INSERT INTO orders(customer_id, customer_name, restaurant_id, status, subtotal, delivery_fee, total,"
            " latitude, longitude, address, landmark, eta_min, eta_max, payment_method, confirmation_key,"
            " created_at, updated_at, address_label, recipient_name, recipient_phone)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (tg_id, user["name"], s["rest"].id, "PENDING", s["subtotal"], s["fee"], s["total"],
             addr["latitude"], addr["longitude"], addr["address"], user["landmark"],
             s["eta"][0], s["eta"][1], "COD", key, ts, ts,
             addr["label"], addr["recipient_name"] or user["name"], addr["recipient_phone"]),
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
        row = conn.execute("SELECT id FROM orders WHERE confirmation_key=? AND customer_id=?", (key, tg_id)).fetchone()
        if row:
            return row["id"], False
        raise OrderError("This checkout has expired. Please open your cart again.") from None
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
            conn.execute("UPDATE orders SET status=?, updated_at=?, delivered_at=CASE WHEN ?='DELIVERED' THEN ? ELSE delivered_at END WHERE id=?",
                         (new_status, ts, new_status, ts, order_id))
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


ACTIVE = ("PENDING", "ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY")


def active_orders():
    conn = db.connect()
    rows = conn.execute(
        f"SELECT * FROM orders WHERE status IN ({','.join('?' * len(ACTIVE))}) ORDER BY id", ACTIVE
    ).fetchall()
    conn.close()
    return rows


def orders_of(customer_id, limit=5):
    conn = db.connect()
    rows = conn.execute("SELECT * FROM orders WHERE customer_id=? ORDER BY id DESC LIMIT ?", (customer_id, limit)).fetchall()
    conn.close()
    return rows


def order_log(order_id):
    conn = db.connect()
    rows = conn.execute("SELECT status, note, at FROM order_log WHERE order_id=? ORDER BY id", (order_id,)).fetchall()
    conn.close()
    return rows


def rate_order(order_id, customer_id, stars):
    """Store a 1-5 rating once, only by the customer, only after delivery."""
    stars = int(stars)
    if not 1 <= stars <= 5:
        raise OrderError("Rating must be 1-5.")
    conn = db.connect()
    try:
        with conn:
            row = conn.execute("SELECT customer_id, status, rating FROM orders WHERE id=?", (order_id,)).fetchone()
            if not row or row["customer_id"] != customer_id:
                raise OrderError("Not your order.")
            if row["status"] != "DELIVERED":
                raise OrderError("You can rate an order after it is delivered.")
            if row["rating"]:
                raise OrderError("You already rated this order.")
            conn.execute("UPDATE orders SET rating=? WHERE id=?", (stars, order_id))
    finally:
        conn.close()


# ----------------------------------------------------------------------------- reorder / "the usual"
@dataclass(frozen=True)
class KeptLine:
    item_id: str
    name: str
    qty: int
    unit: int           # today's catalogue price, never the price on the old order
    amount: int


@dataclass(frozen=True)
class DroppedLine:
    name: str
    qty: int
    reason: str


@dataclass(frozen=True)
class ReorderPlan:
    order_id: int
    restaurant_id: str
    kept: tuple[KeptLine, ...]
    dropped: tuple[DroppedLine, ...]
    blocked: str | None = None      # set when the whole order cannot be placed (closed, out of range, gone)

    @property
    def subtotal(self) -> int:
        return sum(k.amount for k in self.kept)


@dataclass(frozen=True)
class Usual:
    slot: str
    order_id: int       # the most recent delivered order in that slot from the favourite kitchen
    times: int
    plan: ReorderPlan


def recent_delivered(customer_id, limit=3):
    """The customer's last delivered orders, newest first (only their own: the query is keyed on customer_id)."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM orders WHERE customer_id=? AND status='DELIVERED' ORDER BY id DESC LIMIT ?",
        (customer_id, max(1, min(int(limit), 20))),
    ).fetchall()
    conn.close()
    return rows


def reorder_plan(tg_id, order_id, now: datetime | None = None) -> ReorderPlan:
    """Rebuild a cart from one of the customer's delivered orders against *today's* catalogue.

    Kept: the item still exists on that restaurant's menu and is available; quantity is clamped to 1..MAX_QTY; the
    price is the current catalogue price. Dropped lines carry a reason. When the restaurant is closed, inactive or
    outside the active address's delivery radius, nothing is kept and `blocked` says why. With no active address the
    radius cannot be checked here; the normal cart screen then asks for an address.
    """
    order, items = get_order(order_id)
    if not order or order["customer_id"] != tg_id:
        raise OrderError("Not your order.")
    if order["status"] != "DELIVERED":
        raise OrderError("You can only order again from a delivered order.")
    rest = catalogue.RESTAURANTS.get(order["restaurant_id"])
    wanted = [(i["item_id"], i["item_name"], clamp_qty(i["quantity"])) for i in items]

    blocked = None
    if rest is None or not rest.active:
        blocked = "That restaurant isn't taking orders any more."
    elif not rest.open_at(now):
        blocked = f"{rest.name} is closed right now (open {rest.hours_label})."
    else:
        addr = db.get_active_address(tg_id)
        if addr:
            dist = haversine_km(addr["latitude"], addr["longitude"], rest.lat, rest.lon)
            if dist > rest.radius_km:
                blocked = (f"{rest.name} doesn't deliver to {addr['label']} "
                           f"({dist:.1f} km away, limit {rest.radius_km:g} km).")
    if blocked:
        return ReorderPlan(order_id, order["restaurant_id"], (), tuple(DroppedLine(n, q, blocked) for _, n, q in wanted), blocked)

    kept, dropped = [], []
    for item_id, name, qty in wanted:
        it = catalogue.ITEMS.get(item_id)
        if it is None or it.restaurant_id != rest.id:
            dropped.append(DroppedLine(name, qty, "no longer on the menu"))
        elif not it.available:
            dropped.append(DroppedLine(name, qty, "unavailable right now"))
        else:
            kept.append(KeptLine(it.id, it.name, qty, it.price, it.price * qty))
    return ReorderPlan(order_id, rest.id, tuple(kept), tuple(dropped))


def reorder(tg_id, order_id, now: datetime | None = None):
    """Fill the cart from a delivered order. Returns (plan, replaced_previous_cart); the cart is untouched if nothing was kept."""
    plan = reorder_plan(tg_id, order_id, now)
    if not plan.kept:
        return plan, False
    return plan, replace_cart(tg_id, [(k.item_id, k.qty) for k in plan.kept])


USUAL_MIN_TIMES = 2


def _slot_of(created_at: str) -> str | None:
    try:
        dt = datetime.fromisoformat(created_at)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return catalogue.current_slot(dt)


def usual_for_slot(tg_id, now: datetime | None = None) -> Usual | None:
    """"Your usual <slot>": a restaurant the customer ordered from, and had delivered, at least twice in the current meal slot.

    Deterministic and cheap: one indexed-by-customer SQL read of recent delivered orders, grouped in Python by (slot,
    restaurant). The favourite is the most frequent kitchen (ties: most recent order). It is only offered when the
    most recent such order can be rebuilt right now (open, in range, something still available).
    """
    slot = catalogue.current_slot(now)
    conn = db.connect()
    rows = conn.execute(
        "SELECT id, restaurant_id, created_at FROM orders WHERE customer_id=? AND status='DELIVERED' ORDER BY id DESC LIMIT 60",
        (tg_id,),
    ).fetchall()
    conn.close()
    by_rest: dict[str, list[int]] = {}
    for r in rows:
        if _slot_of(r["created_at"]) == slot:
            by_rest.setdefault(r["restaurant_id"], []).append(r["id"])          # newest first, as fetched
    ranked = sorted((ids for ids in by_rest.values() if len(ids) >= USUAL_MIN_TIMES), key=lambda ids: (-len(ids), -ids[0]))
    for ids in ranked:
        plan = reorder_plan(tg_id, ids[0], now)
        if plan.kept:
            return Usual(slot, ids[0], len(ids), plan)
    return None
