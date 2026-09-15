from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.schedule_service import (
    ScheduleValidationError,
    parse_schedule_datetime,
    validate_schedule,
)


def test_parse_schedule_datetime() -> None:
    value = parse_schedule_datetime("2026-09-15", "21:30", "Asia/Tokyo")
    assert value == datetime(2026, 9, 15, 21, 30, tzinfo=ZoneInfo("Asia/Tokyo"))


@pytest.mark.parametrize(
    ("date_value", "time_value"),
    [("2026/09/15", "21:30"), ("2026-09-15", "9pm"), ("2026-02-30", "10:00")],
)
def test_parse_schedule_datetime_rejects_invalid_input(
    date_value: str, time_value: str
) -> None:
    with pytest.raises(ScheduleValidationError):
        parse_schedule_datetime(date_value, time_value, "Asia/Tokyo")


def test_end_must_be_after_start() -> None:
    start = parse_schedule_datetime("2026-09-15", "21:30", "Asia/Tokyo")
    with pytest.raises(ScheduleValidationError):
        validate_schedule(start, start)
