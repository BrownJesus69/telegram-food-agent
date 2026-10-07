"""Reorder / "the usual": rebuilding carts from delivered orders, the usual-slot rule, and the bot flow."""
import dataclasses
from datetime import timezone

import pytest
from aiogram.methods import EditMessageText

from foodbot import config, db, fulfilment, handlers, orders
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km

from .bot_harness import CUSTOMER
from .conftest import BREAKFAST, KORAMANGALA, LATE, NOON

FAR_AWAY = (13.55, 77.60)                       # ~70 km north of Koramangala: outside every kitchen's radius


def _near(rest, point=KORAMANGALA):
    return haversine_km(*point, rest.lat, rest.lon) <= rest.radius_km


def _available(rest):
    return sorted((i for i in catalogue.ITEMS_BY_RESTAURANT[rest.id] if i.available), key=lambda i: i.id)


def kitchen(*, open_at=NOON, closed_at=None, near=True, skip=()):
    """A deterministic restaurant: open at `open_at`, optionally closed at `closed_at`, near (or far from) Koramangala."""
    for r in sorted(catalogue.RESTAURANTS.values(), key=lambda r: r.id):
        if r.id in skip or not r.active or len(_available(r)) < 3:
            continue
        if open_at is not None and not r.open_at(open_at):
            continue
        if closed_at is not None and r.open_at(closed_at):
            continue
        if _near(r) == near:
            return r
    raise AssertionError("no suitable restaurant in the catalogue")


def utc_iso(ist_dt):
    return ist_dt.astimezone(timezone.utc).isoformat(timespec="seconds")


_keys = iter(range(10_000))


def delivered(uid, rest, lines, *, when=NOON, status="DELIVERED", old_price=1):
    """Insert a finished order directly: lines = [(item_id, item_name, qty)]. The old unit price is deliberately wrong."""
    conn = db.connect()
    with conn:
        total = sum(q for _, _, q in lines) * old_price
        oid = conn.execute(
            "INSERT INTO orders(customer_id, customer_name, restaurant_id, status, subtotal, delivery_fee, total, latitude, longitude,"
            " confirmation_key, created_at, updated_at, delivered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (uid, "T", rest.id, status, total, 0, total, *KORAMANGALA, f"seed{next(_keys)}", utc_iso(when), utc_iso(when), utc_iso(when)),
        ).lastrowid
        for item_id, name, qty in lines:
            conn.execute("INSERT INTO order_items(order_id, item_id, item_name, quantity, unit_price) VALUES(?,?,?,?,?)",
                         (oid, item_id, name, qty, old_price))
    conn.close()
    return oid


def lines_of(rest, n=2, qty=1):
    return [(i.id, i.name, qty) for i in _available(rest)[:n]]


# ----------------------------------------------------------------------------------- rebuild
def test_rebuild_keeps_available_items_at_todays_prices_and_drops_the_rest(at_koramangala, monkeypatch):
    rest = kitchen()
    a, b, c = _available(rest)[:3]
    oid = delivered(CUSTOMER, rest, [(a.id, a.name, 2), (b.id, b.name, 1), (c.id, c.name, 1), ("ghost-item", "Vanished Dish", 1)])
    monkeypatch.setitem(catalogue.ITEMS, b.id, dataclasses.replace(b, available=False))
    plan = orders.reorder_plan(CUSTOMER, oid)
    assert plan.blocked is None
    assert [(k.item_id, k.qty, k.unit, k.amount) for k in plan.kept] == [(a.id, 2, a.price, 2 * a.price), (c.id, 1, c.price, c.price)]
    assert {d.name: d.reason for d in plan.dropped} == {b.name: "unavailable right now", "Vanished Dish": "no longer on the menu"}
    assert plan.subtotal == 2 * a.price + c.price                          # nothing of the old Rs 1 price survives


def test_reorder_fills_the_cart_through_the_normal_cart_summary(at_koramangala):
    rest = kitchen()
    other = kitchen(skip={rest.id})
    orders.add_item(CUSTOMER, _available(other)[0].id, 1)                  # an existing cart elsewhere
    oid = delivered(CUSTOMER, rest, lines_of(rest))
    plan, replaced = orders.reorder(CUSTOMER, oid)
    assert replaced and len(plan.kept) == 2
    s = orders.cart_summary(CUSTOMER)
    assert s["rest"].id == rest.id and [ln["item_id"] for ln in s["lines"]] == [k.item_id for k in plan.kept]
    assert s["subtotal"] == plan.subtotal


