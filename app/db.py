from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.models import Base


def create_engine(settings: Settings):
    # For sqlite we want aiosqlite driver (sqlite+aiosqlite:///./bot.db by default)
    return create_async_engine(settings.database_url, future=True)


def get_session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope(session_factory) -> AsyncSession:
    session: AsyncSession = session_factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
