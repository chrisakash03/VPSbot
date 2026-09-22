from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from vpsbot.db.models import PendingReminder
from vpsbot.reminders.schedule_spec import ScheduleSpec


async def save_pending(
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    notify_chat_id: int,
    spec: ScheduleSpec,
    ttl_minutes: int = 30,
) -> PendingReminder:
    now = datetime.now(ZoneInfo("UTC"))
    await session.execute(delete(PendingReminder).where(PendingReminder.user_id == user_id))
    pending = PendingReminder(
        user_id=user_id,
        chat_id=chat_id,
        notify_chat_id=notify_chat_id,
        spec_json=spec.to_json(),
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    session.add(pending)
    await session.commit()
    await session.refresh(pending)
    return pending


async def get_pending(
    session: AsyncSession,
    pending_id: int,
    user_id: int,
) -> tuple[ScheduleSpec, int] | None:
    row = await session.get(PendingReminder, pending_id)
    if not row or row.user_id != user_id:
        return None
    now = datetime.now(ZoneInfo("UTC"))
    if row.expires_at <= now:
        await session.delete(row)
        await session.commit()
        return None
    notify = row.notify_chat_id if row.notify_chat_id else row.chat_id
    return ScheduleSpec.from_json(row.spec_json), notify


async def delete_pending(session: AsyncSession, pending_id: int, user_id: int) -> None:
    row = await session.get(PendingReminder, pending_id)
    if row and row.user_id == user_id:
        await session.delete(row)
        await session.commit()