def test_closed_restaurant_blocks_the_whole_reorder(at_koramangala):
    rest = kitchen(open_at=NOON, closed_at=LATE)
    oid = delivered(CUSTOMER, rest, lines_of(rest))
    ok = orders.reorder_plan(CUSTOMER, oid, now=NOON)
    assert ok.kept and ok.blocked is None
    plan, replaced = orders.reorder(CUSTOMER, oid, now=LATE)
    assert not plan.kept and "closed" in plan.blocked and len(plan.dropped) == 2 and not replaced
    assert orders.cart_summary(CUSTOMER) is None                           # the cart was not touched


def test_closed_by_the_frozen_clock_without_passing_now(at_koramangala, monkeypatch):
    rest = kitchen(open_at=NOON, closed_at=LATE)
    oid = delivered(CUSTOMER, rest, lines_of(rest))
    monkeypatch.setattr(catalogue, "now_ist", lambda: LATE)
    assert "closed" in orders.reorder_plan(CUSTOMER, oid).blocked


def test_out_of_radius_for_the_active_address_blocks_the_reorder(at_koramangala):
    rest = kitchen()
    oid = delivered(CUSTOMER, rest, lines_of(rest))
    db.add_address(CUSTOMER, "Far", "Somewhere far", *FAR_AWAY, "T")      # becomes the active address
    plan = orders.reorder_plan(CUSTOMER, oid)
    assert not plan.kept and "doesn't deliver to Far" in plan.blocked
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "T")
    assert orders.reorder_plan(CUSTOMER, oid).kept


def test_someone_elses_order_and_undelivered_orders_are_refused(at_koramangala):
    rest = kitchen()
    mine = delivered(CUSTOMER, rest, lines_of(rest))
    theirs = delivered(2, rest, lines_of(rest))
    pending = delivered(CUSTOMER, rest, lines_of(rest), status="PENDING")
    cancelled = delivered(CUSTOMER, rest, lines_of(rest), status="CANCELLED")
    assert orders.reorder_plan(CUSTOMER, mine).kept
    for oid in (theirs, pending, cancelled, 9999):
        with pytest.raises(orders.OrderError):
            orders.reorder_plan(CUSTOMER, oid)
    assert [o["id"] for o in orders.recent_delivered(CUSTOMER)] == [mine]


def test_quantities_are_clamped(at_koramangala):
    rest = kitchen()
    a, b, c = _available(rest)[:3]
    oid = delivered(CUSTOMER, rest, [(a.id, a.name, 99), (b.id, b.name, 0), (c.id, c.name, -4)])
    assert [k.qty for k in orders.reorder_plan(CUSTOMER, oid).kept] == [orders.MAX_QTY, 1, 1]


def test_recent_delivered_is_newest_first_and_limited(at_koramangala):
    rest = kitchen()
    ids = [delivered(CUSTOMER, rest, lines_of(rest)) for _ in range(5)]
    assert [o["id"] for o in orders.recent_delivered(CUSTOMER, 3)] == ids[::-1][:3]


# --------------------------------------------------------------------------------- the usual
def test_usual_needs_two_delivered_orders_from_the_same_kitchen_in_this_slot(at_koramangala):
    rest = kitchen()
    other = kitchen(skip={rest.id})
    delivered(CUSTOMER, rest, lines_of(rest), when=NOON)
    assert orders.usual_for_slot(CUSTOMER) is None                          # once is not a habit
    delivered(CUSTOMER, other, lines_of(other), when=NOON.replace(day=3))
    assert orders.usual_for_slot(CUSTOMER) is None                          # two different kitchens: still no habit
    latest = delivered(CUSTOMER, rest, lines_of(rest, 1, 2), when=NOON.replace(day=4))
    u = orders.usual_for_slot(CUSTOMER)
    assert u and u.slot == "lunch" and u.times == 2 and u.order_id == latest and u.plan.restaurant_id == rest.id


