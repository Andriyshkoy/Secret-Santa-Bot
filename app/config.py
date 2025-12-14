import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    bot_token: str
    admin_tg_id: int
    database_url: str
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str


def load_settings() -> Settings:
    """
    Load and validate environment variables.
    Uses DATABASE_URL if provided, otherwise builds it from individual Postgres vars.
    """
    load_dotenv()

    bot_token = os.getenv("BOT_TOKEN")
    admin_tg_id = os.getenv("ADMIN_TG_ID")

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if not admin_tg_id:
        raise RuntimeError("ADMIN_TG_ID is required")

    postgres_host = os.getenv("POSTGRES_HOST", "db")
    postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db = os.getenv("POSTGRES_DB", "santa")
    postgres_user = os.getenv("POSTGRES_USER", "santa")
    postgres_password = os.getenv("POSTGRES_PASSWORD", "santa")

    database_url = os.getenv(
        "DATABASE_URL",
        f"postgresql+asyncpg://{postgres_user}:{postgres_password}"
        f"@{postgres_host}:{postgres_port}/{postgres_db}",
    )

    return Settings(
        bot_token=bot_token,
        admin_tg_id=int(admin_tg_id),
        database_url=database_url,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
        postgres_db=postgres_db,
        postgres_user=postgres_user,
        postgres_password=postgres_password,
    )
