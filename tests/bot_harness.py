"""Drive the real handlers with Telegram's HTTP layer replaced by a recorder (no network, no token needed)."""
import re
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.enums import ParseMode
from aiogram.methods import EditMessageLiveLocation, EditMessageText, SendLocation, SendMessage, StopMessageLiveLocation
from aiogram.types import CallbackQuery, Chat, Location, Message, MessageEntity, Update, User

from foodbot import address_flow
from foodbot.handlers import router

CUSTOMER, ADMIN = 1, 999

_ALLOWED_TAGS = {"b", "i", "u", "s", "a", "code", "pre"}
_TAG = re.compile(r"<(/?)([a-zA-Z]+)[^>]*>")
_BAD_AMP = re.compile(r"&(?!(?:amp|lt|gt|quot);|#\d+;|#x[0-9a-fA-F]+;)")


def assert_valid_telegram_html(text: str):
    """Telegram rejects the whole message on malformed HTML; catch that here instead of in production."""
    stack = []
    for m in _TAG.finditer(text):
        closing, name = m.group(1), m.group(2).lower()
        assert name in _ALLOWED_TAGS, f"unsupported tag <{name}> in {text!r}"
        if closing:
            assert stack and stack.pop() == name, f"unbalanced </{name}> in {text!r}"
        else:
            stack.append(name)
    assert not stack, f"unclosed tags {stack} in {text!r}"
    stripped = _TAG.sub("", text)
    assert "<" not in stripped and ">" not in stripped.replace("&gt;", ""), f"raw angle bracket in {text!r}"
    assert not _BAD_AMP.search(stripped), f"unescaped & in {text!r}"
    assert len(text) <= 4096, "message too long for Telegram"


def assert_valid_markup(markup):
    for row in getattr(markup, "inline_keyboard", []) or []:
        for b in row:
            assert b.text.strip(), "empty button text"
            if b.callback_data:
                assert len(b.callback_data.encode()) <= 64, f"callback_data too long: {b.callback_data!r}"


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
            assert_valid_telegram_html(method.text or "")
            assert_valid_markup(getattr(method, "reply_markup", None))
            self._mid += 1
            chat_id = getattr(method, "chat_id", None) or CUSTOMER
            return Message(message_id=self._mid, date=datetime.now(), chat=Chat(id=chat_id, type="private"),
                           text=getattr(method, "text", ""))
        if isinstance(method, SendLocation):
            self._mid += 1
            return Message(message_id=self._mid, date=datetime.now(), chat=Chat(id=method.chat_id, type="private"),
                           location=Location(latitude=method.latitude, longitude=method.longitude))
        if isinstance(method, (EditMessageLiveLocation, StopMessageLiveLocation)):
            return True
        return True

    def texts(self, chat_id=None):
        return [m.text for m in self.sent if isinstance(m, SendMessage) and (chat_id is None or m.chat_id == chat_id)]

    def of(self, cls):
        return [m for m in self.sent if isinstance(m, cls)]

    def last_text(self, chat_id=CUSTOMER):
        t = self.texts(chat_id)
        return t[-1] if t else ""

    def buttons(self, chat_id=None):
        out = []
        for m in self.sent:
            if isinstance(m, SendMessage) and (chat_id is None or m.chat_id == chat_id):
                kb = getattr(m, "reply_markup", None)
                for row in getattr(kb, "inline_keyboard", []) or []:
                    out += [b.callback_data for b in row if b.callback_data]
        return out

    def button_labels(self, chat_id=None):
        out = []
        for m in self.sent:
            if isinstance(m, SendMessage) and (chat_id is None or m.chat_id == chat_id):
                for row in getattr(getattr(m, "reply_markup", None), "inline_keyboard", []) or []:
                    out += [(b.text, b.callback_data) for b in row if b.callback_data]
        return out


class BotEnv:
    def __init__(self):
        self.session = RecordingSession()
        self.bot = Bot("123456:TEST", session=self.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.dp = Dispatcher()
        for r in (address_flow.router, router):
            r._parent_router = None          # module-level routers are reused across tests; aiogram forbids re-attaching
            self.dp.include_router(r)
        self._uid = 10

    def _next(self):
        self._uid += 1
        return self._uid

    @staticmethod
    def user(uid):
        return User(id=uid, is_bot=False, first_name="Tester" if uid == CUSTOMER else "Admin")

    def _msg(self, uid, text=None, location=None):
        ents = [MessageEntity(type="bot_command", offset=0, length=len(text.split()[0]))] if text and text.startswith("/") else None
        return Message(message_id=self._next(), date=datetime.now(), chat=Chat(id=uid, type="private"),
                       from_user=self.user(uid), text=text, entities=ents, location=location)

    async def say(self, uid, text):
        await self.dp.feed_update(self.bot, Update(update_id=self._next(), message=self._msg(uid, text)))

    async def send_location(self, uid, lat, lon):
        await self.dp.feed_update(self.bot, Update(update_id=self._next(),
                                  message=self._msg(uid, location=Location(latitude=lat, longitude=lon))))

    async def press(self, uid, data):
        cb = CallbackQuery(id=str(self._next()), from_user=self.user(uid), chat_instance="ci", data=data,
                           message=self._msg(uid, "x"))
        await self.dp.feed_update(self.bot, Update(update_id=self._next(), callback_query=cb))

    def button(self, prefix, chat_id=CUSTOMER, last=True):
        found = [b for b in self.session.buttons(chat_id) if b.startswith(prefix)]
        assert found, f"no button starting with {prefix!r}; have {self.session.buttons(chat_id)[-8:]}"
        return found[-1] if last else found[0]
