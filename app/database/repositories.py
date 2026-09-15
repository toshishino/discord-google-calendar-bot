from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import BotEvent, EventMember, GoogleAccount, OAuthState


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_account(self, discord_user_id: int) -> GoogleAccount | None:
        return self.session.scalar(
            select(GoogleAccount).where(GoogleAccount.discord_user_id == discord_user_id)
        )

    def upsert_account(self, **values) -> GoogleAccount:
        account = self.get_account(values["discord_user_id"])
        if account is None:
            account = GoogleAccount(**values)
            self.session.add(account)
        else:
            for key, value in values.items():
                setattr(account, key, value)
        self.session.flush()
        return account

    def delete_account(self, discord_user_id: int) -> bool:
        result = self.session.execute(
            delete(GoogleAccount).where(GoogleAccount.discord_user_id == discord_user_id)
        )
        return bool(result.rowcount)

    def save_oauth_state(self, nonce: str, discord_user_id: int, expires_at: datetime) -> None:
        self.session.add(OAuthState(nonce=nonce, discord_user_id=discord_user_id, expires_at=expires_at))

    def consume_oauth_state(self, nonce: str) -> OAuthState | None:
        state = self.session.get(OAuthState, nonce)
        if state is None:
            return None
        self.session.delete(state)
        self.session.flush()
        expires_at = state.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            return None
        return state

    def purge_expired_oauth_states(self) -> None:
        self.session.execute(delete(OAuthState).where(OAuthState.expires_at <= datetime.now(timezone.utc)))

    def create_event(
        self,
        *,
        guild_id: int,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        created_by: int,
    ) -> BotEvent:
        event = BotEvent(
            guild_id=guild_id,
            title=title,
            description=description,
            start_at=start_at,
            end_at=end_at,
            created_by=created_by,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def add_event_member(
        self,
        *,
        event_id: int,
        discord_user_id: int,
        google_event_id: str | None,
        status: str,
        error_message: str | None = None,
    ) -> EventMember:
        member = EventMember(
            event_id=event_id,
            discord_user_id=discord_user_id,
            google_event_id=google_event_id,
            status=status,
            error_message=error_message,
        )
        self.session.add(member)
        self.session.flush()
        return member

    def get_event(self, event_id: int, guild_id: int) -> BotEvent | None:
        return self.session.scalar(
            select(BotEvent).where(BotEvent.id == event_id, BotEvent.guild_id == guild_id)
        )

