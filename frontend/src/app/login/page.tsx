"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { AxiomMark } from "@/components/brand/AxiomMark";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading, login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "register") {
        await register(name.trim(), email.trim(), password);
      } else {
        await login(email.trim(), password);
      }
      router.replace("/");
      router.refresh();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "登入失敗";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-2">
      <div className="panel p-6 md:p-8">
        <div className="mb-6 flex items-center gap-3">
          <AxiomMark size={40} />
          <div>
            <div className="font-display text-xl text-ink-950">Axiom</div>
            <p className="text-sm text-ink-600">
              {mode === "login"
                ? "登入後同步進度，並獲得較高每日 AI 額度"
                : "免費註冊：進度跟著帳號，每日 AI 額度比訪客更多"}
            </p>
          </div>
        </div>

        <div className="mb-5 flex rounded-xl border border-ink-100 bg-white/60 p-1 text-sm">
          <button
            type="button"
            className={`flex-1 rounded-lg py-2 transition ${
              mode === "login" ? "bg-ink-950 text-white" : "text-ink-600"
            }`}
            onClick={() => {
              setMode("login");
              setError(null);
            }}
          >
            登入
          </button>
          <button
            type="button"
            className={`flex-1 rounded-lg py-2 transition ${
              mode === "register" ? "bg-ink-950 text-white" : "text-ink-600"
            }`}
            onClick={() => {
              setMode("register");
              setError(null);
            }}
          >
            註冊
          </button>
        </div>

        <form className="space-y-4" onSubmit={onSubmit}>
          {mode === "register" ? (
            <label className="block text-sm">
              <span className="mb-1.5 block text-ink-700">名稱</span>
              <input
                className="w-full rounded-xl border border-ink-100 bg-white px-3 py-2.5 outline-none ring-accent/30 focus:ring-2"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                required
                minLength={1}
                maxLength={120}
              />
            </label>
          ) : null}

          <label className="block text-sm">
            <span className="mb-1.5 block text-ink-700">電子郵件</span>
            <input
              type="email"
              className="w-full rounded-xl border border-ink-100 bg-white px-3 py-2.5 outline-none ring-accent/30 focus:ring-2"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
          </label>

          <label className="block text-sm">
            <span className="mb-1.5 block text-ink-700">密碼</span>
            <input
              type="password"
              className="w-full rounded-xl border border-ink-100 bg-white px-3 py-2.5 outline-none ring-accent/30 focus:ring-2"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              required
              minLength={mode === "register" ? 8 : 1}
            />
            {mode === "register" ? (
              <span className="mt-1 block text-xs text-ink-500">至少 8 個字元</span>
            ) : null}
          </label>

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-ink-800 disabled:opacity-60"
          >
            {submitting ? "處理中…" : mode === "login" ? "登入" : "建立帳號"}
          </button>
        </form>

        <p className="mt-5 text-center text-xs text-ink-500">
          也可先以訪客使用，不必登入。{" "}
          <Link href="/" className="text-accent underline-offset-2 hover:underline">
            返回總覽
          </Link>
        </p>
      </div>
    </div>
  );
}
