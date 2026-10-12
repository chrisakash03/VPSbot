from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import dateparser
from dateparser.search import search_dates

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.text_normalize import (
    interval_days_from_text,
    normalize_reminder_text,
    strip_schedule_duration_phrases,
)
from vpsbot.utils.timezone import format_local, to_utc

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

# Times like 12:48pm, 1250pm, 11.00pm, 9 am (dateparser.search often misses these).
_TIME_TOKEN = re.compile(
    r"\b(?P<t>(?:\d{1,2}:\d{2}|\d{1,2}\.\d{2}|\d{3,4}|\d{1,2})\s*(?:a\.?m\.?|p\.?m\.?))\b",
    re.I,
)
_DAY_ANCHOR = re.compile(r"\b(today|tomorrow)\b", re.I)
# search_dates drops or splits these ("13 october 2026 6am" -> nothing, or
# "2026" + "6am" read as 11 June). dateparser.parse on the span itself is reliable.
_MONTH_NAME = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
    r"nov(?:ember)?|dec(?:ember)?"
)
_DAY_NUM = r"\d{1,2}(?:st|nd|rd|th)?"
_CALENDAR_DATE = re.compile(
    rf"\b(?:"
    rf"\d{{4}}-\d{{1,2}}-\d{{1,2}}"
    rf"|{_DAY_NUM}\s+(?:{_MONTH_NAME})(?:\s+\d{{4}})?"
    rf"|(?:{_MONTH_NAME})\s+{_DAY_NUM}(?:\s+\d{{4}})?"
    rf")\b",
    re.I,
)
_CALENDAR_DATE_PHRASE = re.compile(
    rf"(?:\b(?:on|at|by)\s+)?{_CALENDAR_DATE.pattern}",
    re.I,
)

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


# "now" is the current instant. It shows up in reminder text ("can do now")
# and should not be a second fire time.
_NOW_FRAGMENT = re.compile(r"^now(?:\s*\+)?$", re.I)
# "to" after a clock time is an infinitive ("5pm to ask"). Other languages
# read "to" as a weekday, which drops the real day word such as "friday".
_INFINITIVE_TO_AFTER_TIME = re.compile(r"((?:a|p)\.?m\.?)\s+to\b", re.I)


def _dateparser_settings(tz_name: str, now_utc: datetime | None = None) -> dict[str, Any]:
    base = (now_utc or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo(tz_name))
    return {
        "TIMEZONE": tz_name,
        "RETURN_AS_TIMEZONE_AWARE": True,
        "PREFER_DATES_FROM": "future",
        "RELATIVE_BASE": base,
    }


def _text_for_date_search(text: str) -> str:
    text = _INFINITIVE_TO_AFTER_TIME.sub(r"\1", text)
    return re.sub(r"\bnow\b", " ", text, flags=re.I)


def _strip_phrase(text: str, phrase: str) -> str:
    return re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE).strip()


def _detect_recurrence(text: str) -> tuple[RecurrenceKind, str | None, str, int | None]:
    interval = interval_days_from_text(text)
    if interval is not None:
        n, phrase = interval
        return RecurrenceKind.INTERVAL, phrase, _strip_phrase(text, phrase), n
    lowered = text.lower()
    for pattern, kind, phrase in RECURRENCE_PATTERNS:
        if pattern.search(lowered):
            remaining = _strip_phrase(text, phrase)
            return kind, phrase, remaining, None
    return RecurrenceKind.NONE, None, text, None


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


def _find_time_token(text: str) -> str | None:
    best: str | None = None
    for match in _TIME_TOKEN.finditer(text):
        token = match.group("t")
        if not _normalize_time_token(token):
            continue
        if best is None or len(token) > len(best):
            best = token
    return best


def _normalize_time_token(token: str) -> str | None:
    """Turn 1250pm / 12:50pm / 9am into something dateparser understands."""
    raw = token.strip().lower().replace(".", "")
    m = re.match(r"^(\d{1,2}):(\d{2})\s*(am|pm)$", raw)
    if m:
        return f"{int(m.group(1))}:{m.group(2)}{m.group(3)}"
    m = re.match(r"^(\d{3,4})\s*(am|pm)$", raw)
    if m:
        digits = m.group(1)
        ampm = m.group(2)
        if len(digits) == 3:
            hour, minute = int(digits[0]), int(digits[1:])
        else:
            hour, minute = int(digits[:2]), int(digits[2:])
        if hour < 1 or hour > 12 or minute < 0 or minute > 59:
            return None
        return f"{hour}:{minute:02d}{ampm}"
    m = re.match(r"^(\d{1,2})\s*(am|pm)$", raw)
    if m:
        return f"{int(m.group(1))}{m.group(2)}"
    return None


