from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.parsing import _clean_message
from vpsbot.reminders.schedule_spec import (
    EndKind,
    ParseSource,
    ReviewAction,
    ScheduleEnd,
    ScheduleSpec,
    validate_schedule_spec,
)

MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}
WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


@dataclass
class JevAnswer:
    choice: str | None = None
    noul: float | None = None
    confidence: float | None = None


def _part(answers: dict[str, Any], key: str) -> JevAnswer:
    raw = answers.get(key)
    if raw is None:
        return JevAnswer()
    if hasattr(raw, "choice"):
        return JevAnswer(choice=raw.choice, confidence=raw.confidence)
    if hasattr(raw, "noul"):
        return JevAnswer(noul=float(raw.noul), confidence=getattr(raw, "confidence", None))
    if isinstance(raw, dict):
        return JevAnswer(
            choice=raw.get("choice"),
            noul=raw.get("noul"),
            confidence=raw.get("confidence"),
        )
    return JevAnswer()


def resolve_weekday(today: date, weekday: str, week_offset: str) -> date:
    w = WEEKDAYS.index(weekday)
    this_monday = today - timedelta(days=today.weekday())
    if week_offset == "next":
        return this_monday + timedelta(days=7 + w)
    if week_offset == "current":
        return this_monday + timedelta(days=w)
    return today + timedelta(days=(w - today.weekday()) % 7)


def assemble_date(parts: dict[str, JevAnswer], today: date) -> tuple[date | None, float | None, str]:
    confs: list[float] = []
    mode = parts["date_mode"].choice
    if parts["date_mode"].confidence is not None:
        confs.append(parts["date_mode"].confidence)

    if mode == "none" or mode is None:
        return None, min(confs) if confs else None, "no date stated"

    if mode == "absolute":
        month, day, year = (
            parts["date_month"].choice,
            parts["date_day"].choice,
            parts["date_year"].choice,
        )
        for p in (parts["date_month"], parts["date_day"], parts["date_year"]):
            if p.confidence is not None:
                confs.append(p.confidence)
        if "none" in (month, day) or not day or not day.isdigit() or month not in MONTHS:
            return None, min(confs) if confs else None, "absolute date incomplete"
        if year == "out_of_range":
            return None, min(confs) if confs else None, "year out of range"
        y = today.year
        if year and year != "none" and year.isdigit():
            y = int(year)
        elif year == "none":
            try:
                resolved = date(today.year, MONTHS[month], int(day))
            except ValueError:
                return None, min(confs) if confs else None, "impossible date"
            if resolved < today - timedelta(days=31):
                resolved = date(today.year + 1, MONTHS[month], int(day))
            return resolved, min(confs), ""
        try:
            return date(y, MONTHS[month], int(day)), min(confs), ""
        except ValueError:
            return None, min(confs) if confs else None, "impossible date"

    if mode == "relative":
        anchor = parts["date_day_anchor"].choice
        if parts["date_day_anchor"].confidence is not None:
            confs.append(parts["date_day_anchor"].confidence)
        if anchor == "today":
            return today, min(confs), ""
        if anchor == "tomorrow":
            return today + timedelta(days=1), min(confs), ""
        if anchor == "day_after":
            return today + timedelta(days=2), min(confs), ""
        if anchor == "weekday":
            weekday, offset = parts["date_weekday"].choice, parts["date_week_offset"].choice
            for p in (parts["date_weekday"], parts["date_week_offset"]):
                if p.confidence is not None:
                    confs.append(p.confidence)
            if weekday not in WEEKDAYS:
                return None, min(confs) if confs else None, "weekday missing"
            return resolve_weekday(today, weekday, offset or "none"), min(confs), ""
        return None, min(confs) if confs else None, "relative anchor missing"

    return None, min(confs) if confs else None, f"unknown mode {mode}"


