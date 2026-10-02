export function LearningProgress({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail?: string;
}) {
  const percent = Math.max(0, Math.min(100, value * 100));
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium text-ink-800">{label}</span>
        <span className="text-ink-500">{Math.round(percent)}%{detail ? ` · ${detail}` : ""}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-ink-100">
        <div className="h-full rounded-full bg-accent-500" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
