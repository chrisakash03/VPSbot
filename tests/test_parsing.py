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


def test_parse_daily_recurrence():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("every day at 8am drink water", "UTC", now_utc=now)
    assert parsed.recurrence.value == "daily"
    assert parsed.recurrence_rule is not None
