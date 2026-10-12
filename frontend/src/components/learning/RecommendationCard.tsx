import Link from "next/link";

export function RecommendationCard({
  subject,
  topic,
  reason,
  action,
  why,
  concept,
  recommended_difficulty,
  priority_label,
  evidence,
}: {
  subject: string;
  topic: string;
  reason: string;
  action: string;
  why?: string;
  sequence?: string[];
  evidence?: Record<string, unknown>;
  recommended_difficulty?: string;
  concept?: string | null;
  strategy?: string | null;
  difficulty?: number | null;
  priority_label?: string;
}) {
  const explanation = (why || reason || "").trim();
  const mastery =
    evidence && typeof evidence.mastery === "number" ? evidence.mastery : null;
  const consecutive =
    evidence && typeof evidence.consecutive_errors === "number"
      ? evidence.consecutive_errors
      : null;
  const practiceHref = `/tutor?subject=${encodeURIComponent(subject)}&topic=${encodeURIComponent(topic)}${
    concept ? `&concept=${encodeURIComponent(concept)}` : ""
  }`;
  const solverHref = `/solver?subject=${encodeURIComponent(subject)}&topic=${encodeURIComponent(topic)}`;

  return (
    <article className="rounded-xl border border-ink-100 bg-white p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs text-accent-700">{subject}</p>
        {priority_label ? (
          <span className="text-[11px] text-ink-400">{priority_label}</span>
        ) : null}
      </div>
      <h3 className="mt-1 font-medium text-ink-950">{topic}</h3>
      {concept ? <p className="mt-0.5 text-sm text-ink-500">{concept}</p> : null}
      <p className="mt-2 text-sm text-ink-800">{action}</p>
      {explanation ? (
        <p className="mt-2 text-sm leading-relaxed text-ink-600">
          <span className="font-medium text-ink-800">為什麼：</span>
          {explanation}
        </p>
      ) : null}
      {(mastery != null || consecutive != null || recommended_difficulty) && (
        <p className="mt-2 text-xs text-ink-400">
          {mastery != null ? `掌握度 ${(mastery * 100).toFixed(0)}%` : null}
          {mastery != null && (consecutive != null || recommended_difficulty)
            ? " · "
            : null}
          {consecutive != null ? `連續錯誤 ${consecutive}` : null}
          {consecutive != null && recommended_difficulty ? " · " : null}
          {recommended_difficulty
            ? `建議難度 ${recommended_difficulty}`
            : null}
        </p>
      )}
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
        <Link
          href={practiceHref}
          className="inline-flex text-sm font-medium text-accent-700 hover:text-ink-950"
        >
          開始練習 →
        </Link>
        <Link
          href={solverHref}
          className="inline-flex text-sm text-ink-500 hover:text-ink-800"
        >
          帶焦點解題
        </Link>
      </div>
    </article>
  );
}
