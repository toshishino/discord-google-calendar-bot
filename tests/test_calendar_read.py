from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from test_availability import dt

from app.google.calendar import GoogleCalendarService


def test_pagination_allday_transparent_cancelled():
    calendar = GoogleCalendarService(
        SimpleNamespace(default_timezone="Asia/Tokyo"), None
    )
    calendar.ensure_fresh_credentials = MagicMock()
    api = MagicMock()
    api.events.return_value.list.return_value.execute.side_effect = [
        {
            "timeZone": "Asia/Tokyo",
            "nextPageToken": "next",
            "items": [
                {"start": {"date": "2026-10-08"}, "end": {"date": "2026-10-09"}},
                {"status": "cancelled"},
                {"transparency": "transparent"},
            ],
        },
        {
            "items": [
                {
                    "start": {"dateTime": dt(20).isoformat()},
                    "end": {"dateTime": dt(21).isoformat()},
                }
            ]
        },
    ]
    with patch("app.google.calendar.build", return_value=api):
        busy = calendar.list_busy_intervals(
            SimpleNamespace(calendar_id="primary"), dt(18), dt(23)
        )
    assert len(busy) == 2
    assert busy[0][0] == dt(0)
    assert busy[1] == (dt(20), dt(21))
    assert api.events.return_value.list.call_args.kwargs["pageToken"] == "next"
