from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def to_utc(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(ZoneInfo("UTC"))


def ensure_utc(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; we always persist UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def format_local(dt: datetime, tz_name: str) -> str:
    local = ensure_utc(dt).astimezone(ZoneInfo(tz_name))
    return local.strftime("%A, %d %b %Y at %H:%M")
