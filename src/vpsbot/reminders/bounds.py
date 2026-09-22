from __future__ import annotations

from datetime import timedelta

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.schedule_spec import EndKind, ScheduleEnd, ScheduleSpec
from vpsbot.reminders.text_normalize import FOR_DAYS_RE, FOR_WEEKS_RE, TIMES_RE


def _set_duration_end(spec: ScheduleSpec, days: int) -> None:
    spec.end = ScheduleEnd(
        kind=EndKind.DURATION_DAYS,
        duration_days=days,
        until_utc=spec.start_at_utc + timedelta(days=days),
    )


def apply_end_bound_from_text(text: str, spec: ScheduleSpec) -> ScheduleSpec:
    """Fill recurrence end bounds from phrases like 'for 3 days' when not already set."""
    if spec.recurrence == RecurrenceKind.NONE or spec.end.kind != EndKind.NONE:
        return spec

    m_times = TIMES_RE.search(text)
    if m_times:
        n = int(m_times.group(1))
        spec.end = ScheduleEnd(
            kind=EndKind.MAX_OCCURRENCES,
            max_occurrences=n,
            remaining_occurrences=n,
        )
        return spec

    m_weeks = FOR_WEEKS_RE.search(text)
    if m_weeks:
        _set_duration_end(spec, int(m_weeks.group(1)) * 7)
        return spec

    m_days = FOR_DAYS_RE.search(text)
    if not m_days:
        return spec

    n = int(m_days.group(1))
    if spec.recurrence == RecurrenceKind.DAILY:
        spec.end = ScheduleEnd(
            kind=EndKind.MAX_OCCURRENCES,
            max_occurrences=n,
            remaining_occurrences=n,
        )
    else:
        _set_duration_end(spec, n)
    return spec
