from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.recurrence import (
    decrement_occurrence_rule,
    next_occurrence,
    series_should_end,
)


def test_interval_next():
    rule = {
        "anchor_utc": "2026-01-01T20:00:00+00:00",
        "interval_days": 2,
        "hour": 20,
        "minute": 0,
    }
    after = datetime(2026, 1, 1, 21, 0, tzinfo=ZoneInfo("UTC"))
    nxt = next_occurrence(RecurrenceKind.INTERVAL, rule, after)
    assert nxt == datetime(2026, 1, 3, 20, 0, tzinfo=ZoneInfo("UTC"))


def test_decrement_occurrences():
    rule = {"remaining_occurrences": 3}
    updated = decrement_occurrence_rule(rule)
    assert updated["remaining_occurrences"] == 2


def test_series_should_end_by_date():
    rule = {"ends_at": "2026-01-05T00:00:00+00:00"}
    nxt = datetime(2026, 1, 6, 0, 0, tzinfo=ZoneInfo("UTC"))
    assert series_should_end(rule, nxt)
