import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_demo_lists_only_read_tools_and_returns_candidates():
    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server", "--demo"],
        )
        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as client,
        ):
            await client.initialize()
            tools = (await client.list_tools()).tools
            assert {tool.name for tool in tools} == {
                "get_schedule",
                "find_available_time",
            }
            for tool in tools:
                assert "discord_user_id" not in tool.inputSchema["properties"]
            result = await client.call_tool(
                "find_available_time",
                {
                    "start_at": "2026-10-08T19:00:00+09:00",
                    "end_at": "2026-10-08T23:00:00+09:00",
                    "duration_minutes": 60,
                },
            )
            assert not result.isError
            data = json.loads(result.content[0].text)
            assert data["requires_human_selection"] is True
            assert data["free_intervals"] == [
                {
                    "start_at": "2026-10-08T19:00:00+09:00",
                    "end_at": "2026-10-08T20:00:00+09:00",
                },
                {
                    "start_at": "2026-10-08T21:00:00+09:00",
                    "end_at": "2026-10-08T23:00:00+09:00",
                },
            ]
            invalid = await client.call_tool(
                "get_schedule",
                {
                    "start_at": "2026-10-08T19:00:00",
                    "end_at": "2026-10-08T23:00:00",
                },
            )
            assert invalid.isError

    asyncio.run(exercise())
