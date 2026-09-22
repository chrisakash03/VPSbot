from __future__ import annotations

import re

from vpsbot.db.models import RecurrenceKind
from vpsbot.reminders.parsing import ParseError, ParsedReminder

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


def should_invoke_jev(
    text: str,
    fast_result: ParsedReminder | None,
    error: ParseError | None,
) -> bool:
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
