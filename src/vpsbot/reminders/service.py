from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vpsbot.db.models import RecurrenceKind, Reminder
from vpsbot.reminders.parsing import recurrence_rule_to_json
from vpsbot.reminders.recurrence import (
    decrement_occurrence_rule,
    load_rule,
    next_occurrence,
    series_should_end,
)
from vpsbot.reminders.schedule_spec import ScheduleSpec


async def create_reminder_from_spec(
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    notify_chat_id: int,
    spec: ScheduleSpec,
) -> Reminder:
    parsed = spec.to_parsed_reminder()
    return await create_reminder(
        session,
        user_id=user_id,
        chat_id=chat_id,
        notify_chat_id=notify_chat_id,
        message=parsed.message,
        fire_at_utc=parsed.fire_at_utc,
        recurrence=parsed.recurrence,
        recurrence_rule=parsed.recurrence_rule,
    )


async def create_reminder(
    session: AsyncSession,
    *,
    user_id: int,
    chat_id: int,
    notify_chat_id: int,
    message: str,
    fire_at_utc: datetime,
    recurrence: RecurrenceKind,
    recurrence_rule: dict | None,
) -> Reminder:
    now = datetime.now(ZoneInfo("UTC"))
    reminder = Reminder(
        user_id=user_id,
        chat_id=chat_id,
        notify_chat_id=notify_chat_id,
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

    rule = decrement_occurrence_rule(rule)
    if rule.get("remaining_occurrences") is not None and int(rule["remaining_occurrences"]) <= 0:
        reminder.active = False
        reminder.recurrence_rule = recurrence_rule_to_json(rule)
        await session.commit()
        return None
    now = datetime.now(ZoneInfo("UTC"))
    nxt = next_occurrence(kind, rule, now)
    if series_should_end(rule, nxt):
        reminder.active = False
        reminder.recurrence_rule = recurrence_rule_to_json(rule)
        await session.commit()
        return None
    reminder.next_fire_at = nxt
    reminder.recurrence_rule = recurrence_rule_to_json(rule)
    await session.commit()
    await session.refresh(reminder)
    return reminder
