"""Lean Student Learning State for Agent decisions (not full chat history)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.error_dna import ErrorDNAService
from app.config import settings
from app.models import Attempt, LearningRecord, LearningSession, TopicMastery


class StudentLearningState(BaseModel):
    student_id: int
    current_topic: str | None = None
    current_concept: str | None = None
    subject: str | None = None
    mastery: float | None = None
    mastery_confidence: float | None = None
    recent_performance: dict[str, Any] = Field(default_factory=dict)
    recent_errors: list[dict[str, Any]] = Field(default_factory=list)
    repeated_error_patterns: list[dict[str, Any]] = Field(default_factory=list)
    current_difficulty: str | None = None
    difficulty_level: int | None = None
    recent_learning_activity: list[dict[str, Any]] = Field(default_factory=list)
    active_session_id: int | None = None
    notes: str = (
        "Lean learning state for decision-making. Missing fields stay null/empty; "
        "no invented values."
    )


class StudentLearningStateService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id
        self.error_dna = ErrorDNAService(db, self.user_id)

    def get(
        self,
        *,
        subject: str | None = None,
        topic: str | None = None,
        concept: str | None = None,
    ) -> StudentLearningState:
        mastery_row = None
        if subject and topic:
            mastery_row = (
                self.db.query(TopicMastery)
                .filter(
                    TopicMastery.user_id == self.user_id,
                    TopicMastery.subject == subject,
                    TopicMastery.topic == topic,
                )
                .first()
            )

        attempts_q = self.db.query(Attempt).filter(Attempt.user_id == self.user_id)
        if subject:
            attempts_q = attempts_q.filter(Attempt.subject == subject)
        if topic:
            attempts_q = attempts_q.filter(Attempt.topic == topic)
        recent_attempts = attempts_q.order_by(Attempt.id.desc()).limit(8).all()

        scored = [a for a in recent_attempts if a.is_correct is not None]
        accuracy = None
        if scored:
            accuracy = round(
                sum(1 for a in scored if a.is_correct) / len(scored), 4
            )

        dna = self.error_dna.profile(subject=subject, topic=topic, recent_limit=5)

        session = (
            self.db.query(LearningSession)
            .filter(
                LearningSession.user_id == self.user_id,
                LearningSession.status.in_(("started", "active")),
            )
            .order_by(LearningSession.started_at.desc())
            .first()
        )

        activity_q = self.db.query(LearningRecord).filter(
            LearningRecord.user_id == self.user_id
        )
        if subject:
            activity_q = activity_q.filter(LearningRecord.subject == subject)
        if topic:
            activity_q = activity_q.filter(LearningRecord.topic == topic)
        activity = activity_q.order_by(LearningRecord.id.desc()).limit(5).all()

        current_concept = concept
        if current_concept is None and recent_attempts:
            current_concept = recent_attempts[0].related_concept

        return StudentLearningState(
            student_id=self.user_id,
            subject=subject or (mastery_row.subject if mastery_row else None),
            current_topic=topic or (mastery_row.topic if mastery_row else None),
            current_concept=current_concept,
            mastery=mastery_row.mastery_estimate if mastery_row else None,
            mastery_confidence=mastery_row.confidence if mastery_row else None,
            recent_performance={
                "recent_attempt_count": len(recent_attempts),
                "scored_attempt_count": len(scored),
                "recent_accuracy": accuracy,
                "consecutive_errors": (
                    mastery_row.consecutive_errors if mastery_row else None
                ),
            },
            recent_errors=dna.recent_errors,
            repeated_error_patterns=dna.repeated_errors[:8],
            current_difficulty=(
                mastery_row.recommended_difficulty if mastery_row else None
            ),
            difficulty_level=mastery_row.difficulty_level if mastery_row else None,
            recent_learning_activity=[
                {
                    "activity_type": row.activity_type,
                    "subject": row.subject,
                    "topic": row.topic,
                    "duration_minutes": row.duration_minutes,
                    "questions_attempted": row.questions_attempted,
                    "questions_correct": row.questions_correct,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in activity
            ],
            active_session_id=session.id if session else None,
        )
