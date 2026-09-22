from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vpsbot.db.models import Base, RecurrenceKind, Reminder
from vpsbot.db.session import init_db
from vpsbot.reminders.startup import catch_up_overdue_reminders


@pytest.mark.asyncio
async def test_catch_up_sends_and_deactivates_one_off():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    now = datetime.now(ZoneInfo("UTC"))
    past = now - timedelta(minutes=5)
    async with session_factory() as session:
        session.add(
            Reminder(
                user_id=1,
                chat_id=100,
                notify_chat_id=100,
                message="overdue test",
                next_fire_at=past,
                recurrence=RecurrenceKind.NONE.value,
                recurrence_rule=None,
                created_at=now,
                active=True,
            )
        )
        await session.commit()

    bot = AsyncMock()
    scheduler = MagicMock()
    scheduler.schedule_reminder = AsyncMock()

    count = await catch_up_overdue_reminders(session_factory, bot, scheduler)
    assert count == 1
    bot.send_message.assert_called_once()
    assert "delayed" in bot.send_message.call_args[0][1].lower()
    scheduler.schedule_reminder.assert_not_called()

    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(select(Reminder))
        rem = result.scalar_one()
        assert rem.active is False

    await engine.dispose()
