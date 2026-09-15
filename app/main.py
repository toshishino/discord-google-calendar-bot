import asyncio
import logging

import uvicorn

from app.bot.client import CalendarBot
from app.config import get_settings
from app.container import Container
from app.web.api import create_app


async def run() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    container = Container.build(settings)
    bot = CalendarBot(container)
    api = create_app(container)
    server = uvicorn.Server(
        uvicorn.Config(api, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
    )

    try:
        await asyncio.gather(server.serve(), bot.start(settings.discord_bot_token))
    finally:
        if not bot.is_closed():
            await bot.close()
        container.engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())

