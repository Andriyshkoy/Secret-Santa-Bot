from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """
    Provides an AsyncSession for every update.
    """

    def __init__(self, session_factory: async_sessionmaker):
        super().__init__()
        self.session_factory = session_factory

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = self.session_factory()
        try:
            data["session"] = session
            result = await handler(event, data)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


class SettingsMiddleware(BaseMiddleware):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["settings"] = self.settings
        return await handler(event, data)
