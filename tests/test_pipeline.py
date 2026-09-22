from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest

from vpsbot.config import Settings
from pathlib import Path

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.pipeline import parse_reminder_pipeline
from vpsbot.reminders.schedule_spec import EndKind, ParseSource, ReviewAction, ScheduleEnd, ScheduleSpec


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
async def test_pipeline_fast_path():
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    result = await parse_reminder_pipeline(
        "remind me tomorrow at 5pm to call mom",
        _settings(jev_enabled=False),
        now_utc=now,
    )
    assert result.spec is not None
    assert result.spec.source == ParseSource.FAST


@pytest.mark.asyncio
async def test_pipeline_invokes_jev_on_complex():
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    fake_spec = ScheduleSpec(
        message="task",
        start_at_utc=now,
        recurrence=RecurrenceKind.INTERVAL,
        interval_days=2,
        end=ScheduleEnd(kind=EndKind.DURATION_DAYS, duration_days=14),
        source=ParseSource.JEV,
        confidence=0.9,
    )
    with patch(
        "vpsbot.reminders.pipeline.parse_with_jev",
        new=AsyncMock(return_value=fake_spec),
    ):
        result = await parse_reminder_pipeline(
            "every 2 days at 8pm for 2 weeks do task",
            _settings(),
            now_utc=now,
        )
    assert result.spec is not None
    assert result.spec.recurrence == RecurrenceKind.INTERVAL


@pytest.mark.asyncio
async def test_pipeline_skips_jev_for_daily_for_n_days():
    now = datetime(2026, 9, 22, 2, 0, tzinfo=ZoneInfo("UTC"))
    jev = AsyncMock()
    with patch("vpsbot.reminders.pipeline.parse_with_jev", new=jev):
        result = await parse_reminder_pipeline(
            "do survey everyday at 8pm for 3 days",
            _settings(),
            now_utc=now,
        )
    jev.assert_not_called()
    assert result.spec is not None
    assert result.spec.source == ParseSource.FAST
    assert result.spec.review == ReviewAction.AUTO
    assert result.spec.end.kind == EndKind.MAX_OCCURRENCES
    assert result.spec.end.remaining_occurrences == 3
