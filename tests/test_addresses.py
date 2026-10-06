"""Delivery addresses: address book, switching anywhere, ordering for someone else, and data safety."""
import sqlite3

import pytest

from foodbot import db, geocoding, orders
from foodbot.services import catalogue
from foodbot.services.search import search_items

from .bot_harness import ADMIN, CUSTOMER
from .conftest import KORAMANGALA, NOON

WHITEFIELD = (12.9698, 77.7500)


def _orderable_near(point):
    return next(r for r in search_items("biryani", *point, limit=50, now=NOON) if r.item.price * 2 >= r.restaurant.min_order)


# ------------------------------------------------------------------------ database layer
def test_address_book_crud_and_label_reuse():
    home = db.add_address(1, "Home", "12 5th Block, Koramangala", *KORAMANGALA, "Tester")
    office = db.add_address(1, "Office", "ITPL, Whitefield", *WHITEFIELD, "Tester", activate=False)
    assert db.get_active_address(1)["id"] == home
    assert [a["label"] for a in db.list_addresses(1)] == ["Home", "Office"]
    assert db.set_active_address(1, office) and db.location_of(1) == WHITEFIELD
    # same label again replaces instead of duplicating
    again = db.add_address(1, "office", "New tower, Whitefield", *WHITEFIELD, "Tester", activate=False)
    assert again == office and len(db.list_addresses(1)) == 2
    assert db.delete_address(1, office)
    assert db.get_active_address(1) is None                 # deleting the active address leaves none selected
    assert not db.set_active_address(1, office)             # and a deleted address cannot be re-activated


def test_addresses_are_private_to_their_owner():
    db.upsert_user(2, "Other")
    mine = db.add_address(1, "Home", "x", *KORAMANGALA)
    assert db.get_address(mine, 2) is None
    assert not db.set_active_address(2, mine)
    assert not db.delete_address(2, mine)
    assert not db.update_recipient(2, mine, "A", None)


