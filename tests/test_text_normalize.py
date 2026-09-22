from vpsbot.reminders.text_normalize import normalize_reminder_text


def test_strip_duplicate_r_prefix():
    assert (
        normalize_reminder_text("/r collect parcel at 6pm")
        == "collect parcel at 6pm"
    )
    assert (
        normalize_reminder_text("/r@kyloreminderbot /r collect parcel")
        == "collect parcel"
    )
