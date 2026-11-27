import { defineAgent } from "@grok/agent-sdk";

export default defineAgent({
  description:
    "実装のレビューとテスト計画。バグ、セキュリティ、仕様乖離、テスト不足を指摘し、差し戻し可否を判定する。",
});