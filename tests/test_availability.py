from datetime import datetime

import pytest

from app.services.availability_service import find_free_slots


def dt(hour):
    return datetime.fromisoformat(f"2026-10-08T{hour:02d}:00:00+09:00")


def test_merges_overlap_clips_and_keeps_human_choice():
    assert find_free_slots(
        dt(18),
        dt(23),
        [
            (dt(17), dt(19)),
            (dt(20), dt(21)),
            (dt(20), dt(22)),
        ],
        60,
    ) == [(dt(19), dt(20)), (dt(22), dt(23))]


def test_empty_and_fully_busy():
    assert find_free_slots(dt(18), dt(23), [], 60) == [(dt(18), dt(23))]
    assert find_free_slots(dt(18), dt(23), [(dt(17), dt(23))], 60) == []


@pytest.mark.parametrize(
    "start,end,duration",
    [
        (dt(18).replace(tzinfo=None), dt(23), 60),
        (dt(23), dt(18), 60),
        (dt(18), dt(23), 0),
        (dt(18), dt(23), 1441),
        (dt(18), datetime.fromisoformat("2026-12-01T23:00:00+09:00"), 60),
    ],
)
def test_rejects_invalid_inputs(start, end, duration):
    with pytest.raises(ValueError):
        find_free_slots(start, end, [], duration)
