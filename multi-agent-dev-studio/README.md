# multi-agent-dev-studio

複数の AI エージェントでアプリ開発する **Agent SDK** プロジェクトです。

- **オーケストレーター** — フェーズ管理とハンドオフ
- **spec-architect** / **implementer** / **reviewer** — 役割別プロンプト（**モデルは親と同一の無料枠**を継承）

### 追加課金を避ける設定

- デフォルトモデル: `grok-3-mini`（Cursor 無料プランの枠内想定）
- サブエージェントは `model` 未指定で親を継承（有料モデルを混在させない）
- `concurrency.maxRunningTurns: 1` で同時ターンを抑止
- 環境変数 `DEV_STUDIO_MODEL` でアカウントで有効な無料モデルに変更可能（例: `gpt-4o-mini`, `gemini-2.5-flash`, `cursor-small`）

```bash
export DEV_STUDIO_MODEL=gpt-4o-mini   # お使いの無料枠に合わせて
```

## ローカル実行（R7600 など自宅 PC）

このフォルダは Cloud Agent VM 上の `/home/ubuntu/...` ではなく、**Git リポジトリ内**にあります。必ずこのディレクトリに移動してから `serve` してください（ホームで実行すると `No agent found` になります）。

```bash
git clone https://github.com/watskmt/tobetsu-garbage-bot.git
cd tobetsu-garbage-bot/multi-agent-dev-studio
npm install
npx --yes "@grok/agent-sdk@0.7.3" login    # 初回のみ（済なら不要）
npx --yes "@grok/agent-sdk@0.7.3" validate --dir .
npm run check
npx --yes "@grok/agent-sdk@0.7.3" serve --dir . --mode single --dev
```

すでにリポジトリを clone 済みなら:

```bash
cd ~/path/to/tobetsu-garbage-bot/multi-agent-dev-studio
npm install
npx --yes "@grok/agent-sdk@0.7.3" serve --dir . --mode single --dev
```

ブラウザで Playground（通常 `http://127.0.0.1:3000/playground`）を開き、例:

> 在庫管理の最小 Web アプリを作りたい。仕様からレビューまで回してください。

Cursor へサインイン（`npx --yes "@grok/agent-sdk@0.7.3" login` または `CURSOR_API_KEY`）後:

```bash
npx --yes "@grok/agent-sdk@0.7.3" run --dir . --message "在庫管理ミニアプリを仕様からレビューまで"
npx --yes "@grok/agent-sdk@0.7.3" eval --dir .
```

## モデルの変更

`DEV_STUDIO_MODEL` または `bot/lib/models.ts` の `DEFAULT_FREE_MODEL` を、Cursor の設定 → Models で有効にした**無料枠**のスラッグに合わせてください。有料モデル（Claude / Composer 等）を設定しないでください。

## レイアウト

| パス | 役割 |
| --- | --- |
| `bot/instructions.md` | オーケストレーター指示 |
| `bot/subagents/*` | 仕様 / 実装 / レビュー |
| `bot/tools/pipeline_*.ts` | 共有パイプライン状態（KV） |
| `bot/skills/dev-pipeline` | 標準ループ手順 |