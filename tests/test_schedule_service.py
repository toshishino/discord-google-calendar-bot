from datetime import datetime
from zoneinfo import ZoneInfo

from cryptography.fernet import Fernet

from app.database.repositories import Repository
from app.database.session import create_db_engine, create_session_factory, init_db
from app.security.token_crypto import TokenCrypto
from app.services.schedule_service import ScheduleService


class FakeCalendar:
    def create_event(self, account, **_kwargs) -> str:
        return f"event-{account.discord_user_id}"


def test_create_continues_when_a_member_is_not_linked() -> None:
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    factory = create_session_factory(engine)
    crypto = TokenCrypto(Fernet.generate_key().decode())

    with factory() as session:
        Repository(session).upsert_account(
            discord_user_id=10,
            google_user_id="g-10",
            google_email="member@example.com",
            encrypted_access_token=crypto.encrypt("token"),
            encrypted_refresh_token=crypto.encrypt("refresh"),
            token_expiry=None,
            calendar_id="primary",
        )
        session.commit()

        service = ScheduleService(session, FakeCalendar(), "Asia/Tokyo")  # type: ignore[arg-type]
        result = service.create(
            guild_id=1,
            created_by=99,
            title="Meeting",
            description=None,
            start_at=datetime(2026, 9, 15, 20, tzinfo=ZoneInfo("Asia/Tokyo")),
            end_at=datetime(2026, 9, 15, 21, tzinfo=ZoneInfo("Asia/Tokyo")),
            discord_user_ids=[10, 20],
        )

        assert [item.success for item in result.members] == [True, False]
        assert result.members[1].message == "Google Calendar未連携"
