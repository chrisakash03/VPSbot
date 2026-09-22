from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.schedule_spec import ScheduleSpec, validate_schedule_spec


def test_validate_interval_requires_days():
    now = datetime(2026, 1, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
    spec = ScheduleSpec(
        message="task",
        start_at_utc=now + timedelta(hours=1),
        recurrence=RecurrenceKind.INTERVAL,
        interval_days=None,
    )
    errors = validate_schedule_spec(spec, now)
    assert any("interval_days" in e for e in errors)
