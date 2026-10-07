"""Map-picker Mini App: the bot side. The page's sendData() payload is client-controlled, so it is untrusted input."""
import json

import pytest
from aiogram.methods import SendMessage
from aiogram.types import ReplyKeyboardRemove

from foodbot import address_flow, config, db, geocoding
from foodbot import keyboards as kb

from .bot_harness import CUSTOMER

KORAMANGALA_PIN = {"lat": 12.9352, "lon": 77.6245}
URL = "https://example.github.io/telegram-food-agent/"


def _pick(lat, lon):
    return json.dumps({"lat": lat, "lon": lon})


def _snapshot(uid):
    user = db.get_user(uid)
    return user["draft"], user["awaiting"], [tuple(a) for a in db.list_addresses(uid)]


# ------------------------------------------------------------------------------- the button
def _flat_buttons(markup):
    return [b for row in markup.keyboard for b in row]


def test_map_button_offered_only_when_miniapp_url_is_set(monkeypatch):
    monkeypatch.setattr(config, "MINIAPP_URL", "")
    assert [b.request_location for b in _flat_buttons(kb.location_request())] == [True]

    monkeypatch.setattr(config, "MINIAPP_URL", URL)
    buttons = _flat_buttons(kb.location_request())
    assert [b.text for b in buttons] == ["📍 Share location", "🗺 Pick on map"]
    assert buttons[1].web_app.url == URL


@pytest.mark.parametrize("url", ["http://example.com/map", "javascript:alert(1)", "example.com/map", "   "])
def test_non_https_miniapp_url_is_never_offered(monkeypatch, url):
    monkeypatch.setattr(config, "MINIAPP_URL", url)       # Telegram only accepts https web apps
    assert all(b.web_app is None for b in _flat_buttons(kb.location_request()))


async def test_address_prompt_carries_the_map_button_only_when_configured(bot_env, monkeypatch):
    env, session = bot_env, bot_env.session

    async def open_add_prompt():
        session.sent.clear()
        await env.press(CUSTOMER, "addr:cancel")          # reset any half-finished address step
        session.sent.clear()
        await env.say(CUSTOMER, "change address")
        await env.press(CUSTOMER, env.button("addr:new:"))
        prompts = [m for m in session.of(SendMessage) if m.reply_markup is not None and hasattr(m.reply_markup, "keyboard")]
        assert prompts, "address prompt must carry the reply keyboard"
        return _flat_buttons(prompts[-1].reply_markup)

    monkeypatch.setattr(config, "MINIAPP_URL", "")
    assert not any(b.web_app for b in await open_add_prompt())
    monkeypatch.setattr(config, "MINIAPP_URL", URL)
    assert any(b.web_app and b.web_app.url == URL for b in await open_add_prompt())


# ------------------------------------------------------------------------- the happy path
async def test_valid_pick_goes_to_the_label_prompt_and_saves_like_a_gps_pin(bot_env):
    env, session = bot_env, bot_env.session
    await env.send_web_app_data(CUSTOMER, _pick(**KORAMANGALA_PIN))
    assert "What should I call this address?" in session.last_text()
    assert "label" not in db.get_draft(CUSTOMER)
    assert (db.get_draft(CUSTOMER)["lat"], db.get_draft(CUSTOMER)["lon"]) == (12.9352, 77.6245)
    # the map keyboard is removed once the pick arrives
    assert any(isinstance(m.reply_markup, ReplyKeyboardRemove) for m in session.of(SendMessage))

    await env.press(CUSTOMER, "addr:lbl:home")
    saved = db.get_active_address(CUSTOMER)
    assert saved["label"] == "Home" and (saved["latitude"], saved["longitude"]) == (12.9352, 77.6245)


async def test_friend_flow_works_from_a_map_pick(bot_env):
    env, session = bot_env, bot_env.session
    await env.send_web_app_data(CUSTOMER, _pick(12.9698, 77.75))        # Whitefield
    await env.press(CUSTOMER, "addr:lbl:friend")
    await env.say(CUSTOMER, "Asha")
    await env.say(CUSTOMER, "98450 12345")
    saved = db.get_active_address(CUSTOMER)
    assert saved["label"] == "Friend" and saved["recipient_name"] == "Asha"
    assert "Recipient" in session.last_text() or any("Recipient" in t for t in session.texts(CUSTOMER))


