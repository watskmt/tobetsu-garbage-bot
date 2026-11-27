---
name: dev-pipeline
description: 仕様から実装、レビューまでの標準ループとパイプラインツールの使い方。
---

# 開発パイプライン手順

1. `pipeline_get` — 状態確認。
2. 未初期化なら `pipeline_update` で `projectName` と `goal`。
3. `pipeline_handoff` で `spec` フェーズへ。
4. `task` で `spec-architect` に委譲 → 返答を `pipeline_update` の `spec` に保存。
5. `pipeline_handoff` で `implement` → `implementer` に仕様全文を渡す。
6. 実装後 `pipeline_handoff` で `review` → `reviewer` に spec と実装パスを渡す。
7. 判定が `request_changes` なら `openIssues` を更新し implement へ戻る。
8. `approve` 系なら `phase: done`。