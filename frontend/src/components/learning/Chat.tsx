import type { AgentRunResponse, LearningTrace as LearningTraceData } from "@/lib/api";
import { cn } from "@/lib/utils";
import { ToolTrace } from "./ToolTrace";
import { LearningTraceView } from "./LearningTrace";

export type ChatItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  imageName?: string;
  imagePreviewUrl?: string;
  model?: string;
  trace?: AgentRunResponse;
  outcomeRecorded?: boolean;
  fading?: boolean;
};

function masteryDeltaLabel(trace: LearningTraceData | undefined): string | null {
  if (!trace?.mastery_update && !trace?.mastery_updated) return null;
  const before = Number(
    trace.mastery_before?.topic ?? trace.mastery_update?.before ?? NaN
  );
  const after = Number(
    trace.mastery_after?.topic ?? trace.mastery_update?.after ?? NaN
  );
  if (Number.isNaN(before) || Number.isNaN(after)) return "已寫入掌握度";
  return `掌握度 ${Math.round(before * 100)}% → ${Math.round(after * 100)}%`;
}

function OutcomeChip({
  turn,
  allowMark,
}: {
  turn: ChatItem;
  allowMark: boolean;
}) {
  if (turn.role !== "assistant" || !turn.trace) return null;
  const lt = turn.trace.learning_trace as LearningTraceData | undefined;
  const autoRecorded = Boolean(lt?.mastery_update || lt?.mastery_updated);
  const delta = masteryDeltaLabel(lt);

  if (turn.outcomeRecorded || autoRecorded) {
    return (
      <p className="rounded-full bg-accent-50 px-3 py-1 text-xs text-accent-900">
        {turn.outcomeRecorded ? "已手動記錄" : "已自動記錄"}
        {delta ? ` · ${delta}` : ""}
      </p>
    );
  }

  if (lt?.outcome_student_message && !allowMark) {
    return (
      <p className="rounded-full bg-ink-50 px-3 py-1 text-xs text-ink-600">
        未寫入掌握度 · {lt.outcome_student_message}
      </p>
    );
  }

  if (!allowMark) {
    return (
      <p className="rounded-full bg-ink-50 px-3 py-1 text-xs text-ink-500">
        需先從推薦或練習進入，才能記錄結果
      </p>
    );
  }

  if (turn.trace.session_id) {
    return (
      <p className="rounded-full bg-amber-50 px-3 py-1 text-xs text-amber-900">
        請標記對錯，Axiom 才會更新你的學習狀態
      </p>
    );
  }

  return null;
}

export function Chat({
  turns,
  onRecordOutcome,
  recordingId,
  allowOutcomeMark = false,
}: {
  turns: ChatItem[];
  onRecordOutcome?: (turn: ChatItem, correct: boolean) => void;
  recordingId?: string | null;
  allowOutcomeMark?: boolean;
}) {
  return (
    <div className="space-y-5">
      {turns.map((turn) => {
        const needsMark =
          Boolean(onRecordOutcome) &&
          allowOutcomeMark &&
          !turn.outcomeRecorded &&
          Boolean(turn.trace?.session_id) &&
          !turn.trace?.learning_trace?.mastery_update &&
          !turn.trace?.learning_trace?.mastery_updated;
        const isUser = turn.role === "user";

        return (
          <article
            key={turn.id}
            className={cn(
              turn.fading ? "animate-fadeOut pointer-events-none" : "animate-fadeUp",
              isUser ? "ml-auto max-w-[min(100%,36rem)]" : "mr-auto w-full max-w-[min(100%,48rem)]"
            )}
          >
            <div
              className={cn(
                "rounded-2xl px-4 py-3.5 text-[15px] leading-[1.7]",
                isUser
                  ? "bg-ink-950 text-white shadow-soft"
                  : "border border-ink-100/80 bg-white/90 text-ink-800 shadow-soft"
              )}
            >
              <p className="whitespace-pre-wrap">{turn.content}</p>
              {turn.imagePreviewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={turn.imagePreviewUrl}
                  alt=""
                  className="mt-3 max-h-44 rounded-xl border border-white/15 object-contain"
                />
              ) : null}
            </div>

            {turn.trace ? (
              <div className="mt-2.5 space-y-2.5 px-0.5">
                <OutcomeChip turn={turn} allowMark={allowOutcomeMark} />

                {needsMark ? (
                  <div className="flex flex-wrap gap-2 pt-0.5">
                    <button
                      type="button"
                      disabled={recordingId === turn.id}
                      onClick={() => onRecordOutcome?.(turn, true)}
                      className="rounded-full bg-ink-950 px-3.5 py-1.5 text-xs font-medium text-white transition hover:bg-ink-800 disabled:opacity-50"
                    >
                      對
                    </button>
                    <button
                      type="button"
                      disabled={recordingId === turn.id}
                      onClick={() => onRecordOutcome?.(turn, false)}
                      className="rounded-full border border-ink-200 bg-white px-3.5 py-1.5 text-xs font-medium text-ink-700 transition hover:border-ink-300 hover:bg-ink-50 disabled:opacity-50"
                    >
                      錯
                    </button>
                  </div>
                ) : null}

                <details className="group text-xs text-ink-500">
                  <summary className="cursor-pointer list-none text-ink-400 transition hover:text-ink-700 [&::-webkit-details-marker]:hidden">
                    <span className="underline decoration-ink-200 underline-offset-4 group-open:text-ink-700">
                      詳情
                    </span>
                  </summary>
                  <div className="mt-2 space-y-2">
                    <ToolTrace trace={turn.trace} />
                    {turn.trace.learning_trace ? (
                      <LearningTraceView
                        trace={turn.trace.learning_trace as LearningTraceData}
                      />
                    ) : null}
                  </div>
                </details>
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
