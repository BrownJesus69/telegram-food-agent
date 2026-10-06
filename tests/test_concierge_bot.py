"""The concierge inside the real conversation: plans, quick picks, voice, explanations, AI second opinion."""
from datetime import datetime

from aiogram.methods import AnswerCallbackQuery
from aiogram.types import Chat, Message, Update, Voice

from foodbot import db, handlers, orders
from foodbot.concierge.intent import from_dict

from .bot_harness import CUSTOMER
from .conftest import KORAMANGALA


def _located():
    db.add_address(CUSTOMER, "Home", "Koramangala flat", *KORAMANGALA, "Tester")


async def test_group_request_becomes_a_one_tap_cart(bot_env):
    env, session = bot_env, bot_env.session
    _located()
    await env.say(CUSTOMER, "feed 4 people, 2 veg and 2 non veg under 1500")
    assert any("🧠" in t and "2 veg + 2 non-veg" in t and "for 4" in t for t in session.texts(CUSTOMER))
    card = next(t for t in session.texts(CUSTOMER) if "One order," in t)
    assert "serves every diet in one order" in card and "✨" in card
    await env.press(CUSTOMER, env.button("plan:"))
    s = orders.cart_summary(CUSTOMER)
    assert len(s["lines"]) == 2 and s["subtotal"] <= 1500
    assert "Your cart" in session.last_text()


async def test_plan_button_is_private_to_the_user_it_was_offered_to(bot_env):
    env, session = bot_env, bot_env.session
    _located()
    await env.say(CUSTOMER, "feed 4 people, 2 veg and 2 non veg under 1500")
    token_btn = env.button("plan:")
    db.upsert_user(2, "Other")
    await env.press(2, token_btn)
    assert orders.cart_summary(2) is None
    alerts = [m.text for m in session.sent if isinstance(m, AnswerCallbackQuery) and m.text]
    assert any("expired" in a for a in alerts)


async def test_vague_request_shows_what_was_understood_and_why(bot_env):
    env, session = bot_env, bot_env.session
    _located()
    await env.say(CUSTOMER, "light dinner for 2 under 500, no onion garlic")
    header = next(t for t in session.texts(CUSTOMER) if "🧠" in t)
    assert "dinner" in header and "light" in header and "no onion-garlic" in header
    cards = [t for t in session.texts(CUSTOMER) if "✨" in t]
    assert cards and all("Jain-friendly" in c for c in cards)


async def test_greeting_offers_quick_picks_for_the_time_of_day(bot_env):
    env, session = bot_env, bot_env.session
    await env.say(CUSTOMER, "hi")
    assert "Bengaluru" in session.last_text()
    picks = [b for b in session.buttons(CUSTOMER) if b.startswith("ask:")]
    assert len(picks) == 3
    _located()
    await env.press(CUSTOMER, picks[0])
    assert any("🧠" in t for t in session.texts(CUSTOMER))


async def test_nothing_found_explains_why(bot_env):
    env, session = bot_env, bot_env.session
    _located()
    await env.say(CUSTOMER, "biryani under 100")
    msg = session.last_text()
    assert "couldn't find a match" in msg and "Cheapest match" in msg and "₹100" in msg
    assert any(b == "addr:book:s" for b in session.buttons(CUSTOMER))


async def test_typos_are_handled_by_the_rules_without_any_llm(bot_env):
    env, session = bot_env, bot_env.session
    _located()
    await env.say(CUSTOMER, "msala dosee")                       # two typos; the planner's fuzzy matching still finds dosa
    assert env.button("sel:")
    assert not any("AI-assisted" in t for t in session.texts(CUSTOMER))


async def test_unknown_text_with_ai_second_opinion(bot_env, monkeypatch):
    env, session = bot_env, bot_env.session
    _located()

    async def fake_second_opinion(text, req, **kw):
        assert "gorkhali" in text
        return from_dict({"dishes": ["masala dosa"]}, raw=text, source="llm")

    monkeypatch.setattr(handlers, "second_opinion", fake_second_opinion)
    await env.say(CUSTOMER, "gorkhali thindi")
    header = next(t for t in session.texts(CUSTOMER) if "🧠" in t)
    assert "masala dosa" in header and "AI-assisted" in header
    assert env.button("sel:")


async def test_voice_note_is_transcribed_then_handled_like_text(bot_env, monkeypatch):
    env, session = bot_env, bot_env.session
    _located()

    async def fake_transcribe(bot, voice):
        return "chicken biryani under 400"

    monkeypatch.setattr(handlers, "transcribe_voice", fake_transcribe)
    msg = Message(message_id=5, date=datetime.now(), chat=Chat(id=CUSTOMER, type="private"), from_user=env.user(CUSTOMER),
                  voice=Voice(file_id="f", file_unique_id="u", duration=4))
    await env.dp.feed_update(env.bot, Update(update_id=1, message=msg))
    assert any("I heard" in t and "chicken biryani under 400" in t for t in session.texts(CUSTOMER))
    assert any("🧠" in t and "chicken biryani" in t for t in session.texts(CUSTOMER))


async def test_voice_failure_and_length_limit(bot_env, monkeypatch):
    env, session = bot_env, bot_env.session

    async def nothing(bot, voice):
        return None

    monkeypatch.setattr(handlers, "transcribe_voice", nothing)
    for duration, expect in ((5, "couldn't make that out"), (90, "30 seconds")):
        msg = Message(message_id=6, date=datetime.now(), chat=Chat(id=CUSTOMER, type="private"), from_user=env.user(CUSTOMER),
                      voice=Voice(file_id="f", file_unique_id="u", duration=duration))
        await env.dp.feed_update(env.bot, Update(update_id=2, message=msg))
        assert expect in session.last_text()


async def test_changing_address_reruns_the_concierge_request(bot_env):
    env, session = bot_env, bot_env.session
    _located()
    office = db.add_address(CUSTOMER, "Office", "Tech park, Whitefield", 12.9698, 77.75, "Tester", activate=False)
    await env.say(CUSTOMER, "veg biryani")
    first = list(handlers.LAST_SHOWN[CUSTOMER])
    await env.press(CUSTOMER, f"addr:use:{office}:s")
    assert any("Re-checking" in t for t in session.texts(CUSTOMER))
    assert list(handlers.LAST_SHOWN[CUSTOMER]) != first


async def test_budget_miss_is_explained_without_bothering_the_llm(bot_env, monkeypatch):
    """Found in live QA: 'biryani under 100' was labelled AI-assisted although the budget explained the miss."""
    env, session = bot_env, bot_env.session
    _located()

    async def must_not_be_called(*a, **k):
        raise AssertionError("an explainable miss must not spend an LLM call")

    monkeypatch.setattr(handlers, "second_opinion", must_not_be_called)
    await env.say(CUSTOMER, "biryani under 100")
    msg = session.last_text()
    assert "Cheapest match" in msg and "AI-assisted" not in msg and "biryani · Biryani" not in msg
