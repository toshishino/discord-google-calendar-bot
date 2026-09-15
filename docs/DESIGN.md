# Discord × Google Calendar Bot V0.1 設計

## 目的

Discordユーザーが各自のGoogleアカウントをOAuth 2.0で連携し、`/schedule-add` で指定された最大5名それぞれのGoogle Calendarへ予定を登録する。

## V0.1機能

- `/calendar-link`: Google OAuth連携URLを本人だけに表示
- `/calendar-status`: 連携状態を確認
- `/calendar-unlink`: Googleトークンをrevokeし、保存情報を削除
- `/schedule-add`: 最大5名のカレンダーへ同一予定を登録
- `/schedule-delete`: 作成者またはサーバー管理者がBot作成予定を削除
- SQLiteによるユーザー・予定・メンバー別Google Event IDの保存
- FernetによるOAuthトークンの暗号化保存

## セキュリティ境界

- OAuth stateは署名、有効期限10分、DB nonceによる1回限りの使用
- OAuth Token、Discord Token、Client Secretは環境変数のみ
- OAuth TokenやGoogle API内部エラーをDiscord・ログへ出さない
- コマンド応答と連携URLはephemeral
- 予定削除は同一Discordサーバー内の作成者または管理者のみ

## データ

- `google_accounts`: Discord IDと暗号化Google認証情報
- `events`: Bot内の予定と作成者・Discordサーバー
- `event_members`: メンバー別のGoogle Event IDと処理状態
- `oauth_states`: 期限付き・単回使用のOAuth nonce

## 制約

- タイムゾーンはV0.1では `Asia/Tokyo` 固定（環境変数で変更可能）
- 1コマンドの対象はDiscordの引数上限に合わせ最大5名
- GoogleからDiscordへの逆同期、空き時間検索、定期予定、通知は対象外

