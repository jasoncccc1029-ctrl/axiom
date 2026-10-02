export function WeakTopicCard({
  subject,
  topic,
  mastery,
  errors,
}: {
  subject: string;
  topic: string;
  mastery: number;
  errors: number;
}) {
  return (
    <article className="rounded-xl border border-ink-100 bg-ink-50/50 p-4">
      <p className="text-xs text-ink-400">{subject}</p>
      <p className="mt-1 font-medium text-ink-900">{topic}</p>
      <p className="mt-2 text-xs text-ink-500">
        {Math.round(mastery * 100)}%
        {errors > 0 ? ` · ${errors}` : ""}
      </p>
    </article>
  );
}
