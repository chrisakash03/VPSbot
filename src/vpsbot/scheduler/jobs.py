from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.app_state import get_state
from vpsbot.db.models import Reminder
from vpsbot.reminders.delivery import deliver_reminder
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
        updated = await deliver_reminder(
            session,
            state.bot,
            reminder,
            job_id=job_id,
            late=False,
        )

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
