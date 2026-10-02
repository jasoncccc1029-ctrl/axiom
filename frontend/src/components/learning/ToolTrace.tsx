import type { AgentRunResponse } from "@/lib/api";
import { VerificationBadge } from "./VerificationBadge";

export function ToolTrace({ trace }: { trace: AgentRunResponse }) {
  return (
    <div className="rounded-xl border border-ink-100/80 bg-ink-50/50 p-3 text-xs text-ink-600">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span>{trace.route ?? "tutor"}</span>
        <VerificationBadge status={trace.verification_status} />
      </div>
      {trace.steps.length ? (
        <ol className="space-y-1.5 border-l border-ink-200 pl-3">
          {trace.steps.map((step) => (
            <li key={step.index}>
              <span className="text-ink-800">{step.action}</span>
              {step.tool ? <span className="text-ink-400"> · {step.tool}</span> : null}
            </li>
          ))}
        </ol>
      ) : null}
      {trace.sources.length ? (
        <div className="mt-2 border-t border-ink-100 pt-2 text-ink-500">
          {trace.sources.map((source) => (
            <p key={source.chunk_id}>
              {source.document_title} · p.{source.page}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}
