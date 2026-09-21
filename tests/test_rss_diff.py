from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.rss.diff import FeedEntry, diff_new_entries


def _entry(guid: str) -> FeedEntry:
    return FeedEntry(
        guid=guid,
        link=f"https://example.com/{guid}",
        title=guid,
        published_at=datetime.now(ZoneInfo("UTC")),
    )


def test_first_poll_only_newest():
    entries = [_entry("c"), _entry("b"), _entry("a")]
    new, last = diff_new_entries(entries, None)
    assert len(new) == 1
    assert new[0].guid == "c"
    assert last == "c"


def test_diff_after_last_seen():
    entries = [_entry("new2"), _entry("new1"), _entry("old")]
    new, last = diff_new_entries(entries, "old")
    assert [e.guid for e in new] == ["new1", "new2"]
    assert last == "new2"
