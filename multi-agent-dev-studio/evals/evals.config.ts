import { defineEvalConfig } from "@grok/agent-sdk/evals";
import { resolveSharedModelId } from "../bot/lib/models";

export default defineEvalConfig({
  maxConcurrency: 1,
  judge: { model: resolveSharedModelId() },
});