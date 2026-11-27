import { defineAgent } from "@grok/agent-sdk";
import { resolveSharedModelId } from "./lib/models";

export default defineAgent({
  model: resolveSharedModelId(),
  name: "multi-agent-dev-studio",
  description:
    "複数の専門エージェントで仕様・実装・レビューを回すアプリ開発オーケストレーター（無料枠モデル共有）",
  local: {
    sandbox: true,
  },
  concurrency: { maxRunningTurns: 1 },
});