from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.reminders.jev.assemble import assemble_from_answers
from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.schedule_spec import EndKind, ReviewAction


class FakeAnswer:
    def __init__(self, choice=None, noul=None, confidence=0.9):
        self.choice = choice
        self.noul = noul
        self.confidence = confidence


def test_assemble_interval_with_duration():
    now = datetime(2026, 9, 22, 2, 0, tzinfo=ZoneInfo("UTC"))
    answers = {
        "is_recurring": FakeAnswer(noul=1.0, confidence=0.95),
        "schedule_kind": FakeAnswer(choice="interval_days", confidence=0.92),
        "interval_days": FakeAnswer(choice="2", confidence=0.9),
        "weekday_name": FakeAnswer(choice="none", confidence=0.9),
        "end_kind": FakeAnswer(choice="duration", confidence=0.88),
        "duration_days": FakeAnswer(choice="none", confidence=0.9),
        "duration_weeks": FakeAnswer(choice="2", confidence=0.87),
        "max_occurrences": FakeAnswer(choice="none", confidence=0.9),
        "time_kind": FakeAnswer(choice="specific_time", confidence=0.91),
        "hour_local": FakeAnswer(choice="20", confidence=0.9),
        "minute_local": FakeAnswer(choice="0", confidence=0.9),
        "date_mode": FakeAnswer(choice="relative", confidence=0.9),
        "date_month": FakeAnswer(choice="none", confidence=0.9),
        "date_day": FakeAnswer(choice="none", confidence=0.9),
        "date_year": FakeAnswer(choice="none", confidence=0.9),
        "date_day_anchor": FakeAnswer(choice="today", confidence=0.9),
        "date_weekday": FakeAnswer(choice="none", confidence=0.9),
        "date_week_offset": FakeAnswer(choice="none", confidence=0.9),
    }
    spec = assemble_from_answers(
        answers,
        user_text="do task every 2 days at 8pm for 2 weeks",
        tz_name="UTC",
        now_utc=now,
    )
    assert spec.recurrence == RecurrenceKind.INTERVAL
    assert spec.interval_days == 2
    assert spec.end.duration_days == 14
    assert spec.review in (ReviewAction.AUTO, ReviewAction.CONFIRM)


def test_assemble_daily_for_three_days_from_text_fallback():
    now = datetime(2026, 9, 22, 2, 0, tzinfo=ZoneInfo("UTC"))
    answers = {
        "is_recurring": FakeAnswer(noul=1.0, confidence=0.95),
        "schedule_kind": FakeAnswer(choice="daily", confidence=0.92),
        "interval_days": FakeAnswer(choice="none", confidence=0.9),
        "weekday_name": FakeAnswer(choice="none", confidence=0.9),
        "end_kind": FakeAnswer(choice="none", confidence=0.88),
        "duration_days": FakeAnswer(choice="none", confidence=0.9),
        "duration_weeks": FakeAnswer(choice="none", confidence=0.9),
        "max_occurrences": FakeAnswer(choice="none", confidence=0.9),
        "time_kind": FakeAnswer(choice="specific_time", confidence=0.91),
        "hour_local": FakeAnswer(choice="20", confidence=0.9),
        "minute_local": FakeAnswer(choice="0", confidence=0.9),
        "date_mode": FakeAnswer(choice="relative", confidence=0.9),
        "date_month": FakeAnswer(choice="none", confidence=0.9),
        "date_day": FakeAnswer(choice="none", confidence=0.9),
        "date_year": FakeAnswer(choice="none", confidence=0.9),
        "date_day_anchor": FakeAnswer(choice="today", confidence=0.9),
        "date_weekday": FakeAnswer(choice="none", confidence=0.9),
        "date_week_offset": FakeAnswer(choice="none", confidence=0.9),
    }
    spec = assemble_from_answers(
        answers,
        user_text="do survey every day at 8pm for 3 days",
        tz_name="UTC",
        now_utc=now,
    )
    assert spec.recurrence == RecurrenceKind.DAILY
    assert spec.end.kind == EndKind.MAX_OCCURRENCES
    assert spec.end.remaining_occurrences == 3
    assert "survey" in spec.message.lower()
