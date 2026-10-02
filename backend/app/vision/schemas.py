"""Structured vision analysis result."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ContentType = Literal["math_problem", "lecture", "note", "diagram", "text", "unknown"]


class VisionAnalysis(BaseModel):
    content_type: ContentType = "unknown"
    subject: str = "unknown"
    topic: str = "unknown"
    problem_text: str = ""
    detected_formula: list[str] = Field(default_factory=list)
    diagram_description: str = ""
    detected_tables: list[list[list[str]]] = Field(default_factory=list)
    question_type: str = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    raw_text: str | None = None
    provider: str = "unknown"
    model: str | None = None
    total_duration_ns: int | None = None
    load_duration_ns: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_duration_ns: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
