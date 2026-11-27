import { defineTool } from "@grok/agent-sdk/tools";
import { prompt } from "@grok/agent-sdk";
import * as z from "zod/v4";
import {
  PIPELINE_KV_KEY,
  emptyPipeline,
  type DevPhase,
  type PipelineState,
} from "../lib/pipeline";

const phaseSchema = z.enum(["intake", "spec", "implement", "review", "done"]);

export default defineTool({
  description: prompt`
    開発パイプライン状態を作成または部分更新する。
    初回は projectName と goal を渡して初期化。以降は phase や spec 等をマージする。
  `,
  inputSchema: z.object({
    projectName: z.string().min(1).optional(),
    goal: z.string().min(1).optional(),
    stackNotes: z.string().optional(),
    phase: phaseSchema.optional(),
    spec: z.string().optional(),
    implementationNotes: z.string().optional(),
    reviewReport: z.string().optional(),
    openIssues: z.array(z.string()).optional(),
    appendOpenIssue: z.string().optional(),
    clearOpenIssues: z.boolean().optional(),
  }),
  effect: "write",
  async execute(input, ctx) {
    const existing = (await ctx.host.kv.get(PIPELINE_KV_KEY)) as PipelineState | undefined;
    let state: PipelineState;

    if (existing === undefined) {
      if (!input.projectName || !input.goal) {
        return {
          ok: false,
          error: "初回は projectName と goal が必須です。",
        };
      }
      state = emptyPipeline(input.goal, input.projectName);
    } else {
      state = { ...existing };
    }

    if (input.projectName) state.projectName = input.projectName;
    if (input.goal) state.goal = input.goal;
    if (input.stackNotes) state.stackNotes = input.stackNotes;
    if (input.phase) state.phase = input.phase as DevPhase;
    if (input.spec !== undefined) state.spec = input.spec;
    if (input.implementationNotes !== undefined) {
      state.implementationNotes = input.implementationNotes;
    }
    if (input.reviewReport !== undefined) state.reviewReport = input.reviewReport;
    if (input.clearOpenIssues) state.openIssues = [];
    if (input.openIssues) state.openIssues = input.openIssues;
    if (input.appendOpenIssue) {
      state.openIssues = [...state.openIssues, input.appendOpenIssue];
    }

    state.updatedAt = new Date().toISOString();
    await ctx.host.kv.put(PIPELINE_KV_KEY, state);

    return { ok: true, state };
  },
});