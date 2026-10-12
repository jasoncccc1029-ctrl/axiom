"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/States";
import Link from "next/link";
import {
  apiGet,
  type ErrorDNAProfile,
  type ProgressData,
  type RecommendationsResponse,
  type StudentModel,
} from "@/lib/api";
import { formatMinutes, formatPercent } from "@/lib/utils";
import { LearningProgress } from "@/components/learning/LearningProgress";
import { WeakTopicCard } from "@/components/learning/WeakTopicCard";
import { MasteryTree } from "@/components/learning/MasteryTree";
import { RecommendationCard } from "@/components/learning/RecommendationCard";

export default function ProgressPage() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [student, setStudent] = useState<StudentModel | null>(null);
  const [errorDna, setErrorDna] = useState<ErrorDNAProfile | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [progress, studentData, recs] = await Promise.all([
        apiGet<ProgressData>("/api/progress"),
        apiGet<StudentModel>("/api/student"),
        apiGet<RecommendationsResponse>("/api/recommendations").catch(() => null),
      ]);
      const top = recs?.recommendations?.[0];
      const dnaQs = new URLSearchParams();
      if (top?.subject) dnaQs.set("subject", top.subject);
      if (top?.topic) dnaQs.set("topic", top.topic);
      const dna = await apiGet<ErrorDNAProfile>(
        `/api/student/error-dna${dnaQs.toString() ? `?${dnaQs}` : ""}`
      ).catch(() => null);
      setData(progress);
      setStudent(studentData);
      setErrorDna(dna);
      setRecommendations(recs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const weakTopics = data?.topic_mastery.filter((item) => item.mastery < 0.6) ?? [];
  const mastery =
    student?.mastery ??
    data?.topic_mastery.map((item) => ({
      ...item,
      confidence: 0,
      correct_attempts: 0,
      last_practiced_at: null,
      next_review_at: null,
    })) ??
    [];
  const recs = recommendations?.recommendations ?? [];
  const frequentErrors = errorDna?.most_frequent_error_types ?? [];

  return (
    <div>
      <PageHeader title="進度" />

      {loading ? <LoadingBlock rows={5} /> : null}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {!loading && !error && data ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-3">
            {[
              { label: "時間", value: formatMinutes(data.total_study_minutes) },
              { label: "題數", value: `${data.total_questions}` },
              { label: "正確率", value: formatPercent(data.accuracy_rate) },
            ].map((item, i) => (
              <div
                key={item.label}
                className="panel p-5 animate-fadeUp"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <p className="text-xs text-ink-400">{item.label}</p>
                <p className="mt-3 font-display text-3xl text-ink-950">{item.value}</p>
              </div>
            ))}
          </div>

          <section className="panel p-6">
            <h2 className="font-display text-xl text-ink-950">建議下一步</h2>
            <p className="mt-1 text-sm text-ink-500">
              Observe → Understand → Adapt：根據掌握度與錯因決定，不是隨機推薦。
            </p>
            {recs[0] ? (
              <p className="mt-2 rounded-lg bg-ink-50 px-3 py-2 text-xs leading-relaxed text-ink-600">
                <span className="font-medium text-ink-800">目前最該練：</span>
                {[recs[0].subject, recs[0].topic, recs[0].concept]
                  .filter(Boolean)
                  .join(" · ")}
                {recs[0].why || recs[0].reason
                  ? ` — ${recs[0].why || recs[0].reason}`
                  : ""}
              </p>
            ) : null}
            {recs.length ? (
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {recs.slice(0, 4).map((item) => (
                  <RecommendationCard key={`${item.subject}-${item.topic}`} {...item} />
                ))}
              </div>
            ) : (
              <div className="mt-4">
                <EmptyState
                  title="還沒有足夠資料做推薦"
                  description={
                    recommendations?.message ||
                    data.data_message ||
                    "先練習幾題，這裡會出現有原因的下一步建議。"
                  }
                  action={
                    <Link
                      href="/tutor"
                      className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm text-white hover:bg-ink-800"
                    >
                      去教學
                    </Link>
                  }
                />
              </div>
            )}
          </section>

          {data.subject_abilities.length ? (
            <section className="panel p-6 animate-fadeUp">
              <h2 className="font-display text-xl text-ink-950">科目</h2>
              <div className="mt-5 space-y-4">
                {data.subject_abilities.map((s) => (
                  <div key={s.subject}>
                    <div className="mb-2 flex items-center justify-between text-sm">
                      <span className="font-medium text-ink-800">{s.subject}</span>
                      <span className="text-ink-500">
                        {s.score}% · {s.questions}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-ink-100">
                      <div
                        className="h-full rounded-full bg-accent-500 transition-all"
                        style={{ width: `${Math.min(100, s.score)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {mastery.length ? (
            <section className="panel p-6">
              <h2 className="font-display text-xl text-ink-950">掌握</h2>
              <div className="mt-5">
                <MasteryTree mastery={mastery} />
              </div>
            </section>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            {frequentErrors.length || data.mistake_patterns.length ? (
              <section className="panel p-6">
                <h2 className="font-display text-xl text-ink-950">錯因 DNA</h2>
                <p className="mt-1 text-sm text-ink-500">
                  你最常出現的錯誤類型
                  {errorDna?.subject
                    ? ` · 焦點 ${[errorDna.subject, errorDna.topic].filter(Boolean).join(" · ")}`
                    : ""}
                </p>
                <ul className="mt-4 space-y-2">
                  {frequentErrors.length
                    ? frequentErrors.slice(0, 6).map((item) => (
                        <li
                          key={item.error_type}
                          className="rounded-xl bg-red-50/60 p-3 text-sm text-ink-700"
                        >
                          <span className="font-medium text-ink-900">{item.error_type}</span>
                          <span className="text-ink-500"> · {item.count} 次</span>
                          {item.evidence?.[0]?.detail ? (
                            <p className="mt-1 text-xs text-ink-500">
                              例：{item.evidence[0].detail}
                            </p>
                          ) : null}
                        </li>
                      ))
                    : data.mistake_patterns.map((item) => (
                        <li
                          key={`${item.pattern}-${item.topic}`}
                          className="rounded-xl bg-red-50/60 p-3 text-sm text-ink-700"
                        >
                          {item.pattern} · {item.count}
                        </li>
                      ))}
                </ul>
                {(() => {
                  const focusSubject =
                    errorDna?.subject ||
                    recommendations?.recommendations?.[0]?.subject ||
                    null;
                  const focusTopic =
                    errorDna?.topic ||
                    recommendations?.recommendations?.[0]?.topic ||
                    null;
                  if (!focusSubject) return null;
                  return (
                    <Link
                      href={`/tutor?subject=${encodeURIComponent(focusSubject)}${
                        focusTopic ? `&topic=${encodeURIComponent(focusTopic)}` : ""
                      }`}
                      className="mt-4 inline-flex text-sm font-medium text-accent-700 hover:text-ink-950"
                    >
                      針對錯因去練習 →
                    </Link>
                  );
                })()}
              </section>
            ) : null}
            {data.accuracy_trend.length ? (
              <section className="panel p-6">
                <h2 className="font-display text-xl text-ink-950">趨勢</h2>
                <p className="mt-1 text-sm text-ink-500">正確率有沒有在改善</p>
                <div className="mt-4 space-y-3">
                  {data.accuracy_trend.map((point) => (
                    <LearningProgress
                      key={point.date}
                      label={point.date}
                      value={point.accuracy}
                      detail={`${point.correct}/${point.attempted}`}
                    />
                  ))}
                </div>
              </section>
            ) : null}
          </div>

          {weakTopics.length ? (
            <section className="panel p-6">
              <h2 className="font-display text-xl text-ink-950">弱點</h2>
              <p className="mt-1 text-sm text-ink-500">掌握度偏低或連續錯誤較多的主題</p>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {weakTopics.map((item) => (
                  <WeakTopicCard
                    key={`${item.subject}-${item.topic}`}
                    subject={item.subject}
                    topic={item.topic}
                    mastery={item.mastery}
                    errors={item.consecutive_errors}
                  />
                ))}
              </div>
            </section>
          ) : null}

          {data.strengths.length ? (
            <section className="panel p-6 animate-fadeUp">
              <h2 className="font-display text-xl text-ink-950">優勢</h2>
              <ul className="mt-4 space-y-2">
                {data.strengths.map((s) => (
                  <li
                    key={s}
                    className="rounded-xl bg-accent-50 px-3 py-2 text-sm text-accent-900"
                  >
                    {s}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
