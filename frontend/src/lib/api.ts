/** Same-origin base. Next.js rewrites `/api/*` → FastAPI `127.0.0.1:8000`. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";


export type Material = {
  id: number;
  title: string;
  subject: string;
  file_type: string;
  original_filename: string | null;
  description: string | null;
  mime_type?: string | null;
  size_bytes?: number;
  ingestion_status?: string;
  page_count?: number;
  created_at: string;
};

export type ProgressData = {
  today_study_minutes: number;
  week_questions_completed: number;
  accuracy_rate: number;
  weak_subjects: string[];
  recommended: string[];
  total_study_minutes: number;
  total_questions: number;
  subject_abilities: { subject: string; score: number; questions: number }[];
  strengths: string[];
  topic_mastery: {
    subject: string;
    topic: string;
    mastery: number;
    attempts: number;
    consecutive_errors: number;
  }[];
  accuracy_trend: { date: string; attempted: number; correct: number; accuracy: number }[];
  mistake_patterns: { pattern: string; count: number; subject?: string; topic?: string }[];
  learning_history: {
    activity_type: string;
    subject?: string;
    topic?: string;
    duration_minutes: number;
    questions_attempted: number;
    questions_correct: number;
    created_at: string;
  }[];
  enough_data: boolean;
  data_message: string | null;
};

export type SolveResult = {
  problem: string;
  steps: { step: number; title: string; content: string }[];
  answer: string;
  verification: { status?: string; message?: string };
  provider: string;
  model?: string;
};

export type ChatResponse = {
  reply: string;
  provider: string;
  model: string;
  material_id: number | null;
};

export type OllamaHealth = {
  ok: boolean;
  reachable: boolean;
  model: string;
  model_available: boolean;
  models: string[];
  message: string;
};

export type SystemComponentHealth = {
  ok: boolean;
  detail: string;
  provider?: string | null;
  model?: string | null;
  reachable?: boolean | null;
};

export type SystemHealth = {
  ok: boolean;
  backend: SystemComponentHealth;
  text_brain: SystemComponentHealth;
  ollama: SystemComponentHealth;
  vision: SystemComponentHealth;
  version: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") return data.detail;
    return JSON.stringify(data?.detail ?? data);
  } catch {
    return res.statusText || "Request failed";
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json() as Promise<T>;
}

export async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
}

export async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError(await parseError(res), res.status);
  return res.json() as Promise<T>;
}

export function uploadMaterial(
  form: FormData,
  onProgress?: (pct: number) => void
): Promise<Material> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/materials/upload`);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as Material);
      } else {
        try {
          const data = JSON.parse(xhr.responseText);
          reject(new ApiError(data.detail ?? "Upload failed", xhr.status));
        } catch {
          reject(new ApiError("Upload failed", xhr.status));
        }
      }
    };
    xhr.onerror = () => reject(new ApiError("Network error during upload", 0));
    xhr.send(form);
  });
}

export type VisionAnalysis = {
  content_type: string;
  subject: string;
  topic: string;
  problem_text: string;
  detected_formula: string[];
  diagram_description: string;
  detected_tables: string[][][];
  question_type: string;
  confidence: number;
  provider: string;
  model: string | null;
};

export type VisionAnalyzeResponse = {
  analysis: VisionAnalysis;
  stored_filename: string;
  mime_type: string;
  size: number;
  timing?: {
    response_time_ms: number;
    image_size_bytes: number;
    total_duration_ns?: number;
  };
};

export type TeachingMode =
  | "hint"
  | "tutor"
  | "direct_solve"
  | "socratic"
  | "step_by_step"
  | "full_solution"
  | "concept"
  | "error_diagnosis";

export type AgentRunResponse = {
  trace_id: string;
  conversation_id: number;
  session_id?: number | null;
  question_id?: number | null;
  steps: { index: number; action: string; tool: string | null; reason: string }[];
  tool_calls: { tool: string; ok: boolean; execution_time_ms: number; summary: string }[];
  sources: {
    document_id: number;
    document_title: string;
    page: number;
    chunk_id: number;
    score: number;
  }[];
  adaptive_decision: {
    strategy?: string;
    explanation_level?: string;
    question_difficulty?: string;
    hint_level?: string;
    sequence?: string[];
    mastery?: number | null;
    evidence_attempts?: number;
    enough_data?: boolean;
    why?: string;
    mode_adaptation?: string;
    requested_mode?: string;
    adapted_mode?: string;
  };
  final_answer: string;
  verification_status: "VERIFIED" | "PARTIALLY_VERIFIED" | "FAILED" | "NOT_VERIFIABLE";
  requested_mode?: TeachingMode;
  mode: TeachingMode;
  intent?: string;
  route?: string;
  provider: string;
  model: string;
  latency_ms: number;
  learning_trace?: LearningTrace;
  recommendation?: Recommendation | null;
};

export type Recommendation = {
  subject: string;
  topic: string;
  reason: string;
  action: string;
  priority: number;
  priority_label?: string;
  concept?: string | null;
  strategy?: string | null;
  difficulty?: number | null;
  sequence?: string[];
  due_for_review?: boolean;
  why?: string;
  evidence?: Record<string, unknown>;
  recommended_difficulty?: string;
};

export type RecommendationsResponse = {
  recommendations: Recommendation[];
  enough_data: boolean;
  message: string | null;
};

export type ErrorTypeCount = {
  error_type: string;
  count: number;
  evidence?: { detail?: string; topic?: string | null; concept?: string | null }[];
};

export type ErrorDNAProfile = {
  user_id: number;
  subject?: string | null;
  topic?: string | null;
  most_frequent_error_types: ErrorTypeCount[];
  repeated_errors: Record<string, unknown>[];
  recent_errors: Record<string, unknown>[];
  evidence_count: number;
  notes?: string;
};

export type LearningTrace = {
  session_id: number;
  trace_id?: string | null;
  student_state?: Record<string, unknown>;
  detected_weakness?: string | null;
  weakness?: Record<string, unknown> | null;
  error_diagnosis?: Record<string, unknown> | null;
  tutor_decision?: Record<string, unknown>;
  difficulty_decision?: Record<string, unknown> | null;
  agent_decision?: Record<string, unknown>;
  selected_tools?: string[];
  tools?: string[];
  verification?: string | null;
  outcome_status?: string | null;
  outcome_reason?: string | null;
  outcome_evidence?: string[];
  outcome_student_message?: string | null;
  mastery_updated?: boolean;
  attempt?: Record<string, unknown> | null;
  learning_result?: Record<string, unknown>;
  mastery_before?: Record<string, unknown> | null;
  mastery_after?: Record<string, unknown> | null;
  mastery_update?: Record<string, unknown> | null;
  mastery_delta?: Record<string, unknown> | null;
  next_recommendation?: Recommendation | null;
  recommendation?: Recommendation | null;
};

export type LearningOutcomeResponse = {
  attempt: {
    attempt_id: number;
    mastery: number;
    attempts: number;
    correct_attempts: number;
    consecutive_errors: number;
    confidence: number;
    recommended_difficulty: string;
    mastery_before: number;
    session_id?: number | null;
    misconception?: string | null;
  };
  recommendation: Recommendation | null;
  learning_trace: LearningTrace;
  bank_verified?: boolean | null;
};

export type PracticeProblem = {
  id: number;
  question: string;
  subject: string;
  topic: string;
  concept?: string | null;
  difficulty: number;
  gradable?: boolean;
};

export type SelectionReason = {
  topic_match: boolean;
  concept_match: boolean;
  difficulty_match: boolean;
  error_pattern_match: boolean;
  recent_repetition_penalty: number;
  target_difficulty?: number | null;
  difficulty_level?: number | null;
  student_reasons?: string[];
  recommendation_used?: boolean;
  error_concept?: string | null;
};

export type NextProblemResponse = {
  problem: PracticeProblem | null;
  selection_reason: SelectionReason | null;
  message?: string | null;
};

export type StudentLearningState = {
  student_id: number;
  current_topic?: string | null;
  current_concept?: string | null;
  subject?: string | null;
  recent_errors?: { topic?: string | null; concept?: string | null }[];
};

export type EvaluationSession = {
  evaluation_id: string;
  subject: string;
  topic: string;
  group_arm: string;
  status: string;
  learning_session_id?: number | null;
  pre_test_score?: number | null;
  post_test_score?: number | null;
  delayed_test_score?: number | null;
  started_at?: string | null;
  learning_started_at?: string | null;
  ended_at?: string | null;
  notes?: string | null;
};

export type EvaluationMetrics = {
  evaluation_id: string;
  group_arm: string;
  complete: boolean;
  missing_phases: string[];
  pre_test_score?: number | null;
  post_test_score?: number | null;
  delayed_test_score?: number | null;
  learning_gain?: number | null;
  retention_delta?: number | null;
  mastery_before?: number | null;
  mastery_after?: number | null;
  mastery_change?: number | null;
  weak_concepts_before: { concept?: string; mastery?: number }[];
  weak_concepts_after: { concept?: string; mastery?: number }[];
  concepts_recovered: string[];
  concept_recovery_rate?: number | null;
  error_recovery?: {
    improved?: boolean | null;
    early_error_rate?: number | null;
    late_error_rate?: number | null;
    summary: string;
  } | null;
  difficulty_progression?: {
    start_level?: number | null;
    end_level?: number | null;
    progression?: string | null;
    summary: string;
  } | null;
  recommendation_effectiveness?: {
    recommendations_count: number;
    accuracy_after_recommendation?: number | null;
    summary: string;
  } | null;
  causal_claim_allowed: boolean;
  interpretation_caveat: string;
};

export type LearningReport = {
  evaluation_id: string;
  subject: string;
  topic: string;
  group_arm: string;
  initial_state: string;
  weak_concepts: string[];
  learning_interventions: string[];
  mastery_changes: string;
  post_test?: string | null;
  learning_gain?: number | null;
  concept_recovery: string;
  remaining_weaknesses: string[];
  disclaimer: string;
  evidence_refs: string[];
};

export type StudentModel = {
  user_id: number;
  total_study_minutes: number;
  total_questions: number;
  accuracy: number;
  weak_concepts: string[];
  strong_concepts: string[];
  mastery: {
    subject: string;
    topic: string;
    mastery: number;
    confidence: number;
    attempts: number;
    correct_attempts: number;
    consecutive_errors: number;
    last_practiced_at: string | null;
    next_review_at: string | null;
  }[];
};

export type MemoryResponse = {
  repeated_mistakes: {
    pattern: string;
    misconception?: string | null;
    subject?: string | null;
    topic?: string | null;
    count: number;
  }[];
  recent_questions: {
    id: number;
    subject?: string | null;
    topic?: string | null;
    answer?: string | null;
    correct?: boolean | null;
    ai_explanation?: string | null;
    misconception?: string | null;
    created_at: string;
  }[];
  recent_activity: {
    type: string;
    subject?: string | null;
    topic?: string | null;
    duration_minutes: number;
    created_at: string;
  }[];
};

export type ProblemSolveResponse = {
  problem: string;
  proposed_solution: string;
  tool: string;
  tool_result: Record<string, unknown>;
  final_answer: string;
  verification_status: "VERIFIED" | "PARTIALLY_VERIFIED" | "FAILED" | "NOT_VERIFIABLE";
  provider: string;
  model: string;
  subject?: string | null;
  topic?: string | null;
  personalized?: boolean;
};

export function analyzeVisionImage(
  file: File,
  onProgress?: (pct: number) => void
): Promise<VisionAnalyzeResponse> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/api/vision/analyze`);
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return;
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as VisionAnalyzeResponse);
      } else {
        try {
          const data = JSON.parse(xhr.responseText);
          reject(new ApiError(data.detail ?? "Vision analyze failed", xhr.status));
        } catch {
          reject(new ApiError("Vision analyze failed", xhr.status));
        }
      }
    };
    xhr.onerror = () => reject(new ApiError("Network error during vision analyze", 0));
    xhr.send(form);
  });
}
