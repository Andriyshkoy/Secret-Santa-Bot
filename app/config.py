import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    bot_token: str
    admin_tg_id: int
    database_url: str


def load_settings() -> Settings:
    """
    Load and validate environment variables.
    Uses DATABASE_URL if provided, otherwise defaults to local sqlite file.
    """
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    admin_tg_id = os.getenv("ADMIN_TG_ID")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if not admin_tg_id:
        raise RuntimeError("ADMIN_TG_ID is required")

    database_url = os.getenv(
        "DATABASE_URL",
        "sqlite+aiosqlite:///./bot.db",
    )

    return Settings(
        bot_token=bot_token,
        admin_tg_id=int(admin_tg_id),
        database_url=database_url,
    )
