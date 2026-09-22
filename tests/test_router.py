from vpsbot.reminders.parsing import ParseError, parse_reminder_text
from vpsbot.reminders.router import matches_complex_heuristic, should_invoke_jev


def test_complex_heuristic_every_n_days():
    assert matches_complex_heuristic("every 2 days at 8pm")


def test_should_invoke_on_parse_error():
    assert should_invoke_jev("nonsense", None, ParseError("x"))


def test_should_not_invoke_simple():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    now = datetime(2026, 1, 1, 10, 0, tzinfo=ZoneInfo("UTC"))
    parsed = parse_reminder_text("remind me tomorrow at 5pm", "UTC", now_utc=now)
    assert not should_invoke_jev("remind me tomorrow at 5pm", parsed, None)
