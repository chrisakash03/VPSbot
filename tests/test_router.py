from vpsbot.reminders.parsing import ParseError, parse_reminder_text
from vpsbot.reminders.router import matches_complex_heuristic, should_invoke_jev


def test_complex_heuristic_every_n_days():
    assert matches_complex_heuristic("every 2 days at 8pm")


def test_should_invoke_on_parse_error():
    assert should_invoke_jev("nonsense", None, ParseError("x"))


def test_every_n_days_with_week_bound_stays_on_fast_path():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 10, 12, 8, 7, tzinfo=ZoneInfo("UTC"))
    text = "every 7 days at 8pm for 6 weeks check tickets"
    parsed = parse_reminder_text(text, "Asia/Singapore", now_utc=now)
    assert not should_invoke_jev(text, parsed, None)


def test_until_still_invokes_jev():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 10, 12, 8, 7, tzinfo=ZoneInfo("UTC"))
    text = "every 7 days at 8pm until december check tickets"
    parsed = parse_reminder_text(text, "Asia/Singapore", now_utc=now)
    assert should_invoke_jev(text, parsed, None)


def test_should_not_invoke_simple():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("remind me tomorrow at 5pm", "UTC", now_utc=now)
    assert not should_invoke_jev("remind me tomorrow at 5pm", parsed, None)
