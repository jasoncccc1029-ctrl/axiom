"use client";

import { Paperclip } from "lucide-react";
import { cn } from "@/lib/utils";

export function FileUploader({
  accept,
  onSelect,
  disabled,
  label = "附加",
  iconOnly = false,
}: {
  accept: string;
  onSelect: (file: File) => void;
  disabled?: boolean;
  label?: string;
  iconOnly?: boolean;
}) {
  return (
    <label
      className={cn(
        "inline-flex h-[42px] cursor-pointer items-center rounded-xl text-ink-500 transition hover:bg-ink-50 hover:text-ink-800",
        iconOnly ? "w-[42px] justify-center" : "gap-1.5 px-2.5 text-xs"
      )}
      title={label}
      aria-label={label}
    >
      <Paperclip className="h-4 w-4" />
      {iconOnly ? <span className="sr-only">{label}</span> : label}
      <input
        type="file"
        className="hidden"
        accept={accept}
        disabled={disabled}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onSelect(file);
          event.currentTarget.value = "";
        }}
      />
    </label>
  );
}
