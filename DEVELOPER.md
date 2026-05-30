# 当別町ごみ収集日Bot — 開発者ドキュメント

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [アーキテクチャ](#2-アーキテクチャ)
3. [ファイル構成](#3-ファイル構成)
4. [ローカル開発環境のセットアップ](#4-ローカル開発環境のセットアップ)
5. [収集ルールの管理](#5-収集ルールの管理)
6. [例外日の管理](#6-例外日の管理)
7. [管理画面の使い方](#7-管理画面の使い方)
8. [Push通知機能](#8-push通知機能)
9. [広告ブロードキャスト機能](#9-広告ブロードキャスト機能)
10. [運営者情報・法的文書](#10-運営者情報法的文書)
11. [認証・セキュリティ](#11-認証セキュリティ)
12. [本番サーバー（AWS EC2）へのデプロイ](#12-本番サーバーaws-ec2へのデプロイ)
13. [コード更新手順](#13-コード更新手順)
14. [運用コマンド](#14-運用コマンド)
15. [トラブルシューティング](#15-トラブルシューティング)

---

## 1. プロジェクト概要

北海道当別町のごみ収集スケジュールを管理・通知する LINE Bot。

- **LINEユーザー**向け：「今日」「明日」「１週間」「今月」でごみ収集日を確認、毎日の収集情報をPush通知で受信
- **管理者**向け：Web管理画面でカレンダーの例外日設定・広告ブロードキャスト管理

### 技術スタック

| レイヤー | 技術 |
|----------|------|
| Webフレームワーク | FastAPI + Uvicorn |
| LINE連携 | line-bot-sdk v3 |
| スケジュール生成 | ルールベース（rules.json）＋動的追加生成 |
| 例外設定 | corrections.json |
| Push通知・広告スケジュール | APScheduler（BackgroundScheduler） |
| 管理UI | バニラHTML/CSS/JS（static/admin.html） |
| 本番環境 | AWS EC2 t2.micro + Nginx + Let's Encrypt |
| ドメイン | DuckDNS（無料） |

---

## 2. アーキテクチャ

```
LINE ユーザー
    │  メッセージ送信
    ▼
LINE Platform
    │  POST /webhook
    ▼
FastAPI (app.py)
    │
    ├── GarbageCalendar (calendar_parser.py)
    │       │
    │       ├── rules.json        ← 基本ルール（毎週の収集曜日）
    │       └── corrections.json  ← 例外日の上書き
    │
    ├── user_store.py             ← ユーザーの地区設定・通知時刻（users.json）
    │
    ├── broadcast_store.py        ← 広告ブロードキャストスケジュール（broadcasts.json）
    │
    └── APScheduler（BackgroundScheduler）
            │
            ├── 毎分: 通知時刻に一致するユーザーへ当日収集情報をPush送信
            └── 週1/隔週/月1: ブロードキャスト広告をPush送信

管理者
    │  ブラウザ（要ログイン）
    ▼
https://<ドメイン>/admin
    │  POST /admin/login          ← パスワード認証 → BearerトークンをlocalStorageに保存
    │
    ├── GET  /api/schedule        ← 月間スケジュール取得（Bearer認証必須）
    ├── POST /api/correction      ← 例外日の保存（Bearer認証必須）
    ├── GET  /api/broadcasts      ← 広告スケジュール一覧（Bearer認証必須）
    ├── POST /api/broadcasts      ← 広告スケジュール作成（Bearer認証必須）
    ├── POST /api/broadcasts/{id}/send ← 今すぐ送信（Bearer認証必須）
    ├── PATCH /api/broadcasts/{id}    ← 有効/無効切替（Bearer認証必須）
    └── DELETE /api/broadcasts/{id}  ← スケジュール削除（Bearer認証必須）

一般ユーザー（認証不要）
    ├── GET /privacy              ← プライバシーポリシーページ
    ├── GET /terms                ← 利用規約ページ
    └── GET /api/bot-info         ← 運営者情報JSON
```

---

## 3. ファイル構成

```
tobetsu-garbage-bot/
├── app.py               # FastAPIメインアプリ（LINEボット＋管理API＋スケジューラ）
├── calendar_parser.py   # スケジュール生成・管理クラス
├── user_store.py        # ユーザー地区設定・通知時刻の読み書き
├── broadcast_store.py   # 広告ブロードキャストスケジュールの読み書き
├── rules.json           # 各地区の収集曜日ルール（要編集）
├── corrections.json     # 例外日の手動修正（管理画面から自動更新）
├── users.json           # ユーザー別地区設定・通知時刻（自動生成）
├── broadcasts.json      # 広告ブロードキャストスケジュール（管理画面から自動更新）
├── requirements.txt     # Pythonパッケージ一覧
├── Procfile             # Heroku互換起動設定
├── .env                 # 環境変数（Gitに含めない）
├── static/
│   ├── admin.html       # 管理Webページ（カレンダー編集・広告管理）
│   ├── privacy.html     # プライバシーポリシーページ
│   └── terms.html       # 利用規約ページ
└── cache/               # PDF解析キャッシュ（Gitに含めない）
```

### Gitに含めないファイル（.gitignore）

| ファイル | 理由 |
|----------|------|
| `.env` | LINEシークレット・管理パスワードが含まれる |
| `cache/` | 自動生成される大きなキャッシュ |
| `venv/` | 環境依存のパッケージ群 |

> ⚠️ `corrections.json`・`users.json`・`broadcasts.json` はGit管理されていますが、EC2サーバーでの変更が保護されます（デプロイスクリプトで上書きしない）。

---

## 4. ローカル開発環境のセットアップ

```bash
cd ~/tobetsu-garbage-bot

# 仮想環境作成
python3 -m venv venv
source venv/bin/activate

# パッケージインストール
pip install -r requirements.txt

# .envファイル作成
cat > .env << 'EOF'
LINE_CHANNEL_ACCESS_TOKEN=xxxx
LINE_CHANNEL_SECRET=xxxx
ADMIN_PASSWORD=任意のパスワード
ADMIN_SECRET_KEY=$(openssl rand -hex 32)
BOT_OPERATOR_NAME=当別町ごみ収集日Bot運営者
BOT_OPERATOR_EMAIL=your@example.com
BOT_BASE_URL=https://tobetsu-bot.duckdns.org
EOF

# 起動
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### ローカルでLINEボットをテストする（HTTPS必須）

```bash
# cloudflaredインストール（初回のみ）
brew install cloudflared

# 別ターミナルで起動
cloudflared tunnel --url http://localhost:8000
```

表示された `https://xxxx.trycloudflare.com` を LINE Developers Console の Webhook URL に設定する。

---

## 5. 収集ルールの管理

### rules.json の構造

```json
{
  "1": {
    "weekday_rules": [
      {"weekday": [0, 3], "type": "燃やせるごみ"},
      {"weekday": [1], "nth": [1], "type": "燃えないごみ"},
      {"weekday": [2], "nth": [1, 3], "type": "資源物"},
      {"weekday": [4], "type": "燃やせないごみ"}
    ]
  }
}
```

| キー | 説明 |
|------|------|
| `weekday` | 収集曜日（0=月, 1=火, 2=水, 3=木, 4=金, 5=土, 6=日） |
| `nth` | 第N週のみ収集（省略すると毎週） |
| `type` | ごみ種別（下記5種類から選ぶ） |

### ごみ種別の正式表記

| 表記 | 管理画面表示 |
|------|------------|
| `燃やせるごみ` | 赤い○ |
| `燃やせないごみ` | ピンク背景 |
| `燃えないごみ` | 水色背景 |
| `資源物` | 青い□枠 |
| `スプレー缶` | 「スプレー缶」ラベル |

> ⚠️ 表記を誤るとLINEボット・管理画面で正しく表示されません。上記の表記を正確に使用してください。

### 現在の各地区ルール

| 地区 | 燃やせるごみ | 燃えないごみ | 資源物 | 燃やせないごみ |
|------|------------|------------|--------|--------------|
| 1地区 | 月・木（毎週） | 第1火 | 第1・3水 | 金（毎週） |
| 2地区 | 火・金（毎週） | 第2火 | 第2・4水 | 木（毎週） |
| 3地区 | 火・金（毎週） | 第3火 | 第1・3水 | 木（毎週） |
| 4地区 | 月・木（毎週） | 第4火 | 第2・4水 | 金（毎週） |

### ルール変更後の反映

```bash
scp -i ~/Downloads/tobetsu-key.pem \
  /Users/watsk/tobetsu-garbage-bot/rules.json \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/

sudo systemctl restart tobetsu-bot
```

---

## 6. 例外日の管理

### corrections.json の構造

```json
{
  "_comment": "手動修正",
  "1": {
    "2026-05-05": [],              // 空リスト = 収集なし
    "2026-05-12": ["燃えないごみ"]  // 上書き設定
  }
}
```

| 値 | 動作 |
|----|------|
| `["燃やせるごみ"]` | その日のルールを上書き |
| `[]` | 収集なし（祝日振替など） |
| キーを削除（ルールに戻す） | 管理画面の「ルールに戻す」ボタンで実行 |

---

## 7. 管理画面の使い方

アクセス先：`https://<ドメイン>/admin`

### ログイン

パスワードを入力してログイン。トークンはブラウザの `localStorage` に保存され、次回アクセス時は自動ログイン。

### 年間ビュー

- **‹ 年度 ›** ボタンで前年度・翌年度に移動
- 未生成の年度は初回表示時に自動生成される
- 月をクリックすると月別編集画面に遷移

### 月別ビュー

| 表示 | 意味 |
|------|------|
| 赤い○ | 燃やせるごみ |
| 青い□枠 | 資源物 |
| ピンク背景 | 燃やせないごみ |
| 水色背景 | 燃えないごみ |
| 緑の二重丸 | 今日 |
| 黄色左ボーダー＋⚠ | 例外設定あり |

日付の文字色：日曜・祝日=赤、土曜=青、平日=黒（固定）

### 例外日の設定

1. 対象日をクリック → モーダルが開く
2. 収集種別のチェックボックスで設定
3. ボタンの選択：
   - **保存**：チェックした内容で上書き
   - **収集なし**：その日の収集を全てキャンセル
   - **ルールに戻す**：例外設定を削除

### 広告タブ（📢 広告）

管理画面の「📢 広告」タブで広告ブロードキャストを管理します（詳細は[セクション9](#9-広告ブロードキャスト機能)）。

---

## 8. Push通知機能

### 概要

ユーザーが設定した時刻（正時のみ）に、当日のごみ収集情報をLINE Push通知で送信する機能です。収集なしの日は通知を送信しません。

### 仕組み

- APScheduler の BackgroundScheduler が**毎分**起動
- JST 現在時刻（`HH:00` 形式）と一致する通知時刻を設定したユーザーを `users.json` から抽出
- 各ユーザーの地区に対して `get_today()` を呼び出し、収集情報をPush送信
- `"収集なし"` が含まれる場合は送信をスキップ

### タイムゾーン

`calendar_parser.py` の日付取得は `datetime.now(JST).date()` を使用しています。EC2 のシステムタイムゾーン（UTC）に依存しないため、早朝の通知でも正しく当日の収集情報を返します。

### users.json のデータ構造

```json
{
  "Uxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx": {
    "district": 3,
    "notify_time": "07:00"
  }
}
```

| フィールド | 説明 |
|-----------|------|
| `district` | 収集地区（1〜4） |
| `notify_time` | 通知時刻（`"HH:00"` 形式、未設定なら通知なし） |

### ユーザー向けコマンド

| 送信内容 | 動作 |
|---------|------|
| `通知設定` | 時刻選択クイックリプライを表示 |
| `通知7時` / `7時通知` / `毎朝8時` | 毎日その時刻に通知を設定（正時のみ） |
| `通知オフ` / `通知OFF` / `通知なし` | 通知を停止 |
| `通知確認` | 現在の設定を表示 |

---

## 9. 広告ブロードキャスト機能

### 概要

管理画面からテキストまたは画像バナーを、設定したスケジュールで全ユーザーにPush送信する機能です。

### スケジュール種別

| 種別 | APScheduler | 設定項目 |
|------|-------------|---------|
| 週1 | CronTrigger | 曜日・時刻 |
| 隔週 | IntervalTrigger（2週間間隔） | 曜日・時刻（初回実行日を自動計算） |
| 月1 | CronTrigger | 日付（1〜28日）・時刻 |

> 隔週スケジュールは作成時に次回実行日時（`start_date`）を計算して `broadcasts.json` に保存します。アプリ再起動時もこの `start_date` をもとにリズムが引き継がれます。

### broadcasts.json のデータ構造

```json
[
  {
    "id": "a1b2c3d4",
    "name": "月初キャンペーン",
    "type": "text",
    "text": "今月もよろしくお願いします。",
    "schedule": "monthly",
    "day_of_month": 1,
    "hour": 9,
    "enabled": true,
    "created_at": "2026-05-30T10:00:00+09:00"
  },
  {
    "id": "e5f6g7h8",
    "name": "バナー広告",
    "type": "image",
    "image_url": "https://example.com/banner.jpg",
    "preview_url": "https://example.com/banner_preview.jpg",
    "schedule": "weekly",
    "day_of_week": 0,
    "hour": 8,
    "enabled": true,
    "created_at": "2026-05-30T10:00:00+09:00"
  }
]
```

### 画像バナーの注意点

- `image_url` と `preview_url` は **HTTPS 公開 URL** が必須（LINE API の要件）
- `preview_url` を省略した場合は `image_url` と同じURLが使用される

### 管理画面での操作

1. 「📢 広告」タブを開く
2. 「＋ 新規広告スケジュール」を展開してフォームを入力
3. 登録後、一覧に表示される
4. 各スケジュールの操作：
   - **有効/無効トグル**：スケジューラへの登録・解除
   - **今すぐ送信**：即時に全ユーザーへPush（確認ダイアログあり）
   - **削除**：スケジュールを削除

### API エンドポイント（すべてBearer認証必須）

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/broadcasts` | スケジュール一覧 |
| POST | `/api/broadcasts` | スケジュール作成 |
| PATCH | `/api/broadcasts/{id}` | 有効/無効切替・内容更新 |
| DELETE | `/api/broadcasts/{id}` | スケジュール削除 |
| POST | `/api/broadcasts/{id}/send` | 今すぐ全ユーザーへ送信 |

---

## 10. 運営者情報・法的文書

### 概要

LINE Bot を公式に運用するために必要な、プライバシーポリシーと利用規約のページを提供します。

### ページ一覧

| URL | 内容 |
|-----|------|
| `/privacy` | プライバシーポリシー |
| `/terms` | 利用規約 |
| `/api/bot-info` | 運営者情報 JSON（認証不要） |

`/privacy` と `/terms` は `/api/bot-info` から運営者名・連絡先を動的に取得して表示します。

### 環境変数

| 変数 | 用途 | 例 |
|------|------|-----|
| `BOT_OPERATOR_NAME` | 運営者名（ページ・Bot応答に表示） | `当別町ごみ収集日Bot運営者` |
| `BOT_OPERATOR_EMAIL` | 問い合わせ先メール | `your@example.com` |
| `BOT_BASE_URL` | サービスのベースURL | `https://tobetsu-bot.duckdns.org` |

### Botキーワード

| 送信内容 | 応答 |
|---------|------|
| `このBotについて` / `ヘルプ` / `運営情報` | 運営者情報・リンク一覧 |
| `プライバシーポリシー` | `/privacy` のURL |
| `利用規約` | `/terms` のURL |

### LINE Developers コンソールへの設定

LINE の審査・運用要件として、チャネル設定に以下のURLを登録してください。

- **プライバシーポリシーURL**：`https://tobetsu-bot.duckdns.org/privacy`
- **利用規約URL**：`https://tobetsu-bot.duckdns.org/terms`

---

## 11. 認証・セキュリティ

### 環境変数

| 変数 | 用途 | 必須 |
|------|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API トークン | ✅ |
| `LINE_CHANNEL_SECRET` | Webhook 署名検証キー | ✅ |
| `ADMIN_PASSWORD` | 管理画面ログインパスワード | ✅ |
| `ADMIN_SECRET_KEY` | Bearerトークン署名用シークレット | ✅ |
| `BOT_OPERATOR_NAME` | 運営者名 | 推奨 |
| `BOT_OPERATOR_EMAIL` | 問い合わせ先メール | 推奨 |
| `BOT_BASE_URL` | サービスのベースURL | 推奨 |

### トークンの仕組み

```
ログイン: ADMIN_PASSWORD を検証
    ↓
トークン発行: HMAC-SHA256(ADMIN_SECRET_KEY, "admin-session")
    ↓
ブラウザの localStorage に保存
    ↓
以降の API リクエストに Authorization: Bearer <token> を付与
```

### 役割の違い

| 変数 | 変更した場合の影響 |
|------|-----------------|
| `ADMIN_PASSWORD` | 次回ログインから新パスワードが必要になる |
| `ADMIN_SECRET_KEY` | **既存の全セッションが即時無効化**される |

### 不正アクセス時の対応

```bash
vi /home/ec2-user/tobetsu-garbage-bot/.env
# ADMIN_SECRET_KEY を変更して保存

sudo systemctl restart tobetsu-bot
```

### ADMIN_SECRET_KEY の生成

```bash
openssl rand -hex 32
```

---

## 12. 本番サーバー（AWS EC2）へのデプロイ

### サーバー情報

| 項目 | 値 |
|------|-----|
| サーバー | AWS EC2 t2.micro (Amazon Linux 2023) |
| Elastic IP | 18.180.39.33 |
| ドメイン | tobetsu-bot.duckdns.org |
| アプリパス | `/home/ec2-user/tobetsu-garbage-bot/` |
| サービス名 | `tobetsu-bot` (systemd) |

### SSH接続

```bash
ssh -i ~/Downloads/tobetsu-key.pem ec2-user@18.180.39.33
```

### .env の設定（EC2側）

```env
LINE_CHANNEL_ACCESS_TOKEN=xxxx
LINE_CHANNEL_SECRET=xxxx
ADMIN_PASSWORD=強いパスワード
ADMIN_SECRET_KEY=（openssl rand -hex 32 で生成）
BOT_OPERATOR_NAME=当別町ごみ収集日Bot運営者
BOT_OPERATOR_EMAIL=your@example.com
BOT_BASE_URL=https://tobetsu-bot.duckdns.org
```

---

## 13. コード更新手順

### GitHub Actions（自動デプロイ）

`master` ブランチへのプッシュで自動デプロイが実行されます。

デプロイ対象ファイル（サーバー側データは保護）：

```
app.py / broadcast_store.py / calendar_parser.py / user_store.py
rules.json / requirements.txt / static/admin.html
static/privacy.html / static/terms.html / DEVELOPER.md / USER.md
```

保護されるファイル（デプロイで上書きされない）：

```
corrections.json / users.json / broadcasts.json / .env
```

### 手動転送 → 再起動

```bash
scp -i ~/Downloads/tobetsu-key.pem \
  /Users/watsk/tobetsu-garbage-bot/app.py \
  /Users/watsk/tobetsu-garbage-bot/broadcast_store.py \
  /Users/watsk/tobetsu-garbage-bot/calendar_parser.py \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/

scp -i ~/Downloads/tobetsu-key.pem \
  /Users/watsk/tobetsu-garbage-bot/static/admin.html \
  /Users/watsk/tobetsu-garbage-bot/static/privacy.html \
  /Users/watsk/tobetsu-garbage-bot/static/terms.html \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/static/

sudo systemctl restart tobetsu-bot
```

### サーバー側データのバックアップ

```bash
scp -i ~/Downloads/tobetsu-key.pem \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/corrections.json \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/users.json \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/broadcasts.json \
  /Users/watsk/tobetsu-garbage-bot/
```

---

## 14. 運用コマンド

### サービス管理

```bash
sudo systemctl status tobetsu-bot   # 状態確認
sudo systemctl restart tobetsu-bot  # 再起動
sudo systemctl stop tobetsu-bot     # 停止
sudo systemctl start tobetsu-bot    # 起動
```

### ログ確認

```bash
sudo journalctl -u tobetsu-bot -f             # リアルタイム
sudo journalctl -u tobetsu-bot -n 100         # 直近100行
sudo journalctl -u tobetsu-bot --since today  # 今日分
```

### Nginx

```bash
sudo nginx -t                    # 設定テスト
sudo systemctl reload nginx      # 設定リロード
sudo systemctl restart nginx     # 再起動
```

### SSL証明書（Let's Encrypt）

```bash
sudo certbot renew --dry-run        # 自動更新テスト
sudo certbot renew --force-renewal  # 強制更新
```

---

## 15. トラブルシューティング

### LINEボットが応答しない

```bash
sudo systemctl status tobetsu-bot
sudo journalctl -u tobetsu-bot -n 50
sudo systemctl status nginx
# LINE Developers Console で Webhook URL を確認・検証
```

### Push通知が届かない

```bash
# ユーザーの通知時刻設定を確認
cat /home/ec2-user/tobetsu-garbage-bot/users.json

# スケジューラのログを確認（"push failed" エラーが出ていないか）
sudo journalctl -u tobetsu-bot --since today | grep push
```

- LINE Messaging API の Push 送信は有料プランが必要な場合があります
- 収集なしの日は意図的に通知を送信しません

### 広告が送信されない

```bash
# broadcasts.json の内容確認
cat /home/ec2-user/tobetsu-garbage-bot/broadcasts.json

# スケジューラログを確認
sudo journalctl -u tobetsu-bot --since today | grep broadcast
```

- `enabled: false` になっていないか確認
- 隔週スケジュールの `start_date` が正しく設定されているか確認

### 管理画面にログインできない

- `.env` に `ADMIN_PASSWORD` と `ADMIN_SECRET_KEY` が設定されているか確認
- ブラウザの localStorage をクリアして再試行（DevTools → Application → Local Storage）

```bash
grep ADMIN /home/ec2-user/tobetsu-garbage-bot/.env
sudo systemctl restart tobetsu-bot
```

### 管理画面が 401 エラーを返す

```bash
# ADMIN_SECRET_KEY を変更して再起動すると全セッション強制ログアウト
sudo systemctl restart tobetsu-bot
# ブラウザで再ログイン
```

### スケジュールがおかしい

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/schedule?district=1&year=2026&month=6"

cat /home/ec2-user/tobetsu-garbage-bot/rules.json
cat /home/ec2-user/tobetsu-garbage-bot/corrections.json
sudo systemctl restart tobetsu-bot
```

### EC2再起動後

Elastic IP 固定済みのためIPは変わらない。systemd で自動起動設定済み。

```bash
sudo systemctl status tobetsu-bot
sudo systemctl status nginx
```

### Python 3.9 互換性エラー（`int | None` など）

ファイル先頭に以下を追加：

```python
from __future__ import annotations
```

---

*最終更新: 2026年5月*
