# 当別町ごみ収集日Bot — 開発者ドキュメント

## 目次

1. [プロジェクト概要](#1-プロジェクト概要)
2. [アーキテクチャ](#2-アーキテクチャ)
3. [ファイル構成](#3-ファイル構成)
4. [ローカル開発環境のセットアップ](#4-ローカル開発環境のセットアップ)
5. [収集ルールの管理](#5-収集ルールの管理)
6. [例外日の管理](#6-例外日の管理)
7. [管理画面の使い方](#7-管理画面の使い方)
8. [認証・セキュリティ](#8-認証セキュリティ)
9. [本番サーバー（AWS EC2）へのデプロイ](#9-本番サーバーaws-ec2へのデプロイ)
10. [コード更新手順](#10-コード更新手順)
11. [運用コマンド](#11-運用コマンド)
12. [トラブルシューティング](#12-トラブルシューティング)

---

## 1. プロジェクト概要

北海道当別町のごみ収集スケジュールを管理・通知する LINE Bot。

- **LINEユーザー**向け：「今日」「明日」「１週間」「今月」でごみ収集日を確認
- **管理者**向け：Web管理画面でカレンダーの例外日を設定

### 技術スタック

| レイヤー | 技術 |
|----------|------|
| Webフレームワーク | FastAPI + Uvicorn |
| LINE連携 | line-bot-sdk v3 |
| スケジュール生成 | ルールベース（rules.json）＋動的追加生成 |
| 例外設定 | corrections.json |
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
    └── user_store.py             ← ユーザーの地区設定（users.json）

管理者
    │  ブラウザ（要ログイン）
    ▼
https://<ドメイン>/admin
    │  POST /admin/login   ← パスワード認証 → BearerトークンをlocalStorageに保存
    │
    ├── GET  /api/schedule    ← 月間スケジュール取得（Bearer認証必須）
    └── POST /api/correction  ← 例外日の保存（Bearer認証必須）
```

---

## 3. ファイル構成

```
tobetsu-garbage-bot/
├── app.py               # FastAPIメインアプリ（LINEボット＋管理API＋認証）
├── calendar_parser.py   # スケジュール生成・管理クラス
├── user_store.py        # ユーザー地区設定の読み書き
├── rules.json           # 各地区の収集曜日ルール（要編集）
├── corrections.json     # 例外日の手動修正（管理画面から自動更新）
├── users.json           # ユーザー別地区設定（自動生成）
├── requirements.txt     # Pythonパッケージ一覧
├── Procfile             # Heroku互換起動設定
├── .env                 # 環境変数（Gitに含めない）
├── static/
│   └── admin.html       # 管理Webページ
└── cache/               # PDF解析キャッシュ（Gitに含めない）
```

### Gitに含めないファイル（.gitignore）

| ファイル | 理由 |
|----------|------|
| `.env` | LINEシークレット・管理パスワードが含まれる |
| `cache/` | 自動生成される大きなキャッシュ |
| `venv/` | 環境依存のパッケージ群 |

> ⚠️ `corrections.json` と `users.json` はGit管理されています。
> EC2サーバーでの変更を手元に取り込む場合はサーバーからscpで取得してください。

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
# ローカルから転送
scp -i ~/Downloads/tobetsu-key.pem \
  /Users/watsk/tobetsu-garbage-bot/rules.json \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/

# EC2でサービス再起動（メモリ上のスケジュールを再生成）
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
- 未生成の年度は **初回表示時に自動生成**される
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

---

## 8. 認証・セキュリティ

### 環境変数

| 変数 | 用途 | 必須 |
|------|------|------|
| `ADMIN_PASSWORD` | 管理画面ログインパスワード | ✅ |
| `ADMIN_SECRET_KEY` | Bearerトークン署名用シークレット | ✅ |

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
# ADMIN_SECRET_KEY を変更して再起動するだけで全セッション強制ログアウト
# EC2側の .env を編集
vi /home/ec2-user/tobetsu-garbage-bot/.env

sudo systemctl restart tobetsu-bot
```

### ADMIN_SECRET_KEY の生成

```bash
openssl rand -hex 32
```

---

## 9. 本番サーバー（AWS EC2）へのデプロイ

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

### .env の必須設定

```env
LINE_CHANNEL_ACCESS_TOKEN=xxxx
LINE_CHANNEL_SECRET=xxxx
ADMIN_PASSWORD=強いパスワード
ADMIN_SECRET_KEY=openssl rand -hex 32 で生成した値
```

---

## 10. コード更新手順

### ファイル転送 → 再起動

```bash
# 複数ファイルをまとめて転送
scp -i ~/Downloads/tobetsu-key.pem \
  /Users/watsk/tobetsu-garbage-bot/app.py \
  /Users/watsk/tobetsu-garbage-bot/calendar_parser.py \
  /Users/watsk/tobetsu-garbage-bot/static/admin.html \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/

# admin.html は static/ サブディレクトリに転送
scp -i ~/Downloads/tobetsu-key.pem \
  /Users/watsk/tobetsu-garbage-bot/static/admin.html \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/static/

# サービス再起動
sudo systemctl restart tobetsu-bot
sudo systemctl status tobetsu-bot
```

### corrections.json をEC2からローカルへバックアップ

```bash
scp -i ~/Downloads/tobetsu-key.pem \
  ec2-user@18.180.39.33:/home/ec2-user/tobetsu-garbage-bot/corrections.json \
  /Users/watsk/tobetsu-garbage-bot/corrections.json
```

---

## 11. 運用コマンド

### サービス管理

```bash
sudo systemctl status tobetsu-bot   # 状態確認
sudo systemctl restart tobetsu-bot  # 再起動
sudo systemctl stop tobetsu-bot     # 停止
sudo systemctl start tobetsu-bot    # 起動
```

### ログ確認

```bash
sudo journalctl -u tobetsu-bot -f          # リアルタイム
sudo journalctl -u tobetsu-bot -n 100      # 直近100行
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
sudo certbot renew --dry-run      # 自動更新テスト
sudo certbot renew --force-renewal  # 強制更新
```

---

## 12. トラブルシューティング

### LINEボットが応答しない

```bash
sudo systemctl status tobetsu-bot
sudo journalctl -u tobetsu-bot -n 50
sudo systemctl status nginx
# LINE Developers Console で Webhook URL を確認・検証
```

### 管理画面にログインできない

- `.env` に `ADMIN_PASSWORD` と `ADMIN_SECRET_KEY` が設定されているか確認
- ブラウザの localStorage をクリアして再試行（DevTools → Application → Local Storage）

```bash
# EC2側で .env の内容確認
grep ADMIN /home/ec2-user/tobetsu-garbage-bot/.env
sudo systemctl restart tobetsu-bot
```

### 管理画面が 401 エラーを返す

```bash
# トークンの再発行（ADMIN_SECRET_KEY を変更して再起動）
sudo systemctl restart tobetsu-bot
# ブラウザで再ログイン
```

### スケジュールがおかしい

```bash
# スケジュール内容を確認（EC2側）
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/schedule?district=1&year=2026&month=6"

cat /home/ec2-user/tobetsu-garbage-bot/rules.json
cat /home/ec2-user/tobetsu-garbage-bot/corrections.json
sudo systemctl restart tobetsu-bot
```

### EC2再起動後

Elastic IP 固定済みのため IP は変わらない。systemd で自動起動設定済み。

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
