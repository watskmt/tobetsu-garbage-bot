import { defineTool } from "@grok/agent-sdk/tools";
import { prompt } from "@grok/agent-sdk";
import * as z from "zod/v4";
import {
  PIPELINE_KV_KEY,
  type DevPhase,
  type HandoffRecord,
  type PipelineState,
} from "../lib/pipeline";

const phaseSchema = z.enum(["intake", "spec", "implement", "review", "done"]);

export default defineTool({
  description: prompt`
    フェーズ間ハンドオフを記録し、phase を更新する。
    サブエージェント完了後に呼び、次の担当へ渡す文脈を残す。
  `,
  inputSchema: z.object({
    toPhase: phaseSchema,
    summary: z.string().min(1).describe("次の担当者向けの要約（日本語）"),
    fromPhase: phaseSchema.optional(),
  }),
  effect: "idempotent",
  async execute({ toPhase, summary, fromPhase }, ctx) {
    const raw = await ctx.host.kv.get(PIPELINE_KV_KEY);
    if (raw === undefined) {
      return {
        ok: false,
        error: "パイプライン未初期化。先に pipeline_update を実行してください。",
      };
    }
    const state = raw as PipelineState;
    const from: DevPhase | "user" = fromPhase ?? state.phase;
    const record: HandoffRecord = {
      from,
      to: toPhase,
      summary,
      at: new Date().toISOString(),
    };
    state.handoffs = [...state.handoffs, record];
    state.phase = toPhase;
    state.updatedAt = record.at;
    await ctx.host.kv.put(PIPELINE_KV_KEY, state);

    return { ok: true, handoff: record, state };
  },
});