def _explicit_calendar_span(text: str) -> str | None:
    match = _CALENDAR_DATE.search(text)
    if not match:
        return None
    return match.group(0)


def _parse_explicit_calendar(
    text: str,
    tz_name: str,
    now_utc: datetime | None = None,
) -> datetime | None:
    """Parse a written calendar date, with the clock token if one is present."""
    span = _explicit_calendar_span(text)
    if not span:
        return None
    settings = _dateparser_settings(tz_name, now_utc)
    token = _find_time_token(text)
    normalized = _normalize_time_token(token) if token else None
    phrases = [span]
    if normalized:
        phrases = [f"{span} {normalized}", f"{normalized} on {span}", span]
    for phrase in phrases:
        dt = dateparser.parse(phrase, settings=settings)
        if dt is not None:
            return dt
    return None


def _explicit_day_anchor(text: str) -> str | None:
    match = _DAY_ANCHOR.search(text)
    if not match:
        return None
    return match.group(1).lower()


def _day_anchor_in_text(text: str) -> str:
    return _explicit_day_anchor(text) or "today"


_CLOCK_FILLER = re.compile(r"\b(?:at|on|by|around|the|a|an)\b", re.I)
_DATE_WORD = re.compile(
    r"\b(?:today|tomorrow|tonight|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b",
    re.I,
)


def _fragment_is_real_date(fragment: str) -> bool:
    """Ignore dateparser hits on ordinary words such as 'are' or 'do'."""
    if re.search(r"\d", fragment):
        return True
    return _DATE_WORD.search(fragment) is not None


def _schedule_words_only(fragment: str) -> str | None:
    """Return text to keep when a date hit also swallowed task words.

    None means the whole fragment is schedule text and should be removed.
    """
    kept: list[str] = []
    for word in fragment.split():
        core = word.strip(".,:;").lower()
        if not core:
            continue
        if _DATE_WORD.fullmatch(core) or _CLOCK_FILLER.fullmatch(core):
            continue
        if re.search(r"\d", core) or _normalize_time_token(word):
            continue
        kept.append(word)
    if not kept:
        return None
    return " ".join(kept)


def _fragment_is_clock_only(fragment: str, token: str) -> bool:
    """True when search_dates latched onto the clock token and nothing else."""
    rest = re.sub(re.escape(token), " ", fragment, count=1, flags=re.I)
    rest = _CLOCK_FILLER.sub(" ", rest)
    return rest.strip(" .,:;-") == ""


def _matches_are_clock_only(matches: list[tuple[str, datetime]], token: str) -> bool:
    if not matches:
        return True
    return all(_fragment_is_clock_only(fragment, token) for fragment, _ in matches)


def _parse_time_with_anchor(
    time_token: str,
    text: str,
    tz_name: str,
    now_utc: datetime | None = None,
) -> datetime | None:
    settings = _dateparser_settings(tz_name, now_utc)
    normalized = _normalize_time_token(time_token)
    if not normalized:
        return None
    day = _day_anchor_in_text(text)
    for phrase in (f"{day} at {normalized}", f"at {normalized} {day}", normalized):
        dt = dateparser.parse(phrase, settings=settings)
        if dt is not None:
            return dt
    return None


def _utc_minute(dt: datetime, tz_name: str) -> datetime:
    return to_utc(dt, tz_name).replace(second=0, microsecond=0)


def _local_calendar_date(dt: datetime, tz_name: str) -> date:
    tz = ZoneInfo(tz_name)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(tz).date()


def _should_use_calendar_match_over_token(
    matches: list[tuple[str, datetime]],
    anchored: datetime,
    working: str,
    tz_name: str,
    now_utc: datetime,
) -> bool:
    """Keep a full calendar date from search_dates instead of today+time from the token."""
    if len(matches) != 1:
        return len(matches) > 1
    frag, match_dt = matches[0]
    token = _find_time_token(working)
    if not token:
        return False
    compact = token.replace(" ", "").lower()
    frag_norm = frag.replace(" ", "").lower()
    if compact not in frag_norm:
        return False
    now_cmp = _utc_minute(now_utc, "UTC")
    match_utc = _utc_minute(match_dt, tz_name)
    if match_utc <= now_cmp:
        return False
    if _local_calendar_date(anchored, tz_name) == _local_calendar_date(match_dt, tz_name):
        return False
    local_match = match_dt.astimezone(ZoneInfo(tz_name))
    if (
        local_match.hour == 0
        and local_match.minute == 0
        and (anchored.hour != 0 or anchored.minute != 0)
    ):
        # e.g. "10am on 27 sept" -> 10 Sep 2027 00:00 from search_dates.
        return False
    return True


