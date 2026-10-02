import type { VisionAnalysis } from "@/lib/api";

export function VisionResultCard({ result }: { result: VisionAnalysis }) {
  return (
    <section className="rounded-xl border border-ink-100 bg-ink-50/50 p-4 text-sm">
      <p className="text-ink-800">
        {result.subject} · {result.topic}
      </p>
      {result.detected_formula.length ? (
        <p className="mt-2 font-mono text-xs text-ink-700">{result.detected_formula.join(" · ")}</p>
      ) : null}
    </section>
  );
}