# --------------------------------------------------------------------------- out of area
@pytest.mark.parametrize("lat,lon", [(28.6139, 77.2090), (0.0, 0.0), (12.97, 78.5), (-12.97, 77.59), (90.0, 180.0)])
async def test_pick_outside_bengaluru_is_rejected_like_a_gps_pin(bot_env, lat, lon):
    env, session = bot_env, bot_env.session
    await env.send_web_app_data(CUSTOMER, _pick(lat, lon))
    assert any("outside Bengaluru" in t for t in session.texts(CUSTOMER))
    assert any(b.startswith("addr:area:") for b in session.buttons(CUSTOMER))
    assert "lat" not in db.get_draft(CUSTOMER) and db.list_addresses(CUSTOMER) == []


# ----------------------------------------------------------------------- hostile payloads
def _ids(raw):
    return repr(raw)[:24]


HOSTILE = [
    "",
    "not json",
    "{",
    "null",
    "[]",
    "[12.9, 77.6]",
    '"12.9,77.6"',
    "12.9",
    "{}",
    '{"lat": 12.9}',
    '{"lon": 77.6}',
    '{"lat": "12.9", "lon": "77.6"}',
    '{"lat": null, "lon": 77.6}',
    '{"lat": true, "lon": true}',
    '{"lat": [12.9], "lon": {"x": 1}}',
    '{"lat": NaN, "lon": 77.6}',
    '{"lat": 12.9, "lon": Infinity}',
    '{"lat": -Infinity, "lon": 77.6}',
    '{"lat": 1e999, "lon": 77.6}',
    '{"lat": 91, "lon": 77.6}',
    '{"lat": 12.9, "lon": 181}',
    '{"lat": 12.9, "lon": -181}',
    '{"lat": 1' + "0" * 400 + ', "lon": 77.6}',
    "[" * 5000,
    '{"lat": 12.9, "lon": 77.6, "pad": "' + "x" * 600 + '"}',            # oversized
    "x" * 100_000,
    '{"lat": 12.9, "lon": 77.6}\x00',
    "\ud800",                                                           # lone surrogate
]


@pytest.mark.parametrize("raw", HOSTILE, ids=_ids)
def test_parser_rejects_hostile_payloads_without_raising(raw):
    assert address_flow.parse_miniapp_pin(raw) is None


@pytest.mark.parametrize("raw", [None, 12, b'{"lat": 12.9, "lon": 77.6}', ["lat"]])
def test_parser_rejects_non_strings(raw):
    assert address_flow.parse_miniapp_pin(raw) is None


@pytest.mark.parametrize("raw,expected", [
    ('{"lat": 12.9716, "lon": 77.5946}', (12.9716, 77.5946)),
    ('{"lat": 13, "lon": 77}', (13.0, 77.0)),
    ('{"lat": 12.97161234567, "lon": 77.59461234567}', (12.971612, 77.594612)),     # rounded to ~0.1 m
    ('{"lat": 12.9, "lon": 77.6, "extra": 1}', (12.9, 77.6)),
])
def test_parser_accepts_well_formed_payloads(raw, expected):
    assert address_flow.parse_miniapp_pin(raw) == expected


@pytest.mark.parametrize("raw", HOSTILE, ids=_ids)
async def test_hostile_payload_gets_a_friendly_reply_and_changes_nothing(bot_env, raw):
    env, session = bot_env, bot_env.session
    before = _snapshot(CUSTOMER)
    await env.send_web_app_data(CUSTOMER, raw)                       # must not raise
    assert "couldn't read that map pick" in session.last_text()
    assert _snapshot(CUSTOMER) == before
    assert not any(isinstance(m.reply_markup, ReplyKeyboardRemove) for m in session.of(SendMessage))   # leave the map for a retry


async def test_hostile_payload_does_not_disturb_a_pending_address_step(bot_env):
    env = bot_env
    await env.send_web_app_data(CUSTOMER, _pick(**KORAMANGALA_PIN))
    before = _snapshot(CUSTOMER)
    await env.send_web_app_data(CUSTOMER, '{"lat": NaN, "lon": 1}')
    assert _snapshot(CUSTOMER) == before
    await env.press(CUSTOMER, "addr:lbl:office")                       # the earlier valid pick can still be completed
    assert db.get_active_address(CUSTOMER)["label"] == "Office"


def test_miniapp_and_bot_agree_on_the_service_area():
    """docs/miniapp/index.html hard-codes the bounding box; it must match the bot's, or the page would offer unusable pins."""
    from pathlib import Path
    page = (Path(__file__).resolve().parent.parent / "docs" / "miniapp" / "index.html").read_text(encoding="utf-8")
    lat_min, lat_max, lon_min, lon_max = geocoding.BENGALURU_BBOX
    for value in (lat_min, lat_max, lon_min, lon_max):
        assert f"{value:.2f}" in page, f"{value} missing from docs/miniapp/index.html"
