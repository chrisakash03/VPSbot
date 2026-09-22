from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from vpsbot.db.models import RecurrenceKind


def load_rule(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return json.loads(raw)


def next_occurrence(
    kind: RecurrenceKind,
    rule: dict[str, Any],
    after_utc: datetime,
) -> datetime:
    """Compute the next fire time strictly after ``after_utc`` (UTC)."""
    if kind == RecurrenceKind.NONE:
        raise ValueError("No recurrence for one-off reminder")

    anchor = datetime.fromisoformat(rule["anchor_utc"])
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=ZoneInfo("UTC"))

    hour = int(rule.get("hour", anchor.hour))
    minute = int(rule.get("minute", anchor.minute))

    cursor = max(after_utc, anchor)
    if kind == RecurrenceKind.DAILY:
        candidate = cursor.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= after_utc:
            candidate += timedelta(days=1)
        return candidate

    if kind == RecurrenceKind.WEEKLY:
        weekday = rule.get("weekday")
        if weekday is None:
            weekday = anchor.weekday()
        candidate = cursor.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (int(weekday) - candidate.weekday()) % 7
        candidate += timedelta(days=days_ahead)
        if candidate <= after_utc:
            candidate += timedelta(days=7)
        return candidate

    if kind == RecurrenceKind.FORTNIGHTLY:
        weekday = int(rule.get("weekday", anchor.weekday()))
        candidate = cursor.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_since = (candidate.date() - anchor.date()).days
        weeks_since = max(0, days_since // 7)
        if weeks_since % 2 != 0:
            weeks_since += 1
        candidate = anchor + timedelta(weeks=weeks_since)
        candidate = candidate.replace(hour=hour, minute=minute, second=0, microsecond=0)
        while candidate.weekday() != weekday:
            candidate += timedelta(days=1)
        if candidate <= after_utc:
            candidate += timedelta(weeks=2)
        return candidate

    if kind == RecurrenceKind.MONTHLY:
        day = int(rule.get("day", anchor.day))
        year, month = after_utc.year, after_utc.month
        candidate = _safe_month_day(year, month, day, hour, minute)
        if candidate <= after_utc:
            year, month = _next_month(year, month)
            candidate = _safe_month_day(year, month, day, hour, minute)
        return candidate

    if kind == RecurrenceKind.YEARLY:
        month = int(rule.get("month", anchor.month))
        day = int(rule.get("day", anchor.day))
        year = after_utc.year
        candidate = _safe_month_day(year, month, day, hour, minute)
        if candidate <= after_utc:
            candidate = _safe_month_day(year + 1, month, day, hour, minute)
        return candidate

    if kind == RecurrenceKind.INTERVAL:
        interval_days = int(rule.get("interval_days", 1))
        candidate = anchor
        while candidate <= after_utc:
            candidate += timedelta(days=interval_days)
        return candidate

    raise ValueError(f"Unsupported recurrence kind: {kind}")


def series_should_end(rule: dict[str, Any], next_fire_utc: datetime) -> bool:
    ends_at = rule.get("ends_at")
    if ends_at:
        end_dt = datetime.fromisoformat(ends_at)
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=ZoneInfo("UTC"))
        if next_fire_utc > end_dt:
            return True
    remaining = rule.get("remaining_occurrences")
    if remaining is not None and int(remaining) <= 0:
        return True
    return False


def decrement_occurrence_rule(rule: dict[str, Any]) -> dict[str, Any]:
    updated = dict(rule)
    remaining = updated.get("remaining_occurrences")
    if remaining is not None:
        updated["remaining_occurrences"] = max(0, int(remaining) - 1)
    return updated


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def _safe_month_day(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    import calendar

    last = calendar.monthrange(year, month)[1]
    safe_day = min(day, last)
    return datetime(year, month, safe_day, hour, minute, tzinfo=ZoneInfo("UTC"))
