from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vpsbot.db.models import Reminder
from vpsbot.reminders.delivery import deliver_reminder
from vpsbot.scheduler.service import BotScheduler
from vpsbot.utils.timezone import ensure_utc

logger = logging.getLogger(__name__)


async def catch_up_overdue_reminders(
    session_factory: async_sessionmaker[AsyncSession],
    bot: Bot,
    scheduler: BotScheduler,
) -> int:
    """
    On startup: for each active reminder whose fire time passed while the bot was down,
    send once and deactivate (one-off) or reschedule to the next occurrence (recurring).
    """
    now = datetime.now(ZoneInfo("UTC"))
    async with session_factory() as session:
        result = await session.execute(
            select(Reminder).where(Reminder.active.is_(True)).order_by(Reminder.next_fire_at.asc())
        )
        candidates = list(result.scalars().all())

    delivered = 0
    for rem in candidates:
        if ensure_utc(rem.next_fire_at) > now:
            continue
        async with session_factory() as session:
            reminder = await session.get(Reminder, rem.id)
            if not reminder or not reminder.active:
                continue
            if ensure_utc(reminder.next_fire_at) > now:
                continue
            job_id = f"reminder:{reminder.id}:catchup"
            logger.info(
                "Catch-up reminder %s (scheduled %s UTC)",
                reminder.id,
                ensure_utc(reminder.next_fire_at).isoformat(),
            )
            updated = await deliver_reminder(
                session,
                bot,
                reminder,
                job_id=job_id,
                late=True,
            )
            delivered += 1
        if updated:
            await scheduler.schedule_reminder(updated)

    if delivered:
        logger.info("Catch-up delivered %s overdue reminder(s)", delivered)
    return delivered
