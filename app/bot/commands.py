from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from contextlib import contextmanager

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy.orm import Session

from app.container import Container
from app.database.repositories import Repository
from app.google.calendar import GoogleCalendarError
from app.services.schedule_service import (
    ScheduleService,
    ScheduleValidationError,
    parse_schedule_datetime,
)

logger = logging.getLogger(__name__)


@contextmanager
def db_session(container: Container) -> Iterator[Session]:
    session = container.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class CalendarCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, container: Container) -> None:
        self.bot = bot
        self.container = container

    @app_commands.command(
        name="calendar-link", description="Google Calendarを連携します"
    )
    async def calendar_link(self, interaction: discord.Interaction) -> None:
        with db_session(self.container) as session:
            url = self.container.oauth.create_authorization_url(
                interaction.user.id, Repository(session)
            )
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="Googleアカウントを連携", url=url))
        await interaction.response.send_message(
            "10分以内にボタンからGoogle Calendarを連携してください。",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(
        name="calendar-status", description="Google Calendarの連携状態を確認します"
    )
    async def calendar_status(self, interaction: discord.Interaction) -> None:
        with db_session(self.container) as session:
            account = Repository(session).get_account(interaction.user.id)
            message = (
                f"✅ Google Calendar連携済み（{account.google_email or 'メール非表示'}）"
                if account
                else "❌ 未連携です。`/calendar-link` から連携してください。"
            )
        await interaction.response.send_message(message, ephemeral=True)

    @app_commands.command(
        name="calendar-unlink", description="Google Calendar連携を解除します"
    )
    async def calendar_unlink(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)

        def unlink() -> bool:
            with db_session(self.container) as session:
                repository = Repository(session)
                account = repository.get_account(interaction.user.id)
                if account is None:
                    return False
                try:
                    self.container.calendar.revoke(account)
                except GoogleCalendarError:
                    logger.warning(
                        "Google token revoke failed for user %s", interaction.user.id
                    )
                repository.delete_account(interaction.user.id)
                return True

        removed = await asyncio.to_thread(unlink)
        message = (
            "✅ Google Calendar連携を解除しました。"
            if removed
            else "Google Calendarは未連携です。"
        )
        await interaction.followup.send(message, ephemeral=True)


class ScheduleCommands(commands.Cog):
    def __init__(self, bot: commands.Bot, container: Container) -> None:
        self.bot = bot
        self.container = container

    @app_commands.command(
        name="schedule-add",
        description="複数メンバーのGoogle Calendarへ予定を登録します",
    )
    @app_commands.describe(
        title="予定名",
        date="日付（YYYY-MM-DD）",
        start_time="開始時刻（HH:MM）",
        end_time="終了時刻（HH:MM）",
        member1="登録対象（必須）",
        member2="登録対象",
        member3="登録対象",
        member4="登録対象",
        member5="登録対象",
        description="説明（任意）",
    )
    async def schedule_add(
        self,
        interaction: discord.Interaction,
        title: app_commands.Range[str, 1, 255],
        date: str,
        start_time: str,
        end_time: str,
        member1: discord.Member,
        member2: discord.Member | None = None,
        member3: discord.Member | None = None,
        member4: discord.Member | None = None,
        member5: discord.Member | None = None,
        description: app_commands.Range[str, 0, 2000] | None = None,
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "このコマンドはサーバー内で使用してください。", ephemeral=True
            )
            return
        try:
            start_at = parse_schedule_datetime(
                date, start_time, self.container.settings.default_timezone
            )
            end_at = parse_schedule_datetime(
                date, end_time, self.container.settings.default_timezone
            )
            if end_at <= start_at:
                raise ScheduleValidationError("終了時刻は開始時刻より後にしてください")
        except ScheduleValidationError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        members = [
            member for member in (member1, member2, member3, member4, member5) if member
        ]
        await interaction.response.defer(ephemeral=True, thinking=True)

        def create_schedule():
            with db_session(self.container) as session:
                service = ScheduleService(
                    session,
                    self.container.calendar,
                    self.container.settings.default_timezone,
                )
                return service.create(
                    guild_id=interaction.guild_id,
                    created_by=interaction.user.id,
                    title=str(title),
                    description=str(description) if description else None,
                    start_at=start_at,
                    end_at=end_at,
                    discord_user_ids=[member.id for member in members],
                )

        result = await asyncio.to_thread(create_schedule)
        lines = [
            "✅ 予定登録処理が完了しました",
            f"**{title}**",
            f"{date} {start_time}〜{end_time}",
            f"Bot Event ID: `{result.event_id}`",
            "",
        ]
        lines.extend(
            f"{'✅' if item.success else '❌'} <@{item.discord_user_id}> — {item.message}"
            for item in result.members
        )
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(
        name="schedule-delete", description="Botが作成した予定を削除します"
    )
    @app_commands.describe(event_id="予定登録時に表示されたBot Event ID")
    async def schedule_delete(
        self, interaction: discord.Interaction, event_id: int
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "このコマンドはサーバー内で使用してください。", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        permissions = getattr(interaction.user, "guild_permissions", None)
        is_admin = bool(permissions and permissions.administrator)

        def delete_schedule():
            with db_session(self.container) as session:
                service = ScheduleService(
                    session,
                    self.container.calendar,
                    self.container.settings.default_timezone,
                )
                return service.delete(
                    event_id=event_id,
                    guild_id=interaction.guild_id,
                    requested_by=interaction.user.id,
                    is_admin=is_admin,
                )

        try:
            result = await asyncio.to_thread(delete_schedule)
        except ScheduleValidationError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        lines = [f"予定 `{result.event_id}` の削除処理が完了しました", ""]
        lines.extend(
            f"{'✅' if item.success else '❌'} <@{item.discord_user_id}> — {item.message}"
            for item in result.members
        )
        await interaction.followup.send("\n".join(lines), ephemeral=True)
