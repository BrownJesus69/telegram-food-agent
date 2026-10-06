"""End-to-end conversation tests: real handlers + real database, with Telegram's HTTP layer replaced by a recorder."""
from datetime import datetime

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Chat, Location, Message, MessageEntity, Update, User

from foodbot import config, db, orders
from foodbot.handlers import router

from .conftest import KORAMANGALA

CUSTOMER, ADMIN = 1, 999


class RecordingSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent: list = []
        self._mid = 100

    async def close(self):
        pass

    async def stream_content(self, *a, **kw):
        yield b""

    async def make_request(self, bot, method, timeout=None):
        self.sent.append(method)
        if isinstance(method, (SendMessage, EditMessageText)):
            self._mid += 1
            return Message(message_id=self._mid, date=datetime.now(), chat=Chat(id=method.chat_id if hasattr(method, "chat_id") and method.chat_id else CUSTOMER, type="private"),
                           text=getattr(method, "text", ""))
        return True

    def texts(self, chat_id=None):
        return [m.text for m in self.sent if isinstance(m, SendMessage) and (chat_id is None or m.chat_id == chat_id)]

    def buttons(self, chat_id=None):
        out = []
        for m in self.sent:
            if isinstance(m, SendMessage) and (chat_id is None or m.chat_id == chat_id):
                kb = getattr(m, "reply_markup", None)
                for row in getattr(kb, "inline_keyboard", []) or []:
                    out += [b.callback_data for b in row if b.callback_data]
        return out


@pytest.fixture
def bot_env(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_IDS", {ADMIN})
    session = RecordingSession()
    bot = Bot("123456:TEST", session=session)
    dp = Dispatcher()
    router._parent_router = None          # the module-level router is reused across tests; aiogram forbids re-attaching
    dp.include_router(router)
    return dp, bot, session


def _user(uid):
    return User(id=uid, is_bot=False, first_name="Tester" if uid == CUSTOMER else "Admin")


def _msg(uid, text=None, location=None, mid=1):
    entities = [MessageEntity(type="bot_command", offset=0, length=len(text.split()[0]))] if text and text.startswith("/") else None
    return Message(message_id=mid, date=datetime.now(), chat=Chat(id=uid, type="private"), from_user=_user(uid),
                   text=text, entities=entities, location=location)


async def say(env, uid, text):
    dp, bot, _ = env
    await dp.feed_update(bot, Update(update_id=1, message=_msg(uid, text)))


async def press(env, uid, data):
    dp, bot, _ = env
    cb = CallbackQuery(id="cb1", from_user=_user(uid), chat_instance="ci", data=data, message=_msg(uid, "x"))
    await dp.feed_update(bot, Update(update_id=2, callback_query=cb))


async def test_full_order_journey(bot_env):
    """start -> location -> search -> select -> checkout -> confirm -> admin accepts -> customer is told."""
    _, _, session = bot_env
    await say(bot_env, CUSTOMER, "/start")
    assert any("simulated" in t for t in session.texts(CUSTOMER))

    dp, bot, _ = bot_env
    await dp.feed_update(bot, Update(update_id=3, message=_msg(CUSTOMER, location=Location(latitude=KORAMANGALA[0], longitude=KORAMANGALA[1]))))
    assert any("Location saved" in t for t in session.texts(CUSTOMER))

    await say(bot_env, CUSTOMER, "3 chicken biryani under 300")
    sel = next(b for b in session.buttons(CUSTOMER) if b.startswith("sel:"))
    assert sel.endswith(":3")
    await press(bot_env, CUSTOMER, sel)
    assert any("Your cart" in t for t in session.texts(CUSTOMER))

    await press(bot_env, CUSTOMER, "checkout")
    await press(bot_env, CUSTOMER, "skip_landmark")
    confirm = [b for b in session.buttons(CUSTOMER) if b.startswith("confirm:")][-1]
    await press(bot_env, CUSTOMER, confirm)
    await press(bot_env, CUSTOMER, confirm)                              # double tap must not create a second order
    assert len(orders.recent_orders(10)) == 1
    assert any("ORDER #1" in t for t in session.texts(ADMIN))

    accept = next(b for b in session.buttons(ADMIN) if b.startswith("adm:ACCEPTED"))
    await press(bot_env, CUSTOMER, accept)                               # a customer pressing admin buttons is refused
    assert orders.get_order(1)[0]["status"] == "PENDING"
    await press(bot_env, ADMIN, accept)
    assert orders.get_order(1)[0]["status"] == "ACCEPTED"
    assert any("was accepted" in t for t in session.texts(CUSTOMER))


async def test_search_requires_location_first(bot_env):
    _, _, session = bot_env
    await say(bot_env, CUSTOMER, "/start")
    await say(bot_env, CUSTOMER, "biryani")
    assert any("share your location" in t.lower() for t in session.texts(CUSTOMER))


async def test_show_menu_by_restaurant_name(bot_env):
    _, _, session = bot_env
    from foodbot.services import catalogue
    rest = next(iter(catalogue.RESTAURANTS.values()))
    await say(bot_env, CUSTOMER, "/start")
    await say(bot_env, CUSTOMER, f"show me menu of {rest.name}")
    assert any(rest.name in t and "₹" in t for t in session.texts(CUSTOMER))


async def test_unknown_dish_gets_helpful_message(bot_env):
    _, _, session = bot_env
    db.upsert_user(CUSTOMER, "Tester")
    db.set_location(CUSTOMER, *KORAMANGALA, "x")
    await say(bot_env, CUSTOMER, "xylophone")
    assert any("couldn't find" in t for t in session.texts(CUSTOMER))
