"""Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str


class SystemComponentHealth(BaseModel):
    ok: bool
    detail: str
    provider: str | None = None
    model: str | None = None
    reachable: bool | None = None


class SystemHealthResponse(BaseModel):
    ok: bool
    backend: SystemComponentHealth
    #: Canonical text-Brain health (follows AI_PROVIDER).
    text_brain: SystemComponentHealth
    #: Historical alias of ``text_brain`` (kept for older clients / tests).
    ollama: SystemComponentHealth
    vision: SystemComponentHealth
    version: str


class OllamaHealthResponse(BaseModel):
    ok: bool
    reachable: bool
    model: str
    model_available: bool
    models: list[str]
    message: str


class MaterialCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=120)
    description: str | None = None


class MaterialOut(BaseModel):
    id: int
    title: str
    subject: str
    file_type: str
    original_filename: str | None
    description: str | None
    mime_type: str | None = None
    size_bytes: int = 0
    ingestion_status: str = "pending"
    page_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    material_id: int | None = None
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    provider: str
    model: str
    material_id: int | None = None


class SolveRequest(BaseModel):
    problem: str = Field(..., min_length=1)
    subject: str | None = None
    material_id: int | None = None


class SolveStep(BaseModel):
    step: int
    title: str
    content: str


class SolveResponse(BaseModel):
    problem: str
    steps: list[SolveStep]
    answer: str
    verification: dict[str, Any]
    provider: str
    model: str


class SubjectAbility(BaseModel):
    subject: str
    score: float
    questions: int


class TopicMasteryOut(BaseModel):
    subject: str
    topic: str
    mastery: float
    attempts: int
    consecutive_errors: int


class AccuracyTrendPoint(BaseModel):
    date: str
    attempted: int
    correct: int
    accuracy: float


class MistakePatternOut(BaseModel):
    pattern: str
    count: int
    subject: str | None = None
    topic: str | None = None


class LearningHistoryOut(BaseModel):
    activity_type: str
    subject: str | None = None
    topic: str | None = None
    duration_minutes: int
    questions_attempted: int
    questions_correct: int
    created_at: datetime


class ProgressResponse(BaseModel):
    today_study_minutes: int
    week_questions_completed: int
    accuracy_rate: float
    weak_subjects: list[str]
    recommended: list[str]
    total_study_minutes: int
    total_questions: int
    subject_abilities: list[SubjectAbility]
    strengths: list[str]
    topic_mastery: list[TopicMasteryOut] = Field(default_factory=list)
    accuracy_trend: list[AccuracyTrendPoint] = Field(default_factory=list)
    mistake_patterns: list[MistakePatternOut] = Field(default_factory=list)
    learning_history: list[LearningHistoryOut] = Field(default_factory=list)
    enough_data: bool = False
    data_message: str | None = None


class VisionAnalysisOut(BaseModel):
    content_type: str
    subject: str
    topic: str
    problem_text: str
    detected_formula: list[str]
    diagram_description: str
    detected_tables: list[list[list[str]]] = Field(default_factory=list)
    question_type: str = "unknown"
    confidence: float
    provider: str
    model: str | None = None


class VisionTiming(BaseModel):
    response_time_ms: float
    image_size_bytes: int
    total_duration_ns: int | None = None
    load_duration_ns: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_duration_ns: int | None = None


class VisionAnalyzeResponse(BaseModel):
    analysis: VisionAnalysisOut
    stored_filename: str
    mime_type: str
    size: int
    timing: VisionTiming | None = None


class VisionHealthResponse(BaseModel):
    ok: bool
    provider: str
    reachable: bool
    model: str
    model_available: bool
    models: list[str]
    message: str
