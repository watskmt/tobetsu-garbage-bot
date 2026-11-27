import { defineEval } from "@grok/agent-sdk/evals";

export default defineEval({
  tags: ["smoke"],
  description: "パイプラインを初期化し pipeline_get で読み返す。",
  async test(t) {
    await t.send(
      'プロジェクト "demo-app" で goal "TODO リスト" を pipeline_update で初期化し、pipeline_get で確認して要約してください。サブエージェントは呼ばないでください。',
    );
    t.succeeded();
    t.calledTool("pipeline_update");
    t.calledTool("pipeline_get");
  },
});