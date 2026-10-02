"""Problem bank repository — independent of chat Question rows."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import Problem, utcnow


class ProblemCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=20_000)
    answer: str | None = Field(default=None, max_length=10_000)
    explanation: str | None = Field(default=None, max_length=20_000)
    subject: str = Field(..., min_length=1, max_length=120)
    topic: str = Field(..., min_length=1, max_length=160)
    concept: str | None = Field(default=None, max_length=160)
    difficulty: float = Field(default=0.5, ge=0.0, le=1.0)
    external_key: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProblemUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=20_000)
    answer: str | None = Field(default=None, max_length=10_000)
    explanation: str | None = Field(default=None, max_length=20_000)
    subject: str | None = Field(default=None, min_length=1, max_length=120)
    topic: str | None = Field(default=None, min_length=1, max_length=160)
    concept: str | None = Field(default=None, max_length=160)
    difficulty: float | None = Field(default=None, ge=0.0, le=1.0)
    external_key: str | None = Field(default=None, max_length=80)
    metadata: dict[str, Any] | None = None


class ProblemOut(BaseModel):
    id: int
    external_key: str | None = None
    question: str
    answer: str | None = None
    explanation: str | None = None
    subject: str
    topic: str
    concept: str | None = None
    difficulty: float
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


class ProblemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: ProblemCreate) -> ProblemOut:
        row = Problem(
            external_key=payload.external_key,
            question=payload.question,
            answer=payload.answer,
            explanation=payload.explanation,
            subject=payload.subject,
            topic=payload.topic,
            concept=payload.concept,
            difficulty=payload.difficulty,
            metadata_json=json.dumps(payload.metadata or {}, ensure_ascii=False),
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._to_out(row)

    def get(self, problem_id: int) -> ProblemOut | None:
        row = self.db.get(Problem, problem_id)
        return self._to_out(row) if row else None

    def list(
        self,
        *,
        subject: str | None = None,
        topic: str | None = None,
        concept: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProblemOut]:
        query = self.db.query(Problem)
        if subject:
            query = query.filter(Problem.subject == subject)
        if topic:
            query = query.filter(Problem.topic == topic)
        if concept:
            query = query.filter(Problem.concept == concept)
        rows = (
            query.order_by(Problem.id.desc())
            .offset(max(0, offset))
            .limit(min(200, max(1, limit)))
            .all()
        )
        return [self._to_out(row) for row in rows]

    def update(self, problem_id: int, payload: ProblemUpdate) -> ProblemOut | None:
        row = self.db.get(Problem, problem_id)
        if row is None:
            return None
        data = payload.model_dump(exclude_unset=True)
        if "metadata" in data:
            meta = data.pop("metadata")
            row.metadata_json = json.dumps(meta or {}, ensure_ascii=False)
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = utcnow()
        self.db.commit()
        self.db.refresh(row)
        return self._to_out(row)

    def _to_out(self, row: Problem) -> ProblemOut:
        try:
            metadata = json.loads(row.metadata_json or "{}")
        except json.JSONDecodeError:
            metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}
        return ProblemOut(
            id=row.id,
            external_key=row.external_key,
            question=row.question,
            answer=row.answer,
            explanation=row.explanation,
            subject=row.subject,
            topic=row.topic,
            concept=row.concept,
            difficulty=float(row.difficulty),
            metadata=metadata,
            created_at=row.created_at.isoformat() if row.created_at else None,
            updated_at=row.updated_at.isoformat() if row.updated_at else None,
        )
