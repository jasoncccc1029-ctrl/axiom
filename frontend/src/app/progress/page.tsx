"use client";

import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingBlock } from "@/components/ui/States";
import { apiGet, type ProgressData, type StudentModel } from "@/lib/api";
import { formatMinutes, formatPercent } from "@/lib/utils";
import { LearningProgress } from "@/components/learning/LearningProgress";
import { WeakTopicCard } from "@/components/learning/WeakTopicCard";
import { MasteryTree } from "@/components/learning/MasteryTree";

export default function ProgressPage() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [student, setStudent] = useState<StudentModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [progress, studentData] = await Promise.all([
        apiGet<ProgressData>("/api/progress"),
        apiGet<StudentModel>("/api/student"),
      ]);
      setData(progress);
      setStudent(studentData);
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
              <div key={item.label} className="panel p-5 animate-fadeUp" style={{ animationDelay: `${i * 60}ms` }}>
                <p className="text-xs text-ink-400">{item.label}</p>
                <p className="mt-3 font-display text-3xl text-ink-950">{item.value}</p>
              </div>
            ))}
          </div>

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
            {data.mistake_patterns.length ? (
              <section className="panel p-6">
                <h2 className="font-display text-xl text-ink-950">錯因</h2>
                <ul className="mt-4 space-y-2">
                  {data.mistake_patterns.map((item) => (
                    <li key={`${item.pattern}-${item.topic}`} className="rounded-xl bg-red-50/60 p-3 text-sm text-ink-700">
                      {item.pattern} · {item.count}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            {data.accuracy_trend.length ? (
              <section className="panel p-6">
                <h2 className="font-display text-xl text-ink-950">趨勢</h2>
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
            <section className="grid gap-3 md:grid-cols-2">
              {weakTopics.map((item) => (
                <WeakTopicCard
                  key={`${item.subject}-${item.topic}`}
                  subject={item.subject}
                  topic={item.topic}
                  mastery={item.mastery}
                  errors={item.consecutive_errors}
                />
              ))}
            </section>
          ) : null}

          {data.strengths.length ? (
            <section className="panel p-6 animate-fadeUp">
              <h2 className="font-display text-xl text-ink-950">優勢</h2>
              <ul className="mt-4 space-y-2">
                {data.strengths.map((s) => (
                  <li key={s} className="rounded-xl bg-accent-50 px-3 py-2 text-sm text-accent-900">
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
