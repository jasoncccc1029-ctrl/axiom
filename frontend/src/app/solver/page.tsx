"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingBlock } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { VerificationBadge } from "@/components/learning/VerificationBadge";
import { apiPostJson, type ProblemSolveResponse } from "@/lib/api";

export default function SolverPage() {
  const { push } = useToast();
  const [problem, setProblem] = useState("solve 2*x + 4 = 10");
  const [subject, setSubject] = useState("mathematics");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProblemSolveResponse | null>(null);

  async function handleSolve(e: React.FormEvent) {
    e.preventDefault();
    if (!problem.trim()) {
      push("請輸入題目", "error");
      return;
    }
    try {
      setLoading(true);
      const data = await apiPostJson<ProblemSolveResponse>("/api/problems/solve", {
        problem: problem.trim(),
        subject,
      });
      setResult(data);
    } catch (err) {
      push(err instanceof Error ? err.message : "解題失敗", "error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader title="解題" />

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <form onSubmit={handleSolve} className="panel space-y-4 p-5">
          <label className="block text-sm">
            <span className="sr-only">科目</span>
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2"
            >
              <option value="mathematics">數學</option>
              <option value="physics">物理</option>
              <option value="python">程式</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="sr-only">題目</span>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              rows={8}
              placeholder="題目"
              className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2"
            />
          </label>
          <button
            type="submit"
            disabled={loading}
            className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm text-white disabled:opacity-60"
          >
            {loading ? "…" : "解題"}
          </button>
        </form>

        <div className="space-y-4">
          {loading ? <LoadingBlock rows={5} /> : null}
          {!loading && result ? (
            <div className="space-y-4">
              <section className="panel p-5">
                <div className="flex justify-end">
                  <VerificationBadge status={result.verification_status} />
                </div>
                <p className="mt-2 text-sm text-ink-600">{result.problem}</p>
                <p className="mt-4 text-sm text-ink-800">{result.final_answer}</p>
              </section>
              {result.proposed_solution ? (
                <section className="panel p-5">
                  <p className="whitespace-pre-wrap text-sm text-ink-700">
                    {result.proposed_solution}
                  </p>
                </section>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
