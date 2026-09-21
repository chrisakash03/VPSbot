from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.app_state import get_state
from vpsbot.db.models import RecurrenceKind, Reminder, SchedulerAuditLog
from vpsbot.reminders.recurrence import load_rule, next_occurrence
from vpsbot.reminders.service import reschedule_after_fire
from vpsbot.rss.digest_runner import run_daily_digest
from vpsbot.rss.poller import poll_all_feeds

logger = logging.getLogger(__name__)


async def fire_reminder_job(reminder_id: int) -> None:
    state = get_state()
    fired_at = datetime.now(ZoneInfo("UTC"))
    job_id = f"reminder:{reminder_id}"
    logger.info("Firing reminder %s at %s (UTC)", reminder_id, fired_at.isoformat())

    async with state.session_factory() as session:
        reminder = await session.get(Reminder, reminder_id)
        if not reminder or not reminder.active:
            return
        chat_id = reminder.chat_id
        text = reminder.message
        scheduled_for = reminder.next_fire_at
        session.add(
            SchedulerAuditLog(
                job_id=job_id,
                reminder_id=reminder_id,
                scheduled_for=scheduled_for,
                fired_at=fired_at,
                event="fired",
            )
        )
        await session.commit()

    await state.bot.send_message(chat_id, f"⏰ Reminder: {text}")

    async with state.session_factory() as session:
        reminder = await session.get(Reminder, reminder_id)
        if not reminder:
            return
        updated = await reschedule_after_fire(session, reminder)

    if updated:
        await state.scheduler.schedule_reminder(updated)


async def rss_poll_job() -> None:
    state = get_state()
    await poll_all_feeds(state.session_factory)


async def daily_digest_job() -> None:
    state = get_state()

    async def send(chat_id: int, text: str) -> None:
        await state.bot.send_message(chat_id, text)

    await run_daily_digest(state.session_factory, state.settings, send)
