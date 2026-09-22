from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from vpsbot.config import Settings
from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.bounds import apply_end_bound_from_text
from vpsbot.reminders.text_normalize import normalize_reminder_text
from vpsbot.reminders.parsing import parse_reminder_text
from vpsbot.reminders.pipeline import parse_reminder_pipeline
from vpsbot.reminders.schedule_spec import EndKind, ScheduleSpec


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
        "jev_enabled": False,
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


def test_normalize_everyday():
    assert normalize_reminder_text("do survey everyday at 8pm") == "do survey every day at 8pm"


def test_parse_daily_for_three_days_message():
    now = datetime(2026, 9, 22, 10, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "do survey everyday at 8pm for 3 days",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed.recurrence == RecurrenceKind.DAILY
    assert parsed.message == "do survey"


def test_apply_end_bound_daily_for_days():
    start = datetime(2026, 9, 22, 12, 0, tzinfo=ZoneInfo("UTC"))
    spec = ScheduleSpec(
        message="do survey",
        start_at_utc=start,
        recurrence=RecurrenceKind.DAILY,
    )
    apply_end_bound_from_text("every day at 8pm for 3 days", spec)
    assert spec.end.kind == EndKind.MAX_OCCURRENCES
    assert spec.end.remaining_occurrences == 3


@pytest.mark.asyncio
async def test_pipeline_fast_daily_for_three_days_without_jev():
    now = datetime(2026, 9, 22, 2, 0, tzinfo=ZoneInfo("UTC"))
    result = await parse_reminder_pipeline(
        "do survey everyday at 8pm for 3 days",
        _settings(jev_enabled=False),
        now_utc=now,
    )
    assert result.spec is not None
    assert result.spec.recurrence == RecurrenceKind.DAILY
    assert result.spec.end.kind == EndKind.MAX_OCCURRENCES
    assert result.spec.end.remaining_occurrences == 3
    assert result.spec.message == "do survey"
