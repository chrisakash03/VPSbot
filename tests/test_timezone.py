from datetime import datetime
from zoneinfo import ZoneInfo

from vpsbot.utils.timezone import ensure_utc, format_local


def test_format_local_naive_utc_from_sqlite():
    # As stored/read from SQLite: naive clock in UTC
    naive = datetime(2026, 9, 22, 4, 50, 0)
    assert format_local(naive, "Asia/Singapore") == "Tuesday, 22 Sep 2026 at 12:50"


def test_ensure_utc_aware():
    aware = datetime(2026, 9, 22, 4, 50, tzinfo=ZoneInfo("UTC"))
    assert ensure_utc(aware).hour == 4
