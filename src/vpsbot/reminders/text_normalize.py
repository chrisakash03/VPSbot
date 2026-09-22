from __future__ import annotations

import re

FOR_DAYS_RE = re.compile(r"\bfor\s+(?:the\s+next\s+)?(\d+)\s+days?\b", re.I)
FOR_WEEKS_RE = re.compile(r"\bfor\s+(?:the\s+next\s+)?(\d+)\s+weeks?\b", re.I)
TIMES_RE = re.compile(r"\b(\d+)\s+times\b", re.I)


def normalize_reminder_text(text: str) -> str:
    """Normalize common phrasing before fast parse or Jev."""
    text = re.sub(r"^(?:/r(?:@[\w]+)?\s+)+", "", text.strip(), flags=re.I)
    return re.sub(r"\beveryday\b", "every day", text, flags=re.I)


def has_schedule_bound_phrase(text: str) -> bool:
    return bool(FOR_DAYS_RE.search(text) or FOR_WEEKS_RE.search(text) or TIMES_RE.search(text))


def strip_schedule_duration_phrases(text: str) -> str:
    """Remove duration bounds so dateparser does not treat '3 days' as a date."""
    text = FOR_DAYS_RE.sub(" ", text)
    text = FOR_WEEKS_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()
