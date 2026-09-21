from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vpsbot.config import Settings
from vpsbot.scheduler.service import BotScheduler


@dataclass
class BotContext:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    scheduler: BotScheduler
