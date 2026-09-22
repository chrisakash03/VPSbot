from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from vpsbot.reminders.parsing import ParseError, parse_reminder_text


def test_parse_simple_reminder():
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "remind me to submit the report tomorrow at 5pm",
        "Asia/Singapore",
        now_utc=now,
    )
    assert "submit" in parsed.message.lower()
    assert parsed.fire_at_utc > now


def test_parse_rejects_past():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
    with pytest.raises(ParseError):
        parse_reminder_text("remind me on 2020-01-01 at 9am", "UTC", now_utc=now)


def test_parse_today_before_time():
    now = datetime(2026, 9, 22, 4, 49, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("test today 1250pm", "Asia/Singapore", now_utc=now)
    assert parsed.message == "test"
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 12 and local.minute == 50


def test_parse_compact_time_with_today():
    now = datetime(2026, 9, 22, 4, 48, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "send this reminder to me 1250pm today",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed.message == "send this reminder to me"
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 12 and local.minute == 50


def test_parse_time_only_today():
    # 12:47 SGT = 04:47 UTC
    now = datetime(2026, 9, 22, 4, 47, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("test item 12:48pm", "Asia/Singapore", now_utc=now)
    assert parsed.message == "test item"
    assert parsed.fire_at_utc > now
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 12 and local.minute == 48


def test_parse_absolute_date_with_time():
    now = datetime(2026, 9, 22, 11, 35, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "collect parcel from chop ah tat at 6pm on 23 september 2026",
        "Asia/Singapore",
        now_utc=now,
    )
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.year == 2026 and local.month == 9 and local.day == 23
    assert local.hour == 18 and local.minute == 0
    assert "collect parcel" in parsed.message.lower()


def test_parse_daily_recurrence():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("every day at 8am drink water", "UTC", now_utc=now)
    assert parsed.recurrence.value == "daily"
    assert parsed.recurrence_rule is not None
