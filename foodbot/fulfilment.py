"""Everything that happens in Telegram when an order changes state: customer messages, admin cards, the rider's live location.

`advance()` is the single entry point used by the admin buttons, the customer's cancel button and the kitchen simulator,
so all three behave identically and the admin's order card stays in sync no matter who moved the order.
"""
from __future__ import annotations

import html
import logging
from datetime import datetime, timezone

from aiogram.exceptions import TelegramAPIError

from foodbot import config, courier, db, metrics, orders
from foodbot import keyboards as kb
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km
from foodbot.services.eta import travel_minutes

log = logging.getLogger(__name__)
esc = html.escape

STATUS_TEXT = {
    "ACCEPTED": "✅ Order #{id} was accepted. {restaurant} is getting started.",
    "PREPARING": "👨‍🍳 Order #{id} is being prepared.",
    "OUT_FOR_DELIVERY": "🛵 Order #{id} is out for delivery.",
    "DELIVERED": "🎉 Order #{id} was delivered. Enjoy your meal!",
}
STEPS = (("PENDING", "Placed"), ("ACCEPTED", "Accepted"), ("PREPARING", "Preparing"), ("OUT_FOR_DELIVERY", "On the way"), ("DELIVERED", "Delivered"))


# ----------------------------------------------------------------------------- views
def admin_card(order, items, rider=None):
    lines = "\n".join(f"{i['quantity']} × {i['item_name']} (₹{i['unit_price']})" for i in items)
    rest = catalogue.get_restaurant(order["restaurant_id"])
    maps = f"https://maps.google.com/?q={order['latitude']},{order['longitude']}"
    text = (
        f"🔔 <b>ORDER #{order['id']}</b> — {esc(order['status'])}\n"
        f"Restaurant: {esc(rest.name if rest else order['restaurant_id'])}\n"
        f"Customer: {esc(order['customer_name'] or '-')} (ID {order['customer_id']})\n"
        f"Deliver to: <b>{esc(order['recipient_name'] or order['customer_name'] or '-')}</b>"
        f"{' · ' + esc(order['recipient_phone']) if order['recipient_phone'] else ''}\n\n"
        f"{esc(lines)}\n\n"
        f"Subtotal ₹{order['subtotal']} · Delivery ₹{order['delivery_fee']} · <b>Total ₹{order['total']}</b>\n"
        f"Payment: {order['payment_method']}\n"
        f"Address ({esc(order['address_label'] or 'saved')}): {esc(order['address'] or '-')}\n"
        f"Landmark: {esc(order['landmark'] or '-')}\n"
        f"Map: {maps}"
    )
    if rider:
        text += f"\nRider: {esc(rider['name'])} · {esc(rider['vehicle'])}"
    if order["rating"]:
        text += f"\nCustomer rating: {'⭐' * int(order['rating'])}"
    return text


def progress_bar(status: str) -> str:
    """✅ Placed → ✅ Accepted → 🔄 Preparing → ⬜ On the way → ⬜ Delivered"""
    order = [s for s, _ in STEPS]
    if status not in order:
        return {"CANCELLED": "❌ Cancelled", "REJECTED": "❌ Not accepted by the restaurant"}.get(status, status)
    idx = order.index(status)
    parts = []
    for i, (_, label) in enumerate(STEPS):
        icon = "✅" if i < idx or status == "DELIVERED" else ("🔄" if i == idx else "⬜")
        parts.append(f"{icon} {label}")
    return " → ".join(parts)


