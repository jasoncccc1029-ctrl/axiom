export function cn(...parts: Array<string | false | null | undefined>) {
  return parts.filter(Boolean).join(" ");
}

export function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes} 分`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} 時 ${m} 分` : `${h} 時`;
}

export function formatPercent(rate: number) {
  return `${Math.round(rate * 100)}%`;
}