def assemble_from_answers(
    answers: dict[str, Any],
    *,
    user_text: str,
    tz_name: str,
    now_utc: datetime,
    fallback_start_utc: datetime | None = None,
) -> ScheduleSpec:
    keys = [
        "date_mode",
        "date_month",
        "date_day",
        "date_year",
        "date_day_anchor",
        "date_weekday",
        "date_week_offset",
        "schedule_kind",
        "interval_days",
        "weekday_name",
        "end_kind",
        "duration_weeks",
        "max_occurrences",
        "time_kind",
        "hour_local",
        "minute_local",
    ]
    parts = {k: _part(answers, k) for k in keys}

    tz = ZoneInfo(tz_name)
    today = now_utc.astimezone(tz).date()
    confidences: list[float] = []

    start_date, date_conf, date_note = assemble_date(parts, today)
    if date_conf is not None:
        confidences.append(date_conf)

    hour, minute = 9, 0
    time_kind = parts["time_kind"].choice
    if parts["time_kind"].confidence is not None:
        confidences.append(parts["time_kind"].confidence)
    if time_kind == "specific_time":
        h, m = parts["hour_local"].choice, parts["minute_local"].choice
        for p in (parts["hour_local"], parts["minute_local"]):
            if p.confidence is not None:
                confidences.append(p.confidence)
        if h and h.isdigit():
            hour = int(h)
        if m == "other":
            minute = 0
        elif m and m.isdigit():
            minute = int(m)
    elif time_kind == "unclear":
        pass

    if start_date is None and fallback_start_utc is not None:
        local = fallback_start_utc.astimezone(tz)
        start_date = local.date()
        hour, minute = local.hour, local.minute
    elif start_date is None:
        start_date = today

    start_local = datetime(
        start_date.year,
        start_date.month,
        start_date.day,
        hour,
        minute,
        tzinfo=tz,
    )
    start_utc = start_local.astimezone(ZoneInfo("UTC"))

    kind_choice = parts["schedule_kind"].choice or "unclear"
    if parts["schedule_kind"].confidence is not None:
        confidences.append(parts["schedule_kind"].confidence)

    recurrence_map = {
        "one_off": RecurrenceKind.NONE,
        "daily": RecurrenceKind.DAILY,
        "weekly": RecurrenceKind.WEEKLY,
        "interval_days": RecurrenceKind.INTERVAL,
        "fortnightly": RecurrenceKind.FORTNIGHTLY,
        "monthly": RecurrenceKind.MONTHLY,
        "yearly": RecurrenceKind.YEARLY,
        "unclear": RecurrenceKind.NONE,
    }
    recurrence = recurrence_map.get(kind_choice, RecurrenceKind.NONE)
    is_recurring = _part(answers, "is_recurring").noul or 0.0
    if is_recurring >= 0.5 and recurrence == RecurrenceKind.NONE and kind_choice == "unclear":
        recurrence = RecurrenceKind.DAILY

    interval_days: int | None = None
    if recurrence == RecurrenceKind.INTERVAL:
        id_choice = parts["interval_days"].choice
        if parts["interval_days"].confidence is not None:
            confidences.append(parts["interval_days"].confidence)
        if id_choice and id_choice.isdigit():
            interval_days = int(id_choice)

    weekday_idx: int | None = None
    wd = parts["weekday_name"].choice
    if wd in WEEKDAYS:
        weekday_idx = WEEKDAYS.index(wd)

    end = ScheduleEnd()
    end_choice = parts["end_kind"].choice or "none"
    if parts["end_kind"].confidence is not None:
        confidences.append(parts["end_kind"].confidence)

    if end_choice == "duration":
        dw = parts["duration_weeks"].choice
        if parts["duration_weeks"].confidence is not None:
            confidences.append(parts["duration_weeks"].confidence)
        if dw and dw.isdigit():
            end = ScheduleEnd(
                kind=EndKind.DURATION_DAYS,
                duration_days=int(dw) * 7,
            )
    elif end_choice == "max_occurrences":
        mo = parts["max_occurrences"].choice
        if parts["max_occurrences"].confidence is not None:
            confidences.append(parts["max_occurrences"].confidence)
        if mo and mo.isdigit():
            n = int(mo)
            end = ScheduleEnd(
                kind=EndKind.MAX_OCCURRENCES,
                max_occurrences=n,
                remaining_occurrences=n,
            )
    elif end_choice == "until_date" and start_date:
        end = ScheduleEnd(
            kind=EndKind.UNTIL_UTC,
            until_utc=start_utc + timedelta(days=30),
        )

    message = _clean_message(user_text, tz_name, None)
    overall = min(confidences) if confidences else 0.0

    review = ReviewAction.AUTO
    reason: str | None = None
    if kind_choice == "unclear" or end_choice == "unclear" or date_note:
        review = ReviewAction.CLARIFY
        reason = date_note or "Schedule pattern unclear"
    elif overall < 0.6:
        review = ReviewAction.CLARIFY
        reason = "Low confidence interpretation"
    elif overall < 0.85:
        review = ReviewAction.CONFIRM
        reason = "Please confirm this schedule"

    spec = ScheduleSpec(
        message=message,
        start_at_utc=start_utc,
        recurrence=recurrence,
        interval_days=interval_days,
        weekday=weekday_idx,
        end=end,
        source=ParseSource.JEV,
        review=review,
        review_reason=reason,
        confidence=overall,
    )

    if end.kind == EndKind.DURATION_DAYS and end.duration_days:
        spec.end.until_utc = start_utc + timedelta(days=end.duration_days)

    errors = validate_schedule_spec(spec, now_utc)
    if errors:
        spec.review = ReviewAction.CLARIFY
        spec.review_reason = "; ".join(errors)

    return spec
