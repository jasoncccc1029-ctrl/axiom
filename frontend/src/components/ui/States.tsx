import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function LoadingBlock({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-3", className)}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton h-12 w-full" style={{ animationDelay: `${i * 80}ms` }} />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title?: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-200 bg-white/40 px-6 py-16 text-center animate-fadeUp">
      {title ? <h3 className="font-display text-lg text-ink-900">{title}</h3> : null}
      {description ? <p className="mt-2 max-w-sm text-sm text-ink-500">{description}</p> : null}
      {action ? <div className={title || description ? "mt-5" : undefined}>{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="rounded-xl border border-red-200 bg-red-50/80 px-4 py-3 animate-fadeUp">
      {title ? <h3 className="font-display text-sm text-red-900">{title}</h3> : null}
      <p className={cn("text-sm text-red-700", title && "mt-1")}>{message}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 text-sm text-red-800 underline decoration-red-300 underline-offset-2 hover:text-red-950"
        >
          重試
        </button>
      ) : null}
    </div>
  );
}

export function UploadProgress({ percent, label }: { percent: number; label?: string }) {
  return (
    <div className="animate-fadeUp">
      {label ? (
        <div className="mb-1.5 flex items-center justify-between text-xs text-ink-500">
          <span>{label}</span>
          <span>{percent}%</span>
        </div>
      ) : (
        <p className="mb-1.5 text-right text-xs text-ink-400">{percent}%</p>
      )}
      <div className="h-1.5 overflow-hidden rounded-full bg-ink-100">
        <div
          className="h-full rounded-full bg-accent-500 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
