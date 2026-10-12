"use client";

import type { TeachingMode } from "@/lib/api";

const MODES: { value: TeachingMode; label: string }[] = [
  { value: "hint", label: "提示" },
  { value: "socratic", label: "蘇格拉底" },
  { value: "tutor", label: "教學" },
  { value: "step_by_step", label: "逐步" },
  { value: "concept", label: "概念" },
  { value: "error_diagnosis", label: "錯因" },
  { value: "direct_solve", label: "直解" },
  { value: "full_solution", label: "完整解" },
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
