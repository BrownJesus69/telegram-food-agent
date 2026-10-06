import asyncio
import contextlib
import logging
import signal
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import foodbot
from foodbot import address_flow, config, db, maintenance, observability, ops, simulator, state
from foodbot.handlers import router
from foodbot.services.catalogue import load

log = logging.getLogger(__name__)
HEARTBEAT_SECONDS = 60


async def heartbeat(bot: Bot):
    """Prove Telegram is reachable (the health check goes red if this stops succeeding)."""
    while True:
        try:
            await bot.get_me()
            state.telegram_ok_at = time.time()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.warning("telegram heartbeat failed: %s", type(e).__name__)
        await asyncio.sleep(HEARTBEAT_SECONDS)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.update.outer_middleware(observability.UpdateMiddleware())
    dp.include_router(address_flow.router)   # location pins + addr:* callbacks
    dp.include_router(router)
    return dp


async def main():
    observability.setup_logging(config.LOG_FORMAT)
    config.validate()
    db.init_db()

    n_rest, n_items = load()
    log.info("FoodBot v%s: %s restaurants, %s menu items (LLM %s, simulation %s)", foodbot.__version__, n_rest, n_items,
             "configured" if config.GROQ_API_KEY else "off", "on" if config.SIMULATE_DELIVERY else "off")

    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    await bot.delete_webhook(drop_pending_updates=False)
    me = await bot.get_me()
    state.telegram_ok_at = time.time()
    log.info("Running as @%s", me.username)

    runner = await ops.start()
    tasks = [asyncio.create_task(heartbeat(bot)), asyncio.create_task(maintenance.run())]
    if config.SIMULATE_DELIVERY:
        tasks.append(asyncio.create_task(simulator.run(bot)))

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):                 # docker stop -> finish the current update, then exit cleanly
        with contextlib.suppress(NotImplementedError):          # not supported on Windows event loops
            loop.add_signal_handler(sig, lambda: asyncio.ensure_future(dp.stop_polling()))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), handle_signals=False)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await runner.cleanup()
        await bot.session.close()
        log.info("shut down cleanly")


if __name__ == "__main__":
    asyncio.run(main())
