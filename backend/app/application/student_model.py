"""Read models for student, topics, mastery and useful learning memory."""

from __future__ import annotations

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Attempt, LearningRecord, Mistake, StudentProfile, TopicMastery


class MasteryItem(BaseModel):
    subject: str
    topic: str
    mastery: float
    confidence: float
    attempts: int
    correct_attempts: int
    consecutive_errors: int
    last_practiced_at: str | None
    next_review_at: str | None


class StudentModelResponse(BaseModel):
    user_id: int
    total_study_minutes: int
    total_questions: int
    accuracy: float
    weak_concepts: list[str]
    strong_concepts: list[str]
    mastery: list[MasteryItem]


class TopicItem(BaseModel):
    subject: str
    topic: str
    attempts: int


class MemoryResponse(BaseModel):
    repeated_mistakes: list[dict[str, object]]
    recent_questions: list[dict[str, object]]
    recent_activity: list[dict[str, object]]


class StudentModelService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id

    def student(self) -> StudentModelResponse:
        profile = (
            self.db.query(StudentProfile)
            .filter(StudentProfile.user_id == self.user_id)
            .first()
        )
        mastery = self.mastery()
        return StudentModelResponse(
            user_id=self.user_id,
            total_study_minutes=profile.total_study_minutes if profile else 0,
            total_questions=profile.total_questions if profile else 0,
            accuracy=profile.accuracy_rate if profile else 0.0,
            weak_concepts=[
                f"{item.subject} / {item.topic}"
                for item in mastery
                if item.attempts >= 2 and item.mastery < 0.6
            ],
            strong_concepts=[
                f"{item.subject} / {item.topic}"
                for item in mastery
                if item.attempts >= 3 and item.mastery >= 0.8
            ],
            mastery=mastery,
        )

    def mastery(self) -> list[MasteryItem]:
        rows = (
            self.db.query(TopicMastery)
            .filter(TopicMastery.user_id == self.user_id)
            .order_by(TopicMastery.subject, TopicMastery.topic)
            .all()
        )
        return [
            MasteryItem(
                subject=row.subject,
                topic=row.topic,
                mastery=row.mastery_estimate,
                confidence=row.confidence,
                attempts=row.attempts,
                correct_attempts=row.correct_attempts,
                consecutive_errors=row.consecutive_errors,
                last_practiced_at=row.last_practiced_at.isoformat()
                if row.last_practiced_at
                else None,
                next_review_at=row.next_review_at.isoformat() if row.next_review_at else None,
            )
            for row in rows
        ]

    def topics(self) -> list[TopicItem]:
        rows = (
            self.db.query(Attempt.subject, Attempt.topic, func.count(Attempt.id))
            .filter(
                Attempt.user_id == self.user_id,
                Attempt.subject.isnot(None),
                Attempt.topic.isnot(None),
            )
            .group_by(Attempt.subject, Attempt.topic)
            .order_by(Attempt.subject, Attempt.topic)
            .all()
        )
        return [
            TopicItem(subject=subject, topic=topic, attempts=int(count))
            for subject, topic, count in rows
        ]

    def memory(self) -> MemoryResponse:
        mistakes = (
            self.db.query(
                Mistake.pattern,
                Attempt.subject,
                Attempt.topic,
                func.count(Mistake.id),
                func.max(Mistake.misconception),
            )
            .join(Attempt, Mistake.attempt_id == Attempt.id)
            .filter(Attempt.user_id == self.user_id)
            .group_by(
                Mistake.pattern,
                Attempt.subject,
                Attempt.topic,
            )
            .order_by(func.count(Mistake.id).desc())
            .limit(20)
            .all()
        )
        attempts = (
            self.db.query(Attempt)
            .filter(Attempt.user_id == self.user_id)
            .order_by(Attempt.created_at.desc())
            .limit(20)
            .all()
        )
        activity = (
            self.db.query(LearningRecord)
            .filter(LearningRecord.user_id == self.user_id)
            .order_by(LearningRecord.created_at.desc())
            .limit(20)
            .all()
        )
        return MemoryResponse(
            repeated_mistakes=[
                {
                    "pattern": pattern,
                    "misconception": misconception,
                    "subject": subject,
                    "topic": topic,
                    "count": int(count),
                }
                for pattern, subject, topic, count, misconception in mistakes
            ],
            recent_questions=[
                {
                    "id": row.id,
                    "subject": row.subject,
                    "topic": row.topic,
                    "answer": row.answer,
                    "correct": row.is_correct,
                    "ai_explanation": row.ai_explanation,
                    "misconception": row.detected_misconception,
                    "created_at": row.created_at.isoformat(),
                }
                for row in attempts
            ],
            recent_activity=[
                {
                    "type": row.activity_type,
                    "subject": row.subject,
                    "topic": row.topic,
                    "duration_minutes": row.duration_minutes,
                    "created_at": row.created_at.isoformat(),
                }
                for row in activity
            ],
        )
