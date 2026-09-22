from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vpsbot.config import Settings
from vpsbot.db.models import Feed, RssQueueItem
from vpsbot.db.session import init_db
from vpsbot.rss.digest_runner import run_digest


def _settings(**kwargs) -> Settings:
    base = {
        "telegram_bot_token": "x",
        "telegram_admin_user_id": 1,
        "openai_api_key": "x",
        "timezone": "UTC",
        "digest_time": "08:00",
        "digest_send_empty": False,
        "rss_poll_interval_minutes": 30,
        "database_path": Path("/tmp/t.db"),
        "jev_enabled": True,
        "typesafe_api_key": "key",
        "jev_model": "jev-latest",
        "jev_confidence_auto": 0.85,
        "jev_confidence_min": 0.60,
        "jev_timeout_seconds": 30.0,
        "digest_group_chat_id": None,
        "reminder_retention_days": 90,
        "scheduler_audit_retention_days": 30,
    }
    base.update(kwargs)
    return Settings(**base)


@pytest.mark.asyncio
async def test_run_digest_notify_when_empty():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    send = AsyncMock()
    await run_digest(
        session_factory,
        _settings(),
        send,
        42,
        notify_when_empty=True,
    )
    send.assert_awaited_once_with(42, "Nothing new in your feeds today.")
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_digest_on_demand_does_not_check_group_enabled():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    send = AsyncMock()
    with patch(
        "vpsbot.rss.digest_runner.any_digest_group_enabled",
        new=AsyncMock(return_value=False),
    ) as enabled_check:
        await run_digest(
            session_factory,
            _settings(),
            send,
            99,
            notify_when_empty=True,
        )
    enabled_check.assert_not_called()
    send.assert_awaited_once()
    await engine.dispose()


@pytest.mark.asyncio
async def test_run_digest_marks_queue_items_digested():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    await init_db(engine)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(ZoneInfo("UTC"))

    async with session_factory() as session:
        feed = Feed(url="https://example.com/rss", title="Example")
        session.add(feed)
        await session.flush()
        session.add(
            RssQueueItem(
                feed_id=feed.id,
                guid="g1",
                link="https://example.com/1",
                title="Story",
                collected_at=now,
                digested=False,
            )
        )
        await session.commit()

    send = AsyncMock()
    with patch(
        "vpsbot.rss.digest_runner.summarize_digest",
        return_value="Digest body",
    ):
        await run_digest(
            session_factory,
            _settings(),
            send,
            7,
            notify_when_empty=True,
        )

    send.assert_awaited_once_with(7, "Digest body")
    async with session_factory() as session:
        result = await session.execute(select(RssQueueItem))
        item = result.scalar_one()
        assert item.digested is True
    await engine.dispose()
