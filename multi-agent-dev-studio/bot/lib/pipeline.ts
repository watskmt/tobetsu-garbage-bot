export type DevPhase = "intake" | "spec" | "implement" | "review" | "done";

export type HandoffRecord = {
  from: DevPhase | "user";
  to: DevPhase;
  summary: string;
  at: string;
};

export type PipelineState = {
  projectName: string;
  goal: string;
  stackNotes: string;
  phase: DevPhase;
  spec?: string;
  implementationNotes?: string;
  reviewReport?: string;
  openIssues: string[];
  handoffs: HandoffRecord[];
  updatedAt: string;
};

export const PIPELINE_KV_KEY = "pipeline:current";

export function emptyPipeline(goal: string, projectName: string): PipelineState {
  const now = new Date().toISOString();
  return {
    projectName,
    goal,
    stackNotes: "未定 — 仕様フェーズで決定",
    phase: "intake",
    openIssues: [],
    handoffs: [],
    updatedAt: now,
  };
}

export function nextPhaseAfter(phase: DevPhase): DevPhase | null {
  const order: DevPhase[] = ["intake", "spec", "implement", "review", "done"];
  const i = order.indexOf(phase);
  if (i < 0 || i >= order.length - 1) return null;
  return order[i + 1]!;
}