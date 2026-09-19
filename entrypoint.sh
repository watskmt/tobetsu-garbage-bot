#!/bin/sh
set -e

DATA_DIR="/data"
APP_DIR="/app"

# ボリュームに初期データをコピー（初回起動時のみ）
for f in users.json broadcasts.json corrections.json rules.json clicks.json; do
  if [ ! -f "$DATA_DIR/$f" ]; then
    if [ -f "$APP_DIR/$f" ]; then
      cp "$APP_DIR/$f" "$DATA_DIR/$f"
    elif [ "$f" = "broadcasts.json" ]; then
      echo "[]" > "$DATA_DIR/$f"   # broadcasts.json は配列
    else
      echo "{}" > "$DATA_DIR/$f"
    fi
  fi
done

# 管理画面から差し替え可能な文書（privacy.html / terms.html）をボリュームへ配置する。
#   - ボリュームに無ければイメージ同梱分をコピー
#   - ボリュームの内容が「前回イメージから配置したまま」（記録したハッシュと一致）なら
#     新しいイメージの内容で更新する（リポジトリ側の改訂を反映するため）
#   - 管理画面でアップロードされたもの（ハッシュ不一致）はそのまま残す
#   - ハッシュ記録が無い（旧バージョンから初回移行）場合はバックアップを取ってから更新する
mkdir -p "$DATA_DIR/static" "$DATA_DIR/static/.seed" "$DATA_DIR/static/backup"
for f in privacy.html terms.html; do
  src="$APP_DIR/static/$f"
  dst="$DATA_DIR/static/$f"
  seed="$DATA_DIR/static/.seed/$f.sha256"
  [ -f "$src" ] || continue
  src_hash=$(sha256sum "$src" | cut -d' ' -f1)
  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    echo "$src_hash" > "$seed"
  elif [ ! -f "$seed" ]; then
    cp "$dst" "$DATA_DIR/static/backup/$f.$(date +%Y%m%d%H%M%S)"
    cp "$src" "$dst"
    echo "$src_hash" > "$seed"
    echo "[entrypoint] $f: 旧版をバックアップしてイメージ同梱版に更新しました"
  elif [ "$(cat "$seed")" = "$(sha256sum "$dst" | cut -d' ' -f1)" ] && [ "$(cat "$seed")" != "$src_hash" ]; then
    cp "$src" "$dst"
    echo "$src_hash" > "$seed"
    echo "[entrypoint] $f: イメージ同梱版に更新しました"
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
