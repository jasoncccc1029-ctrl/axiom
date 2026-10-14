"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { getAiUsage, type AiUsageStatus } from "@/lib/api";

export function PublicBanner() {
  const { user, loading } = useAuth();
  const [usage, setUsage] = useState<AiUsageStatus | null>(null);

  const refreshUsage = useCallback(async () => {
    try {
      setUsage(await getAiUsage());
    } catch {
      setUsage(null);
    }
  }, []);

  useEffect(() => {
    void refreshUsage();
    const onFocus = () => void refreshUsage();
    window.addEventListener("focus", onFocus);
    const id = window.setInterval(() => void refreshUsage(), 60_000);
    return () => {
      window.removeEventListener("focus", onFocus);
      window.clearInterval(id);
    };
  }, [refreshUsage, user?.id]);

  const quotaLabel =
    usage && usage.enabled
      ? `今日 AI ${usage.used}/${usage.limit}`
      : null;

  if (!loading && user) {
    return (
      <div className="border-b border-accent-200/60 bg-accent-50/90 px-4 py-2 text-center text-xs text-ink-700 md:text-sm">
        已登入為 {user.name}
        {quotaLabel ? ` · ${quotaLabel}` : null}
        {" · "}
        額度於每日 UTC 午夜重置
      </div>
    );
  }

  return (
    <div className="border-b border-accent-200/60 bg-accent-50/90 px-4 py-2 text-center text-xs text-ink-700 md:text-sm">
      訪客可試用 AI
      {quotaLabel ? `（${quotaLabel}）` : null}
      。{" "}
      <Link href="/login" className="font-medium text-accent underline-offset-2 hover:underline">
        登入／註冊
      </Link>{" "}
      後每日額度更高，進度也會跟著帳號走。
    </div>
  );
}
