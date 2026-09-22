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
    jev_enabled: bool
    typesafe_api_key: str | None
    jev_model: str
    jev_confidence_auto: float
    jev_confidence_min: float
    jev_timeout_seconds: float
    digest_group_chat_id: int | None
    reminder_retention_days: int
    scheduler_audit_retention_days: int

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
        jev_enabled=_bool("JEV_ENABLED", False),
        typesafe_api_key=os.getenv("TYPESAFE_API_KEY"),
        jev_model=os.getenv("JEV_MODEL", "jev-latest"),
        jev_confidence_auto=float(os.getenv("JEV_CONFIDENCE_AUTO", "0.85")),
        jev_confidence_min=float(os.getenv("JEV_CONFIDENCE_MIN", "0.60")),
        jev_timeout_seconds=float(os.getenv("JEV_TIMEOUT_SECONDS", "30")),
        digest_group_chat_id=_optional_int("DIGEST_GROUP_CHAT_ID"),
        reminder_retention_days=int(os.getenv("REMINDER_RETENTION_DAYS", "90")),
        scheduler_audit_retention_days=int(os.getenv("SCHEDULER_AUDIT_RETENTION_DAYS", "30")),
    )


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if not raw or not raw.strip():
        return None
    return int(raw.strip())
