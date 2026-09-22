from __future__ import annotations

from datetime import datetime, timedelta

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.parsing import ParsedReminder
from vpsbot.reminders.schedule_spec import (
    EndKind,
    ParseSource,
    ScheduleEnd,
    ScheduleSpec,
    parsed_reminder_to_spec,
    validate_schedule_spec,
)
from vpsbot.reminders.text_normalize import (
    FOR_DAYS_RE,
    FOR_WEEKS_RE,
    TIMES_RE,
    has_schedule_bound_phrase,
)


def _set_duration_end(spec: ScheduleSpec, days: int) -> None:
    spec.end = ScheduleEnd(
        kind=EndKind.DURATION_DAYS,
        duration_days=days,
        until_utc=spec.start_at_utc + timedelta(days=days),
    )


def fast_bounded_spec_if_complete(
    text: str,
    fast_result: ParsedReminder,
    now_utc: datetime,
) -> ScheduleSpec | None:
    """Use fast parse + text bounds when that fully resolves a bounded recurrence phrase."""
    if not has_schedule_bound_phrase(text):
        return None
    spec = parsed_reminder_to_spec(fast_result, ParseSource.FAST)
    if spec.recurrence == RecurrenceKind.NONE:
        return None
    end_before = spec.end.kind
    apply_end_bound_from_text(text, spec)
    if spec.end.kind == EndKind.NONE or spec.end.kind == end_before:
        return None
    if validate_schedule_spec(spec, now_utc):
        return None
    return spec


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
