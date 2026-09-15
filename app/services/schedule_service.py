from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.database.repositories import Repository
from app.google.calendar import GoogleCalendarError, GoogleCalendarService, GoogleReauthRequired


class ScheduleValidationError(ValueError):
    pass


@dataclass(frozen=True)
class MemberResult:
    discord_user_id: int
    success: bool
    message: str


@dataclass(frozen=True)
class ScheduleResult:
    event_id: int
    members: list[MemberResult]


def parse_schedule_datetime(date_value: str, time_value: str, timezone_name: str) -> datetime:
    try:
        local = datetime.strptime(f"{date_value} {time_value}", "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ScheduleValidationError("日付は YYYY-MM-DD、時刻は HH:MM で入力してください") from exc
    return local.replace(tzinfo=ZoneInfo(timezone_name))


def validate_schedule(start_at: datetime, end_at: datetime) -> None:
    if end_at <= start_at:
        raise ScheduleValidationError("終了時刻は開始時刻より後にしてください")


class ScheduleService:
    def __init__(self, session: Session, calendar: GoogleCalendarService, timezone_name: str) -> None:
        self.session = session
        self.repository = Repository(session)
        self.calendar = calendar
        self.timezone_name = timezone_name

    def create(
        self,
        *,
        guild_id: int,
        created_by: int,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        discord_user_ids: list[int],
    ) -> ScheduleResult:
        validate_schedule(start_at, end_at)
        unique_user_ids = list(dict.fromkeys(discord_user_ids))
        event = self.repository.create_event(
            guild_id=guild_id,
            title=title.strip(),
            description=description,
            start_at=start_at.astimezone(timezone.utc),
            end_at=end_at.astimezone(timezone.utc),
            created_by=created_by,
        )
        results: list[MemberResult] = []

        for user_id in unique_user_ids:
            account = self.repository.get_account(user_id)
            if account is None:
                message = "Google Calendar未連携"
                self.repository.add_event_member(
                    event_id=event.id,
                    discord_user_id=user_id,
                    google_event_id=None,
                    status="not_linked",
                    error_message=message,
                )
                results.append(MemberResult(user_id, False, message))
                continue
            try:
                google_event_id = self.calendar.create_event(
                    account,
                    title=title,
                    description=description,
                    start_at=start_at,
                    end_at=end_at,
                    timezone_name=self.timezone_name,
                )
                self.repository.add_event_member(
                    event_id=event.id,
                    discord_user_id=user_id,
                    google_event_id=google_event_id,
                    status="created",
                )
                results.append(MemberResult(user_id, True, "登録済み"))
            except GoogleReauthRequired:
                message = "Googleとの再連携が必要です"
                self.repository.add_event_member(
                    event_id=event.id,
                    discord_user_id=user_id,
                    google_event_id=None,
                    status="reauth_required",
                    error_message=message,
                )
                results.append(MemberResult(user_id, False, message))
            except GoogleCalendarError:
                message = "Google Calendarへの登録に失敗しました"
                self.repository.add_event_member(
                    event_id=event.id,
                    discord_user_id=user_id,
                    google_event_id=None,
                    status="failed",
                    error_message=message,
                )
                results.append(MemberResult(user_id, False, message))

        self.session.commit()
        return ScheduleResult(event.id, results)

    def delete(self, *, event_id: int, guild_id: int, requested_by: int, is_admin: bool) -> ScheduleResult:
        event = self.repository.get_event(event_id, guild_id)
        if event is None or event.status == "deleted":
            raise ScheduleValidationError("対象の予定が見つかりません")
        if event.created_by != requested_by and not is_admin:
            raise ScheduleValidationError("削除できるのは作成者または管理者だけです")

        results: list[MemberResult] = []
        for member in event.members:
            if not member.google_event_id or member.status not in {"created", "delete_failed"}:
                results.append(MemberResult(member.discord_user_id, False, "登録済み予定なし"))
                continue
            account = self.repository.get_account(member.discord_user_id)
            if account is None:
                member.status = "delete_failed"
                member.error_message = "Google Calendar未連携"
                results.append(MemberResult(member.discord_user_id, False, member.error_message))
                continue
            try:
                self.calendar.delete_event(account, member.google_event_id)
                member.status = "deleted"
                member.error_message = None
                results.append(MemberResult(member.discord_user_id, True, "削除済み"))
            except GoogleCalendarError:
                member.status = "delete_failed"
                member.error_message = "Google Calendarからの削除に失敗しました"
                results.append(MemberResult(member.discord_user_id, False, member.error_message))

        event.status = (
            "partial_delete"
            if any(member.status == "delete_failed" for member in event.members)
            else "deleted"
        )
        self.session.commit()
        return ScheduleResult(event.id, results)
