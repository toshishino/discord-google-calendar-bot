from datetime import datetime, timezone

from sqlalchemy import select

from app.database.models import EventMember
from app.database.repositories import Repository
from app.database.session import create_db_engine, create_session_factory, init_db


def test_create_event_and_member() -> None:
    engine = create_db_engine("sqlite:///:memory:")
    init_db(engine)
    factory = create_session_factory(engine)

    with factory() as session:
        repository = Repository(session)
        event = repository.create_event(
            guild_id=1,
            title="Meeting",
            description=None,
            start_at=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
            end_at=datetime(2026, 9, 15, 13, tzinfo=timezone.utc),
            created_by=2,
        )
        repository.add_event_member(
            event_id=event.id,
            discord_user_id=3,
            google_event_id="google-event",
            status="created",
        )
        session.commit()

        stored = session.scalar(select(EventMember))
        assert stored is not None
        assert stored.event_id == event.id
        assert stored.google_event_id == "google-event"
