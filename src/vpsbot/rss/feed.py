from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any
from zoneinfo import ZoneInfo

import feedparser

from vpsbot.rss.diff import FeedEntry, entry_identity


def _parse_published(entry: dict[str, Any]) -> datetime | None:
    if entry.get("published_parsed"):
        return datetime(*entry.published_parsed[:6], tzinfo=ZoneInfo("UTC"))
    if entry.get("updated_parsed"):
        return datetime(*entry.updated_parsed[:6], tzinfo=ZoneInfo("UTC"))
    raw = entry.get("published") or entry.get("updated")
    if raw:
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=ZoneInfo("UTC"))
            return dt.astimezone(ZoneInfo("UTC"))
        except (TypeError, ValueError):
            return None
    return None


def fetch_feed_entries(url: str) -> tuple[str | None, list[FeedEntry]]:
    parsed = feedparser.parse(url)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise ValueError(f"Failed to parse feed: {url}")
    title = getattr(parsed.feed, "title", None)
    entries: list[FeedEntry] = []
    for raw in parsed.entries:
        entries.append(
            FeedEntry(
                guid=entry_identity(raw),
                link=str(raw.get("link") or ""),
                title=str(raw.get("title") or "(no title)"),
                published_at=_parse_published(raw),
            )
        )
    return title, entries
