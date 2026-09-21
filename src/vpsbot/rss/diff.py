from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class FeedEntry:
    guid: str
    link: str
    title: str
    published_at: datetime | None


def entry_identity(entry: dict[str, Any]) -> str:
    guid = entry.get("id") or entry.get("guid")
    if guid:
        return str(guid)
    link = entry.get("link")
    if link:
        return str(link)
    title = entry.get("title", "")
    return f"{title}:{entry.get('published', '')}"


def diff_new_entries(
    entries: list[FeedEntry],
    last_seen_id: str | None,
) -> tuple[list[FeedEntry], str | None]:
    """
    Return entries newer than last_seen_id.

    Feed entries are assumed newest-first (feedparser default).
    On first run (no last_seen_id), only the newest item is taken to avoid flooding.
    """
    if not entries:
        return [], last_seen_id

    ordered = list(entries)
    if last_seen_id is None:
        newest = ordered[0]
        return [newest], newest.guid

    new_items: list[FeedEntry] = []
    seen_last = False
    for item in ordered:
        if item.guid == last_seen_id:
            seen_last = True
            break
        new_items.append(item)

    if not seen_last and ordered and ordered[0].guid != last_seen_id:
        # Last seen missing (feed rotated) — treat all as new but cap to 20
        new_items = ordered[:20]

    new_items.reverse()
    new_last = ordered[0].guid if ordered else last_seen_id
    return new_items, new_last
