from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vpsbot.config import Settings
from vpsbot.db.models import PendingReminder, Reminder, SchedulerAuditLog

logger = logging.getLogger(__name__)


async def purge_stale_data(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Remove inactive reminders and old audit rows so the DB does not grow forever."""
    now = datetime.now(ZoneInfo("UTC"))

    async with session_factory() as session:
        expired_pending = await session.execute(
            delete(PendingReminder).where(PendingReminder.expires_at < now)
        )
        if expired_pending.rowcount:
            logger.info("Purged %s expired pending reminder(s)", expired_pending.rowcount)

        if settings.reminder_retention_days > 0:
            cutoff = now - timedelta(days=settings.reminder_retention_days)
            inactive = await session.execute(
                delete(Reminder).where(
                    Reminder.active.is_(False),
                    Reminder.created_at < cutoff,
                )
            )
            if inactive.rowcount:
                logger.info(
                    "Purged %s inactive reminder row(s) older than %s days",
                    inactive.rowcount,
                    settings.reminder_retention_days,
                )

        if settings.scheduler_audit_retention_days > 0:
            audit_cutoff = now - timedelta(days=settings.scheduler_audit_retention_days)
            audits = await session.execute(
                delete(SchedulerAuditLog).where(SchedulerAuditLog.scheduled_for < audit_cutoff)
            )
            if audits.rowcount:
                logger.info(
                    "Purged %s scheduler audit row(s) older than %s days",
                    audits.rowcount,
                    settings.scheduler_audit_retention_days,
                )

        await session.commit()
