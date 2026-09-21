from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import dateparser
from dateparser.search import search_dates

from vpsbot.db.models import RecurrenceKind
from vpsbot.utils.timezone import to_utc

RECURRENCE_PATTERNS: list[tuple[re.Pattern[str], RecurrenceKind, str]] = [
    (re.compile(r"\bevery\s+day\b", re.I), RecurrenceKind.DAILY, "every day"),
    (re.compile(r"\bevery\s+week\b", re.I), RecurrenceKind.WEEKLY, "every week"),
    (
        re.compile(r"\bevery\s+monday\b", re.I),
        RecurrenceKind.WEEKLY,
        "every monday",
    ),
    (
        re.compile(r"\bevery\s+tuesday\b", re.I),
        RecurrenceKind.WEEKLY,
        "every tuesday",
    ),
    (
        re.compile(r"\bevery\s+wednesday\b", re.I),
        RecurrenceKind.WEEKLY,
        "every wednesday",
    ),
    (
        re.compile(r"\bevery\s+thursday\b", re.I),
        RecurrenceKind.WEEKLY,
        "every thursday",
    ),
    (
        re.compile(r"\bevery\s+friday\b", re.I),
        RecurrenceKind.WEEKLY,
        "every friday",
    ),
    (
        re.compile(r"\bevery\s+saturday\b", re.I),
        RecurrenceKind.WEEKLY,
        "every saturday",
    ),
    (
        re.compile(r"\bevery\s+sunday\b", re.I),
        RecurrenceKind.WEEKLY,
        "every sunday",
    ),
    (
        re.compile(r"\bevery\s+2\s+weeks?\b", re.I),
        RecurrenceKind.FORTNIGHTLY,
        "every 2 weeks",
    ),
    (
        re.compile(r"\bevery\s+fortnight\b", re.I),
        RecurrenceKind.FORTNIGHTLY,
        "every fortnight",
    ),
    (re.compile(r"\bevery\s+month\b", re.I), RecurrenceKind.MONTHLY, "every month"),
    (re.compile(r"\bevery\s+year\b", re.I), RecurrenceKind.YEARLY, "every year"),
    (
        re.compile(r"\bevery\s+year\s+on\s+my\s+birthday\b", re.I),
        RecurrenceKind.YEARLY,
        "every year on my birthday",
    ),
]

WEEKDAY_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass(frozen=True)
class ParsedReminder:
    message: str
    fire_at_utc: datetime
    recurrence: RecurrenceKind
    recurrence_rule: dict[str, Any] | None


class ParseError(Exception):
    pass


def _dateparser_settings(tz_name: str) -> dict[str, Any]:
    return {
        "TIMEZONE": tz_name,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": datetime.now(ZoneInfo(tz_name)),
    }


def _strip_phrase(text: str, phrase: str) -> str:
    return re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE).strip()


def _detect_recurrence(text: str) -> tuple[RecurrenceKind, str | None, str]:
    lowered = text.lower()
    for pattern, kind, phrase in RECURRENCE_PATTERNS:
        if pattern.search(lowered):
            remaining = _strip_phrase(text, phrase)
            return kind, phrase, remaining
    return RecurrenceKind.NONE, None, text


def _extract_weekday(phrase: str | None) -> int | None:
    if not phrase:
        return None
    for name, idx in WEEKDAY_MAP.items():
        if name in phrase.lower():
            return idx
    return None


def _strip_reminder_prefix(text: str) -> str:
    return re.sub(
        r"^(remind me to|remind me|reminder to|reminder)\s+",
        "",
        text.strip(),
        flags=re.I,
    ).strip()


def _search_dates_filtered(text: str, settings: dict[str, Any]) -> list[tuple[str, datetime]]:
    noise = {"me", "at", "on", "by", "to", "the", "a", "an"}
    matches = search_dates(text, settings=settings) or []
    return [
        (fragment, dt)
        for fragment, dt in matches
        if fragment.lower() not in noise and len(fragment.strip()) >= 3
    ]


def _parse_anchor_datetime(text: str, tz_name: str) -> datetime:
    settings = _dateparser_settings(tz_name)
    working = _strip_reminder_prefix(text)
    matches = _search_dates_filtered(working, settings)
    if not matches:
        raise ParseError("Could not find a date or time. Try something like 'tomorrow at 5pm'.")
    if len(matches) == 1:
        _, dt = matches[0]
    else:
        combined = " ".join(fragment for fragment, _ in matches)
        dt = dateparser.parse(combined, settings=settings)
        if dt is None:
            dt = matches[-1][1]
        unique = {m[1].replace(second=0, microsecond=0) for m in matches}
        if len(unique) > 1 and dateparser.parse(combined, settings=settings) is None:
            raise ParseError(
                "Multiple possible times found. Please use one clear date/time expression."
            )
    return to_utc(dt, tz_name)


def _clean_message(text: str, tz_name: str, recurrence_phrase: str | None) -> str:
    settings = _dateparser_settings(tz_name)
    working = text
    if recurrence_phrase:
        working = _strip_phrase(working, recurrence_phrase)
    matches = _search_dates_filtered(working, settings)
    for fragment, _ in reversed(matches):
        working = working.replace(fragment, " ")
    working = re.sub(r"\b(at|on|by)\b\s*$", "", working, flags=re.I)
    working = re.sub(r"\s+", " ", working).strip()
    working = re.sub(
        r"^(remind me to|remind me|reminder to|reminder)\s+",
        "",
        working,
        flags=re.I,
    ).strip()
    return working or "Reminder"


def parse_reminder_text(text: str, tz_name: str, now_utc: datetime | None = None) -> ParsedReminder:
    """Parse free-text reminder input into message, UTC fire time, and recurrence."""
    now_utc = now_utc or datetime.now(ZoneInfo("UTC"))
    recurrence, phrase, remainder = _detect_recurrence(text)
    try:
        fire_at = _parse_anchor_datetime(remainder if phrase else text, tz_name)
    except ParseError:
        raise
    if fire_at <= now_utc:
        raise ParseError("That time is in the past. Please choose a future date and time.")

    message = _clean_message(text, tz_name, phrase)
    rule: dict[str, Any] | None = None
    if recurrence != RecurrenceKind.NONE:
        rule = {
            "kind": recurrence.value,
            "anchor_utc": fire_at.isoformat(),
            "weekday": _extract_weekday(phrase or ""),
            "month": fire_at.month,
            "day": fire_at.day,
            "hour": fire_at.hour,
            "minute": fire_at.minute,
        }
    return ParsedReminder(
        message=message,
        fire_at_utc=fire_at,
        recurrence=recurrence,
        recurrence_rule=rule,
    )


def recurrence_rule_to_json(rule: dict[str, Any] | None) -> str | None:
    if rule is None:
        return None
    return json.dumps(rule)
