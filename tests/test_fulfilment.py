"""Delivery simulation: courier model, kitchen/rider scheduler, live location, tracking, ratings."""
from datetime import datetime, timedelta, timezone

import pytest
from aiogram.methods import (
    AnswerCallbackQuery,
    EditMessageLiveLocation,
    EditMessageText,
    SendLocation,
    StopMessageLiveLocation,
)

from foodbot import config, courier, db, fulfilment, orders, simulator
from foodbot.services import catalogue
from foodbot.services.distance import haversine_km
from foodbot.services.search import search_items

from .bot_harness import ADMIN, CUSTOMER
from .conftest import KORAMANGALA, NOON


@pytest.fixture(autouse=True)
def fast_sim(monkeypatch):
    monkeypatch.setattr(config, "SIMULATE_DELIVERY", True)
    monkeypatch.setattr(config, "SIM_SECONDS_PER_MINUTE", 1.0)
    monkeypatch.setattr(config, "SIM_ACCEPT_SECONDS", 8.0)
    monkeypatch.setattr(config, "SIM_REJECT_RATE", 0.0)
    monkeypatch.setattr(config, "SIM_LIVE_EDIT_SECONDS", 5.0)
    monkeypatch.setattr(config, "ADMIN_IDS", {ADMIN})


def place_order(uid=CUSTOMER, key="k1"):
    """A real order through the real checkout, near Koramangala, at the frozen lunchtime."""
    db.add_address(uid, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    hit = next(r for r in search_items("biryani", *KORAMANGALA, limit=50, now=NOON) if r.item.price * 2 >= r.restaurant.min_order)
    orders.add_item(uid, hit.item.id, 2)
    db.set_field(uid, pending_key=key)
    oid, _ = orders.create_order(uid, key)
    return oid


def t0(oid):
    return datetime.fromisoformat(orders.get_order(oid)[0]["updated_at"])


async def run_until(env, oid, seconds, step=2.0, start=None):
    """Advance the simulated clock in `step` increments, ticking the scheduler, like the real loop would."""
    start = start or datetime.now(timezone.utc)
    t = 0.0
    while t <= seconds:
        await simulator.tick(env.bot, start + timedelta(seconds=t))
        t += step
    return start + timedelta(seconds=seconds)


# ---------------------------------------------------------------------------- courier model
def test_rider_persona_is_deterministic_and_plausible():
    a, b = courier.persona_for(7), courier.persona_for(7)
    assert a == b and courier.persona_for(8) != a
    assert 4.5 <= a.rating <= 4.9 and "KA " in a.vehicle and "•" in a.phone


def test_route_starts_at_kitchen_ends_at_door_and_moves_monotonically_closer():
    start, end = (12.9352, 77.6245), (12.9784, 77.6408)
    route = courier.build_route(start, end, 42)
    assert route[0] == start and route[-1] == end
    assert courier.position_at(route, 0) == start and courier.position_at(route, 1) == end
    assert courier.position_at(route, -3) == start and courier.position_at(route, 9) == end        # clamped
    remaining = [haversine_km(*courier.position_at(route, p / 20), *end) for p in range(21)]
    # the path wobbles a little, but the rider never ends further from home than where it started and finishes at zero
    assert remaining[0] > remaining[10] > remaining[20] == pytest.approx(0, abs=1e-9)
    assert courier.route_length_km(route) >= haversine_km(*start, *end)                            # roads are never shorter than the crow flies
    assert courier.build_route(start, end, 42) == route and courier.build_route(start, end, 43) != route


# ---------------------------------------------------------------------------- full lifecycle
async def test_unattended_order_runs_to_delivery_with_live_location(bot_env):
    env, session = bot_env, bot_env.session
    oid = place_order()
    db.save_order_message(oid, ADMIN, 555, "admin_card")
    start = t0(oid)

    await simulator.tick(env.bot, start + timedelta(seconds=1))
    assert orders.get_order(oid)[0]["status"] == "PENDING"                            # the kitchen has not "read" it yet

    seen = []
    t = 2.0
    while t < 400 and orders.get_order(oid)[0]["status"] != "DELIVERED":
        await simulator.tick(env.bot, start + timedelta(seconds=t))
        status = orders.get_order(oid)[0]["status"]
        if status != "PENDING" and (not seen or seen[-1] != status):
            seen.append(status)
        t += 2.0
    assert seen == ["ACCEPTED", "PREPARING", "OUT_FOR_DELIVERY", "DELIVERED"]
    assert [r["status"] for r in orders.order_log(oid)] == ["PENDING", *seen]

    # customer saw each stage, the rider and the live location
    texts = " ".join(session.texts(CUSTOMER))
    for needle in ("was accepted", "is being prepared", "picked up order", "halfway", "almost there", "was delivered"):
        assert needle in texts, needle
    rider = db.get_courier(oid)
    assert rider["name"] in texts and rider["live_stopped"] == 1

    sent = session.of(SendLocation)
    assert len(sent) == 1 and sent[0].live_period >= 60
    edits = session.of(EditMessageLiveLocation)
    assert len(edits) >= 3 and all(e.message_id == rider["live_message_id"] for e in edits)
    rest = catalogue.get_restaurant(orders.get_order(oid)[0]["restaurant_id"])
    first, last = edits[0], edits[-1]
    assert haversine_km(first.latitude, first.longitude, rest.lat, rest.lon) < haversine_km(last.latitude, last.longitude, rest.lat, rest.lon)
    assert haversine_km(last.latitude, last.longitude, *KORAMANGALA) < haversine_km(first.latitude, first.longitude, *KORAMANGALA)
    assert len(session.of(StopMessageLiveLocation)) == 1

    # the admin card was edited in place at every stage, ending DELIVERED, with the rider on it
    card_edits = [m for m in session.of(EditMessageText) if m.message_id == 555]
    assert len(card_edits) >= 4 and "DELIVERED" in card_edits[-1].text and rider["name"] in card_edits[-1].text
    assert orders.get_order(oid)[0]["delivered_at"]


async def test_rating_prompt_and_rules(bot_env):
    env, session = bot_env, bot_env.session
    oid = place_order()
    await run_until(env, oid, 400, start=t0(oid))
    assert orders.get_order(oid)[0]["status"] == "DELIVERED"
    assert any(b.startswith(f"rate:{oid}:") for b in session.buttons(CUSTOMER))

    db.upsert_user(2, "Other")
    await env.press(2, f"rate:{oid}:5")                                        # someone else's order
    assert orders.get_order(oid)[0]["rating"] is None
    await env.press(CUSTOMER, f"rate:{oid}:4")
    assert orders.get_order(oid)[0]["rating"] == 4
    await env.press(CUSTOMER, f"rate:{oid}:1")                                 # only once
    assert orders.get_order(oid)[0]["rating"] == 4
    assert any("rated 4/5" in t for t in session.texts(ADMIN))
    alerts = [m.text for m in session.of(AnswerCallbackQuery) if m.text]
    assert any("Not your order" in a for a in alerts) and any("already rated" in a for a in alerts)


async def test_cannot_rate_before_delivery():
    oid = place_order()
    with pytest.raises(orders.OrderError, match="after it is delivered"):
        orders.rate_order(oid, CUSTOMER, 5)
    with pytest.raises(orders.OrderError):
        orders.rate_order(oid, CUSTOMER, 9)


# ---------------------------------------------------------------------------- humans stay in charge
async def test_admin_can_move_the_order_and_the_simulator_continues_from_there(bot_env):
    env = bot_env
    oid = place_order()
    await env.press(ADMIN, f"adm:ACCEPTED:{oid}")                              # operator acts before the simulator
    assert orders.get_order(oid)[0]["status"] == "ACCEPTED"
    await env.press(ADMIN, f"adm:PREPARING:{oid}")
    assert db.get_courier(oid) is not None                                     # rider assigned at preparing, manual or not
    await run_until(env, oid, 400, start=t0(oid))
    assert orders.get_order(oid)[0]["status"] == "DELIVERED"
    notes = [r["note"] for r in orders.order_log(oid)]
    assert "by restaurant operator" in notes and "simulated kitchen" in notes


async def test_customer_cancel_is_respected_by_the_simulator(bot_env):
    env, session = bot_env, bot_env.session
    oid = place_order()
    db.save_order_message(oid, ADMIN, 777, "admin_card")
    await env.press(CUSTOMER, f"ucancel:{oid}")
    assert orders.get_order(oid)[0]["status"] == "CANCELLED"
    await run_until(env, oid, 120, start=t0(oid))
    assert orders.get_order(oid)[0]["status"] == "CANCELLED"                   # never resurrected
    assert any("cancelled by the customer" in t for t in session.texts(ADMIN))
    assert any(m.message_id == 777 and "CANCELLED" in m.text for m in session.of(EditMessageText))


async def test_simulated_kitchen_can_decline_an_order(bot_env, monkeypatch):
    monkeypatch.setattr(config, "SIM_REJECT_RATE", 1.0)
    env, session = bot_env, bot_env.session
    oid = place_order()
    await run_until(env, oid, 60, start=t0(oid))
    assert orders.get_order(oid)[0]["status"] == "REJECTED"
    assert any("could not be accepted" in t and "No payment was collected" in t for t in session.texts(CUSTOMER))
    assert db.get_courier(oid) is None


async def test_simulation_can_be_switched_off(bot_env, monkeypatch):
    monkeypatch.setattr(config, "SIMULATE_DELIVERY", False)
    oid = place_order()
    assert await simulator.tick(bot_env.bot, t0(oid) + timedelta(hours=1)) == 0
    assert orders.get_order(oid)[0]["status"] == "PENDING"


# ---------------------------------------------------------------------------- restart safety
async def test_restart_mid_ride_resumes_on_the_same_live_message(bot_env):
    env, session = bot_env, bot_env.session
    oid = place_order()
    start = t0(oid)
    t = 0.0
    while orders.get_order(oid)[0]["status"] != "OUT_FOR_DELIVERY":
        t += 2.0
        await simulator.tick(env.bot, start + timedelta(seconds=t))
    before = len(session.of(EditMessageLiveLocation))
    msg_id = db.get_courier(oid)["live_message_id"]
    # "restart": there is no in-memory state to lose; a fresh pass just carries on from the database
    import importlib
    importlib.reload(simulator)
    for extra in range(1, 12):
        await simulator.tick(env.bot, start + timedelta(seconds=t + extra * 2))
    assert len(session.of(EditMessageLiveLocation)) > before
    assert {e.message_id for e in session.of(EditMessageLiveLocation)} == {msg_id}
    assert len(session.of(SendLocation)) == 1                                  # did not start a second live location


# ---------------------------------------------------------------------------- tracking
async def test_track_shows_progress_and_belongs_to_the_customer(bot_env):
    env, session = bot_env, bot_env.session
    await env.say(CUSTOMER, "/track")
    assert "no orders yet" in session.last_text()
    oid = place_order()
    await env.say(CUSTOMER, "where is my order")
    text = session.last_text()
    assert f"Order #{oid}" in text and "🔄 Placed" in text and "⬜ Delivered" in text and "Cancel order" in " ".join(
        b.text for m in session.of(type(session.sent[-1])) for row in (getattr(m.reply_markup, "inline_keyboard", []) or []) for b in row)
    await env.press(ADMIN, f"adm:ACCEPTED:{oid}")
    await env.press(ADMIN, f"adm:PREPARING:{oid}")
    await env.press(ADMIN, f"adm:OUT_FOR_DELIVERY:{oid}")
    await env.press(CUSTOMER, f"track:{oid}")
    edited = [m.text for m in session.of(EditMessageText) if "Order #" in (m.text or "") and "On the way" in (m.text or "")]
    assert edited and "away" in edited[-1] and db.get_courier(oid)["name"] in edited[-1]
    db.upsert_user(2, "Other")
    await env.press(2, f"track:{oid}")
    assert any("Not your order" in (m.text or "") for m in session.of(AnswerCallbackQuery))


def test_progress_bar_states():
    assert fulfilment.progress_bar("PENDING").startswith("🔄 Placed")
    assert fulfilment.progress_bar("DELIVERED").count("✅") == 5
    assert "Cancelled" in fulfilment.progress_bar("CANCELLED")
    assert fulfilment.progress_bar("PREPARING") == "✅ Placed → ✅ Accepted → 🔄 Preparing → ⬜ On the way → ⬜ Delivered"