def test_usual_ignores_other_slots_other_customers_and_undelivered_orders(at_koramangala):
    rest = kitchen()
    delivered(CUSTOMER, rest, lines_of(rest), when=BREAKFAST)
    delivered(CUSTOMER, rest, lines_of(rest), when=BREAKFAST.replace(day=3))
    delivered(2, rest, lines_of(rest), when=NOON)
    delivered(2, rest, lines_of(rest), when=NOON.replace(day=3))
    delivered(CUSTOMER, rest, lines_of(rest), when=NOON, status="CANCELLED")
    delivered(CUSTOMER, rest, lines_of(rest), when=NOON.replace(day=3), status="PENDING")
    assert orders.usual_for_slot(CUSTOMER) is None                          # frozen clock is lunch
    u = orders.usual_for_slot(CUSTOMER, now=BREAKFAST)                      # ...but at breakfast time it is a habit
    assert u and u.slot == "breakfast" and u.times == 2


def test_usual_slot_is_judged_in_ist_not_utc(at_koramangala):
    evening_ist = NOON.replace(hour=19, minute=0)                          # 19:00 IST = 13:30 UTC: dinner in IST, lunch if misread as UTC
    rest = next(r for r in sorted(catalogue.RESTAURANTS.values(), key=lambda r: r.id)
                if r.active and len(_available(r)) >= 3 and _near(r) and r.open_at(evening_ist) and r.open_at(NOON))
    delivered(CUSTOMER, rest, lines_of(rest), when=evening_ist)
    delivered(CUSTOMER, rest, lines_of(rest), when=evening_ist.replace(day=3))
    assert orders.usual_for_slot(CUSTOMER) is None
    assert orders.usual_for_slot(CUSTOMER, now=evening_ist).slot == "dinner"


def test_usual_prefers_the_more_frequent_kitchen_and_is_not_offered_when_unorderable(at_koramangala):
    rest = kitchen(open_at=NOON, closed_at=LATE)
    other = kitchen(skip={rest.id})
    for day in (1, 2, 3):
        delivered(CUSTOMER, rest, lines_of(rest), when=NOON.replace(day=day))
    for day in (4, 5):
        delivered(CUSTOMER, other, lines_of(other), when=NOON.replace(day=day))
    assert orders.usual_for_slot(CUSTOMER).plan.restaurant_id == rest.id and orders.usual_for_slot(CUSTOMER).times == 3
    # a habit that cannot be delivered to the active address is not offered
    db.add_address(CUSTOMER, "Far", "Far away", *FAR_AWAY, "T")
    assert orders.usual_for_slot(CUSTOMER) is None


# -------------------------------------------------------------------------------------- bot flow
async def test_text_intents_and_command_list_the_last_three_delivered_orders(bot_env, at_koramangala, monkeypatch):
    env, session = bot_env, bot_env.session

    async def no_llm(*a, **k):
        raise AssertionError("reorder intents must be handled by rules, never the LLM path")
    monkeypatch.setattr(handlers, "understand", no_llm)

    rest = kitchen()
    ids = [delivered(CUSTOMER, rest, lines_of(rest), when=NOON.replace(day=d)) for d in (1, 2, 3, 4)]
    delivered(CUSTOMER, rest, lines_of(rest), status="CANCELLED")
    for phrase in ("order again", "Same as last time", "the usual", "repeat my last order", "Reorder!", "/reorder"):
        session.sent.clear()
        await env.say(CUSTOMER, phrase)
        offered = [b for b in session.buttons(CUSTOMER) if b.startswith("again:")]
        assert offered == [f"again:{i}" for i in ids[::-1][:3]], phrase
        assert rest.name in session.last_text()


async def test_no_delivered_orders_gets_a_friendly_answer(bot_env, at_koramangala):
    await bot_env.say(CUSTOMER, "order again")
    assert "don't have a delivered order" in bot_env.session.last_text()


async def test_pressing_a_reorder_button_fills_the_cart_and_shows_what_was_dropped(bot_env, at_koramangala, monkeypatch):
    env, session = bot_env, bot_env.session
    rest = kitchen()
    a, b, _ = _available(rest)[:3]
    oid = delivered(CUSTOMER, rest, [(a.id, a.name, 2), (b.id, b.name, 1)])
    monkeypatch.setitem(catalogue.ITEMS, b.id, dataclasses.replace(b, available=False))
    await env.press(CUSTOMER, f"again:{oid}")
    texts = session.texts(CUSTOMER)
    assert any(f"order #{oid}" in t and "Not added" in t and b.name in t and "unavailable" in t for t in texts)
    assert "Your cart" in session.last_text() and f"₹{2 * a.price}" in session.last_text()
    assert [(r["item_id"], r["qty"]) for r in orders.cart_summary(CUSTOMER)["lines"]] == [(a.id, 2)]


