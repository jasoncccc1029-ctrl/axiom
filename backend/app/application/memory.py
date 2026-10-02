"""Minimal, local student learning memory without unnecessary personal data."""

from __future__ import annotations

import json
from datetime import timedelta

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.difficulty_policy import label_to_level, level_to_label
from app.config import settings
from app.models import (
    Attempt,
    LearningRecord,
    Mistake,
    StudentProfile,
    Subject,
    Topic,
    TopicMastery,
    utcnow,
)


class LearningRecordRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=120)
    topic: str = Field(..., min_length=1, max_length=160)
    correct: bool
    mistake_pattern: str | None = Field(default=None, max_length=255)
    duration_minutes: int = Field(default=0, ge=0, le=1440)
    mode: str = Field(
        default="tutor",
        pattern="^(hint|tutor|direct_solve|socratic|step_by_step|full_solution|concept|error_diagnosis)$",
    )
    answer: str | None = Field(default=None, max_length=10_000)
    question_id: int | None = None
    trace_id: str | None = Field(default=None, max_length=64)
    session_id: int | None = None
    ai_explanation: str | None = Field(default=None, max_length=20_000)
    detected_misconception: str | None = Field(default=None, max_length=500)
    difficulty: str | None = Field(default=None, max_length=40)
    difficulty_level: int | None = Field(default=None, ge=1, le=5)
    conversation_id: int | None = None
    error_type: str | None = None
    related_concept: str | None = None
    expected_answer: str | None = None
    diagnosis_json: dict | None = None
    verified: bool | None = None
    problem_id: int | None = None


class LearningRecordResponse(BaseModel):
    attempt_id: int
    mastery: float
    attempts: int
    correct_attempts: int
    consecutive_errors: int
    confidence: float = 0.0
    recommended_difficulty: str = "current"
    difficulty_level: int = 3
    mastery_before: float = 0.0
    session_id: int | None = None
    misconception: str | None = None
    error_type: str | None = None
    related_concept: str | None = None
    idempotent_replay: bool = False


