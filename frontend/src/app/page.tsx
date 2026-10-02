"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingBlock } from "@/components/ui/States";
import {
  apiGet,
  type MemoryResponse,
  type ProgressData,
  type RecommendationsResponse,
  type StudentModel,
} from "@/lib/api";
import { RecommendationCard } from "@/components/learning/RecommendationCard";
import { WeakTopicCard } from "@/components/learning/WeakTopicCard";
import { MasteryTree } from "@/components/learning/MasteryTree";
import { formatMinutes, formatPercent } from "@/lib/utils";

export default function DashboardPage() {
  const [data, setData] = useState<ProgressData | null>(null);
  const [student, setStudent] = useState<StudentModel | null>(null);
  const [memory, setMemory] = useState<MemoryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [progress, recommendationData, studentData, memoryData] = await Promise.all([
        apiGet<ProgressData>("/api/progress"),
        apiGet<RecommendationsResponse>("/api/recommendations"),
        apiGet<StudentModel>("/api/student"),
        apiGet<MemoryResponse>("/api/memory"),
      ]);
      setData(progress);
      setRecommendations(recommendationData);
      setStudent(studentData);
      setMemory(memoryData);
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
  const mistakes = memory?.repeated_mistakes ?? [];
  const recs = recommendations?.recommendations ?? [];

  return (
    <div>
      <PageHeader
        title="總覽"
        action={
          <Link
            href="/tutor"
            className="inline-flex items-center justify-center rounded-xl bg-ink-950 px-4 py-2.5 text-sm text-white hover:bg-ink-800"
          >
            教學
          </Link>
        }
      />

      {loading ? <LoadingBlock rows={5} /> : null}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {!loading && !error && data ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "今日", value: formatMinutes(data.today_study_minutes) },
              { label: "本週", value: `${data.week_questions_completed}` },
              { label: "正確率", value: formatPercent(data.accuracy_rate) },
              {
                label: "弱點",
                value: student?.weak_concepts[0] ?? data.weak_subjects[0] ?? "—",
              },
            ].map((stat) => (
              <div key={stat.label} className="panel p-5">
                <p className="text-xs text-ink-400">{stat.label}</p>
                <p className="mt-3 font-display text-2xl tracking-tight text-ink-950">{stat.value}</p>
              </div>
            ))}
          </div>

          {recs.length ? (
            <section className="panel p-6">
              <h2 className="font-display text-xl text-ink-950">下一步</h2>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {recs.map((item) => (
                  <RecommendationCard key={`${item.subject}-${item.topic}`} {...item} />
                ))}
              </div>
            </section>
          ) : null}

          <div className="grid gap-4 lg:grid-cols-2">
            {student?.mastery.length ? (
              <section className="panel p-6">
                <h2 className="font-display text-xl text-ink-950">掌握</h2>
                <div className="mt-4">
                  <MasteryTree mastery={student.mastery} />
                </div>
              </section>
            ) : null}
            {mistakes.length ? (
              <section className="panel p-6">
                <h2 className="font-display text-xl text-ink-950">錯因</h2>
                <ul className="mt-4 space-y-2">
                  {mistakes.map((item) => (
                    <li
                      key={`${item.pattern}-${item.topic}`}
                      className="rounded-xl bg-red-50/70 px-3 py-2 text-sm text-ink-700"
                    >
                      {item.pattern} · {item.count}
                      {item.topic ? ` · ${item.topic}` : ""}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>

          {weakTopics.length ? (
            <section className="panel p-6">
              <h2 className="font-display text-xl text-ink-950">弱點</h2>
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
        </div>
      ) : null}
    </div>
  );
}
