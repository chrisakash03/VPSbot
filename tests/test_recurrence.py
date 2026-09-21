from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.recurrence import next_occurrence


def test_daily_next():
    rule = {
        "anchor_utc": "2026-01-01T08:00:00+00:00",
        "hour": 8,
        "minute": 0,
    }
    after = datetime(2026, 1, 1, 9, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_occurrence(RecurrenceKind.DAILY, rule, after)
    assert nxt == datetime(2026, 1, 2, 8, 0, tzinfo=ZoneInfo("UTC"))


def test_weekly_monday():
    rule = {
        "anchor_utc": "2026-01-05T09:00:00+00:00",
        "weekday": 0,
        "hour": 9,
        "minute": 0,
    }
    after = datetime(2026, 1, 5, 10, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_occurrence(RecurrenceKind.WEEKLY, rule, after)
    assert nxt.weekday() == 0
    assert nxt > after


def test_yearly_birthday():
    rule = {
        "anchor_utc": "2026-03-15T10:00:00+00:00",
        "month": 3,
        "day": 15,
        "hour": 10,
        "minute": 0,
    }
    after = datetime(2026, 3, 15, 11, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_occurrence(RecurrenceKind.YEARLY, rule, after)
    assert nxt.year == 2027
    assert nxt.month == 3
    assert nxt.day == 15
