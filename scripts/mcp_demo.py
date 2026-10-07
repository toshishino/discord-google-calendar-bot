"""Exercise the real MCP protocol with synthetic data, without an LLM/API key."""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp.server", "--demo"],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as client,
    ):
        await client.initialize()
        print("Tools:", [tool.name for tool in (await client.list_tools()).tools])
        result = await client.call_tool(
            "find_available_time",
            {
                "start_at": "2026-10-08T19:00:00+09:00",
                "end_at": "2026-10-08T23:00:00+09:00",
                "duration_minutes": 60,
            },
        )
        for block in result.content:
            if block.type == "text":
                print(block.text)


if __name__ == "__main__":
    asyncio.run(main())
