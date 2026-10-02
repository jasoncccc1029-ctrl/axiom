"""Agent Core request, plan, trace and response schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class TeachingMode(StrEnum):
    HINT = "hint"
    TUTOR = "tutor"
    DIRECT_SOLVE = "direct_solve"
    SOCRATIC = "socratic"
    STEP_BY_STEP = "step_by_step"
    FULL_SOLUTION = "full_solution"
    CONCEPT = "concept"
    ERROR_DIAGNOSIS = "error_diagnosis"


class VerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    FAILED = "FAILED"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"


class AgentRunRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=20_000)
    mode: TeachingMode = TeachingMode.TUTOR
    subject: str | None = Field(default=None, max_length=120)
    topic: str | None = Field(default=None, max_length=160)
    material_id: int | None = None
    confirmed_problem: str | None = Field(default=None, max_length=20_000)
    input_type: Literal["text", "image", "pdf"] = "text"
    conversation_id: int | None = None
    session_id: int | None = None
    record_attempt: bool | None = None


class PlannedStep(BaseModel):
    index: int
    action: str
    tool: str | None = None
    reason: str


class ToolCallTrace(BaseModel):
    tool: str
    ok: bool
    execution_time_ms: float
    summary: str


class SourceReference(BaseModel):
    document_id: int
    document_title: str
    page: int
    chunk_id: int
    score: float


class AgentRunResponse(BaseModel):
    trace_id: str
    conversation_id: int = 0
    session_id: int | None = None
    question_id: int | None = None
    steps: list[PlannedStep]
    tool_calls: list[ToolCallTrace]
    sources: list[SourceReference] = Field(default_factory=list)
    adaptive_decision: dict[str, Any] = Field(default_factory=dict)
    final_answer: str
    verification_status: VerificationStatus
    requested_mode: TeachingMode = TeachingMode.TUTOR
    mode: TeachingMode
    intent: str = "tutor"
    route: str = "tutor"
    provider: str
    model: str
    latency_ms: float
    learning_trace: dict[str, Any] = Field(default_factory=dict)
    recommendation: dict[str, Any] | None = None


class AgentTraceResponse(AgentRunResponse):
    status: str
    error_code: str | None = None
    error_message: str | None = None


class Plan(BaseModel):
    steps: list[PlannedStep]
    category: str
    metadata: dict[str, Any] = Field(default_factory=dict)
