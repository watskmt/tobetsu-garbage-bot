import { defineAgent } from "@grok/agent-sdk";

export default defineAgent({
  description:
    "プロダクト仕様の作成: 要件、ユーザーストーリー、API/データモデル、非機能要件、受け入れ基準。実装コードは書かない。",
  // model 省略 → 親の無料枠モデルを継承
});