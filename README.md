# discord-google-calendar-bot

DiscordメンバーとGoogle Calendarを連携し、Discordのスラッシュコマンドから複数人のカレンダーへ予定を登録するBotです。

## V0.1のコマンド

| コマンド | 内容 |
|---|---|
| `/calendar-link` | Google Calendarを連携 |
| `/calendar-status` | 連携状態を確認 |
| `/calendar-unlink` | Google連携を解除 |
| `/schedule-add` | 最大5名へ予定を登録 |
| `/schedule-delete` | Bot Event IDを指定して予定を削除 |

## 1. Discord Botを作る

1. [Discord Developer Portal](https://discord.com/developers/applications) でApplicationを作成
2. **Bot** からBotを追加し、Tokenを取得
3. **OAuth2 > URL Generator** で `bot` と `applications.commands` を選択
4. Bot権限は最低限 `Send Messages` を付け、対象サーバーへ招待
5. 開発中はサーバーIDを取得し、`.env` の `DISCORD_GUILD_ID` に設定

メンバーをコマンド引数として選択する処理にPrivileged Members Intentは不要です。

## 2. Google Cloudを設定する

1. [Google Cloud Console](https://console.cloud.google.com/) でProjectを作成
2. **Google Calendar API** を有効化
3. OAuth同意画面を設定。公開前は利用メンバーをテストユーザーへ追加
4. OAuth Client IDを **Web application** として作成
5. Authorized redirect URIへ次を登録

```text
http://localhost:8000/oauth/google/callback
```

本番ではHTTPSの公開URLへ変更し、`.env` の `GOOGLE_REDIRECT_URI` と完全一致させます。

要求scopeは次の3つです。

- `openid`
- `userinfo.email`
- `calendar.events`

## 3. 環境変数

```bash
cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

生成値をそれぞれ `TOKEN_ENCRYPTION_KEY` と `OAUTH_STATE_SECRET` へ設定し、Discord・Googleの値も埋めます。`.env` はGitへコミットしません。

## 4. ローカル起動

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.main
```

Windows PowerShellでは仮想環境の有効化だけ次を使用します。

```powershell
.venv\Scripts\Activate.ps1
```

ヘルスチェック:

```text
GET http://localhost:8000/health
```

Google OAuth callbackはブラウザから到達できる必要があります。Codespacesで試す場合はポート8000を公開し、そのHTTPS URLを `GOOGLE_REDIRECT_URI` とGoogle Cloud側のAuthorized redirect URIへ設定してください。

## Docker

```bash
cp .env.example .env
docker compose up --build
```

SQLite DBはホストの `data/app.db` に保存されます。

## テスト

```bash
pip install -r requirements-dev.txt
pytest -q
```

Google APIは実トークンを使わず、日時・暗号化・OAuth state・DBを自動テストします。実サービスの疎通はテスト用DiscordサーバーとGoogle OAuthテストユーザーで確認してください。

## 操作例

1. 各メンバーが `/calendar-link` を実行しGoogle認証
2. `/calendar-status` で連携済みを確認
3. `/schedule-add` でタイトル、日付、開始・終了時刻、対象メンバーを選択
4. 応答に表示される `Bot Event ID` を控える
5. 削除するときは `/schedule-delete event_id:<ID>`

予定登録はメンバーごとに処理を続けるため、一部メンバーが未連携・APIエラーでも他メンバーの登録は継続されます。

## 運用上の注意

- 公開運用ではOAuth callbackを必ずHTTPS化してください。
- SQLiteは単一インスタンス向けです。複数インスタンス化する場合はPostgreSQLへ移行してください。
- `TOKEN_ENCRYPTION_KEY` を失うと保存済みトークンを復号できません。安全にバックアップしてください。
- キーを変更する場合は既存ユーザーの再連携が必要です。

詳細は [docs/DESIGN.md](docs/DESIGN.md) を参照してください。
