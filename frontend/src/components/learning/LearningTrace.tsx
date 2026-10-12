"use client";

import { useState } from "react";
import type { LearningTrace as LearningTraceData } from "@/lib/api";

function human(value: unknown): string | null {
  if (value == null || value === "") return null;
  if (typeof value === "string") return value;
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "yes" : "no";
  return JSON.stringify(value);
}

export function LearningTraceView({ trace }: { trace: LearningTraceData }) {
  const [showRaw, setShowRaw] = useState(false);
  const diagnosis = trace.error_diagnosis ?? {};
  const tutor = trace.tutor_decision ?? trace.agent_decision ?? {};
  const difficulty = trace.difficulty_decision ?? {};
  const masteryBefore = trace.mastery_before ?? {};
  const masteryAfter = trace.mastery_after ?? {};
  const delta = trace.mastery_delta ?? {};
  const recommendation = trace.next_recommendation ?? trace.recommendation;

  const steps: { label: string; value: string }[] = [];

  if (trace.student_state?.attempts) {
    steps.push({
      label: "狀態",
      value: `${Math.round(Number(trace.student_state.mastery ?? 0) * 100)}% · ${trace.student_state.attempts}`,
    });
  }
  const weakness =
    (trace.weakness as { reason?: string } | undefined)?.reason || trace.detected_weakness;
  if (weakness) steps.push({ label: "弱點", value: String(weakness) });
  if (diagnosis.error_type) {
    steps.push({
      label: "診斷",
      value: [human(diagnosis.error_type), human(diagnosis.related_concept)]
        .filter(Boolean)
        .join(" · "),
    });
  }
  const strategy = [tutor.strategy || tutor.adapted_mode || tutor.mode, tutor.reason || tutor.mode_reason]
    .filter(Boolean)
    .join(" · ");
  if (strategy) steps.push({ label: "策略", value: strategy });
  if (difficulty.recommended_difficulty) {
    steps.push({
      label: "難度",
      value: `${human(difficulty.previous_difficulty) ?? "—"} → ${human(difficulty.recommended_difficulty)}`,
    });
  }
  const tools = trace.tools ?? trace.selected_tools;
  if (tools?.length) steps.push({ label: "工具", value: tools.join(", ") });
  if (trace.outcome_student_message || (trace.outcome_status && trace.outcome_status !== "NOT_VERIFIABLE")) {
    steps.push({
      label: "驗證",
      value: String(trace.outcome_student_message || trace.outcome_status || trace.verification),
    });
  }
  if (trace.mastery_update) {
    const before = Math.round(Number(masteryBefore.topic ?? trace.mastery_update.before ?? 0) * 100);
    const after = Math.round(Number(masteryAfter.topic ?? trace.mastery_update.after ?? 0) * 100);
    const d = delta.topic != null ? ` (${Number(delta.topic) >= 0 ? "+" : ""}${Math.round(Number(delta.topic) * 100)}%)` : "";
    steps.push({ label: "掌握", value: `${before}% → ${after}%${d}` });
  }
  if (recommendation?.action) {
    const why =
      typeof recommendation.why === "string" && recommendation.why.trim()
        ? recommendation.why.trim()
        : typeof recommendation.reason === "string"
          ? recommendation.reason
          : "";
    steps.push({
      label: "下一步",
      value: why ? `${recommendation.action}（${why}）` : recommendation.action,
    });
  }

  if (!steps.length && !showRaw) {
    return null;
  }

  return (
    <div className="rounded-xl border border-ink-100/80 bg-white/70 p-3 text-xs text-ink-600">
      {steps.length ? (
        <ol className="space-y-1.5">
          {steps.map((step) => (
            <li key={step.label}>
              <span className="text-ink-800">{step.label}</span>
              <span className="text-ink-400"> · </span>
              <span className="text-ink-500">{step.value}</span>
            </li>
          ))}
        </ol>
      ) : null}
      <button
        type="button"
        className="mt-2 text-[11px] text-ink-400 underline decoration-ink-200 underline-offset-2"
        onClick={() => setShowRaw((value) => !value)}
      >
        {showRaw ? "收合" : "JSON"}
      </button>
      {showRaw ? (
        <pre className="mt-2 max-h-56 overflow-auto rounded-lg bg-ink-50 p-2 text-[10px] text-ink-500">
          {JSON.stringify(trace, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
