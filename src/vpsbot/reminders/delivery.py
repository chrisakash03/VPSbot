from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from vpsbot.db.models import Reminder, SchedulerAuditLog
from vpsbot.reminders.service import reschedule_after_fire
from vpsbot.utils.timezone import ensure_utc


async def deliver_reminder(
    session: AsyncSession,
    bot: Bot,
    reminder: Reminder,
    *,
    job_id: str,
    late: bool = False,
) -> Reminder | None:
    """Send the Telegram message and advance or deactivate the reminder row."""
    fired_at = datetime.now(ZoneInfo("UTC"))
    chat_id = reminder.notify_chat_id or reminder.chat_id
    prefix = "⏰ Reminder (delayed): " if late else "⏰ Reminder: "
    await bot.send_message(chat_id, f"{prefix}{reminder.message}")

    session.add(
        SchedulerAuditLog(
            job_id=job_id,
            reminder_id=reminder.id,
            scheduled_for=ensure_utc(reminder.next_fire_at),
            fired_at=fired_at,
            event="fired",
        )
    )
    await session.commit()
    return await reschedule_after_fire(session, reminder)
