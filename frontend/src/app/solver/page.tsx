"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { X } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { FileUploader } from "@/components/learning/FileUploader";
import { VisionResultCard } from "@/components/learning/VisionResultCard";
import { ErrorState, LoadingBlock, UploadProgress } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { VerificationBadge } from "@/components/learning/VerificationBadge";
import {
  analyzeVisionImage,
  apiGet,
  apiPostJson,
  type ProblemSolveResponse,
  type RecommendationsResponse,
  type VisionAnalyzeResponse,
} from "@/lib/api";

const ACCEPTED_IMAGE_TYPES = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

const SUBJECT_OPTIONS = ["高二數學", "物理", "英文", "程式"] as const;

function mapVisionSubject(raw: string | null | undefined): string | null {
  const value = (raw || "").trim().toLowerCase();
  if (!value) return null;
  if (SUBJECT_OPTIONS.includes(raw as (typeof SUBJECT_OPTIONS)[number])) return raw as string;
  if (value.includes("math") || value.includes("數學")) return "高二數學";
  if (value.includes("phys") || value.includes("物理")) return "物理";
  if (value.includes("eng") || value.includes("英文") || value.includes("english")) return "英文";
  if (value.includes("program") || value.includes("code") || value.includes("程式")) return "程式";
  return null;
}

