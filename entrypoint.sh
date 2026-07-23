#!/bin/sh
set -e

DATA_DIR="/data"
APP_DIR="/app"

# ボリュームに初期データをコピー（初回起動時のみ）
for f in users.json broadcasts.json corrections.json rules.json clicks.json; do
  if [ ! -f "$DATA_DIR/$f" ]; then
    if [ -f "$APP_DIR/$f" ]; then
      cp "$APP_DIR/$f" "$DATA_DIR/$f"
    else
      echo "{}" > "$DATA_DIR/$f"
    fi
  fi
done

# staticファイル（管理者がアップロード可能なもの）
mkdir -p "$DATA_DIR/static"
for f in privacy.html terms.html; do
  if [ ! -f "$DATA_DIR/static/$f" ]; then
    cp "$APP_DIR/static/$f" "$DATA_DIR/static/$f" 2>/dev/null || true
  fi
done

# 書き込みが発生するファイルをボリュームへシンボリックリンク
ln -sf "$DATA_DIR/users.json"           "$APP_DIR/users.json"
ln -sf "$DATA_DIR/broadcasts.json"      "$APP_DIR/broadcasts.json"
ln -sf "$DATA_DIR/corrections.json"     "$APP_DIR/corrections.json"
ln -sf "$DATA_DIR/clicks.json"          "$APP_DIR/clicks.json"
ln -sf "$DATA_DIR/static/privacy.html"  "$APP_DIR/static/privacy.html"
ln -sf "$DATA_DIR/static/terms.html"    "$APP_DIR/static/terms.html"

exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}"
