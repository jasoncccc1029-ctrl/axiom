"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState } from "@/components/ui/States";
import { apiGet, apiPostJson } from "@/lib/api";
import type {
  EvaluationMetrics,
  EvaluationSession,
  LearningReport,
} from "@/lib/api";

type Phase = "setup" | "pretest" | "learning" | "posttest" | "results";

function pct(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value * 100)}%`;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-ink-100 py-3 last:border-0">
      <p className="text-sm text-ink-600">{label}</p>
      <p className="font-display text-xl text-ink-950">{value}</p>
    </div>
  );
}

export default function EvaluationPage() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [subject, setSubject] = useState("mathematics");
  const [topic, setTopic] = useState("logarithms");
  const [groupArm, setGroupArm] = useState<"axiom" | "control">("axiom");
  const [session, setSession] = useState<EvaluationSession | null>(null);
  const [metrics, setMetrics] = useState<EvaluationMetrics | null>(null);
  const [report, setReport] = useState<LearningReport | null>(null);
  const [preCorrect, setPreCorrect] = useState(2);
  const [preTotal, setPreTotal] = useState(4);
  const [postCorrect, setPostCorrect] = useState(3);
  const [postTotal, setPostTotal] = useState(4);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const preScore = useMemo(
    () => (preTotal > 0 ? preCorrect / preTotal : 0),
    [preCorrect, preTotal]
  );
  const postScore = useMemo(
    () => (postTotal > 0 ? postCorrect / postTotal : 0),
    [postCorrect, postTotal]
  );

  async function startEvaluation() {
    setBusy(true);
    setError(null);
    try {
      const created = await apiPostJson<EvaluationSession>("/api/evaluation/start", {
        subject,
        topic,
        group_arm: groupArm,
      });
      setSession(created);
      setPhase("pretest");
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法開始");
    } finally {
      setBusy(false);
    }
  }

  async function submitPretest() {
    if (!session) return;
    if (preTotal < 1 || preCorrect < 0 || preCorrect > preTotal) {
      setError("題數無效");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const items = Array.from({ length: preTotal }, (_, i) => ({
        item_id: `pre-${i + 1}`,
        concept: topic,
        is_correct: i < preCorrect,
      }));
      const updated = await apiPostJson<EvaluationSession>("/api/evaluation/pretest", {
        evaluation_id: session.evaluation_id,
        items,
      });
      setSession(updated);
      setPhase("learning");
    } catch (err) {
      setError(err instanceof Error ? err.message : "記錄失敗");
    } finally {
      setBusy(false);
    }
  }

  async function beginLearning() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await apiPostJson<EvaluationSession>(
        `/api/evaluation/${session.evaluation_id}/begin-learning`,
        {}
      );
      setSession(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法開始");
    } finally {
      setBusy(false);
    }
  }

  async function submitPosttest() {
    if (!session) return;
    if (postTotal < 1 || postCorrect < 0 || postCorrect > postTotal) {
      setError("題數無效");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const items = Array.from({ length: postTotal }, (_, i) => ({
        item_id: `post-${i + 1}`,
        concept: topic,
        is_correct: i < postCorrect,
      }));
      const updated = await apiPostJson<EvaluationSession>("/api/evaluation/posttest", {
        evaluation_id: session.evaluation_id,
        items,
      });
      const [m, r] = await Promise.all([
        apiGet<EvaluationMetrics>(`/api/evaluation/${session.evaluation_id}/metrics`),
        apiGet<LearningReport>(`/api/evaluation/${session.evaluation_id}/report`),
      ]);
      setSession(updated);
      setMetrics(m);
      setReport(r);
      setPhase("results");
    } catch (err) {
      setError(err instanceof Error ? err.message : "記錄失敗");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title="試驗" />

      {error ? <ErrorState message={error} onRetry={() => setError(null)} /> : null}

      {phase === "setup" ? (
        <section className="panel space-y-4 p-6">
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm">
              <span className="sr-only">科目</span>
              <input
                className="w-full rounded-lg border border-ink-200 px-3 py-2"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="科目"
              />
            </label>
            <label className="text-sm">
              <span className="sr-only">主題</span>
              <input
                className="w-full rounded-lg border border-ink-200 px-3 py-2"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="主題"
              />
            </label>
            <label className="text-sm">
              <span className="sr-only">組別</span>
              <select
                className="w-full rounded-lg border border-ink-200 px-3 py-2"
                value={groupArm}
                onChange={(e) => setGroupArm(e.target.value as "axiom" | "control")}
              >
                <option value="axiom">axiom</option>
                <option value="control">control</option>
              </select>
            </label>
          </div>
          <button
            type="button"
            disabled={busy}
            onClick={() => void startEvaluation()}
            className="rounded-lg bg-ink-950 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            開始
          </button>
        </section>
      ) : null}

      {phase === "pretest" && session ? (
        <section className="panel space-y-4 p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm text-ink-500">
              總
              <input
                type="number"
                min={1}
                className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-ink-900"
                value={preTotal}
                onChange={(e) => setPreTotal(Number(e.target.value))}
              />
            </label>
            <label className="text-sm text-ink-500">
              對
              <input
                type="number"
                min={0}
                className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-ink-900"
                value={preCorrect}
                onChange={(e) => setPreCorrect(Number(e.target.value))}
              />
            </label>
          </div>
          <p className="text-sm text-ink-500">{pct(preScore)}</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => void submitPretest()}
            className="rounded-lg bg-ink-950 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            記錄
          </button>
        </section>
      ) : null}

      {phase === "learning" && session ? (
        <section className="panel space-y-4 p-6">
          <p className="text-sm text-ink-500">{pct(session.pre_test_score)}</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy || !!session.learning_session_id}
              onClick={() => void beginLearning()}
              className="rounded-lg border border-ink-200 bg-white px-4 py-2 text-sm disabled:opacity-50"
            >
              {session.learning_session_id ? `#${session.learning_session_id}` : "開始學習"}
            </button>
            <Link href="/tutor" className="rounded-lg bg-ink-950 px-4 py-2 text-sm text-white">
              教學
            </Link>
            <button
              type="button"
              disabled={busy}
              onClick={() => setPhase("posttest")}
              className="rounded-lg border border-ink-200 bg-white px-4 py-2 text-sm"
            >
              後測
            </button>
          </div>
        </section>
      ) : null}

      {phase === "posttest" && session ? (
        <section className="panel space-y-4 p-6">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm text-ink-500">
              總
              <input
                type="number"
                min={1}
                className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-ink-900"
                value={postTotal}
                onChange={(e) => setPostTotal(Number(e.target.value))}
              />
            </label>
            <label className="text-sm text-ink-500">
              對
              <input
                type="number"
                min={0}
                className="mt-1 w-full rounded-lg border border-ink-200 px-3 py-2 text-ink-900"
                value={postCorrect}
                onChange={(e) => setPostCorrect(Number(e.target.value))}
              />
            </label>
          </div>
          <p className="text-sm text-ink-500">{pct(postScore)}</p>
          <button
            type="button"
            disabled={busy}
            onClick={() => void submitPosttest()}
            className="rounded-lg bg-ink-950 px-4 py-2 text-sm text-white disabled:opacity-50"
          >
            記錄
          </button>
        </section>
      ) : null}

      {phase === "results" && metrics && report ? (
        <div className="space-y-6">
          <section className="panel p-6">
            <MetricRow label="前測" value={pct(metrics.pre_test_score)} />
            <MetricRow label="後測" value={pct(metrics.post_test_score)} />
            <MetricRow
              label="增益"
              value={
                metrics.learning_gain == null
                  ? "—"
                  : `${metrics.learning_gain >= 0 ? "+" : ""}${Math.round(metrics.learning_gain * 100)}%`
              }
            />
            <MetricRow
              label="掌握"
              value={
                metrics.mastery_change == null
                  ? "—"
                  : `${pct(metrics.mastery_before)} → ${pct(metrics.mastery_after)}`
              }
            />
            <MetricRow
              label="概念"
              value={
                metrics.concept_recovery_rate == null
                  ? "—"
                  : `${pct(metrics.concept_recovery_rate)}`
              }
            />
            <MetricRow
              label="錯誤"
              value={
                metrics.error_recovery?.improved == null
                  ? "—"
                  : metrics.error_recovery.improved
                    ? "下降"
                    : "未降"
              }
            />
            {metrics.difficulty_progression?.progression ? (
              <MetricRow label="難度" value={metrics.difficulty_progression.progression} />
            ) : null}
          </section>

          <section className="panel space-y-2 p-6 text-sm text-ink-800">
            <p>{report.initial_state}</p>
            {report.weak_concepts.length ? <p>{report.weak_concepts.join(" · ")}</p> : null}
            {report.learning_interventions.length ? (
              <ul className="list-disc pl-5">
                {report.learning_interventions.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : null}
            <p>{report.mastery_changes}</p>
            {report.post_test ? <p>{report.post_test}</p> : null}
            <p>{report.concept_recovery}</p>
            {report.remaining_weaknesses.length ? (
              <p>{report.remaining_weaknesses.join(" · ")}</p>
            ) : null}
          </section>

          <button
            type="button"
            className="rounded-lg border border-ink-200 bg-white px-4 py-2 text-sm"
            onClick={() => {
              setPhase("setup");
              setSession(null);
              setMetrics(null);
              setReport(null);
            }}
          >
            再測
          </button>
        </div>
      ) : null}
    </div>
  );
}
