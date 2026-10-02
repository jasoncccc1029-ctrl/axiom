export function RecommendationCard({
  subject,
  topic,
  action,
  concept,
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
  return (
    <article className="rounded-xl border border-ink-100 bg-white p-4">
      <p className="text-xs text-accent-700">{subject}</p>
      <h3 className="mt-1 font-medium text-ink-950">{topic}</h3>
      {concept ? <p className="mt-0.5 text-sm text-ink-500">{concept}</p> : null}
      <p className="mt-2 text-sm text-ink-800">{action}</p>
    </article>
  );
}
