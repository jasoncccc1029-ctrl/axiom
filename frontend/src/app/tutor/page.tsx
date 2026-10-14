"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ErrorState, LoadingBlock, UploadProgress } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { FileUploader } from "@/components/learning/FileUploader";
import { ProblemConfirmation } from "@/components/learning/ProblemConfirmation";
import { TeachingModeSelector } from "@/components/learning/TeachingModeSelector";
import { Chat, type ChatItem } from "@/components/learning/Chat";
import {
  analyzeVisionImage,
  apiGet,
  apiPostJson,
  type AgentRunResponse,
  type LearningOutcomeResponse,
  type Material,
  type NextProblemResponse,
  type PracticeProblem,
  type SystemHealth,
  type VisionAnalyzeResponse,
  type TeachingMode,
} from "@/lib/api";

type BrainHealth = {
  ok: boolean;
  provider: string;
  model: string | null;
  message: string;
};

const ACCEPTED_IMAGE_TYPES = new Set(["image/jpeg", "image/jpg", "image/png", "image/webp"]);
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;

type ChatTurn = ChatItem;

function difficultyLabel(value: number): string {
  if (value < 0.35) return "Easy";
  if (value < 0.55) return "Medium";
  if (value < 0.75) return "Challenging";
  return "Hard";
}

