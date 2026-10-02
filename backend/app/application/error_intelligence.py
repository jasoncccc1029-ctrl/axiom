"""Error Intelligence: deterministic error typing and repeated-pattern detection.

LLM may propose a diagnosis text; database mastery updates remain in MemoryService.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Attempt, RepeatedErrorPattern, utcnow


class ErrorType(StrEnum):
    CONCEPT_GAP = "CONCEPT_GAP"
    PROCEDURAL_ERROR = "PROCEDURAL_ERROR"
    CALCULATION_ERROR = "CALCULATION_ERROR"
    SIGN_ERROR = "SIGN_ERROR"
    READING_ERROR = "READING_ERROR"
    MISCONCEPTION = "MISCONCEPTION"
    CARELESS_ERROR = "CARELESS_ERROR"
    TIME_PRESSURE = "TIME_PRESSURE"
    UNKNOWN = "UNKNOWN"
    NONE = "NONE"  # correct attempts


REPEATED_ERROR_THRESHOLD = 3

_PATTERN_HINTS: list[tuple[ErrorType, re.Pattern[str]]] = [
    (ErrorType.SIGN_ERROR, re.compile(r"sign|符號|正負|minus|transpose", re.I)),
    (ErrorType.CALCULATION_ERROR, re.compile(r"arithmetic|計算|calc|compute|加减乘除", re.I)),
    (ErrorType.READING_ERROR, re.compile(r"misread|讀題|reading|wording", re.I)),
    (ErrorType.PROCEDURAL_ERROR, re.compile(r"procedure|步驟|order|process|algorithm", re.I)),
    (ErrorType.CONCEPT_GAP, re.compile(r"concept|概念|definition|不懂|gap", re.I)),
    (ErrorType.MISCONCEPTION, re.compile(r"misconception|迷思|confused|誤解", re.I)),
    (ErrorType.CARELESS_ERROR, re.compile(r"careless|粗心|slip|typo", re.I)),
    (ErrorType.TIME_PRESSURE, re.compile(r"time|趕|rush|pressure", re.I)),
]


class ErrorDiagnosis(BaseModel):
    question_id: int | None = None
    subject: str
    topic: str
    concept: str | None = None
    error_type: ErrorType = ErrorType.UNKNOWN
    expected_answer: str | None = None
    student_answer: str | None = None
    diagnosis: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    related_concept: str | None = None
    is_repeated_error: bool = False
    pattern_count: int = 0


class RepeatedErrorView(BaseModel):
    pattern: str
    error_type: str
    subject: str
    topic: str
    concept: str | None = None
    count: int
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    recent_frequency: float = 0.0
    resolved: bool = False


class ErrorIntelligenceService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id

    def classify(
        self,
        *,
        correct: bool,
        subject: str,
        topic: str,
        mistake_pattern: str | None = None,
        detected_misconception: str | None = None,
        student_answer: str | None = None,
        expected_answer: str | None = None,
        concept: str | None = None,
        question_id: int | None = None,
        provided_error_type: str | None = None,
        diagnosis_text: str | None = None,
    ) -> ErrorDiagnosis:
        if correct:
            return ErrorDiagnosis(
                question_id=question_id,
                subject=subject,
                topic=topic,
                concept=concept or _default_concept(topic),
                error_type=ErrorType.NONE,
                expected_answer=expected_answer,
                student_answer=student_answer,
                diagnosis="Correct attempt; no error diagnosed.",
                confidence=1.0,
                related_concept=concept or _default_concept(topic),
                is_repeated_error=False,
                pattern_count=0,
            )

        error_type = _resolve_error_type(
            provided_error_type, mistake_pattern, detected_misconception, diagnosis_text
        )
        related = concept or _infer_concept(topic, mistake_pattern, detected_misconception)
        prior = self.count_pattern(subject, topic, error_type.value, related)
        is_repeated = prior >= 1
        confidence = 0.55
        if provided_error_type:
            confidence = 0.9
        elif mistake_pattern and any(p.search(mistake_pattern) for _, p in _PATTERN_HINTS):
            confidence = 0.82
        elif detected_misconception:
            confidence = 0.75

        diagnosis = diagnosis_text or detected_misconception
        if not diagnosis:
            if is_repeated:
                diagnosis = (
                    f"Student repeatedly shows {error_type.value} on {topic}"
                    + (f" / {related}" if related else "")
                    + "."
                )
            else:
                diagnosis = (
                    f"Detected {error_type.value} on {topic}"
                    + (f" related to {related}" if related else "")
                    + "."
                )
            if mistake_pattern:
                diagnosis += f" Pattern hint: {mistake_pattern}."

        return ErrorDiagnosis(
            question_id=question_id,
            subject=subject,
            topic=topic,
            concept=related,
            error_type=error_type,
            expected_answer=expected_answer,
            student_answer=student_answer,
            diagnosis=diagnosis,
            confidence=round(confidence, 2),
            related_concept=related,
            is_repeated_error=is_repeated,
            pattern_count=prior + 1,
        )

    def count_pattern(
        self,
        subject: str,
        topic: str,
        error_type: str,
        concept: str | None = None,
    ) -> int:
        query = self.db.query(func.count(Attempt.id)).filter(
            Attempt.user_id == self.user_id,
            Attempt.subject == subject,
            Attempt.topic == topic,
            Attempt.is_correct.is_(False),
            Attempt.error_type == error_type,
        )
        if concept:
            query = query.filter(Attempt.related_concept == concept)
        return int(query.scalar() or 0)

    def upsert_repeated_pattern(self, diagnosis: ErrorDiagnosis) -> RepeatedErrorView | None:
        if diagnosis.error_type == ErrorType.NONE:
            return None
        row = (
            self.db.query(RepeatedErrorPattern)
            .filter(
                RepeatedErrorPattern.user_id == self.user_id,
                RepeatedErrorPattern.subject == diagnosis.subject,
                RepeatedErrorPattern.topic == diagnosis.topic,
                RepeatedErrorPattern.error_type == diagnosis.error_type.value,
                RepeatedErrorPattern.concept == (diagnosis.related_concept or diagnosis.concept),
            )
            .first()
        )
        now = utcnow()
        concept = diagnosis.related_concept or diagnosis.concept
        if row is None:
            row = RepeatedErrorPattern(
                user_id=self.user_id,
                subject=diagnosis.subject,
                topic=diagnosis.topic,
                concept=concept,
                error_type=diagnosis.error_type.value,
                pattern=diagnosis.error_type.value,
                count=1,
                first_seen=now,
                last_seen=now,
                resolved=False,
            )
            self.db.add(row)
        else:
            row.count += 1
            row.last_seen = now
            row.resolved = False
        self.db.flush()
        days = 1.0
        if row.first_seen and row.last_seen and row.last_seen > row.first_seen:
            days = max(1.0, (row.last_seen - row.first_seen).total_seconds() / 86400.0)
        return RepeatedErrorView(
            pattern=row.pattern,
            error_type=row.error_type,
            subject=row.subject,
            topic=row.topic,
            concept=row.concept,
            count=row.count,
            first_seen=row.first_seen,
            last_seen=row.last_seen,
            recent_frequency=round(row.count / days, 3),
            resolved=row.resolved,
        )

    def mark_resolved_on_success(
        self,
        *,
        subject: str,
        topic: str,
        concept: str | None = None,
        error_type: str | None = None,
    ) -> None:
        query = self.db.query(RepeatedErrorPattern).filter(
            RepeatedErrorPattern.user_id == self.user_id,
            RepeatedErrorPattern.subject == subject,
            RepeatedErrorPattern.topic == topic,
            RepeatedErrorPattern.resolved.is_(False),
        )
        if concept:
            query = query.filter(RepeatedErrorPattern.concept == concept)
        if error_type:
            query = query.filter(RepeatedErrorPattern.error_type == error_type)
        for row in query.all():
            row.resolved = True
            row.last_seen = utcnow()
        self.db.flush()

    def list_patterns(self, *, unresolved_only: bool = False) -> list[RepeatedErrorView]:
        query = self.db.query(RepeatedErrorPattern).filter(
            RepeatedErrorPattern.user_id == self.user_id
        )
        if unresolved_only:
            query = query.filter(RepeatedErrorPattern.resolved.is_(False))
        rows = query.order_by(RepeatedErrorPattern.count.desc()).all()
        views: list[RepeatedErrorView] = []
        for row in rows:
            days = 1.0
            if row.first_seen and row.last_seen and row.last_seen > row.first_seen:
                days = max(1.0, (row.last_seen - row.first_seen).total_seconds() / 86400.0)
            views.append(
                RepeatedErrorView(
                    pattern=row.pattern,
                    error_type=row.error_type,
                    subject=row.subject,
                    topic=row.topic,
                    concept=row.concept,
                    count=row.count,
                    first_seen=row.first_seen,
                    last_seen=row.last_seen,
                    recent_frequency=round(row.count / days, 3),
                    resolved=row.resolved,
                )
            )
        return views

    def exceeds_threshold(self, diagnosis: ErrorDiagnosis) -> bool:
        return diagnosis.pattern_count >= REPEATED_ERROR_THRESHOLD


def _resolve_error_type(
    provided: str | None,
    mistake_pattern: str | None,
    misconception: str | None,
    diagnosis_text: str | None,
) -> ErrorType:
    if provided:
        try:
            return ErrorType(provided)
        except ValueError:
            pass
    blob = " ".join(x for x in (mistake_pattern, misconception, diagnosis_text) if x)
    for error_type, pattern in _PATTERN_HINTS:
        if blob and pattern.search(blob):
            return error_type
    if misconception:
        return ErrorType.MISCONCEPTION
    if mistake_pattern:
        return ErrorType.PROCEDURAL_ERROR
    return ErrorType.UNKNOWN


def _default_concept(topic: str) -> str:
    return topic.replace(" ", "_").lower() or "general"


def _infer_concept(
    topic: str,
    mistake_pattern: str | None,
    misconception: str | None,
) -> str:
    text = f"{mistake_pattern or ''} {misconception or ''}".lower()
    topic_l = topic.lower()
    if "sign" in text or "符號" in text:
        if "quadratic" in topic_l or "equation" in topic_l:
            return "equation_transformation"
        return "sign_handling"
    if "root" in text and "coefficient" in text:
        return "root_coefficient_relationship"
    if "discriminant" in text:
        return "discriminant"
    if "vertex" in text:
        return "vertex"
    if "force" in text or "newton" in topic_l:
        return "force_direction"
    return _default_concept(topic)