def test_legacy_database_is_migrated(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE users(telegram_id INTEGER PRIMARY KEY, name TEXT, latitude REAL, longitude REAL, address TEXT,
                           awaiting TEXT, landmark TEXT, pending_key TEXT, updated_at TEXT);
        CREATE TABLE orders(id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, customer_name TEXT,
            restaurant_id TEXT NOT NULL, status TEXT NOT NULL, subtotal INTEGER NOT NULL, delivery_fee INTEGER NOT NULL,
            total INTEGER NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, address TEXT, landmark TEXT,
            eta_min INTEGER, eta_max INTEGER, payment_method TEXT NOT NULL DEFAULT 'COD',
            confirmation_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        INSERT INTO users VALUES(7,'Old User',12.93,77.62,'Old pin',NULL,NULL,NULL,'t');
    """)
    conn.commit()
    conn.close()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    db.init_db()
    db.init_db()                                             # idempotent
    a = db.get_active_address(7)
    assert a and (a["latitude"], a["longitude"]) == (12.93, 77.62) and len(db.list_addresses(7)) == 1
    cols = {r["name"] for r in db.connect().execute("PRAGMA table_info(orders)")}
    assert {"address_label", "recipient_name", "recipient_phone"} <= cols


# -------------------------------------------------------------------------- geocoding
def test_area_matching_and_bounds():
    assert geocoding.area_matches("Indiranagar")[0].label.startswith("Indiranagar")
    assert geocoding.area_matches("near koramangala 5th block")[0].label.startswith("Koramangala")
    assert geocoding.area_matches("Indranagar")                         # typo still resolves
    assert geocoding.area_matches("Atlantis") == []
    assert geocoding.in_bengaluru(*KORAMANGALA) and not geocoding.in_bengaluru(28.61, 77.20)    # Delhi
    assert all(geocoding.in_bengaluru(lat, lon) for lat, lon, _ in catalogue.localities().values())


@pytest.mark.parametrize("raw, expected", [
    ("98450 12345", "+919845012345"), ("+91 98450-12345", "+919845012345"), ("919845012345", "+919845012345"),
    ("12345", None), ("5845012345", None), ("call me", None), ("", None),
])
def test_phone_normalisation(raw, expected):
    assert geocoding.normalise_phone(raw) == expected


def test_name_cleaning():
    assert geocoding.clean_name("  Priya   Sharma ") == "Priya Sharma"
    assert geocoding.clean_name("A") is None
    assert len(geocoding.clean_name("x" * 100)) == 40
    assert "<" not in geocoding.clean_name("<b>Mom</b>")


# --------------------------------------------------------------------- conversation flows
async def test_switch_between_home_and_office_changes_results(bot_env):
    env, session = bot_env, bot_env.session
    from foodbot import handlers
    home = db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    office = db.add_address(CUSTOMER, "Office", "Tech park, Whitefield", *WHITEFIELD, "Tester", activate=False)
    await env.say(CUSTOMER, "biryani")
    at_home = list(handlers.LAST_SHOWN[CUSTOMER])
    assert at_home and any("Home" in t for t in session.texts(CUSTOMER))

    await env.press(CUSTOMER, f"addr:use:{office}:s")                    # one tap from the results screen
    at_office = list(handlers.LAST_SHOWN[CUSTOMER])
    assert at_office and at_office != at_home
    assert any("Office" in t and "Delivering to" in t for t in session.texts(CUSTOMER))
    assert db.get_active_address(CUSTOMER)["id"] == office and home != office


async def test_natural_language_address_commands(bot_env):
    env, session = bot_env, bot_env.session
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    office = db.add_address(CUSTOMER, "Office", "Tech park, Whitefield", *WHITEFIELD, "Tester", activate=False)
    await env.say(CUSTOMER, "Deliver to office")
    assert db.get_active_address(CUSTOMER)["id"] == office
    await env.say(CUSTOMER, "change address")
    assert any(b.startswith("addr:use:") for b in session.buttons(CUSTOMER))
    assert "Where should we deliver" in session.last_text()


async def test_cart_reacts_when_address_moves_out_of_range(bot_env):
    env, session = bot_env, bot_env.session
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    far = db.add_address(CUSTOMER, "Office", "Tech park, Whitefield", *WHITEFIELD, "Tester", activate=False)
    orders.add_item(CUSTOMER, _orderable_near(KORAMANGALA).item.id, 2)
    assert not orders.cart_summary(CUSTOMER)["issues"]
    await env.press(CUSTOMER, f"addr:use:{far}:c")                       # change address from the cart screen
    assert "deliver to Office" in session.last_text() and "km away" in session.last_text()


async def test_pin_outside_bengaluru_is_refused_with_a_way_forward(bot_env):
    env, session = bot_env, bot_env.session
    await env.send_location(CUSTOMER, 28.6139, 77.2090)                  # Delhi
    assert any("outside Bengaluru" in t for t in session.texts(CUSTOMER))
    assert any(b.startswith("addr:area:") for b in session.buttons(CUSTOMER))
    assert db.list_addresses(CUSTOMER) == []


async def test_order_for_a_friend_across_town(bot_env):
    """Type an area, mark it as a friend's place, give name + phone, order, and the admin sees who to deliver to."""
    env, session = bot_env, bot_env.session
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    await env.say(CUSTOMER, "change address")
    await env.press(CUSTOMER, env.button("addr:new:"))
    await env.say(CUSTOMER, "Whitefield")
    assert "Which one is it" in session.last_text()
    await env.press(CUSTOMER, "addr:pick:0")
    await env.press(CUSTOMER, "addr:lbl:friend")
    await env.say(CUSTOMER, "Priya Sharma")
    await env.say(CUSTOMER, "12345")                                     # invalid phone is re-asked, not accepted
    assert "doesn't look like an Indian mobile number" in session.last_text()
    await env.say(CUSTOMER, "98450 12345")
    friend = db.get_active_address(CUSTOMER)
    assert friend["label"] == "Friend" and friend["recipient_name"] == "Priya Sharma"
    assert friend["recipient_phone"] == "+919845012345"

    await env.say(CUSTOMER, "3 chicken biryani under 300")
    await env.press(CUSTOMER, env.button("sel:"))
    await env.press(CUSTOMER, "checkout")
    await env.press(CUSTOMER, "skip_landmark")
    assert "Priya Sharma" in session.last_text() and "Friend" in session.last_text()
    await env.press(CUSTOMER, env.button("confirm:"))

    card = next(t for t in session.texts(ADMIN) if "ORDER #1" in t)
    assert "Priya Sharma" in card and "+919845012345" in card and "Friend" in card
    order, _ = orders.get_order(1)
    assert (order["recipient_name"], order["address_label"]) == ("Priya Sharma", "Friend")

    # the order is a snapshot: later edits to the address book never rewrite history
    db.add_address(CUSTOMER, "Friend", "Somewhere else entirely", *KORAMANGALA, "Someone Else", None)
    again, _ = orders.get_order(1)
    assert again["address"] == order["address"] and again["recipient_name"] == "Priya Sharma"


async def test_change_recipient_from_confirm_screen(bot_env):
    env, session = bot_env, bot_env.session
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")
    orders.add_item(CUSTOMER, _orderable_near(KORAMANGALA).item.id, 2)
    await env.press(CUSTOMER, "checkout")
    await env.press(CUSTOMER, "skip_landmark")
    first_key = env.button("confirm:")
    labels = [t for t, _ in session.button_labels(CUSTOMER)]
    assert "📍 Change address" in labels and "👤 Change recipient" in labels

    await env.press(CUSTOMER, "addr:rcpt:k")
    await env.say(CUSTOMER, "Mom")
    await env.say(CUSTOMER, "9845012345")
    assert "Recipient: Mom · +919845012345" in session.last_text()
    assert env.button("confirm:") != first_key                           # a fresh checkout key was issued
    with pytest.raises(orders.OrderError):                               # the stale one must not place an order
        orders.create_order(CUSTOMER, first_key)
