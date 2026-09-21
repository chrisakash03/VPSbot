from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpsbot.db.models import RecurrenceKind, Reminder
from vpsbot.reminders.parsing import recurrence_rule_to_json
from vpsbot.reminders.recurrence import load_rule, next_occurrence


async def create_reminder(
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    message: str,
    fire_at_utc: datetime,
    recurrence: RecurrenceKind,
    recurrence_rule: dict | None,
) -> Reminder:
    now = datetime.now(ZoneInfo("UTC"))
    reminder = Reminder(
        user_id=user_id,
        chat_id=chat_id,
        message=message,
        next_fire_at=fire_at_utc,
        recurrence=recurrence.value,
        recurrence_rule=recurrence_rule_to_json(recurrence_rule),
        created_at=now,
        active=True,
    )
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return reminder


async def list_active_reminders(session: AsyncSession, user_id: int) -> list[Reminder]:
    stmt = (
        select(Reminder)
        .where(Reminder.user_id == user_id, Reminder.active.is_(True))
        .order_by(Reminder.next_fire_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_reminder(session: AsyncSession, reminder_id: int, user_id: int) -> Reminder | None:
    stmt = select(Reminder).where(
        Reminder.id == reminder_id,
        Reminder.user_id == user_id,
        Reminder.active.is_(True),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def cancel_reminder(session: AsyncSession, reminder: Reminder) -> None:
    reminder.active = False
    await session.commit()


async def reschedule_after_fire(session: AsyncSession, reminder: Reminder) -> Reminder | None:
    kind = RecurrenceKind(reminder.recurrence)
    if kind == RecurrenceKind.NONE:
        reminder.active = False
        await session.commit()
        return None

    rule = load_rule(reminder.recurrence_rule)
    if not rule:
        reminder.active = False
        await session.commit()
        return None

    now = datetime.now(ZoneInfo("UTC"))
    nxt = next_occurrence(kind, rule, now)
    reminder.next_fire_at = nxt
    await session.commit()
    await session.refresh(reminder)
    return reminder
