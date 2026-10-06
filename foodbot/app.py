import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from foodbot import address_flow, config, db, simulator
from foodbot.handlers import router
from foodbot.services.catalogue import load


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    config.validate()
    db.init_db()

    n_rest, n_items = load()
    logging.info("Loaded %s restaurants, %s menu items", n_rest, n_items)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.include_router(address_flow.router)   # location pins + addr:* callbacks
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=False)

    me = await bot.get_me()
    logging.info("Running as @%s", me.username)

    sim_task = asyncio.create_task(simulator.run(bot)) if config.SIMULATE_DELIVERY else None
    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        if sim_task:
            sim_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())