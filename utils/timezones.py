from __future__ import annotations

from datetime import datetime, timedelta

import pytz

from models.reminder import VALID_WEEKDAYS

_WEEKDAY_INDEX = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def now_in_tz(tz_name: str) -> datetime:
    return datetime.now(pytz.timezone(tz_name))


def localize(naive_dt: datetime, tz_name: str) -> datetime:
    """Attach tzinfo to a naive datetime without shifting the wall-clock time."""
    tz = pytz.timezone(tz_name)
    return tz.localize(naive_dt)


def next_occurrence_of_weekday(reference: datetime, weekday_name: str) -> datetime:
    """
    Returns the nearest date (today or later) matching weekday_name, keeping
    reference's time-of-day. Used to correct the AI's target_datetime when it
    doesn't actually fall on the weekday it claimed.
    """
    weekday_name = weekday_name.lower()
    if weekday_name not in VALID_WEEKDAYS:
        raise ValueError(f"unknown weekday: {weekday_name}")

    target_idx = _WEEKDAY_INDEX[weekday_name]
    days_ahead = (target_idx - reference.weekday()) % 7
    return reference + timedelta(days=days_ahead)


def ensure_weekly_consistency(target_dt: datetime, day_of_week: str, reference: datetime) -> datetime:
    """
    If target_dt's weekday doesn't match day_of_week, snap it to the next
    correct occurrence instead of silently trusting a wrong AI answer.
    """
    if target_dt.weekday() == _WEEKDAY_INDEX[day_of_week.lower()]:
        return target_dt
    corrected = next_occurrence_of_weekday(reference, day_of_week)
    return corrected.replace(hour=target_dt.hour, minute=target_dt.minute, second=0, microsecond=0)
