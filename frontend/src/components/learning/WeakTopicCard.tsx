import Link from "next/link";

export function WeakTopicCard({
  subject,
  topic,
  mastery,
  errors,
  href,
}: {
  subject: string;
  topic: string;
  mastery: number;
  errors: number;
  href?: string;
}) {
  const practiceHref =
    href ??
    `/tutor?subject=${encodeURIComponent(subject)}&topic=${encodeURIComponent(topic)}`;

  return (
    <article className="rounded-xl border border-ink-100 bg-ink-50/50 p-4">
      <p className="text-xs text-ink-400">{subject}</p>
      <p className="mt-1 font-medium text-ink-900">{topic}</p>
      <p className="mt-2 text-xs text-ink-500">
        掌握度 {Math.round(mastery * 100)}%
        {errors > 0 ? ` · 連續錯誤 ${errors}` : ""}
      </p>
      <Link
        href={practiceHref}
        className="mt-3 inline-flex text-sm font-medium text-accent-700 hover:text-ink-950"
      >
        去教學練習 →
      </Link>
    </article>
  );
}
