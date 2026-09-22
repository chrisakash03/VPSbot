"""Jev question definitions — see https://docs.typesafe.ai/primitives.md"""

from __future__ import annotations

from typesafe_sdk import Choice, Noul

MONTHS = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
WEEKDAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
YEAR_WINDOW = list(range(2024, 2032))


def reminder_questions() -> dict:
    absent = "Not stated or not applicable."
    interval_opts = {"none": absent, "other": "Another interval not in the list."}
    for d in range(1, 15):
        interval_opts[str(d)] = None

    max_occ = {"none": absent, "other": "Another count not in the list."}
    for n in range(2, 31):
        max_occ[str(n)] = None

    duration_days_opts = {"none": absent, "other": "Another day count not in the list."}
    for d in range(1, 31):
        duration_days_opts[str(d)] = None

    duration_weeks = {"none": absent, "1": None, "2": None, "3": None, "4": None, "other": absent}

    hours = {"none": absent}
    for h in range(24):
        hours[str(h)] = None

    minutes = {"none": absent, "0": None, "15": None, "30": None, "45": None, "other": absent}

    role = "when the reminder should first fire"
    return {
        "is_recurring": Noul(
            instructions="The user wants a repeating reminder schedule, not only a one-off.",
        ),
        "schedule_kind": Choice(
            instructions="What recurrence pattern best matches the user text?",
            criteria={
                "one_off": "Single reminder only",
                "daily": "Every day",
                "weekly": "Every week or a specific weekday",
                "interval_days": "Every N days (e.g. every 2 days)",
                "fortnightly": "Every two weeks",
                "monthly": "Every month",
                "yearly": "Every year",
                "unclear": "Cannot determine",
            },
        ),
        "interval_days": Choice(
            instructions="If every N days, what is N?",
            criteria=interval_opts,
        ),
        "weekday_name": Choice(
            instructions="If a specific weekday is named for recurrence, which day?",
            criteria={w: None for w in WEEKDAYS} | {"none": absent},
        ),
        "end_kind": Choice(
            instructions="Does the schedule have an end bound?",
            criteria={
                "none": "Repeats until cancelled",
                "until_date": "Until a specific date",
                "duration": "For a duration (e.g. two weeks)",
                "max_occurrences": "A fixed number of times",
                "unclear": "Cannot determine",
            },
        ),
        "duration_days": Choice(
            instructions="If for a duration in days (e.g. for 3 days), how many days?",
            criteria=duration_days_opts,
        ),
        "duration_weeks": Choice(
            instructions="If for a duration in weeks, how many weeks?",
            criteria=duration_weeks,
        ),
        "max_occurrences": Choice(
            instructions="If a fixed number of reminders, how many total?",
            criteria=max_occ,
        ),
        "time_kind": Choice(
            instructions="Did the user specify a time of day for the reminder?",
            criteria={
                "specific_time": "A specific time was given",
                "no_time_stated": "No time mentioned",
                "unclear": "Cannot determine",
            },
        ),
        "hour_local": Choice(
            instructions="Local hour (24h) for the reminder time if stated.",
            criteria=hours,
        ),
        "minute_local": Choice(
            instructions="Local minute for the reminder time if stated.",
            criteria=minutes,
        ),
        "date_mode": Choice(
            instructions=f"How is {role} written?",
            criteria={"absolute": None, "relative": None, "none": "No date stated"},
        ),
        "date_month": Choice(
            instructions=f"If absolute, which month for {role}?",
            criteria={m: None for m in MONTHS} | {"none": absent},
        ),
        "date_day": Choice(
            instructions=f"If absolute, day of month (1-31) for {role}?",
            criteria={str(d): None for d in range(1, 32)} | {"none": absent},
        ),
        "date_year": Choice(
            instructions=f"If absolute, which year for {role}?",
            criteria={str(y): None for y in YEAR_WINDOW}
            | {"none": "No year stated", "out_of_range": "Year out of range"},
        ),
        "date_day_anchor": Choice(
            instructions=f"If relative, which day anchor for {role}?",
            criteria={
                "today": None,
                "tomorrow": None,
                "day_after": None,
                "weekday": None,
                "none": absent,
            },
        ),
        "date_weekday": Choice(
            instructions=f"If relative weekday, which weekday for {role}?",
            criteria={w: None for w in WEEKDAYS} | {"none": absent},
        ),
        "date_week_offset": Choice(
            instructions=f"Week offset for named weekday for {role}?",
            criteria={"current": None, "next": None, "none": absent},
        ),
    }
