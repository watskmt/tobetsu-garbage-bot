/**
 * 追加課金を避けるため、Cursor 無料プランで使えるモデル ID のみを使う。
 * 環境変数 DEV_STUDIO_MODEL で上書き可能（Playground のモデル一覧と同じスラッグ）。
 *
 * 代表的な無料枠候補（アカウントで有効なものを1つ選ぶ）:
 * - grok-3-mini
 * - gpt-4o-mini
 * - gemini-2.5-flash
 * - cursor-small
 */
export const FREE_MODEL_ALTERNATIVES = [
  "grok-3-mini",
  "gpt-4o-mini",
  "gemini-2.5-flash",
  "cursor-small",
] as const;

const DEFAULT_FREE_MODEL = "grok-3-mini";

/** ルートエージェントとサブエージェント（継承）で共有するモデル ID */
export function resolveSharedModelId(): string {
  const fromEnv = process.env.DEV_STUDIO_MODEL?.trim();
  if (fromEnv) return fromEnv;
  return DEFAULT_FREE_MODEL;
}

export const MODEL_POLICY = {
  mode: "free" as const,
  sharedModelId: resolveSharedModelId(),
  rationale:
    "仕様・実装・レビューは役割別プロンプトで分離し、モデルは1種類だけ使って無料枠のリクエスト数を節約する",
} as const;