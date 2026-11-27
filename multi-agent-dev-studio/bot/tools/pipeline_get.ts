import { defineTool } from "@grok/agent-sdk/tools";
import { prompt } from "@grok/agent-sdk";
import * as z from "zod/v4";
import { PIPELINE_KV_KEY, type PipelineState } from "../lib/pipeline";

export default defineTool({
  description: prompt`
    現在の開発パイプライン状態を読み取る。
    サブエージェント委譲前に必ず呼び、最新の spec / フェーズ / 課題を確認する。
  `,
  inputSchema: z.object({}),
  effect: "read",
  async execute(_input, ctx) {
    const raw = await ctx.host.kv.get(PIPELINE_KV_KEY);
    if (raw === undefined) {
      return {
        initialized: false,
        message: "パイプライン未初期化。pipeline_update で goal と projectName を設定してください。",
      };
    }
    const state = raw as PipelineState;
    return { initialized: true, state };
  },
});