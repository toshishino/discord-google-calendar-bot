"""Deterministic availability calculation; no preference inference or booking."""

from datetime import datetime, timedelta, timezone

from app.services.schedule_service import ScheduleValidationError


def validate_window(start: datetime, end: datetime) -> None:
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ScheduleValidationError("日時にはタイムゾーンを付けてください")
    if not timedelta(0) < end - start <= timedelta(days=31):
        raise ScheduleValidationError("検索範囲は開始より後、最大31日です")


def find_free_slots(
    start: datetime,
    end: datetime,
    busy: list[tuple[datetime, datetime]],
    duration_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Return all maximal free intervals long enough, in chronological order."""
    validate_window(start, end)
    if not 1 <= duration_minutes <= 1440:
        raise ScheduleValidationError("所要時間は1〜1440分です")
    start, end = start.astimezone(timezone.utc), end.astimezone(timezone.utc)
    intervals = []
    for left, right in busy:
        if left.utcoffset() is None or right.utcoffset() is None or right <= left:
            raise ScheduleValidationError("予定の日時が不正です")
        left, right = max(start, left), min(end, right)
        if left < right:
            intervals.append((left, right))
    cursor = start
    slots = []
    minimum = timedelta(minutes=duration_minutes)
    for left, right in sorted(intervals):
        if left - cursor >= minimum:
            slots.append((cursor, left))
        cursor = max(cursor, right)
    if end - cursor >= minimum:
        slots.append((cursor, end))
    return slots
