from __future__ import annotations

from datetime import timezone
from html import escape

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.container import Container
from app.database.repositories import Repository
from app.google.oauth import OAuthStateError


def create_app(container: Container) -> FastAPI:
    app = FastAPI(title="Discord Google Calendar Bot", docs_url=None, redoc_url=None)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/oauth/google/callback", response_class=HTMLResponse)
    def google_callback(request: Request, state: str | None = None, error: str | None = None):
        if error:
            return _page("連携をキャンセルしました", "Discordに戻って、必要ならもう一度お試しください。", False)
        if not state or "code" not in request.query_params:
            raise HTTPException(status_code=400, detail="code or state is missing")

        session = container.session_factory()
        try:
            identity = container.oauth.validate_and_consume_state(state, Repository(session))
            credentials = container.oauth.exchange_code(request.query_params["code"], state)
            google_user_id, google_email = container.calendar.get_identity(credentials)
            repository = Repository(session)
            existing = repository.get_account(identity.discord_user_id)
            encrypted_refresh_token = (
                container.crypto.encrypt(credentials.refresh_token)
                if credentials.refresh_token
                else (existing.encrypted_refresh_token if existing else None)
            )
            repository.upsert_account(
                discord_user_id=identity.discord_user_id,
                google_user_id=google_user_id,
                google_email=google_email,
                encrypted_access_token=container.crypto.encrypt(credentials.token),
                encrypted_refresh_token=encrypted_refresh_token,
                token_expiry=(credentials.expiry.replace(tzinfo=timezone.utc) if credentials.expiry and credentials.expiry.tzinfo is None else credentials.expiry),
                calendar_id="primary",
            )
            session.commit()
        except OAuthStateError as exc:
            session.rollback()
            return _page("連携リンクが無効です", str(exc), False, status_code=400)
        except Exception:
            session.rollback()
            return _page("Google Calendar連携に失敗しました", "Discordからもう一度連携してください。", False, status_code=500)
        finally:
            session.close()

        account_label = escape(google_email or "Googleアカウント")
        return _page("連携が完了しました", f"{account_label} をDiscordユーザーに紐付けました。この画面は閉じて構いません。", True)

    return app


def _page(title: str, message: str, success: bool, status_code: int = 200) -> HTMLResponse:
    color = "#3ba55d" if success else "#ed4245"
    html = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title><style>
body{{font-family:system-ui,sans-serif;background:#1e1f22;color:#f2f3f5;display:grid;place-items:center;min-height:100vh;margin:0}}
main{{max-width:560px;margin:24px;padding:32px;background:#2b2d31;border-radius:12px;border-top:5px solid {color}}}
h1{{font-size:1.5rem}}p{{line-height:1.7;color:#dbdee1}}
</style></head><body><main><h1>{escape(title)}</h1><p>{message}</p></main></body></html>"""
    return HTMLResponse(html, status_code=status_code)
