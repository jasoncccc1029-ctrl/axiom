"use client";

export function ProblemConfirmation({
  value,
  onChange,
  confirmed,
  onConfirm,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  confirmed: boolean;
  onConfirm: () => void;
  disabled?: boolean;
}) {
  return (
    <section className="rounded-xl border border-ink-200 bg-white p-3">
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={confirmed || disabled}
        rows={3}
        placeholder="題目"
        className="w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-accent-400/30"
      />
      <button
        type="button"
        onClick={onConfirm}
        disabled={disabled || confirmed || !value.trim()}
        className="mt-2 rounded-lg bg-ink-950 px-3 py-2 text-xs text-white disabled:opacity-50"
      >
        {confirmed ? "已確認" : "確認"}
      </button>
    </section>
  );
}
