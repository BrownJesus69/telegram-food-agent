"""End-to-end conversation tests: real handlers + real database, Telegram's HTTP layer replaced by a recorder."""
from foodbot import db, orders
from foodbot.services import catalogue

from .bot_harness import ADMIN, CUSTOMER
from .conftest import KORAMANGALA


async def test_full_order_journey(bot_env):
    """start -> pin -> label -> search -> select -> checkout -> confirm -> admin accepts -> customer is told."""
    env, session = bot_env, bot_env.session
    await env.say(CUSTOMER, "/start")
    assert any("simulated" in t for t in session.texts(CUSTOMER))
    assert any("location pin" in t for t in session.texts(CUSTOMER))          # no address yet: asked for one

    await env.send_location(CUSTOMER, *KORAMANGALA)
    assert "What should I call this address" in session.last_text()
    await env.press(CUSTOMER, "addr:lbl:home")
    assert any("Saved. Delivering to" in t for t in session.texts(CUSTOMER))

    await env.say(CUSTOMER, "3 chicken biryani under 300")
    assert any("Delivering to" in t and "Home" in t for t in session.texts(CUSTOMER))
    sel = env.button("sel:")
    assert sel.endswith(":3")
    await env.press(CUSTOMER, sel)
    assert any("Your cart" in t for t in session.texts(CUSTOMER))

    await env.press(CUSTOMER, "checkout")
    await env.press(CUSTOMER, "skip_landmark")
    confirm = env.button("confirm:")
    assert "Recipient:" in session.last_text() and "Home" in session.last_text()
    await env.press(CUSTOMER, confirm)
    await env.press(CUSTOMER, confirm)                                       # double tap must not create a second order
    assert len(orders.recent_orders(10)) == 1
    assert any("ORDER #1" in t for t in session.texts(ADMIN))

    accept = env.button("adm:ACCEPTED", ADMIN)
    await env.press(CUSTOMER, accept)                                        # a customer pressing admin buttons is refused
    assert orders.get_order(1)[0]["status"] == "PENDING"
    await env.press(ADMIN, accept)
    assert orders.get_order(1)[0]["status"] == "ACCEPTED"
    assert any("was accepted" in t for t in session.texts(CUSTOMER))


async def test_search_requires_an_address_first(bot_env):
    env, session = bot_env, bot_env.session
    await env.say(CUSTOMER, "biryani")
    assert any("Where should I deliver" in t for t in session.texts(CUSTOMER))


async def test_show_menu_by_restaurant_name(bot_env):
    env, session = bot_env, bot_env.session
    rest = next(iter(catalogue.RESTAURANTS.values()))
    await env.say(CUSTOMER, f"show me menu of {rest.name}")
    assert any(rest.name in t and "₹" in t for t in session.texts(CUSTOMER))


async def test_unknown_dish_gets_helpful_message(bot_env):
    db.set_location(CUSTOMER, *KORAMANGALA, "x")
    await bot_env.say(CUSTOMER, "xylophone")
    assert any("couldn't find" in t for t in bot_env.session.texts(CUSTOMER))
