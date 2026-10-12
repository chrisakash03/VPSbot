from __future__ import annotations

import re

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.parsing import ParseError, ParsedReminder
from vpsbot.reminders.text_normalize import interval_days_from_text

_BOUND_NEEDS_JEV: list[re.Pattern[str]] = [
    re.compile(r"\buntil\b", re.I),
    re.compile(r"\bfor\s+\d+\s+months?\b", re.I),
]

COMPLEX_HEURISTICS: list[re.Pattern[str]] = [
    re.compile(r"\bevery\s+\d+\s+days?\b", re.I),
    re.compile(r"\bevery\s+other\s+day\b", re.I),
    re.compile(r"\bfor\s+the\s+next\b", re.I),
    re.compile(r"\bfor\s+\d+\s+(days?|weeks?|months?)\b", re.I),
    re.compile(r"\b\d+\s+times\b", re.I),
    re.compile(r"\buntil\b", re.I),
]


def matches_complex_heuristic(text: str) -> bool:
    return any(p.search(text) for p in COMPLEX_HEURISTICS)


def _fast_interval_is_complete(text: str, fast_result: ParsedReminder | None) -> bool:
    """True when 'every N days' was parsed and no leftover bound needs Jev."""
    if fast_result is None or fast_result.recurrence != RecurrenceKind.INTERVAL:
        return False
    if any(pattern.search(text) for pattern in _BOUND_NEEDS_JEV):
        return False
    found = interval_days_from_text(text)
    if found is None:
        return False
    rule = fast_result.recurrence_rule or {}
    return rule.get("interval_days") == found[0]


def should_invoke_jev(
    text: str,
    fast_result: ParsedReminder | None,
    error: ParseError | None,
) -> bool:
    if _fast_interval_is_complete(text, fast_result):
        return False
    if error is not None:
        # Simple time-only phrases should stay on the fast path after parsing fixes.
        if "Could not find a date or time" in str(error):
            return True
        if "in the past" in str(error):
            return False
        return True
    if matches_complex_heuristic(text):
        return True
    lowered = text.lower()
    if fast_result and fast_result.recurrence == RecurrenceKind.NONE:
        if re.search(r"\bevery\b", lowered) or re.search(r"\brepeat\b", lowered):
            return True
    if fast_result and re.search(r"\bevery\s+\d+\s+days?\b", lowered):
        if fast_result.recurrence != RecurrenceKind.INTERVAL:
            return True
    return False
