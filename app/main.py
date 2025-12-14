import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
try:
    from aiogram.client.default import DefaultBotProperties
except ImportError:  # aiogram < 3.7
    DefaultBotProperties = None

from app.bot.handlers import router
from app.bot.middlewares import DbSessionMiddleware, SettingsMiddleware
from app.config import load_settings
from app.db import create_engine, get_session_factory, init_db


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    settings = load_settings()
    engine = create_engine(settings)
    session_factory = get_session_factory(engine)
    await init_db(engine)

    # aiogram 3.7+ expects default properties instead of parse_mode arg
    if DefaultBotProperties is not None:
        bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    else:  # fallback for older aiogram
        bot = Bot(token=settings.bot_token, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.middleware(SettingsMiddleware(settings))
    dp.update.middleware(DbSessionMiddleware(session_factory))
    dp.include_router(router)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
