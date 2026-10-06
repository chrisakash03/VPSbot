from vpsbot.reminders.text_normalize import normalize_reminder_text


def test_tmr_slang_becomes_tomorrow():
    assert (
        normalize_reminder_text("moisturise hands before sleeping tmr at 1am")
        == "moisturise hands before sleeping tomorrow at 1am"
    )
    assert normalize_reminder_text("tmrw 9pm") == "tomorrow 9pm"


def test_strip_duplicate_r_prefix():
    assert (
        normalize_reminder_text("/r collect parcel at 6pm")
        == "collect parcel at 6pm"
    )
    assert (
        normalize_reminder_text("/r@kyloreminderbot /r collect parcel")
        == "collect parcel"
    )
