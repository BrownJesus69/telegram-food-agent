"""Structured logging with per-update context, a global error net, and a per-user rate limiter (aiogram middleware)."""
from __future__ import annotations

import contextvars
import json
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Update

from foodbot import config, metrics

log = logging.getLogger(__name__)
update_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar("update_ctx", default=None)


# ------------------------------------------------------------------------------ logging
class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        c = update_ctx.get() or {}
        record.update_id = c.get("update_id")
        record.user_id = c.get("user_id")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("update_id", "user_id"):
            if getattr(record, key, None) is not None:
                out[key] = getattr(record, key)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def setup_logging(fmt: str = "text", level: int = logging.INFO):
    handler = logging.StreamHandler()
    handler.addFilter(ContextFilter())
    handler.setFormatter(
        JsonFormatter() if fmt == "json"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s [u=%(user_id)s]")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)       # request URLs can carry API keys in some clients
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)


# ------------------------------------------------------------------------------ rate limiting
class TokenBucket:
    """`burst` tokens, refilled at `per_second`. One bucket per user."""

    def __init__(self, burst: float, per_second: float, clock: Callable[[], float] = time.monotonic):
        self.burst, self.rate, self.clock = burst, per_second, clock
        self.state: dict[int, tuple[float, float]] = {}

    def allow(self, key: int) -> bool:
        now = self.clock()
        tokens, last = self.state.get(key, (self.burst, now))
        tokens = min(self.burst, tokens + (now - last) * self.rate)
        ok = tokens >= 1
        self.state[key] = (tokens - 1 if ok else tokens, now)
        if len(self.state) > 5000:                               # bound memory under abuse
            self.state = dict(list(self.state.items())[-2500:])
        return ok


def _who(update: Update):
    """(kind, user_id, chat_id) of an update."""
    if update.message:
        return "message", update.message.from_user.id if update.message.from_user else None, update.message.chat.id
    if update.callback_query:
        cb = update.callback_query
        return "callback", cb.from_user.id, cb.message.chat.id if cb.message else cb.from_user.id
    return "other", None, None


class UpdateMiddleware(BaseMiddleware):
    """Outermost middleware: context, rate limit, latency metrics, and a net so no exception goes unnoticed."""

    def __init__(self, bucket: TokenBucket | None = None):
        self.bucket = bucket or TokenBucket(config.THROTTLE_BURST, config.THROTTLE_PER_SECOND)
        self.warned: dict[int, float] = {}

    async def __call__(self, handler: Callable[[Update, dict], Awaitable[Any]], event: Update, data: dict) -> Any:
        kind, user_id, chat_id = _who(event)
        token = update_ctx.set({"update_id": event.update_id, "user_id": user_id})
        started = time.perf_counter()
        bot = data.get("bot")
        try:
            if user_id is not None and user_id not in config.ADMIN_IDS and not self.bucket.allow(user_id):
                metrics.RATE_LIMITED.inc()
                await self._tell_slow_down(bot, event, user_id, chat_id)
                return None
            return await handler(event, data)
        except Exception:
            metrics.UPDATE_ERRORS.inc()
            log.exception("unhandled error while handling a %s", kind)
            if bot and chat_id:
                try:
                    await bot.send_message(chat_id, "⚠️ Something went wrong on our side. Please try again in a moment.")
                except TelegramAPIError:
                    pass
            return None
        finally:
            metrics.UPDATES.inc(kind=kind)
            metrics.UPDATE_SECONDS.observe(time.perf_counter() - started)
            update_ctx.reset(token)

    async def _tell_slow_down(self, bot, event: Update, user_id: int, chat_id):
        now = time.monotonic()
        try:
            if event.callback_query:
                await event.callback_query.answer("Easy there — one moment please.")
            elif bot and chat_id and now - self.warned.get(user_id, 0) > 10:
                self.warned[user_id] = now
                await bot.send_message(chat_id, "⏳ You're sending messages very fast. Please wait a few seconds.")
        except TelegramAPIError:
            pass
