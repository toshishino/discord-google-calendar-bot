from cryptography.fernet import Fernet

from app.config import Settings
from app.database.repositories import Repository
from app.database.session import create_db_engine, create_session_factory, init_db
from app.google.oauth import GoogleOAuthService, OAuthStateError


def make_settings() -> Settings:
    return Settings(
        discord_bot_token="discord",
        google_client_id="client",
        google_client_secret="secret",
        token_encryption_key=Fernet.generate_key().decode(),
        oauth_state_secret="x" * 48,
        database_url="sqlite:///:memory:",
    )


def test_oauth_state_is_single_use() -> None:
    settings = make_settings()
    engine = create_db_engine(settings.database_url)
    init_db(engine)
    factory = create_session_factory(engine)
    oauth = GoogleOAuthService(settings)

    with factory() as session:
        url = oauth.create_authorization_url(12345, Repository(session))
        session.commit()
    state = url.split("state=", 1)[1].split("&", 1)[0]

    with factory() as session:
        identity = oauth.validate_and_consume_state(state, Repository(session))
        session.commit()
        assert identity.discord_user_id == 12345

    with factory() as session:
        try:
            oauth.validate_and_consume_state(state, Repository(session))
        except OAuthStateError:
            pass
        else:
            raise AssertionError("state must not be reusable")