# ----------------------------------------------------------------------------- timing + route
def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _utc(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _restaurant_point(order) -> tuple[float, float]:
    rest = catalogue.get_restaurant(order["restaurant_id"])
    return (rest.lat, rest.lon) if rest else (order["latitude"], order["longitude"])


def travel_seconds(order, now: datetime | None = None) -> float:
    """Demo-clock duration of the ride: catalogue travel minutes x SIM_SECONDS_PER_MINUTE, kept watchable."""
    dist = haversine_km(*_restaurant_point(order), order["latitude"], order["longitude"])
    minutes = travel_minutes(dist, now)
    return min(max(minutes * config.SIM_SECONDS_PER_MINUTE, 20.0), 900.0)


def route_for(order) -> list[courier.Point]:
    return courier.build_route(_restaurant_point(order), (order["latitude"], order["longitude"]), order["id"])


def ride_progress(order, rider, now: datetime | None = None) -> float:
    if not rider or not rider["pickup_at"] or not rider["travel_s"]:
        return 0.0
    return (_utc(now) - _ts(rider["pickup_at"])).total_seconds() / rider["travel_s"]


def minutes_left(order, rider, now: datetime | None = None) -> int:
    """Remaining ride time in catalogue minutes (what the customer is told), rounded up."""
    left_s = max(0.0, rider["travel_s"] * (1 - ride_progress(order, rider, now)))
    return max(1, round(left_s / max(config.SIM_SECONDS_PER_MINUTE, 0.01) + 0.49))


# ----------------------------------------------------------------------------- telegram helpers
async def notify_customer(bot, order, text, markup=None):
    try:
        return await bot.send_message(order["customer_id"], text, reply_markup=markup)
    except TelegramAPIError as e:
        log.warning("customer notify failed: %s", type(e).__name__)
        return None


async def refresh_admin_cards(bot, order_id):
    order, items = orders.get_order(order_id)
    if not order:
        return
    text = admin_card(order, items, db.get_courier(order_id))
    for m in db.order_messages(order_id, "admin_card"):
        try:
            await bot.edit_message_text(text, chat_id=m["chat_id"], message_id=m["message_id"], reply_markup=kb.admin(order_id, order["status"]))
        except TelegramAPIError:
            pass                                    # unchanged text / deleted message: nothing to fix


async def notify_admins(bot, text):
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError:
            pass


# ----------------------------------------------------------------------------- the ride
async def begin_ride(bot, order, rider, now: datetime | None = None):
    """Kitchen handed over the food: the rider leaves and the customer gets a live-location message to watch."""
    now = _utc(now)
    secs = travel_seconds(order, now)
    db.update_courier(order["id"], pickup_at=now.isoformat(timespec="seconds"), travel_s=secs, milestone=0, live_stopped=0)
    rider = db.get_courier(order["id"])
    start = courier.position_at(route_for(order), 0.0)
    mins = minutes_left(order, rider, now)
    await notify_customer(
        bot, order,
        f"🛵 <b>{esc(rider['name'])}</b> ({rider['rating']}★) picked up order #{order['id']}.\n"
        f"{esc(rider['vehicle'])}\nArriving in about <b>{mins} min</b>. Watch the live location below 👇",
    )
    try:
        msg = await bot.send_location(order["customer_id"], start[0], start[1], live_period=max(60, int(secs) + 60))
        db.update_courier(order["id"], live_chat_id=msg.chat.id, live_message_id=msg.message_id, last_edit_at=now.isoformat(timespec="seconds"))
    except TelegramAPIError as e:
        log.warning("could not start live location for #%s: %s", order["id"], type(e).__name__)


async def tick_ride(bot, order, rider, now: datetime | None = None) -> bool:
    """Move the live location and send milestone messages. Returns True once the rider has arrived."""
    now = _utc(now)
    progress = ride_progress(order, rider, now)
    if progress >= 1:
        return True
    pos = courier.position_at(route_for(order), progress)
    last = _ts(rider["last_edit_at"]) if rider["last_edit_at"] else None
    if rider["live_message_id"] and (last is None or (now - last).total_seconds() >= config.SIM_LIVE_EDIT_SECONDS):
        try:
            await bot.edit_message_live_location(pos[0], pos[1], chat_id=rider["live_chat_id"], message_id=rider["live_message_id"])
        except TelegramAPIError as e:
            log.debug("live location edit skipped for #%s: %s", order["id"], type(e).__name__)
        db.update_courier(order["id"], last_edit_at=now.isoformat(timespec="seconds"))
    milestone = rider["milestone"]
    if milestone < 1 and progress >= 0.5:
        db.update_courier(order["id"], milestone=1)
        await notify_customer(bot, order, f"📍 {esc(rider['name'])} is halfway — about {minutes_left(order, rider, now)} min to go.")
    if milestone < 2 and progress >= 0.85:
        db.update_courier(order["id"], milestone=2)
        await notify_customer(bot, order, f"📍 {esc(rider['name'])} is almost there — look out for a {esc(rider['vehicle'].split(' · ')[0])}.")
    return False


async def end_ride(bot, order, rider):
    if rider and rider["live_message_id"] and not rider["live_stopped"]:
        try:
            await bot.stop_message_live_location(chat_id=rider["live_chat_id"], message_id=rider["live_message_id"])
        except TelegramAPIError:
            pass
        db.update_courier(order["id"], live_stopped=1)


# ----------------------------------------------------------------------------- the one way to change an order
async def advance(bot, order_id, new_status, note=None, now: datetime | None = None, notify=True):
    """Move an order to `new_status` (raises orders.OrderError if the state machine forbids it) and tell everyone."""
    orders.transition(order_id, new_status, note)
    metrics.ORDERS.inc(status=new_status)
    order, _ = orders.get_order(order_id)
    rider = db.get_courier(order_id)

    if new_status == "PREPARING" and config.SIMULATE_DELIVERY and rider is None:
        p = courier.persona_for(order_id)
        db.insert_courier(order_id, p.name, p.vehicle, p.phone, p.rating)
        rider = db.get_courier(order_id)

    if notify:
        if new_status == "REJECTED":
            await notify_customer(bot, order, f"Order #{order_id} could not be accepted.\nReason: {esc(note or 'unable to fulfil')}.\nNo payment was collected.")
        elif new_status in STATUS_TEXT:
            rest = catalogue.get_restaurant(order["restaurant_id"])
            text = STATUS_TEXT[new_status].format(id=order_id, restaurant=esc(rest.name if rest else "The restaurant"))
            if new_status == "ACCEPTED":
                text += f"\nEstimated delivery: {order['eta_min']}–{order['eta_max']} min."
            if new_status == "PREPARING" and rider:
                text += f"\n🛵 {esc(rider['name'])} ({rider['rating']}★) will pick it up."
            if new_status == "DELIVERED":
                text += f"\nTotal ₹{order['total']} · cash on delivery. How was it?"
                await notify_customer(bot, order, text, kb.rating(order_id))
            elif new_status != "OUT_FOR_DELIVERY" or not (rider and config.SIMULATE_DELIVERY):
                await notify_customer(bot, order, text)

    if new_status == "OUT_FOR_DELIVERY" and rider and config.SIMULATE_DELIVERY:
        await begin_ride(bot, order, rider, now)
    if new_status in ("DELIVERED", "CANCELLED", "REJECTED"):
        await end_ride(bot, order, db.get_courier(order_id))
    await refresh_admin_cards(bot, order_id)
    if new_status == "CANCELLED":
        await notify_admins(bot, f"⌁ Order #{order_id} was cancelled by the customer.")
    return order
