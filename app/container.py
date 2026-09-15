from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.database.session import create_db_engine, create_session_factory, init_db
from app.google.calendar import GoogleCalendarService
from app.google.oauth import GoogleOAuthService
from app.security.token_crypto import TokenCrypto


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    crypto: TokenCrypto
    oauth: GoogleOAuthService
    calendar: GoogleCalendarService

    @classmethod
    def build(cls, settings: Settings) -> "Container":
        engine = create_db_engine(settings.database_url)
        init_db(engine)
        session_factory = create_session_factory(engine)
        crypto = TokenCrypto(settings.token_encryption_key)
        return cls(
            settings=settings,
            engine=engine,
            session_factory=session_factory,
            crypto=crypto,
            oauth=GoogleOAuthService(settings),
            calendar=GoogleCalendarService(settings, crypto),
        )