async def test_reorder_from_a_closed_kitchen_explains_and_leaves_the_cart_alone(bot_env, at_koramangala, monkeypatch):
    env, session = bot_env, bot_env.session
    rest = kitchen(open_at=NOON, closed_at=LATE)
    oid = delivered(CUSTOMER, rest, lines_of(rest))
    monkeypatch.setattr(catalogue, "now_ist", lambda: LATE)
    await env.press(CUSTOMER, f"again:{oid}")
    assert "Can't repeat" in session.last_text() and "closed" in session.last_text()
    assert orders.cart_summary(CUSTOMER) is None


async def test_forged_reorder_callbacks_are_refused(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    rest = kitchen()
    theirs = delivered(2, rest, lines_of(rest))
    mine = delivered(CUSTOMER, rest, lines_of(rest))
    for data in (f"again:{theirs}", "again:", "again:x", "again:0", "again:-1", f"again:{mine}:1", f"again:{mine} ", "again:٣", "again:" + "9" * 30):
        session.sent.clear()
        await env.press(CUSTOMER, data)
        assert not session.texts(CUSTOMER), data                            # refused with a popup, nothing sent
        assert orders.cart_summary(CUSTOMER) is None, data
    await env.press(CUSTOMER, f"again:{mine}")
    assert "Your cart" in session.last_text()


@pytest.mark.parametrize("data", ["again:", "again:1:2", "again:+1", "again: 1", "again:1.0", "again:٣", "again:0", "again:" + "1" * 13])
def test_again_parser_is_strict(data):
    assert handlers._parse_again(data) is None


def test_again_parser_accepts_the_keyboard_format():
    assert handlers._parse_again("again:42") == 42


async def test_greeting_shows_the_usual_with_a_button(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    rest = kitchen()
    delivered(CUSTOMER, rest, lines_of(rest, 1), when=NOON.replace(day=2))
    await env.say(CUSTOMER, "hi")
    assert "Your usual" not in session.last_text()                          # one order is not a habit
    last = delivered(CUSTOMER, rest, lines_of(rest, 1), when=NOON.replace(day=3))
    session.sent.clear()
    await env.say(CUSTOMER, "hi")
    text = session.last_text()
    assert "Your usual lunch:" in text and rest.name in text and f"₹{_available(rest)[0].price}" in text
    assert f"again:{last}" in session.buttons(CUSTOMER)
    await env.press(CUSTOMER, f"again:{last}")
    assert "Your cart" in session.last_text()


async def test_hungry_message_without_a_target_offers_the_usual(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    rest = kitchen()
    for d in (2, 3):
        last = delivered(CUSTOMER, rest, lines_of(rest, 1), when=NOON.replace(day=d))
    await env.say(CUSTOMER, "I'm hungry")
    assert any(t.startswith("🔁 Your usual lunch") for t in session.texts(CUSTOMER)) or "Your usual lunch" in " ".join(session.texts(CUSTOMER))
    assert f"again:{last}" in session.buttons(CUSTOMER)


async def test_delivered_message_carries_an_order_again_button(bot_env, at_koramangala, monkeypatch):
    from .test_fulfilment import place_order
    monkeypatch.setattr(config, "SIMULATE_DELIVERY", False)
    env, session = bot_env, bot_env.session
    oid = place_order()
    for status in ("ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"):
        await fulfilment.advance(env.bot, oid, status)
    labels = session.button_labels(CUSTOMER)
    assert ("🔁 Order again", f"again:{oid}") in labels and any(d == f"rate:{oid}:5" for _, d in labels)
    await env.press(CUSTOMER, f"again:{oid}")
    assert "Your cart" in session.last_text()
    await env.press(CUSTOMER, f"rate:{oid}:5")                              # the button survives rating
    edited = session.of(EditMessageText)[-1]
    assert "Thanks for rating" in edited.text
    assert [b.callback_data for row in edited.reply_markup.inline_keyboard for b in row] == [f"again:{oid}"]
