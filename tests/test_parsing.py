from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from vpsbot.reminders.parsing import ParseError, parse_reminder_text


def test_parse_simple_reminder():
    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "remind me to submit the report tomorrow at 5pm",
        "Asia/Singapore",
        now_utc=now,
    )
    assert "submit" in parsed.message.lower()
    assert parsed.fire_at_utc > now


def test_parse_rejects_past():
    now = datetime(2026, 6, 1, 12, 0, tzinfo=ZoneInfo("UTC"))
    with pytest.raises(ParseError):
        parse_reminder_text("remind me on 2020-01-01 at 9am", "UTC", now_utc=now)


def test_parse_today_before_time():
    now = datetime(2026, 9, 22, 4, 49, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("test today 1250pm", "Asia/Singapore", now_utc=now)
    assert parsed.message == "test"
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 12 and local.minute == 50


def test_parse_same_day_morning_from_early_morning():
    # 02:41 SGT = 18:41 UTC previous calendar day in UTC; must still resolve 10:00 same local day.
    now = datetime(2026, 9, 26, 18, 41, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("10am today schedule dm1", "Asia/Singapore", now_utc=now)
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.year == 2026 and local.month == 9 and local.day == 27
    assert local.hour == 10 and local.minute == 0


def test_parse_trailing_period_after_pm():
    now = datetime(2026, 9, 27, 13, 48, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("11pm. today", "Asia/Singapore", now_utc=now)
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 23 and local.minute == 0


def test_parse_dotted_time_today():
    now = datetime(2026, 9, 27, 13, 26, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("11.00pm today", "Asia/Singapore", now_utc=now)
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 23 and local.minute == 0


def test_parse_day_month_with_time_not_swapped():
    now = datetime(2026, 9, 26, 18, 41, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "10am on 27 sept schedule dm1 b2 messages",
        "Asia/Singapore",
        now_utc=now,
    )
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.year == 2026 and local.month == 9 and local.day == 27
    assert local.hour == 10 and local.minute == 0


def test_parse_compact_time_with_today():
    now = datetime(2026, 9, 22, 4, 48, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "send this reminder to me 1250pm today",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed.message == "send this reminder to me"
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 12 and local.minute == 50


def test_parse_time_only_today():
    # 12:47 SGT = 04:47 UTC
    now = datetime(2026, 9, 22, 4, 47, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("test item 12:48pm", "Asia/Singapore", now_utc=now)
    assert parsed.message == "test item"
    assert parsed.fire_at_utc > now
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.hour == 12 and local.minute == 48


def test_parse_absolute_date_with_time():
    now = datetime(2026, 9, 22, 11, 35, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "collect parcel from chop ah tat at 6pm on 23 september 2026",
        "Asia/Singapore",
        now_utc=now,
    )
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert local.year == 2026 and local.month == 9 and local.day == 23
    assert local.hour == 18 and local.minute == 0
    assert "collect parcel" in parsed.message.lower()


def test_parse_tmr_at_1am_not_next_january():
    # 00:04 on 5 Oct in UTC+8 is still 4 Oct in UTC. search_dates turns "at 1am"
    # into 4 Jan next year at midnight when "tmr" is not recognized.
    now = datetime(2026, 10, 4, 16, 4, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "moisturise hands before sleeping tmr at 1am",
        "UTC",
        now_utc=now,
    )
    local = parsed.fire_at_utc.astimezone(ZoneInfo("UTC"))
    assert (local.year, local.month, local.day, local.hour, local.minute) == (
        2026,
        10,
        5,
        1,
        0,
    )
    assert parsed.message == "moisturise hands before sleeping"


def test_parse_tmr_at_1am_singapore():
    now = datetime(2026, 10, 4, 16, 4, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "moisturise hands before sleeping tmr at 1am",
        "Asia/Singapore",
        now_utc=now,
    )
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert (local.year, local.month, local.day, local.hour, local.minute) == (
        2026,
        10,
        6,
        1,
        0,
    )
    assert parsed.message == "moisturise hands before sleeping"


def test_clock_only_past_time_rolls_forward_not_january():
    now = datetime(2026, 10, 4, 16, 4, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("moisturise hands at 1am", "UTC", now_utc=now)
    local = parsed.fire_at_utc.astimezone(ZoneInfo("UTC"))
    assert (local.year, local.month, local.day, local.hour, local.minute) == (
        2026,
        10,
        5,
        1,
        0,
    )


def test_friday_5pm_ignores_now_in_the_task():
    now = datetime(2026, 10, 5, 15, 36, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "remind me on friday 5pm to ask physio what sports i can do now "
        "+ whether i can do things like theme park rides HAHAH",
        "Asia/Singapore",
        now_utc=now,
    )
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert (local.year, local.month, local.day, local.hour, local.minute) == (
        2026,
        10,
        9,
        17,
        0,
    )
    assert local.strftime("%A") == "Friday"
    assert "now" in parsed.message
    assert "friday" not in parsed.message.lower()
    assert "physio" in parsed.message


def test_explicit_today_past_clock_stays_rejected():
    now = datetime(2026, 10, 4, 16, 4, tzinfo=ZoneInfo("UTC"))
    with pytest.raises(ParseError, match="in the past"):
        parse_reminder_text("today at 1am", "UTC", now_utc=now)


def test_parse_daily_recurrence():
    now = datetime(2026, 1, 1, 0, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("every day at 8am drink water", "UTC", now_utc=now)
    assert parsed.recurrence.value == "daily"
    assert parsed.recurrence_rule is not None
