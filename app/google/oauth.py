from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from google_auth_oauthlib.flow import Flow
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings
from app.database.repositories import Repository

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/calendar.events",
]
STATE_MAX_AGE_SECONDS = 600


class OAuthStateError(ValueError):
    pass


@dataclass(frozen=True)
class OAuthIdentity:
    discord_user_id: int
    nonce: str


class GoogleOAuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.serializer = URLSafeTimedSerializer(
            settings.oauth_state_secret, salt="google-oauth-state"
        )

    @property
    def client_config(self) -> dict:
        return {
            "web": {
                "client_id": self.settings.google_client_id,
                "client_secret": self.settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.settings.google_redirect_uri],
            }
        }

    def create_authorization_url(
        self, discord_user_id: int, repository: Repository
    ) -> str:
        nonce = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=STATE_MAX_AGE_SECONDS
        )
        repository.purge_expired_oauth_states()
        repository.save_oauth_state(nonce, discord_user_id, expires_at)

        state = self.serializer.dumps(
            {"discord_user_id": str(discord_user_id), "nonce": nonce}
        )
        flow = Flow.from_client_config(
            self.client_config,
            scopes=GOOGLE_SCOPES,
            redirect_uri=self.settings.google_redirect_uri,
        )
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return url

    def validate_and_consume_state(
        self, state: str, repository: Repository
    ) -> OAuthIdentity:
        try:
            payload = self.serializer.loads(state, max_age=STATE_MAX_AGE_SECONDS)
            discord_user_id = int(payload["discord_user_id"])
            nonce = str(payload["nonce"])
        except (BadSignature, SignatureExpired, KeyError, TypeError, ValueError) as exc:
            raise OAuthStateError("OAuth state is invalid or expired") from exc

        stored = repository.consume_oauth_state(nonce)
        if stored is None or stored.discord_user_id != discord_user_id:
            raise OAuthStateError("OAuth state was already used or expired")
        return OAuthIdentity(discord_user_id=discord_user_id, nonce=nonce)

    def exchange_code(self, code: str, state: str):
        flow = Flow.from_client_config(
            self.client_config,
            scopes=GOOGLE_SCOPES,
            state=state,
            redirect_uri=self.settings.google_redirect_uri,
        )
        flow.fetch_token(code=code)
        return flow.credentials
