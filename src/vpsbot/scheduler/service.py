from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vpsbot.config import Settings
from vpsbot.db.models import RecurrenceKind, Reminder, SchedulerAuditLog
from vpsbot.reminders.recurrence import load_rule, next_occurrence
from vpsbot.scheduler import jobs

logger = logging.getLogger(__name__)


class BotScheduler:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        jobstores = {
            "default": SQLAlchemyJobStore(url=settings.database_url_sync),
        }
        self.scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=ZoneInfo("UTC"))

    def start(self) -> None:
        self.scheduler.start()
        logger.info("APScheduler started")

    def shutdown(self) -> None:
        self.scheduler.shutdown(wait=False)

    def _job_id_reminder(self, reminder_id: int) -> str:
        return f"reminder:{reminder_id}"

    async def _audit(
        self,
        session: AsyncSession,
        *,
        job_id: str,
        reminder_id: int | None,
        scheduled_for: datetime,
        event: str,
        fired_at: datetime | None = None,
    ) -> None:
        session.add(
            SchedulerAuditLog(
                job_id=job_id,
                reminder_id=reminder_id,
                scheduled_for=scheduled_for,
                fired_at=fired_at,
                event=event,
            )
        )
        await session.commit()

    async def schedule_reminder(self, reminder: Reminder) -> None:
        job_id = self._job_id_reminder(reminder.id)
        run_date = reminder.next_fire_at.astimezone(ZoneInfo("UTC"))
        self.scheduler.add_job(
            jobs.fire_reminder_job,
            trigger=DateTrigger(run_date=run_date),
            id=job_id,
            replace_existing=True,
            kwargs={"reminder_id": reminder.id},
        )
        logger.info(
            "Scheduled reminder %s for %s (UTC)",
            reminder.id,
            run_date.isoformat(),
        )
        async with self.session_factory() as session:
            await self._audit(
                session,
                job_id=job_id,
                reminder_id=reminder.id,
                scheduled_for=run_date,
                event="scheduled",
            )

    async def unschedule_reminder(self, reminder_id: int) -> None:
        job_id = self._job_id_reminder(reminder_id)
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

    async def reload_reminders_from_db(self) -> None:
        async with self.session_factory() as session:
            stmt = select(Reminder).where(Reminder.active.is_(True))
            result = await session.execute(stmt)
            reminders = list(result.scalars().all())
        now = datetime.now(ZoneInfo("UTC"))
        for rem in reminders:
            if rem.next_fire_at <= now:
                kind = RecurrenceKind(rem.recurrence)
                if kind == RecurrenceKind.NONE:
                    continue
                rule = load_rule(rem.recurrence_rule)
                if not rule:
                    continue
                nxt = next_occurrence(kind, rule, now)
                async with self.session_factory() as session:
                    db_rem = await session.get(Reminder, rem.id)
                    if db_rem:
                        db_rem.next_fire_at = nxt
                        await session.commit()
                        rem = db_rem
            await self.schedule_reminder(rem)
        logger.info("Reloaded %s active reminders into scheduler", len(reminders))

    def schedule_rss_poll(self) -> None:
        minutes = self.settings.rss_poll_interval_minutes
        self.scheduler.add_job(
            jobs.rss_poll_job,
            trigger=IntervalTrigger(minutes=minutes),
            id="rss_poll",
            replace_existing=True,
        )
        logger.info("RSS poll scheduled every %s minutes", minutes)

    def schedule_daily_digest(self) -> None:
        hour, minute = self._parse_hhmm(self.settings.digest_time)
        tz = ZoneInfo(self.settings.timezone)
        self.scheduler.add_job(
            jobs.daily_digest_job,
            trigger=CronTrigger(hour=hour, minute=minute, timezone=tz),
            id="daily_digest",
            replace_existing=True,
        )
        logger.info(
            "Daily digest scheduled at %s:%s %s",
            hour,
            minute,
            self.settings.timezone,
        )

    @staticmethod
    def _parse_hhmm(value: str) -> tuple[int, int]:
        parts = value.strip().split(":")
        if len(parts) != 2:
            raise ValueError("DIGEST_TIME must be HH:MM")
        return int(parts[0]), int(parts[1])
