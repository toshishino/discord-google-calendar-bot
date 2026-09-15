from __future__ import annotations

from datetime import datetime, timezone

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import Settings
from app.database.models import GoogleAccount
from app.google.oauth import GOOGLE_SCOPES
from app.security.token_crypto import TokenCrypto


class GoogleCalendarError(RuntimeError):
    pass


class GoogleReauthRequired(GoogleCalendarError):
    pass


class GoogleCalendarService:
    def __init__(self, settings: Settings, crypto: TokenCrypto) -> None:
        self.settings = settings
        self.crypto = crypto

    def credentials_for(self, account: GoogleAccount) -> Credentials:
        expiry = account.token_expiry
        if expiry is not None and expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return Credentials(
            token=self.crypto.decrypt(account.encrypted_access_token),
            refresh_token=self.crypto.decrypt(account.encrypted_refresh_token),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_client_id,
            client_secret=self.settings.google_client_secret,
            scopes=GOOGLE_SCOPES,
            expiry=expiry,
        )

    def ensure_fresh_credentials(self, account: GoogleAccount) -> Credentials:
        credentials = self.credentials_for(account)
        if credentials.expired:
            if not credentials.refresh_token:
                raise GoogleReauthRequired("Googleとの再連携が必要です")
            try:
                credentials.refresh(Request())
            except Exception as exc:
                raise GoogleReauthRequired("Googleとの再連携が必要です") from exc
            account.encrypted_access_token = (
                self.crypto.encrypt(credentials.token) or ""
            )
            account.token_expiry = credentials.expiry
        return credentials

    def get_identity(self, credentials: Credentials) -> tuple[str | None, str | None]:
        service = build("oauth2", "v2", credentials=credentials, cache_discovery=False)
        data = service.userinfo().get().execute()
        return data.get("id"), data.get("email")

    def create_event(
        self,
        account: GoogleAccount,
        *,
        title: str,
        description: str | None,
        start_at: datetime,
        end_at: datetime,
        timezone_name: str,
    ) -> str:
        credentials = self.ensure_fresh_credentials(account)
        service = build(
            "calendar", "v3", credentials=credentials, cache_discovery=False
        )
        body = {
            "summary": title,
            "description": description or "",
            "start": {"dateTime": start_at.isoformat(), "timeZone": timezone_name},
            "end": {"dateTime": end_at.isoformat(), "timeZone": timezone_name},
            "extendedProperties": {
                "private": {"createdBy": "discord-google-calendar-bot"}
            },
        }
        try:
            created = (
                service.events()
                .insert(calendarId=account.calendar_id, body=body)
                .execute()
            )
        except HttpError as exc:
            raise GoogleCalendarError("Google Calendarへの登録に失敗しました") from exc
        event_id = created.get("id")
        if not event_id:
            raise GoogleCalendarError("Google CalendarからEvent IDが返りませんでした")
        return str(event_id)

    def delete_event(self, account: GoogleAccount, google_event_id: str) -> None:
        credentials = self.ensure_fresh_credentials(account)
        service = build(
            "calendar", "v3", credentials=credentials, cache_discovery=False
        )
        try:
            service.events().delete(
                calendarId=account.calendar_id, eventId=google_event_id
            ).execute()
        except HttpError as exc:
            if getattr(exc.resp, "status", None) in {404, 410}:
                return
            raise GoogleCalendarError(
                "Google Calendarからの削除に失敗しました"
            ) from exc

    def revoke(self, account: GoogleAccount) -> None:
        token = self.crypto.decrypt(
            account.encrypted_refresh_token
        ) or self.crypto.decrypt(account.encrypted_access_token)
        if token:
            try:
                response = requests.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": token},
                    headers={"content-type": "application/x-www-form-urlencoded"},
                    timeout=10,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                raise GoogleCalendarError("Google連携の解除通知に失敗しました") from exc
