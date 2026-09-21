from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_admin_user_id: int
    openai_api_key: str
    timezone: str
    digest_time: str
    digest_send_empty: bool
    rss_poll_interval_minutes: int
    database_path: Path

    @property
    def database_url_async(self) -> str:
        return f"sqlite+aiosqlite:///{self.database_path}"

    @property
    def database_url_sync(self) -> str:
        return f"sqlite:///{self.database_path}"


def load_settings() -> Settings:
    db_path = Path(_require("DATABASE_PATH"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        telegram_bot_token=_require("TELEGRAM_BOT_TOKEN"),
        telegram_admin_user_id=int(_require("TELEGRAM_ADMIN_USER_ID")),
        openai_api_key=_require("OPENAI_API_KEY"),
        timezone=_require("TIMEZONE"),
        digest_time=_require("DIGEST_TIME"),
        digest_send_empty=_bool("DIGEST_SEND_EMPTY", False),
        rss_poll_interval_minutes=int(_require("RSS_POLL_INTERVAL_MINUTES")),
        database_path=db_path,
    )
