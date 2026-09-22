from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.parsing import ParsedReminder, recurrence_rule_to_json


class EndKind(StrEnum):
    NONE = "none"
    UNTIL_UTC = "until_utc"
    MAX_OCCURRENCES = "max_occurrences"
    DURATION_DAYS = "duration_days"


class ReviewAction(StrEnum):
    AUTO = "auto"
    CONFIRM = "confirm"
    CLARIFY = "clarify"


class ParseSource(StrEnum):
    FAST = "fast"
    JEV = "jev"


@dataclass
class ScheduleEnd:
    kind: EndKind = EndKind.NONE
    until_utc: datetime | None = None
    max_occurrences: int | None = None
    remaining_occurrences: int | None = None
    duration_days: int | None = None


@dataclass
class ScheduleSpec:
    message: str
    start_at_utc: datetime
    recurrence: RecurrenceKind
    interval_days: int | None = None
    weekday: int | None = None
    end: ScheduleEnd = field(default_factory=ScheduleEnd)
    source: ParseSource = ParseSource.FAST
    review: ReviewAction = ReviewAction.AUTO
    review_reason: str | None = None
    confidence: float | None = None

    def to_parsed_reminder(self) -> ParsedReminder:
        rule: dict[str, Any] | None = None
        if self.recurrence != RecurrenceKind.NONE:
            rule = {
                "kind": self.recurrence.value,
                "anchor_utc": self.start_at_utc.isoformat(),
                "hour": self.start_at_utc.hour,
                "minute": self.start_at_utc.minute,
                "day": self.start_at_utc.day,
                "month": self.start_at_utc.month,
            }
            if self.weekday is not None:
                rule["weekday"] = self.weekday
            if self.interval_days is not None:
                rule["interval_days"] = self.interval_days
            if self.end.kind == EndKind.UNTIL_UTC and self.end.until_utc:
                rule["ends_at"] = self.end.until_utc.isoformat()
            if self.end.kind == EndKind.MAX_OCCURRENCES and self.end.remaining_occurrences:
                rule["max_occurrences"] = self.end.max_occurrences
                rule["remaining_occurrences"] = self.end.remaining_occurrences
            if self.end.kind == EndKind.DURATION_DAYS:
                if self.end.duration_days:
                    rule["duration_days"] = self.end.duration_days
                if self.end.until_utc:
                    rule["ends_at"] = self.end.until_utc.isoformat()
        return ParsedReminder(
            message=self.message,
            fire_at_utc=self.start_at_utc,
            recurrence=self.recurrence,
            recurrence_rule=rule,
        )

    def to_json(self) -> str:
        payload = {
            "message": self.message,
            "start_at_utc": self.start_at_utc.isoformat(),
            "recurrence": self.recurrence.value,
            "interval_days": self.interval_days,
            "weekday": self.weekday,
            "end": {
                "kind": self.end.kind.value,
                "until_utc": self.end.until_utc.isoformat() if self.end.until_utc else None,
                "max_occurrences": self.end.max_occurrences,
                "remaining_occurrences": self.end.remaining_occurrences,
                "duration_days": self.end.duration_days,
            },
            "source": self.source.value,
            "review": self.review.value,
            "review_reason": self.review_reason,
            "confidence": self.confidence,
        }
        return json.dumps(payload)

    @classmethod
    def from_json(cls, raw: str) -> ScheduleSpec:
        data = json.loads(raw)
        end_data = data.get("end") or {}
        until = end_data.get("until_utc")
        return cls(
            message=data["message"],
            start_at_utc=datetime.fromisoformat(data["start_at_utc"]),
            recurrence=RecurrenceKind(data["recurrence"]),
            interval_days=data.get("interval_days"),
            weekday=data.get("weekday"),
            end=ScheduleEnd(
                kind=EndKind(end_data.get("kind", "none")),
                until_utc=datetime.fromisoformat(until) if until else None,
                max_occurrences=end_data.get("max_occurrences"),
                remaining_occurrences=end_data.get("remaining_occurrences"),
                duration_days=end_data.get("duration_days"),
            ),
            source=ParseSource(data.get("source", "jev")),
            review=ReviewAction(data.get("review", "auto")),
            review_reason=data.get("review_reason"),
            confidence=data.get("confidence"),
        )


def parsed_reminder_to_spec(parsed: ParsedReminder, source: ParseSource = ParseSource.FAST) -> ScheduleSpec:
    rule = parsed.recurrence_rule or {}
    end = ScheduleEnd()
    if rule.get("ends_at"):
        end = ScheduleEnd(
            kind=EndKind.UNTIL_UTC,
            until_utc=datetime.fromisoformat(rule["ends_at"]),
        )
    elif rule.get("remaining_occurrences") is not None:
        end = ScheduleEnd(
            kind=EndKind.MAX_OCCURRENCES,
            max_occurrences=rule.get("max_occurrences"),
            remaining_occurrences=rule.get("remaining_occurrences"),
        )
    elif rule.get("duration_days"):
        end = ScheduleEnd(
            kind=EndKind.DURATION_DAYS,
            duration_days=int(rule["duration_days"]),
        )
    weekday = rule.get("weekday")
    return ScheduleSpec(
        message=parsed.message,
        start_at_utc=parsed.fire_at_utc,
        recurrence=parsed.recurrence,
        interval_days=rule.get("interval_days"),
        weekday=int(weekday) if weekday is not None else None,
        end=end,
        source=source,
        review=ReviewAction.AUTO,
        confidence=1.0,
    )


def validate_schedule_spec(spec: ScheduleSpec, now_utc: datetime) -> list[str]:
    errors: list[str] = []
    if spec.start_at_utc <= now_utc:
        errors.append("Start time is in the past.")
    if spec.recurrence == RecurrenceKind.INTERVAL and not spec.interval_days:
        errors.append("Interval recurrence requires interval_days.")
    if spec.interval_days is not None and spec.interval_days < 1:
        errors.append("interval_days must be at least 1.")
    if spec.end.kind == EndKind.UNTIL_UTC:
        if not spec.end.until_utc:
            errors.append("until end requires until_utc.")
        elif spec.end.until_utc <= spec.start_at_utc:
            errors.append("End time must be after the first fire.")
    if spec.end.kind == EndKind.MAX_OCCURRENCES:
        if not spec.end.remaining_occurrences or spec.end.remaining_occurrences < 1:
            errors.append("max_occurrences must be at least 1.")
    if spec.end.kind == EndKind.DURATION_DAYS:
        if not spec.end.duration_days or spec.end.duration_days < 1:
            errors.append("duration_days must be at least 1.")
    if not spec.message.strip():
        errors.append("Reminder message is empty.")
    return errors


def spec_to_recurrence_rule_json(spec: ScheduleSpec) -> str | None:
    parsed = spec.to_parsed_reminder()
    return recurrence_rule_to_json(parsed.recurrence_rule)