def _search_dates_filtered(text: str, settings: dict[str, Any]) -> list[tuple[str, datetime]]:
    noise = {"me", "at", "on", "by", "to", "the", "a", "an"}
    matches = search_dates(_text_for_date_search(text), settings=settings) or []
    return [
        (fragment, dt)
        for fragment, dt in matches
        if fragment.lower() not in noise
        and len(fragment.strip()) >= 3
        and _NOW_FRAGMENT.match(fragment.strip()) is None
    ]


def _parse_anchor_datetime(text: str, tz_name: str, now_utc: datetime | None = None) -> datetime:
    settings = _dateparser_settings(tz_name, now_utc)
    working = strip_schedule_duration_phrases(_strip_reminder_prefix(text))
    calendar = _parse_explicit_calendar(working, tz_name, now_utc)
    if calendar is not None:
        return to_utc(calendar, tz_name)
    matches = _search_dates_filtered(working, settings)
    token = _find_time_token(working)
    if token and _normalize_time_token(token):
        anchored = _parse_time_with_anchor(token, working, tz_name, now_utc)
        if anchored is not None:
            now = now_utc or datetime.now(ZoneInfo("UTC"))
            anchored_utc = _utc_minute(anchored, tz_name)
            now_cmp = _utc_minute(now, "UTC")
            use_calendar = _should_use_calendar_match_over_token(
                matches, anchored, working, tz_name, now
            )
            if anchored_utc > now_cmp and not use_calendar:
                return to_utc(anchored, tz_name)
            # "at 1am" with no calendar date: search_dates reads "1" as January
            # and midnight. Keep the clock time instead (next day if today passed).
            if (
                anchored_utc <= now_cmp
                and not use_calendar
                and _explicit_day_anchor(working) is None
                and _explicit_calendar_span(working) is None
                and _matches_are_clock_only(matches, token)
            ):
                return to_utc(anchored + timedelta(days=1), tz_name)
            if (
                anchored_utc <= now_cmp
                and _explicit_day_anchor(working) == "today"
                and _matches_are_clock_only(matches, token)
            ):
                return to_utc(anchored, tz_name)

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


def _clean_message(
    text: str,
    tz_name: str,
    recurrence_phrase: str | None,
    now_utc: datetime | None = None,
) -> str:
    settings = _dateparser_settings(tz_name, now_utc)
    working = strip_schedule_duration_phrases(text)
    interval = interval_days_from_text(working)
    if interval is not None:
        working = _strip_phrase(working, interval[1])
    if recurrence_phrase:
        working = _strip_phrase(working, recurrence_phrase)
    working = _CALENDAR_DATE_PHRASE.sub(" ", working)
    matches = _search_dates_filtered(working, settings)
    for fragment, _ in reversed(matches):
        if not _fragment_is_real_date(fragment):
            continue
        kept = _schedule_words_only(fragment)
        working = working.replace(fragment, f" {kept} " if kept else " ")
    token = _find_time_token(working)
    if token:
        working = working.replace(token, " ")
    working = re.sub(r"\b(today|tomorrow)\b", " ", working, flags=re.I)
    working = re.sub(r"(?:^|\s)[\-–—]+(?=\s|$)", " ", working)
    working = re.sub(r"^\s*(?:at|on|by)\b", " ", working, flags=re.I)
    working = re.sub(r"\b(?:at|on|by)\s*$", "", working, flags=re.I)
    working = re.sub(r"^[\s\-–—:,]+|[\s\-–—:,]+$", "", working)
    working = re.sub(r"\s+", " ", working).strip()
    working = re.sub(
        r"^(remind me to|remind me|reminder to|reminder)\s+",
        "",
        working,
        flags=re.I,
    ).strip()
    working = re.sub(r"^to\s+", "", working, flags=re.I).strip()
    return working or "Reminder"


def parse_reminder_text(text: str, tz_name: str, now_utc: datetime | None = None) -> ParsedReminder:
    """Parse free-text reminder input into message, UTC fire time, and recurrence."""
    now_utc = now_utc or datetime.now(ZoneInfo("UTC"))
    text = normalize_reminder_text(text)
    recurrence, phrase, remainder, interval_days = _detect_recurrence(text)
    try:
        fire_at = _parse_anchor_datetime(remainder if phrase else text, tz_name, now_utc)
    except ParseError:
        raise
    fire_at = fire_at.replace(second=0, microsecond=0)
    now_cmp = now_utc.replace(second=0, microsecond=0)
    if fire_at <= now_cmp:
        raise ParseError(
            f"That time is in the past ({format_local(fire_at, tz_name)}; "
            f"now is {format_local(now_utc, tz_name)} in {tz_name}). "
            "Please choose a future date and time."
        )

    message = _clean_message(text, tz_name, phrase, now_utc)
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
        if interval_days is not None:
            rule["interval_days"] = interval_days
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