export default function TutorPage() {
  const { push } = useToast();
  const [materials, setMaterials] = useState<Material[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [brainHealth, setBrainHealth] = useState<BrainHealth | null>(null);
  const [visionOk, setVisionOk] = useState(true);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [lastFailedPayload, setLastFailedPayload] = useState<{
    content: string;
    imageName?: string;
  } | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [image, setImage] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [visionResult, setVisionResult] = useState<VisionAnalyzeResponse | null>(null);
  const [confirmedProblem, setConfirmedProblem] = useState("");
  const [visionConfirmed, setVisionConfirmed] = useState(false);
  const [mode, setMode] = useState<TeachingMode>("tutor");
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [recordingId, setRecordingId] = useState<string | null>(null);
  const [practiceLoading, setPracticeLoading] = useState(false);
  const [practiceError, setPracticeError] = useState<string | null>(null);
  const [practiceReco, setPracticeReco] = useState<NextProblemResponse | null>(null);
  const [practiceStarted, setPracticeStarted] = useState(false);
  const [practiceProblem, setPracticeProblem] = useState<PracticeProblem | null>(null);
  const [practiceAnswer, setPracticeAnswer] = useState("");
  const [practiceSubmitting, setPracticeSubmitting] = useState(false);
  const [focusSubject, setFocusSubject] = useState<string | null>(null);
  const [focusTopic, setFocusTopic] = useState<string | null>(null);
  const [focusConcept, setFocusConcept] = useState<string | null>(null);
  const [focusSessionId, setFocusSessionId] = useState<number | null>(null);
  const [evalBannerDismissed, setEvalBannerDismissed] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const selectedIdRef = useRef<number | null>(null);
  const turnsRef = useRef<ChatTurn[]>([]);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    turnsRef.current = turns;
  }, [turns]);

  useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const subject = params.get("subject");
      const topic = params.get("topic");
      const concept = params.get("concept");
      const sid = params.get("session_id");
      const mid = params.get("material_id");
      if (subject) setFocusSubject(subject);
      if (topic) setFocusTopic(topic);
      if (concept) setFocusConcept(concept);
      if (sid && !Number.isNaN(Number(sid))) {
        setFocusSessionId(Number(sid));
        setSessionId(Number(sid));
      }
      if (mid && !Number.isNaN(Number(mid))) {
        setSelectedId(Number(mid));
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const loadHealth = useCallback(async () => {
    try {
      const health = await apiGet<SystemHealth>("/api/system/health");
      const brain = health.text_brain ?? health.ollama;
      const next: BrainHealth = {
        ok: Boolean(brain?.ok),
        provider: brain?.provider || "unknown",
        model: brain?.model ?? null,
        message: brain?.detail || "Brain 未就緒",
      };
      setBrainHealth(next);
      setVisionOk(Boolean(health.vision?.ok ?? health.vision?.reachable));
      return next;
    } catch {
      const fallback: BrainHealth = {
        ok: false,
        provider: "unknown",
        model: null,
        message: "無法檢查 Brain 狀態，請確認後端已啟動。",
      };
      setBrainHealth(fallback);
      setVisionOk(false);
      return fallback;
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list] = await Promise.all([apiGet<Material[]>("/api/materials"), loadHealth()]);
      setMaterials(list);
      setSelectedId((prev) => {
        if (prev != null) return prev;
        if (focusSubject) {
          const match = list.find(
            (item) => item.subject.toLowerCase() === focusSubject.toLowerCase()
          );
          if (match) return match.id;
        }
        return list[0]?.id ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入教材");
    } finally {
      setLoading(false);
    }
  }, [loadHealth, focusSubject]);

  useEffect(() => {
    void load();
  }, [load]);

  const loadPractice = useCallback(async () => {
    setPracticeLoading(true);
    setPracticeError(null);
    try {
      const material = materials.find((m) => m.id === selectedId) ?? null;
      const params = new URLSearchParams();
      const subject = focusSubject || material?.subject || null;
      if (subject) params.set("subject", subject);
      if (focusTopic) params.set("topic", focusTopic);
      if (focusConcept) params.set("concept", focusConcept);
      if (sessionId) params.set("session_id", String(sessionId));
      // Engine resolves recommendation + learning-state server-side; avoid client waterfall.
      const qs = params.toString();
      const data = await apiGet<NextProblemResponse>(
        `/api/student/next-problem${qs ? `?${qs}` : ""}`
      );
      setPracticeReco(data);
      if (data.problem?.subject) setFocusSubject(data.problem.subject);
      if (data.problem?.topic) setFocusTopic(data.problem.topic);
      if (data.problem?.concept) setFocusConcept(data.problem.concept);
    } catch (err) {
      setPracticeError(err instanceof Error ? err.message : "無法載入練習推薦");
    } finally {
      setPracticeLoading(false);
    }
  }, [materials, selectedId, sessionId, focusSubject, focusTopic, focusConcept]);

  useEffect(() => {
    if (!loading && !error) void loadPractice();
  }, [loading, error, loadPractice]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, sending, chatError, visionResult, analyzing]);

  const selected = materials.find((m) => m.id === selectedId) ?? null;

  function clearImage() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setImage(null);
    setPreviewUrl(null);
    setImageError(null);
    setUploadPct(null);
    setVisionResult(null);
    setConfirmedProblem("");
    setVisionConfirmed(false);
    setAnalyzing(false);
  }

  async function handlePickImage(file: File | null) {
    if (!visionOk) {
      push("Vision 未就緒（本機 VLM）。仍可文字練習／對話。", "error");
      return;
    }
    clearImage();
    if (!file) return;

    const mime = file.type.toLowerCase();
    if (!ACCEPTED_IMAGE_TYPES.has(mime) && !/\.(jpe?g|png|webp)$/i.test(file.name)) {
      setImageError("僅支援 JPG / JPEG / PNG / WEBP。");
      return;
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setImageError("圖片過大，上限 5 MB。");
      return;
    }

    const url = URL.createObjectURL(file);
    setImage(file);
    setPreviewUrl(url);
    setImageError(null);
    setAnalyzing(true);
    setUploadPct(0);

    try {
      const result = await analyzeVisionImage(file, setUploadPct);
      setVisionResult(result);
      setConfirmedProblem(result.analysis.problem_text);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "圖片分析失敗";
      setImageError(msg);
      push(msg, "error");
    } finally {
      setAnalyzing(false);
      setUploadPct(null);
    }
  }

  async function sendToProvider(
    content: string,
    imageName?: string,
    modeOverride?: TeachingMode
  ) {
    setSending(true);
    setChatError(null);
    setLastFailedPayload(null);
    const effectiveMode = modeOverride ?? mode;

    try {
      const res = await apiPostJson<AgentRunResponse>("/api/agent/run", {
        message: content,
        material_id: selectedIdRef.current,
        problem_id: practiceProblem?.id ?? practiceReco?.problem?.id ?? null,
        confirmed_problem: imageName ? confirmedProblem : null,
        input_type: imageName ? "image" : "text",
        subject:
          practiceProblem?.subject ??
          practiceReco?.problem?.subject ??
          focusSubject ??
          visionResult?.analysis.subject ??
          selected?.subject ??
          null,
        topic:
          practiceProblem?.topic ??
          practiceReco?.problem?.topic ??
          focusTopic ??
          visionResult?.analysis.topic ??
          null,
        mode: effectiveMode,
        conversation_id: conversationId,
        session_id: sessionId,
      });

      setTurns((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: res.final_answer,
          model: res.model,
          trace: res,
          outcomeRecorded: Boolean(res.learning_trace?.mastery_update),
        },
      ]);
      setConversationId(res.conversation_id);
      if (res.session_id) setSessionId(res.session_id);
      clearImage();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "發送失敗";
      setChatError(msg);
      setLastFailedPayload({ content, imageName });
      push(msg, "error");
      await loadHealth();
    } finally {
      setSending(false);
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!message.trim() && !image) return;
    if (image && (!visionResult || !visionConfirmed)) {
      push("請先確認題目", "error");
      return;
    }
    if (brainHealth && !brainHealth.ok) {
      push(brainHealth.message, "error");
      return;
    }

    const content =
      message.trim() ||
      visionResult?.analysis.problem_text ||
      "（已上傳題目圖片，請依 Vision 分析協助教學）";
    const imageName = image?.name;
    setTurns((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "user",
        content,
        imageName,
        imagePreviewUrl: previewUrl ?? undefined,
      },
    ]);
    setMessage("");
    await sendToProvider(content, imageName);
  }

  async function handleRetry() {
    if (!lastFailedPayload || sending) return;
    await sendToProvider(lastFailedPayload.content, lastFailedPayload.imageName);
  }

  async function handleRecordOutcome(turn: ChatTurn, correct: boolean) {
    if (!turn.trace) return;
    setRecordingId(turn.id);
    try {
      const subject =
        practiceProblem?.subject ||
        (turn.trace.learning_trace?.student_state?.subject as string | undefined) ||
        focusSubject ||
        visionResult?.analysis.subject ||
        selected?.subject;
      const topic =
        practiceProblem?.topic ||
        (turn.trace.learning_trace?.student_state?.topic as string | undefined) ||
        focusTopic ||
        visionResult?.analysis.topic;
      if (!subject || !topic) {
        push("缺少科目／主題，無法記錄學習結果。請先從推薦進入練習。", "error");
        return;
      }
      let userAnswer = practiceAnswer.trim();
      if (!userAnswer) {
        const idx = turnsRef.current.findIndex((item) => item.id === turn.id);
        for (let i = idx - 1; i >= 0; i -= 1) {
          if (turnsRef.current[i]?.role === "user") {
            userAnswer = turnsRef.current[i].content;
            break;
          }
        }
      }
      const outcome = await apiPostJson<LearningOutcomeResponse>("/api/learning/outcome", {
        subject,
        topic,
        concept: practiceProblem?.concept ?? focusConcept ?? undefined,
        correct,
        mistake_pattern: correct ? null : "student_marked_incorrect",
        mode: turn.trace.mode,
        session_id: turn.trace.session_id ?? focusSessionId ?? sessionId,
        conversation_id: turn.trace.conversation_id,
        question_id: turn.trace.question_id,
        trace_id: turn.trace.trace_id,
        answer: userAnswer ? userAnswer.slice(0, 500) : null,
        problem_id: practiceProblem ? practiceProblem.id : undefined,
      });
      setTurns((prev) =>
        prev.map((item) =>
          item.id === turn.id
            ? {
                ...item,
                outcomeRecorded: true,
                trace: item.trace
                  ? {
                      ...item.trace,
                      learning_trace: outcome.learning_trace,
                      recommendation: outcome.recommendation,
                    }
                  : item.trace,
              }
            : item
        )
      );
      push(correct ? "對" : "錯", "success");
      if (practiceProblem) {
        setPracticeStarted(false);
        setPracticeAnswer("");
        setPracticeProblem(null);
        await loadPractice();
      }
    } catch (err) {
      push(err instanceof Error ? err.message : "記錄失敗", "error");
    } finally {
      setRecordingId(null);
    }
  }

  function handleStartPractice() {
    if (!practiceReco?.problem) return;
    setPracticeProblem(practiceReco.problem);
    setPracticeStarted(true);
    setPracticeAnswer("");
  }

  async function submitPractice(correct: boolean | null) {
    if (!practiceProblem || practiceSubmitting) return;
    if (correct === null && !practiceAnswer.trim()) {
      push("請作答", "error");
      return;
    }
    setPracticeSubmitting(true);
    try {
      const outcome = await apiPostJson<LearningOutcomeResponse>("/api/learning/outcome", {
        subject: practiceProblem.subject,
        topic: practiceProblem.topic,
        concept: practiceProblem.concept ?? undefined,
        correct: correct ?? undefined,
        mistake_pattern: correct === false ? "practice_incorrect" : null,
        mode: mode === "direct_solve" || mode === "full_solution" ? "tutor" : mode,
        session_id: sessionId,
        answer: practiceAnswer.trim() || null,
        problem_id: practiceProblem.id,
      });
      const checked = Boolean(outcome.bank_verified);
      const resultCorrect = Boolean(
        (outcome.learning_trace?.learning_result as { correct?: boolean } | undefined)?.correct
      );
      push(resultCorrect ? "對" : "錯", checked ? "success" : "info");
      setPracticeStarted(false);
      setPracticeAnswer("");
      setPracticeProblem(null);
      await loadPractice();
    } catch (err) {
      push(err instanceof Error ? err.message : "記錄失敗", "error");
    } finally {
      setPracticeSubmitting(false);
    }
  }

  async function handlePracticeOutcome(correct: boolean) {
    await submitPractice(correct);
  }

  async function handlePracticeSubmit() {
    await submitPractice(null);
  }

  async function askTutorAboutPractice() {
    if (!practiceProblem || sending) return;
    const content = `請用 hint 協助我練習這題（不要直接給答案）：\n${practiceProblem.question}\n\n我的想法：${practiceAnswer.trim() || "（尚未作答）"}`;
    setTurns((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content },
    ]);
    const hintMode: TeachingMode =
      mode === "direct_solve" || mode === "full_solution" ? "hint" : mode;
    await sendToProvider(content, undefined, hintMode);
  }

  const previewProblem = practiceStarted ? practiceProblem : practiceReco?.problem ?? null;

  const whyReason = practiceReco?.selection_reason
    ? [
        ...(practiceReco.selection_reason.student_reasons ?? []),
        practiceReco.selection_reason.error_pattern_match
          ? practiceReco.selection_reason.error_concept
            ? `對應錯因概念：${practiceReco.selection_reason.error_concept}`
            : "對應你近期的錯因模式"
          : null,
        practiceReco.selection_reason.recommendation_used
          ? "依目前推薦策略選題"
          : null,
        practiceReco.selection_reason.difficulty_match ? "難度符合目前建議" : null,
      ]
        .filter(Boolean)
        .join(" · ") || "依你的學習狀態選題"
    : null;

  return (
    <div className="-mb-10 flex h-[calc(100dvh-4rem)] flex-col md:h-[calc(100dvh-2rem)]">
      {loading ? <LoadingBlock rows={4} /> : null}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {!loading && !error ? (
        <section className="panel flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-ink-100/80 px-4 py-2 sm:px-5">
            <div className="min-w-0 flex-1">
              {materials.length > 0 ? (
                <label className="block">
                  <span className="sr-only">教材</span>
                  <select
                    className="w-full max-w-md truncate rounded-xl border border-ink-200 bg-white px-3 py-1.5 text-sm text-ink-900 outline-none ring-accent-400/30 focus:ring-2"
                    value={selectedId ?? ""}
                    onChange={(e) => setSelectedId(Number(e.target.value))}
                  >
                    {materials.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.subject} · {m.title}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="text-sm text-ink-600">
                  尚無教材（仍可練習題庫／對話）。
                  <Link href="/materials" className="ml-2 text-accent-700 hover:underline">
                    上傳教材
                  </Link>
                </p>
              )}
              {focusSubject || focusTopic ? (
                <p className="mt-0.5 truncate text-xs text-ink-400">
                  {[focusSubject, focusTopic, focusConcept].filter(Boolean).join(" · ")}
                </p>
              ) : null}
            </div>
            {brainHealth && !brainHealth.ok ? (
              <button
                type="button"
                onClick={() => void loadHealth()}
                className="max-w-[14rem] truncate text-xs text-red-600 hover:underline"
              >
                {brainHealth.message}
              </button>
            ) : brainHealth?.ok ? (
              <span className="max-w-[12rem] truncate text-xs text-ink-400">
                {brainHealth.provider}
                {brainHealth.model ? ` · ${brainHealth.model}` : ""}
              </span>
            ) : null}
          </div>

          {previewProblem || practiceLoading || practiceError || practiceReco?.message ? (
            <div className="shrink-0 border-b border-ink-100/80 px-4 py-2.5 sm:px-5">
              {practiceLoading ? (
                <p className="text-sm text-ink-400">正在依你的學習狀態選題…</p>
              ) : null}
              {practiceError ? (
                <ErrorState message={practiceError} onRetry={() => void loadPractice()} />
              ) : null}
              {!practiceLoading && !previewProblem && practiceReco?.message ? (
                <p className="text-sm text-ink-500">
                  {practiceReco.message.includes("No problems available")
                    ? "這個科目／主題還沒有題庫題目，仍可直接在下方對話練習。"
                    : practiceReco.message}{" "}
                  <Link
                    href="/"
                    className="font-medium text-accent-700 hover:text-ink-950"
                  >
                    回總覽看推薦 →
                  </Link>
                </p>
              ) : null}

              {previewProblem && !practiceStarted ? (
                <div className="flex flex-wrap items-center gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink-900">
                      {previewProblem.topic}
                      {previewProblem.concept ? ` · ${previewProblem.concept}` : ""}
                      <span className="font-normal text-ink-400">
                        {` · ${difficultyLabel(previewProblem.difficulty)}`}
                      </span>
                    </p>
                    {whyReason ? (
                      <details className="mt-1 text-xs text-ink-500">
                        <summary className="cursor-pointer select-none hover:text-ink-700">
                          為什麼出這題
                        </summary>
                        <p className="mt-1 leading-relaxed text-ink-600">{whyReason}</p>
                      </details>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => void loadPractice()}
                    disabled={practiceLoading}
                    className="text-xs text-ink-400 hover:text-ink-700 disabled:opacity-40"
                  >
                    換題
                  </button>
                  <button
                    type="button"
                    onClick={handleStartPractice}
                    className="rounded-xl bg-ink-950 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800"
                  >
                    開始
                  </button>
                </div>
              ) : null}

              {previewProblem && practiceStarted ? (
                <div className="max-h-[28vh] space-y-2.5 overflow-y-auto overscroll-contain pr-1">
                  <div className="flex items-center justify-between gap-2">
                    <p className="truncate text-xs text-ink-400">
                      {previewProblem.topic}
                      {previewProblem.concept ? ` · ${previewProblem.concept}` : ""}
                      {` · ${difficultyLabel(previewProblem.difficulty)}`}
                    </p>
                    <button
                      type="button"
                      onClick={() => void loadPractice()}
                      disabled={practiceLoading}
                      className="shrink-0 text-xs text-ink-400 hover:text-ink-700 disabled:opacity-40"
                    >
                      換題
                    </button>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-900">
                    {practiceProblem?.question}
                  </p>
                  <textarea
                    value={practiceAnswer}
                    onChange={(e) => setPracticeAnswer(e.target.value)}
                    placeholder="作答"
                    rows={2}
                    className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm outline-none ring-accent-400/30 focus:ring-2"
                    disabled={practiceSubmitting}
                  />
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => void handlePracticeSubmit()}
                      disabled={practiceSubmitting || !practiceAnswer.trim()}
                      className="rounded-xl bg-ink-950 px-3 py-1.5 text-sm text-white hover:bg-ink-800 disabled:opacity-50"
                    >
                      提交
                    </button>
                    <button
                      type="button"
                      onClick={() => void handlePracticeOutcome(true)}
                      disabled={practiceSubmitting}
                      className="rounded-xl border border-ink-200 bg-white px-3 py-1.5 text-sm text-ink-800 hover:bg-ink-50 disabled:opacity-50"
                    >
                      對
                    </button>
                    <button
                      type="button"
                      onClick={() => void handlePracticeOutcome(false)}
                      disabled={practiceSubmitting}
                      className="rounded-xl border border-ink-200 bg-white px-3 py-1.5 text-sm text-ink-800 hover:bg-ink-50 disabled:opacity-50"
                    >
                      錯
                    </button>
                    <button
                      type="button"
                      onClick={() => void askTutorAboutPractice()}
                      disabled={sending || practiceSubmitting}
                      className="rounded-xl border border-ink-200 bg-white px-3 py-1.5 text-sm text-ink-600 hover:bg-ink-50 disabled:opacity-50"
                    >
                      提示
                    </button>
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain scroll-smooth px-4 py-4 sm:px-6">
            {focusSessionId && !evalBannerDismissed ? (
              <div className="mb-4 flex items-start justify-between gap-3 rounded-xl border border-accent-200 bg-accent-50/80 px-3 py-2.5 text-sm text-accent-950">
                <p>
                  試驗模式 · {[focusSubject, focusTopic].filter(Boolean).join(" · ")}
                  {` · session #${focusSessionId}`}
                </p>
                <button
                  type="button"
                  onClick={() => setEvalBannerDismissed(true)}
                  className="text-xs text-accent-800 hover:underline"
                >
                  關閉
                </button>
              </div>
            ) : null}
            {turns.length === 0 && !sending ? (
              <div className="flex min-h-[40vh] flex-col items-center justify-center px-4 text-center">
                <p className="text-base font-medium text-ink-800">對話與講解會出現在這裡</p>
                <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-500">
                  {previewProblem && !practiceStarted
                    ? "先按「開始」作答，Axiom 會依你的掌握度與錯因出題；內容變多時可在此區上下滑動。"
                    : focusSubject && focusTopic
                      ? `目前焦點：${focusSubject} · ${focusTopic}。直接提問，或從上方開始練習。`
                      : "從總覽選推薦進入，或直接提問。無教材也能練題庫。"}
                </p>
                {!previewProblem && !focusSubject ? (
                  <Link
                    href="/"
                    className="mt-4 rounded-xl bg-ink-950 px-4 py-2 text-sm text-white hover:bg-ink-800"
                  >
                    看推薦下一步
                  </Link>
                ) : null}
              </div>
            ) : null}
            <Chat
              turns={turns}
              onRecordOutcome={(turn, correct) => void handleRecordOutcome(turn, correct)}
              recordingId={recordingId}
              allowOutcomeMark={Boolean(
                (focusSubject && focusTopic) ||
                  practiceProblem ||
                  practiceReco?.problem
              )}
            />
            {sending ? (
              <div
                className="mt-5 inline-flex items-center gap-1.5 rounded-2xl border border-ink-100 bg-ink-50/80 px-4 py-3"
                aria-live="polite"
                aria-label="AI 回覆中"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-ink-400 animate-typingDot [animation-delay:0ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-ink-400 animate-typingDot [animation-delay:160ms]" />
                <span className="h-1.5 w-1.5 rounded-full bg-ink-400 animate-typingDot [animation-delay:320ms]" />
              </div>
            ) : null}
            {chatError ? (
              <div className="mt-4 max-w-xl">
                <ErrorState message={chatError} onRetry={handleRetry} />
              </div>
            ) : null}
            <div ref={bottomRef} />
          </div>

          <form
            onSubmit={handleSend}
            className="shrink-0 border-t border-ink-100/80 bg-white/50 px-4 py-3 backdrop-blur-sm sm:px-5"
          >
            {analyzing || uploadPct !== null ? (
              <div className="mb-3">
                <UploadProgress percent={uploadPct ?? 15} />
              </div>
            ) : null}

            {imageError ? (
              <div className="mb-3">
                <ErrorState message={imageError} onRetry={clearImage} />
              </div>
            ) : null}

            {image && previewUrl ? (
              <div className="mb-3 flex items-center gap-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={previewUrl}
                  alt=""
                  className="h-12 w-12 rounded-xl object-cover"
                />
                <button
                  type="button"
                  onClick={clearImage}
                  className="text-xs text-red-600/90 hover:underline"
                >
                  移除
                </button>
              </div>
            ) : null}

            {visionResult ? (
              <div className="mb-3">
                <ProblemConfirmation
                  value={confirmedProblem}
                  onChange={(value) => {
                    setConfirmedProblem(value);
                    setVisionConfirmed(false);
                  }}
                  confirmed={visionConfirmed}
                  onConfirm={() => setVisionConfirmed(true)}
                  disabled={sending}
                />
              </div>
            ) : null}

            <div className="flex items-end gap-2 rounded-2xl border border-ink-200/90 bg-white p-2 shadow-soft focus-within:border-ink-300 focus-within:ring-2 focus-within:ring-accent-400/30">
              <FileUploader
                accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                onSelect={(file) => void handlePickImage(file)}
                disabled={sending || analyzing}
                label="附加圖片"
                iconOnly
              />
              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="問題"
                className="min-w-0 flex-1 bg-transparent px-2 py-2.5 text-sm outline-none placeholder:text-ink-400"
                disabled={sending || analyzing}
              />
              <TeachingModeSelector value={mode} onChange={setMode} disabled={sending} />
              <button
                type="submit"
                disabled={sending || analyzing || Boolean(brainHealth && !brainHealth.ok)}
                className="shrink-0 rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-ink-800 disabled:opacity-50"
              >
                {sending ? "…" : "送出"}
              </button>
            </div>
          </form>
        </section>
      ) : null}
    </div>
  );
}
