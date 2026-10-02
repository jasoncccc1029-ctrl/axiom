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

export function Chat({
  turns,
  onRecordOutcome,
  recordingId,
}: {
  turns: ChatItem[];
  onRecordOutcome?: (turn: ChatItem, correct: boolean) => void;
  recordingId?: string | null;
}) {
  return (
    <div className="space-y-5">
      {turns.map((turn) => {
        const needsMark =
          onRecordOutcome &&
          !turn.outcomeRecorded &&
          turn.trace?.session_id &&
          !turn.trace.learning_trace?.mastery_update;
        const isUser = turn.role === "user";

        return (
          <article
            key={turn.id}
            className={cn(
              turn.fading ? "animate-fadeOut pointer-events-none" : "animate-fadeUp",
              isUser ? "ml-auto max-w-[min(100%,34rem)]" : "mr-auto max-w-[min(100%,40rem)]"
            )}
          >
            <div
              className={cn(
                "rounded-2xl px-4 py-3.5 text-[15px] leading-relaxed",
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
                {needsMark ? (
                  <div className="flex flex-wrap gap-2 pt-0.5">
                    <button
                      type="button"
                      disabled={recordingId === turn.id}
                      onClick={() => onRecordOutcome(turn, true)}
                      className="rounded-full bg-ink-950 px-3.5 py-1.5 text-xs font-medium text-white transition hover:bg-ink-800 disabled:opacity-50"
                    >
                      對
                    </button>
                    <button
                      type="button"
                      disabled={recordingId === turn.id}
                      onClick={() => onRecordOutcome(turn, false)}
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