class MemoryService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id

    def find_attempt_by_trace(self, trace_id: str | None) -> Attempt | None:
        if not trace_id:
            return None
        return (
            self.db.query(Attempt)
            .filter(Attempt.user_id == self.user_id, Attempt.trace_id == trace_id)
            .order_by(Attempt.id.desc())
            .first()
        )

    def record(self, payload: LearningRecordRequest) -> LearningRecordResponse:
        # Idempotency: same trace_id must not double-count mastery.
        if payload.trace_id:
            existing = self.find_attempt_by_trace(payload.trace_id)
            if existing is not None:
                mastery = (
                    self.db.query(TopicMastery)
                    .filter(
                        TopicMastery.user_id == self.user_id,
                        TopicMastery.subject == payload.subject,
                        TopicMastery.topic == payload.topic,
                    )
                    .first()
                )
                return LearningRecordResponse(
                    attempt_id=existing.id,
                    mastery=mastery.mastery_estimate if mastery else 0.0,
                    attempts=mastery.attempts if mastery else 0,
                    correct_attempts=mastery.correct_attempts if mastery else 0,
                    consecutive_errors=mastery.consecutive_errors if mastery else 0,
                    confidence=mastery.confidence if mastery else 0.0,
                    recommended_difficulty=(
                        mastery.recommended_difficulty if mastery else "current"
                    ),
                    difficulty_level=mastery.difficulty_level if mastery else 3,
                    mastery_before=mastery.mastery_estimate if mastery else 0.0,
                    session_id=existing.session_id,
                    misconception=existing.detected_misconception,
                    error_type=existing.error_type,
                    related_concept=existing.related_concept,
                    idempotent_replay=True,
                )

        mastery = (
            self.db.query(TopicMastery)
            .filter(
                TopicMastery.user_id == self.user_id,
                TopicMastery.subject == payload.subject,
                TopicMastery.topic == payload.topic,
            )
            .first()
        )
        mastery_before = float(mastery.mastery_estimate) if mastery else 0.0
        misconception = payload.detected_misconception
        if not payload.correct and payload.mistake_pattern and not misconception:
            prior = (
                self.db.query(func.count(Attempt.id))
                .filter(
                    Attempt.user_id == self.user_id,
                    Attempt.subject == payload.subject,
                    Attempt.topic == payload.topic,
                    Attempt.is_correct.is_(False),
                    Attempt.mistake_pattern == payload.mistake_pattern,
                )
                .scalar()
                or 0
            )
            if prior >= 1:
                misconception = (
                    f"Repeated '{payload.mistake_pattern}' "
                    f"on {payload.subject}/{payload.topic}"
                )

        difficulty_level = payload.difficulty_level
        if difficulty_level is None:
            difficulty_level = label_to_level(
                payload.difficulty
                or (mastery.recommended_difficulty if mastery else "current")
            )

        attempt = Attempt(
            user_id=self.user_id,
            question_id=payload.question_id,
            problem_id=payload.problem_id,
            subject=payload.subject,
            topic=payload.topic,
            answer=payload.answer,
            is_correct=payload.correct,
            mistake_pattern=None if payload.correct else payload.mistake_pattern,
            detected_misconception=misconception,
            ai_explanation=payload.ai_explanation,
            difficulty=payload.difficulty or level_to_label(difficulty_level),
            mode=payload.mode,
            conversation_id=payload.conversation_id,
            session_id=payload.session_id,
            trace_id=payload.trace_id,
            error_type=payload.error_type,
            related_concept=payload.related_concept,
            expected_answer=payload.expected_answer,
            diagnosis_json=json.dumps(payload.diagnosis_json or {}, ensure_ascii=False),
        )
        self.db.add(attempt)
        self._ensure_topic(payload.subject, payload.topic)
        if mastery is None:
            mastery = TopicMastery(
                user_id=self.user_id,
                subject=payload.subject,
                topic=payload.topic,
                attempts=0,
                correct_attempts=0,
                consecutive_errors=0,
                mastery_estimate=0.0,
                confidence=0.0,
                recommended_difficulty="current",
                difficulty_level=3,
                review_count=0,
            )
            self.db.add(mastery)
        mastery.attempts += 1
        if payload.correct:
            mastery.correct_attempts += 1
            mastery.consecutive_errors = 0
            if payload.verified:
                mastery.last_verified_at = utcnow()
        else:
            mastery.consecutive_errors += 1
            mastery.last_mistake_pattern = payload.mistake_pattern
        mastery.mastery_estimate = round(
            (mastery.correct_attempts + 1) / (mastery.attempts + 2), 4
        )
        mastery.confidence = round(min(0.95, mastery.attempts / 10), 4)
        mastery.difficulty_level = difficulty_level
        mastery.recommended_difficulty = level_to_label(difficulty_level)
        mastery.last_practiced_at = utcnow()
        review_days = max(1, round(1 + mastery.mastery_estimate * 13))
        if mastery.consecutive_errors >= 2:
            review_days = 1
        mastery.next_review_at = utcnow() + timedelta(days=review_days)
        if payload.mode == "concept" or (
            payload.diagnosis_json and payload.diagnosis_json.get("strategy") == "REVIEW"
        ):
            mastery.review_count = int(mastery.review_count or 0) + 1

        self.db.add(
            LearningRecord(
                user_id=self.user_id,
                activity_type="attempt",
                subject=payload.subject,
                topic=payload.topic,
                duration_minutes=payload.duration_minutes,
                questions_attempted=1,
                questions_correct=1 if payload.correct else 0,
                notes=payload.mistake_pattern,
                mode=payload.mode,
                trace_id=payload.trace_id,
                session_id=payload.session_id,
            )
        )
        self.db.flush()
        if not payload.correct and (payload.mistake_pattern or misconception or payload.error_type):
            self.db.add(
                Mistake(
                    attempt_id=attempt.id,
                    pattern=payload.mistake_pattern or payload.error_type or "unspecified",
                    misconception=misconception,
                )
            )
        self._update_profile()
        self.db.commit()
        self.db.refresh(attempt)
        return LearningRecordResponse(
            attempt_id=attempt.id,
            mastery=mastery.mastery_estimate,
            attempts=mastery.attempts,
            correct_attempts=mastery.correct_attempts,
            consecutive_errors=mastery.consecutive_errors,
            confidence=mastery.confidence,
            recommended_difficulty=mastery.recommended_difficulty,
            difficulty_level=mastery.difficulty_level,
            mastery_before=mastery_before,
            session_id=payload.session_id,
            misconception=misconception,
            error_type=payload.error_type,
            related_concept=payload.related_concept,
            idempotent_replay=False,
        )

    def _ensure_topic(self, subject_name: str, topic_name: str) -> None:
        subject = self.db.query(Subject).filter(Subject.name == subject_name).first()
        if subject is None:
            subject = Subject(name=subject_name)
            self.db.add(subject)
            self.db.flush()
        topic = (
            self.db.query(Topic)
            .filter(Topic.subject_id == subject.id, Topic.name == topic_name)
            .first()
        )
        if topic is None:
            self.db.add(Topic(subject_id=subject.id, name=topic_name))

    def _update_profile(self) -> None:
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.user_id == self.user_id)
            .first()
        )
        if profile is None:
            profile = StudentProfile(user_id=self.user_id)
            self.db.add(profile)

        total = (
            self.db.query(func.count(Attempt.id))
            .filter(Attempt.user_id == self.user_id)
            .scalar()
            or 0
        )
        correct = (
            self.db.query(func.count(Attempt.id))
            .filter(Attempt.user_id == self.user_id, Attempt.is_correct.is_(True))
            .scalar()
            or 0
        )
        study_minutes = (
            self.db.query(func.coalesce(func.sum(LearningRecord.duration_minutes), 0))
            .filter(LearningRecord.user_id == self.user_id)
            .scalar()
            or 0
        )
        profile.total_questions = int(total or 0)
        profile.accuracy_rate = float(correct or 0) / float(total) if total else 0.0
        profile.total_study_minutes = int(study_minutes)

        mastery_rows = (
            self.db.query(TopicMastery)
            .filter(TopicMastery.user_id == self.user_id, TopicMastery.attempts >= 2)
            .all()
        )
        weak = sorted(
            {row.subject for row in mastery_rows if row.mastery_estimate < 0.6}
        )
        strong = sorted(
            {row.subject for row in mastery_rows if row.mastery_estimate >= 0.8}
        )
        profile.weak_subjects = ",".join(weak) or None
        profile.strengths = ",".join(strong) or None