export default function SolverPage() {
  const { push } = useToast();
  const [problem, setProblem] = useState("");
  const [subject, setSubject] = useState("高二數學");
  const [topic, setTopic] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProblemSolveResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [visionResult, setVisionResult] = useState<VisionAnalyzeResponse | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const qSubject = params.get("subject");
    const qTopic = params.get("topic");
    if (qSubject?.trim()) setSubject(qSubject.trim());
    if (qTopic?.trim()) setTopic(qTopic.trim());

    void (async () => {
      if (qSubject?.trim()) return;
      try {
        const recs = await apiGet<RecommendationsResponse>("/api/recommendations");
        const top = recs.recommendations[0];
        if (top?.subject) setSubject(top.subject);
        if (top?.topic && !qTopic?.trim()) setTopic(top.topic);
      } catch {
        /* keep defaults */
      }
    })();
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function clearImage() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(null);
    setVisionResult(null);
    setImageError(null);
    setUploadPct(null);
    setAnalyzing(false);
  }

  async function handleImageSelect(file: File) {
    const mime = file.type.toLowerCase();
    if (!ACCEPTED_IMAGE_TYPES.has(mime) && !/\.(jpe?g|png|webp)$/i.test(file.name)) {
      setImageError("僅支援 JPG / JPEG / PNG / WEBP。");
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError("圖片過大，上限 5 MB。");
      return;
    }

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    setImageError(null);
    setVisionResult(null);
    setAnalyzing(true);
    setUploadPct(0);
    setResult(null);
    setError(null);

    try {
      const analyzed = await analyzeVisionImage(file, setUploadPct);
      setVisionResult(analyzed);
      const text =
        analyzed.analysis.problem_text?.trim() ||
        analyzed.analysis.diagram_description?.trim() ||
        "";
      if (text) {
        setProblem(text);
      } else {
        push("已上傳圖片，但未能辨識題目文字，請手動輸入或改拍清楚一點。", "error");
      }
      const mapped = mapVisionSubject(analyzed.analysis.subject);
      if (mapped) setSubject(mapped);
      if (analyzed.analysis.topic) setTopic(analyzed.analysis.topic);
      push("題目已從圖片辨識，可直接解題或先修改文字。", "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "圖片分析失敗";
      setImageError(msg);
      push(msg, "error");
    } finally {
      setAnalyzing(false);
      setUploadPct(null);
    }
  }

  async function handleSolve(e: React.FormEvent) {
    e.preventDefault();
    if (!problem.trim()) {
      push(previewUrl ? "請等待圖片辨識完成，或手動輸入題目" : "請輸入題目或上傳圖片", "error");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await apiPostJson<ProblemSolveResponse>("/api/problems/solve", {
        problem: problem.trim(),
        subject,
        topic: topic || undefined,
      });
      setResult(data);
      if (data.subject) setSubject(data.subject);
      if (data.topic) setTopic(data.topic);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "解題失敗";
      setError(msg);
      push(msg, "error");
    } finally {
      setLoading(false);
    }
  }

  const tutorHref = `/tutor?subject=${encodeURIComponent(subject)}${
    topic ? `&topic=${encodeURIComponent(topic)}` : ""
  }`;
  const busy = loading || analyzing;

  return (
    <div>
      <PageHeader title="解題" />

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <form onSubmit={handleSolve} className="panel space-y-4 p-5">
          <label className="block text-sm">
            <span className="mb-1 block text-xs text-ink-400">科目</span>
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2"
            >
              {SUBJECT_OPTIONS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="mb-1 block text-xs text-ink-400">主題（選填，用於個人化解說）</span>
            <input
              value={topic ?? ""}
              onChange={(e) => setTopic(e.target.value.trim() ? e.target.value : null)}
              placeholder="例如：二次函數"
              className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2"
            />
            {topic ? (
              <p className="mt-1 text-xs text-ink-400">
                目前焦點：{subject} · {topic}（會帶入你的掌握度與錯因）
              </p>
            ) : (
              <p className="mt-1 text-xs text-ink-400">
                有主題時，解題會依你的學習狀態調整說明。
              </p>
            )}
          </label>

          <div className="block text-sm">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-xs text-ink-400">題目</span>
              <FileUploader
                accept="image/jpeg,image/jpg,image/png,image/webp,.jpg,.jpeg,.png,.webp"
                label="上傳圖片"
                disabled={busy}
                onSelect={(file) => void handleImageSelect(file)}
              />
            </div>
            <textarea
              value={problem}
              onChange={(e) => setProblem(e.target.value)}
              rows={8}
              placeholder="輸入題目，或上傳題目圖片自動辨識"
              disabled={analyzing}
              className="w-full rounded-xl border border-ink-200 bg-ink-50/40 px-3 py-2.5 outline-none ring-accent-400 focus:ring-2 disabled:opacity-60"
            />
            <p className="mt-1.5 text-xs text-ink-400">
              支援 JPG / PNG / WEBP（≤ 5 MB）。辨識後可再編輯文字再解題。
            </p>
          </div>

          {previewUrl ? (
            <div className="relative overflow-hidden rounded-xl border border-ink-100 bg-ink-50/40">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewUrl}
                alt="題目圖片預覽"
                className="max-h-56 w-full object-contain bg-white"
              />
              <button
                type="button"
                onClick={clearImage}
                disabled={busy}
                className="absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-ink-600 shadow-sm hover:text-ink-950 disabled:opacity-50"
                aria-label="移除圖片"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : null}

          {analyzing || uploadPct !== null ? (
            <UploadProgress percent={uploadPct ?? 15} label="辨識題目中…" />
          ) : null}

          {imageError ? <ErrorState message={imageError} onRetry={() => setImageError(null)} /> : null}

          {visionResult ? <VisionResultCard result={visionResult.analysis} /> : null}

          <button
            type="submit"
            disabled={busy || !problem.trim()}
            className="rounded-xl bg-ink-950 px-4 py-2.5 text-sm text-white disabled:opacity-60"
          >
            {analyzing ? "辨識中…" : loading ? "解題中…" : "解題"}
          </button>
        </form>

        <div className="space-y-4">
          {loading ? <LoadingBlock rows={5} /> : null}
          {error ? <ErrorState message={error} onRetry={() => setError(null)} /> : null}
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
              <section className="panel p-4">
                {result.personalized ? (
                  <p className="text-xs text-accent-800">
                    已依你的學習狀態調整解說
                    {result.subject
                      ? `（${[result.subject, result.topic].filter(Boolean).join(" · ")}）`
                      : ""}
                  </p>
                ) : (
                  <p className="text-xs text-ink-400">
                    未帶入個人化焦點；選科目／主題後再解，Axiom 會更懂你。
                  </p>
                )}
                <p className="mt-2 text-sm text-ink-600">
                  解題完成後，可回到教學依你的弱點繼續練習。
                </p>
                <Link
                  href={tutorHref}
                  className="mt-3 inline-flex text-sm font-medium text-accent-700 hover:text-ink-950"
                >
                  在教學中繼續 →
                </Link>
              </section>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
