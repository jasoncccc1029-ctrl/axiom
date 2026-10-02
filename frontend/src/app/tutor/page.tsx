"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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
  type OllamaHealth,
  type PracticeProblem,
  type RecommendationsResponse,
  type StudentLearningState,
  type VisionAnalyzeResponse,
  type TeachingMode,
} from "@/lib/api";

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
  const [ollamaHealth, setOllamaHealth] = useState<OllamaHealth | null>(null);
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
  const bottomRef = useRef<HTMLDivElement>(null);
  const selectedIdRef = useRef<number | null>(null);

  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const loadHealth = useCallback(async () => {
    try {
      const health = await apiGet<OllamaHealth>("/api/ollama/health");
      setOllamaHealth(health);
      return health;
    } catch {
      const fallback: OllamaHealth = {
        ok: false,
        reachable: false,
        model: "llama3.2:latest",
        model_available: false,
        models: [],
        message: "Ollama 未啟動，請執行 ollama serve。",
      };
      setOllamaHealth(fallback);
      return fallback;
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list] = await Promise.all([apiGet<Material[]>("/api/materials"), loadHealth()]);
      setMaterials(list);
      setSelectedId((prev) => prev ?? (list[0]?.id ?? null));
    } catch (err) {
      setError(err instanceof Error ? err.message : "無法載入教材");
    } finally {
      setLoading(false);
    }
  }, [loadHealth]);

  useEffect(() => {
    void load();
  }, [load]);

  const loadPractice = useCallback(async () => {
    setPracticeLoading(true);
    setPracticeError(null);
    try {
      const material = materials.find((m) => m.id === selectedId) ?? null;
      const params = new URLSearchParams();
      if (material?.subject) params.set("subject", material.subject);
      if (sessionId) params.set("session_id", String(sessionId));
      try {
        const recs = await apiGet<RecommendationsResponse>("/api/recommendations");
        const rec = recs.recommendations.find(
          (item) => Boolean(material?.subject) && item.subject === material?.subject
        );
        if (rec?.topic) params.set("topic", rec.topic);
        if (rec?.concept) params.set("concept", rec.concept);
      } catch {
        /* engine still resolves from stored recommendation / learning state */
      }
      if (!params.get("topic") && material?.subject) {
        try {
          const state = await apiGet<StudentLearningState>(
            `/api/student/learning-state?subject=${encodeURIComponent(material.subject)}`
          );
          const fallbackTopic = state.current_topic || state.recent_errors?.[0]?.topic;
          const fallbackConcept =
            state.current_concept || state.recent_errors?.[0]?.concept;
          if (fallbackTopic) params.set("topic", fallbackTopic);
          if (fallbackConcept) params.set("concept", fallbackConcept);
        } catch {
          /* optional */
        }
      }
      const qs = params.toString();
      const data = await apiGet<NextProblemResponse>(
        `/api/student/next-problem${qs ? `?${qs}` : ""}`
      );
      setPracticeReco(data);
    } catch (err) {
      setPracticeError(err instanceof Error ? err.message : "無法載入練習推薦");
    } finally {
      setPracticeLoading(false);
    }
  }, [materials, selectedId, sessionId]);

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
        confirmed_problem: imageName ? confirmedProblem : null,
        input_type: imageName ? "image" : "text",
        subject:
          practiceProblem?.subject ??
          visionResult?.analysis.subject ??
          selected?.subject ??
          "general",
        topic:
          practiceProblem?.topic ??
          visionResult?.analysis.topic ??
          "general",
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
      await loadHealth();
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
    if (ollamaHealth && !ollamaHealth.ok) {
      push(ollamaHealth.message, "error");
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
        (turn.trace.learning_trace?.student_state?.subject as string | undefined) ||
        visionResult?.analysis.subject ||
        selected?.subject ||
        "general";
      const topic =
        (turn.trace.learning_trace?.student_state?.topic as string | undefined) ||
        visionResult?.analysis.topic ||
        "general";
      const outcome = await apiPostJson<LearningOutcomeResponse>("/api/learning/outcome", {
        subject: practiceProblem?.subject || subject,
        topic: practiceProblem?.topic || topic,
        concept: practiceProblem?.concept ?? undefined,
        correct,
        mistake_pattern: correct ? null : "student_marked_incorrect",
        mode: turn.trace.mode,
        session_id: turn.trace.session_id,
        conversation_id: turn.trace.conversation_id,
        question_id: turn.trace.question_id,
        trace_id: turn.trace.trace_id,
        answer: practiceProblem
          ? practiceAnswer.trim() || null
          : turn.content.slice(0, 500),
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

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col md:h-[calc(100vh-4rem)]">
      {loading ? <LoadingBlock rows={4} /> : null}
      {error ? <ErrorState message={error} onRetry={load} /> : null}

      {!loading && !error ? (
        <section className="panel flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-ink-100/80 px-4 py-2.5 sm:px-5">
            <div className="min-w-0 flex-1">
              {materials.length ? (
                <label className="block">
                  <span className="sr-only">教材</span>
                  <select
                    className="w-full max-w-md truncate rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 outline-none ring-accent-400/30 focus:ring-2"
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
              ) : null}
            </div>
            {ollamaHealth && !ollamaHealth.ok ? (
              <button
                type="button"
                onClick={() => void loadHealth()}
                className="max-w-[14rem] truncate text-xs text-red-600 hover:underline"
              >
                {ollamaHealth.message}
              </button>
            ) : null}
          </div>

          {previewProblem || practiceLoading || practiceError ? (
            <div className="border-b border-ink-100/80 px-4 py-3 sm:px-5">
              <div className="flex items-center justify-end">
                <button
                  type="button"
                  onClick={() => void loadPractice()}
                  disabled={practiceLoading || practiceStarted}
                  className="text-xs text-ink-400 hover:text-ink-700 disabled:opacity-40"
                >
                  換題
                </button>
              </div>

              {practiceLoading ? <p className="mt-2 text-sm text-ink-400">…</p> : null}
              {practiceError ? (
                <p className="mt-2 text-sm text-red-600">{practiceError}</p>
              ) : null}

              {previewProblem ? (
                <div className="mt-1 space-y-3">
                  <p className="text-xs text-ink-400">
                    {previewProblem.topic}
                    {previewProblem.concept ? ` · ${previewProblem.concept}` : ""}
                    {` · ${difficultyLabel(previewProblem.difficulty)}`}
                  </p>

                  {!practiceStarted ? (
                    <button
                      type="button"
                      onClick={handleStartPractice}
                      className="rounded-xl bg-ink-950 px-4 py-2 text-sm font-medium text-white hover:bg-ink-800"
                    >
                      開始
                    </button>
                  ) : (
                    <div className="space-y-3">
                      <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink-900">
                        {practiceProblem?.question}
                      </p>
                      <textarea
                        value={practiceAnswer}
                        onChange={(e) => setPracticeAnswer(e.target.value)}
                        placeholder="作答"
                        rows={3}
                        className="w-full rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm outline-none ring-accent-400/30 focus:ring-2"
                        disabled={practiceSubmitting}
                      />
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void handlePracticeSubmit()}
                          disabled={practiceSubmitting || !practiceAnswer.trim()}
                          className="rounded-xl bg-ink-950 px-3 py-2 text-sm text-white hover:bg-ink-800 disabled:opacity-50"
                        >
                          提交
                        </button>
                        <button
                          type="button"
                          onClick={() => void handlePracticeOutcome(true)}
                          disabled={practiceSubmitting}
                          className="rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 hover:bg-ink-50 disabled:opacity-50"
                        >
                          對
                        </button>
                        <button
                          type="button"
                          onClick={() => void handlePracticeOutcome(false)}
                          disabled={practiceSubmitting}
                          className="rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-800 hover:bg-ink-50 disabled:opacity-50"
                        >
                          錯
                        </button>
                        <button
                          type="button"
                          onClick={() => void askTutorAboutPractice()}
                          disabled={sending || practiceSubmitting}
                          className="rounded-xl border border-ink-200 bg-white px-3 py-2 text-sm text-ink-600 hover:bg-ink-50 disabled:opacity-50"
                        >
                          提示
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex-1 overflow-y-auto px-4 py-5 sm:px-6">
            <Chat
              turns={turns}
              onRecordOutcome={(turn, correct) => void handleRecordOutcome(turn, correct)}
              recordingId={recordingId}
            />
            {sending ? (
              <div className="mt-5 max-w-[4.5rem] rounded-2xl border border-ink-100 bg-ink-50/80 px-4 py-3 text-sm text-ink-400 animate-pulseSoft">
                …
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
            className="border-t border-ink-100/80 bg-white/40 px-4 py-4 backdrop-blur-sm sm:px-5"
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
                disabled={sending || analyzing || Boolean(ollamaHealth && !ollamaHealth.ok)}
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
