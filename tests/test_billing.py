"""Split the bill: the arithmetic (property-style) and the bot flow."""
import pytest
from hypothesis import given
from hypothesis import strategies as st

from foodbot import billing, db, orders

from .bot_harness import CUSTOMER
from .test_fulfilment import place_order


@given(total=st.integers(min_value=0, max_value=1_000_000), people=st.integers(min_value=1, max_value=20))
def test_shares_always_sum_to_the_total_and_differ_by_at_most_one_rupee(total, people):
    shares = billing.split_total(total, people)
    assert len(shares) == people
    assert sum(shares) == total
    assert max(shares) - min(shares) <= 1
    assert min(shares) >= 0
    assert shares == sorted(shares, reverse=True)


def test_remainder_goes_to_the_first_people_one_rupee_each():
    assert billing.split_total(175, 3) == [59, 58, 58]
    assert billing.split_total(100, 8) == [13, 13, 13, 13, 12, 12, 12, 12]
    assert billing.split_total(2, 5) == [1, 1, 0, 0, 0]
    assert billing.split_total(90, 3) == [30, 30, 30]
    assert billing.split_total(77, 1) == [77]


@pytest.mark.parametrize("total, people", [(-1, 2), (100, 0), (100, 21), (100, -3), (1.5, 2), (100, 2.0), ("100", 2), (True, 2)])
def test_invalid_inputs_are_rejected(total, people):
    with pytest.raises(ValueError):
        billing.split_total(total, people)


def test_forwardable_text_is_plain_and_escapes_the_restaurant_name():
    text = billing.format_split(12, "Moonlight Kitchen", 175, 3)
    assert text == "Order #12 · Moonlight Kitchen · total ₹175 / 3 → ₹59, ₹58, ₹58"
    assert billing.format_split(3, "A", 90, 3) == "Order #3 · A · total ₹90 / 3 → ₹30 each"
    nasty = billing.format_split(1, "<b>Tom & Jerry's</b>", 100, 2, delivery_fee=30)
    assert "<b>" not in nasty and "&lt;b&gt;Tom &amp; Jerry" in nasty and "includes ₹30 delivery" in nasty


# ------------------------------------------------------------------------------ bot flow
async def test_split_flow_asks_then_replies_with_an_exact_split_including_delivery(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    oid = place_order()                                              # 2 x biryani: a group-sized order
    order, _ = orders.get_order(oid)
    await env.press(CUSTOMER, f"split:{oid}")
    assert "Split between how many people?" in session.last_text()
    assert [b for b in session.buttons(CUSTOMER) if b.startswith(f"split:{oid}:")] == [f"split:{oid}:{n}" for n in range(2, 9)]

    await env.press(CUSTOMER, f"split:{oid}:3")
    text = session.last_text()
    shares = billing.split_total(order["total"], 3)
    assert f"Order #{oid}" in text and f"total ₹{order['total']} / 3" in text
    assert ", ".join(f"₹{s}" for s in shares) in text or f"₹{shares[0]} each" in text
    assert sum(shares) == order["total"] == order["subtotal"] + order["delivery_fee"]   # the delivery fee is in the bill


async def test_group_order_is_offered_the_split_on_placement(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    from foodbot.services.search import search_items

    from .conftest import KORAMANGALA, NOON
    hit = next(r for r in search_items("biryani", *KORAMANGALA, limit=50, now=NOON) if r.item.price * 2 >= r.restaurant.min_order)
    orders.add_item(CUSTOMER, hit.item.id, 2)
    await env.press(CUSTOMER, "checkout")
    await env.press(CUSTOMER, "skip_landmark")
    await env.press(CUSTOMER, env.button("confirm:"))
    assert "Split the bill" in session.last_text()
    assert any(b.startswith("split:1:") for b in session.buttons(CUSTOMER))


async def test_single_portion_order_gets_no_unprompted_split_but_the_button_exists(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    from foodbot.services.search import search_items

    from .conftest import KORAMANGALA, NOON
    hit = next(r for r in search_items("biryani", *KORAMANGALA, limit=50, now=NOON) if r.item.price >= r.restaurant.min_order)
    orders.add_item(CUSTOMER, hit.item.id, 1)
    await env.press(CUSTOMER, "checkout")
    await env.press(CUSTOMER, "skip_landmark")
    await env.press(CUSTOMER, env.button("confirm:"))
    assert "Split the bill" not in " ".join(session.texts(CUSTOMER))
    assert "split:1" in session.buttons(CUSTOMER)


async def test_someone_elses_order_cannot_be_split(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    oid = place_order()
    db.upsert_user(2, "Other")
    await env.press(2, f"split:{oid}:2")
    await env.press(2, f"split:{oid}")
    assert not [t for t in session.texts(2) if "total" in t or "Split between" in t]
    assert not [t for t in session.texts(CUSTOMER) if t.startswith(f"Order #{oid} ·")]


@pytest.mark.parametrize("data", ["split:", "split:x", "split:1:", "split:1:1", "split:1:9", "split:1:0", "split:1:-2", "split:1:2:3",
                                  "split:0:2", "split:-1:2", "split:1:٣", "split:١:2", "split:1: 2", "split:1:02x", "split:" + "9" * 40 + ":2"])
async def test_forged_split_callbacks_are_refused(bot_env, at_koramangala, data):
    env, session = bot_env, bot_env.session
    place_order()
    await env.press(CUSTOMER, data)
    assert not [t for t in session.texts(CUSTOMER) if t.startswith("Order #1 ·")]


async def test_cancelled_orders_cannot_be_split(bot_env, at_koramangala):
    env, session = bot_env, bot_env.session
    oid = place_order()
    orders.transition(oid, "CANCELLED")
    await env.press(CUSTOMER, f"split:{oid}:2")
    assert not [t for t in session.texts(CUSTOMER) if t.startswith(f"Order #{oid} ·")]
