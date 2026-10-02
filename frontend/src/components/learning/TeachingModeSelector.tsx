"use client";

import type { TeachingMode } from "@/lib/api";

const MODES: { value: TeachingMode; label: string }[] = [
  { value: "hint", label: "Hint" },
  { value: "socratic", label: "Socratic" },
  { value: "tutor", label: "Tutor" },
  { value: "step_by_step", label: "Steps" },
  { value: "concept", label: "Concept" },
  { value: "error_diagnosis", label: "Diagnose" },
  { value: "direct_solve", label: "Solve" },
  { value: "full_solution", label: "Full" },
];

export function TeachingModeSelector({
  value,
  onChange,
  disabled,
}: {
  value: TeachingMode;
  onChange: (value: TeachingMode) => void;
  disabled?: boolean;
}) {
  return (
    <label className="shrink-0">
      <span className="sr-only">模式</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as TeachingMode)}
        className="h-[42px] max-w-[7.5rem] truncate rounded-xl border-0 bg-ink-50 px-2.5 text-xs text-ink-700 outline-none ring-accent-400/30 focus:ring-2 disabled:opacity-50 sm:max-w-[9rem]"
      >
        {MODES.map((mode) => (
          <option key={mode.value} value={mode.value}>
            {mode.label}
          </option>
        ))}
      </select>
    </label>
  );
}
