"""AI may read availability; humans choose and book through Discord."""

import argparse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.container import Container
from app.database.repositories import Repository
from app.google.calendar import GoogleCalendarError
from app.services.availability_service import find_free_slots, validate_window


def create_server(load_busy) -> FastMCP:
    server = FastMCP("Calendar availability (read only)")

    def read(start_at: str, end_at: str):
        start, end = datetime.fromisoformat(start_at), datetime.fromisoformat(end_at)
        validate_window(start, end)
        return start, end, load_busy(start, end)

    def serialize(intervals, tz):
        return [
            {
                "start_at": left.astimezone(tz).isoformat(),
                "end_at": right.astimezone(tz).isoformat(),
            }
            for left, right in intervals
        ]

    @server.tool()
    def get_schedule(start_at: str, end_at: str) -> dict:
        """Read only the configured owner's busy intervals. ISO 8601 with offset.

        Event titles/details are not disclosed. Empty calendar time is not consent
        to a meeting. Do not infer personal preferences or book anything.
        """
        start, end, busy = read(start_at, end_at)
        clipped = [
            (max(start, left), min(end, right))
            for left, right in busy
            if left < end and right > start
        ]
        return {"busy": serialize(clipped, start.tzinfo)}

    @server.tool()
    def find_available_time(
        start_at: str,
        end_at: str,
        duration_minutes: int = 60,
    ) -> dict:
        """List free intervals chronologically using code, without ranking.

        User must specify the search window and choose the actual meeting time.
        A free interval only means no blocking events in this one calendar.
        No creation, updates, deletion, negotiation, or notifications are allowed.
        """
        start, end, busy = read(start_at, end_at)
        slots = find_free_slots(start, end, busy, duration_minutes)
        return {
            "free_intervals": serialize(slots, start.tzinfo),
            "duration_minutes": duration_minutes,
            "requires_human_selection": True,
        }

    return server


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true", help="Synthetic data; no DB/API")
    args = parser.parse_args()
    if args.demo:

        def load_busy(start, end):
            tz = ZoneInfo("Asia/Tokyo")
            first = start.astimezone(tz).replace(
                hour=20, minute=0, second=0, microsecond=0
            )
            return [(first, first + timedelta(hours=1))]

        create_server(load_busy).run(transport="stdio")
        return

    settings = get_settings()
    if not settings.mcp_discord_user_id:
        parser.error("MCP_DISCORD_USER_ID に自分のDiscord IDを設定してください")
    container = Container.build(settings)

    def load_busy(start, end):
        with container.session_factory() as session:
            account = Repository(session).get_account(settings.mcp_discord_user_id)
            if account is None:
                raise ValueError("先にDiscordで /calendar-link を実行してください")
            try:
                busy = container.calendar.list_busy_intervals(account, start, end)
                session.commit()  # Persist refreshed OAuth credentials only.
                return busy
            except GoogleCalendarError as exc:
                raise ValueError(
                    "予定取得に失敗しました。Google連携を確認してください"
                ) from exc

    try:
        create_server(load_busy).run(transport="stdio")
    finally:
        container.engine.dispose()


if __name__ == "__main__":
    main()
