import logging

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.commands import CalendarCommands, ScheduleCommands
from app.container import Container

logger = logging.getLogger(__name__)


class CalendarBot(commands.Bot):
    def __init__(self, container: Container) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.container = container

    async def setup_hook(self) -> None:
        await self.add_cog(CalendarCommands(self, self.container))
        await self.add_cog(ScheduleCommands(self, self.container))
        guild_id = self.container.settings.discord_guild_id
        if guild_id:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d commands to test guild %s", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d global commands", len(synced))

    async def on_ready(self) -> None:
        logger.info("Discord bot logged in as %s", self.user)

    async def on_tree_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        logger.exception("Unhandled slash-command error", exc_info=error)
        message = "処理中にエラーが発生しました。時間をおいて再度お試しください。"
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
