from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from vpsbot.reminders.parsing import ParseError, parse_multi_time_reminders, parse_reminder_text


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


def test_parse_day_month_year_before_clock_when_today_time_has_passed():
    # 23:27 on 11 Oct. search_dates misses "13 october 2026", so a bare 6am
    # would roll to the next morning. The written date must win.
    now = datetime(2026, 10, 11, 15, 27, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text(
        "remind me on 13 october 2026 6am to shave",
        "Asia/Singapore",
        now_utc=now,
    )
    local = parsed.fire_at_utc.astimezone(ZoneInfo("Asia/Singapore"))
    assert (local.year, local.month, local.day, local.hour, local.minute) == (
        2026,
        10,
        13,
        6,
        0,
    )
    assert parsed.message == "shave"


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


def _local(parsed, tz_name="Asia/Singapore"):
    return parsed.fire_at_utc.astimezone(ZoneInfo(tz_name))


def test_multi_slots_keep_their_own_days_and_bare_times_are_today():
    # 10:00 SGT on Thursday 22 Oct 2026.
    now = datetime(2026, 10, 22, 2, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_multi_time_reminders(
        "do this 3pm, tomorrow 5pm, next wednesday 8pm, 11pm",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed is not None
    assert len(parsed) == 4
    assert {item.message for item in parsed} == {"do this"}
    assert [(_local(item).month, _local(item).day, _local(item).hour) for item in parsed] == [
        (10, 22, 15),
        (10, 23, 17),
        (10, 28, 20),
        (10, 28, 23),
    ]
    assert _local(parsed[2]).strftime("%A") == "Wednesday"


def test_next_weekday_skips_to_the_following_week_when_today_is_that_day():
    # 10:00 SGT on Wednesday 21 Oct 2026. "next wednesday" is 28 Oct, not today.
    now = datetime(2026, 10, 21, 2, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_multi_time_reminders(
        "do this 8pm, next wednesday 8pm",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed is not None
    assert (_local(parsed[0]).day, _local(parsed[0]).hour) == (21, 20)
    assert (_local(parsed[1]).day, _local(parsed[1]).hour) == (28, 20)
    assert _local(parsed[1]).strftime("%A") == "Wednesday"


def test_multi_same_day_times():
    # 07:00 SGT on 22 Oct, so 8am, 3pm, and 8pm are still today.
    now = datetime(2026, 10, 21, 23, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_multi_time_reminders(
        "take meds at 8am, 3pm, 8pm",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed is not None
    assert [item.message for item in parsed] == ["take meds", "take meds", "take meds"]
    assert [(_local(item).day, _local(item).hour) for item in parsed] == [
        (22, 8),
        (22, 15),
        (22, 20),
    ]


def test_comma_with_one_time_is_not_a_multi_list():
    now = datetime(2026, 10, 22, 2, 0, tzinfo=ZoneInfo("UTC"))
    assert (
        parse_multi_time_reminders("buy milk, eggs at 5pm", "Asia/Singapore", now_utc=now)
        is None
    )


def test_multi_past_slot_rejects_the_whole_list():
    # 16:00 SGT, so 3pm today has passed. Tomorrow is still valid, but nothing is returned.
    now = datetime(2026, 10, 22, 8, 0, tzinfo=ZoneInfo("UTC"))
    with pytest.raises(ParseError, match="3pm"):
        parse_multi_time_reminders(
            "do this 3pm, tomorrow 5pm",
            "Asia/Singapore",
            now_utc=now,
        )


def test_task_commas_stay_in_the_message_and_bare_times_keep_tomorrow():
    # 23:58 SGT. 12pm and 1pm today have passed, so they must stay on tomorrow.
    now = datetime(2026, 10, 22, 15, 58, tzinfo=ZoneInfo("UTC"))
    task = "schedule telegram messages, draft emails and update nadya"
    leading = parse_multi_time_reminders(
        f"tomorrow 11am, 12pm, 1pm {task}",
        "Asia/Singapore",
        now_utc=now,
    )
    trailing = parse_multi_time_reminders(
        f"{task} tomorrow 11am, 12pm, 1pm",
        "Asia/Singapore",
        now_utc=now,
    )
    for parsed in (leading, trailing):
        assert parsed is not None
        assert len(parsed) == 3
        assert {item.message for item in parsed} == {task}
        assert [(_local(item).day, _local(item).hour) for item in parsed] == [
            (23, 11),
            (23, 12),
            (23, 13),
        ]


def test_bare_time_before_a_named_day_stays_today():
    now = datetime(2026, 10, 22, 2, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_multi_time_reminders(
        "11am, tomorrow 12pm, 1pm",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed is not None
    assert [(_local(item).day, _local(item).hour) for item in parsed] == [
        (22, 11),
        (23, 12),
        (23, 13),
    ]


def test_multi_copies_every_day_onto_each_slot():
    now = datetime(2026, 10, 21, 23, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_multi_time_reminders(
        "take meds every day at 9am, 3pm",
        "Asia/Singapore",
        now_utc=now,
    )
    assert parsed is not None
    assert len(parsed) == 2
    assert {item.message for item in parsed} == {"take meds"}
    assert {item.recurrence.value for item in parsed} == {"daily"}
    assert _local(parsed[0]).day == _local(parsed[1]).day == 22
    assert _local(parsed[0]).hour == 9
    assert _local(parsed[1]).hour == 15
