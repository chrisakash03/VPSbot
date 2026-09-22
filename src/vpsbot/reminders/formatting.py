from __future__ import annotations

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.schedule_spec import EndKind, ScheduleSpec
from vpsbot.utils.timezone import format_local


def format_schedule_preview(spec: ScheduleSpec, tz_name: str) -> str:
    when = format_local(spec.start_at_utc, tz_name)
    parts = [f"Reminder: '{spec.message}' — {when}"]
    if spec.recurrence != RecurrenceKind.NONE:
        recur = spec.recurrence.value
        if spec.recurrence == RecurrenceKind.INTERVAL and spec.interval_days:
            recur = f"every {spec.interval_days} days"
        elif spec.recurrence == RecurrenceKind.DAILY:
            recur = "every day"
        parts.append(f"Repeats: {recur}.")
        if spec.end.kind == EndKind.MAX_OCCURRENCES and spec.end.remaining_occurrences:
            parts.append(f"For {spec.end.remaining_occurrences} times.")
        elif spec.end.kind == EndKind.DURATION_DAYS and spec.end.duration_days:
            parts.append(f"For {spec.end.duration_days} days.")
    return " ".join(parts)


def format_schedule_summary(
    spec: ScheduleSpec,
    tz_name: str,
    *,
    deliver_via_pm: bool = False,
) -> str:
    when = format_local(spec.start_at_utc, tz_name)
    if deliver_via_pm:
        opener = f"Got it — I'll DM you about '{spec.message}' on {when}."
    else:
        opener = f"Got it — I'll remind this chat about '{spec.message}' on {when}."
    lines = [opener]
    if spec.recurrence != RecurrenceKind.NONE:
        recur = spec.recurrence.value
        if spec.recurrence == RecurrenceKind.INTERVAL and spec.interval_days:
            recur = f"every {spec.interval_days} days"
        lines.append(f"Repeats: {recur}.")
        if spec.end.kind == EndKind.UNTIL_UTC and spec.end.until_utc:
            lines.append(f"Until {format_local(spec.end.until_utc, tz_name)}.")
        elif spec.end.kind == EndKind.MAX_OCCURRENCES and spec.end.remaining_occurrences:
            lines.append(f"For {spec.end.remaining_occurrences} times.")
        elif spec.end.kind == EndKind.DURATION_DAYS and spec.end.duration_days:
            lines.append(f"For {spec.end.duration_days} days.")
    return "\n".join(lines)
