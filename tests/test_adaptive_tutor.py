"""Adaptive teaching policy tests based only on stored evidence."""

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.schemas import TeachingMode  # noqa: E402
from app.application.adaptive import AdaptiveTutor  # noqa: E402
from app.application.memory import LearningRecordRequest, MemoryService  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import StudentProfile, User  # noqa: E402


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="adaptive@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def test_repeated_errors_trigger_concept_recovery_not_harder_questions():
    db = make_db()
    try:
        memory = MemoryService(db)
        for _ in range(2):
            memory.record(
                LearningRecordRequest(
                    subject="mathematics",
                    topic="quadratic",
                    correct=False,
                    mistake_pattern="sign error",
                )
            )
        decision = AdaptiveTutor(db).decide(
            subject="mathematics",
            topic="quadratic",
            mode=TeachingMode.TUTOR,
        )
        assert decision.strategy == "concept_recovery"
        assert decision.question_difficulty == "easy"
        assert decision.sequence == [
            "Review concept",
            "Solve easy question",
            "Solve medium question",
            "Diagnose mistakes",
            "Re-test later",
        ]
    finally:
        db.close()


def test_no_data_returns_no_fake_recommendation():
    db = make_db()
    try:
        response = AdaptiveTutor(db).recommendations()
        assert response.recommendations == []
        assert response.enough_data is False
        assert response.message == "Not enough data yet."
    finally:
        db.close()


def test_recommendations_derive_from_mastery():
    db = make_db()
    try:
        memory = MemoryService(db)
        for correct in (False, False, True):
            memory.record(
                LearningRecordRequest(
                    subject="physics",
                    topic="forces",
                    correct=correct,
                    mistake_pattern=None if correct else "direction error",
                )
            )
        response = AdaptiveTutor(db).recommendations()
        assert response.recommendations
        assert response.recommendations[0].topic == "forces"
        assert "mastery" in response.recommendations[0].reason.lower()
        assert response.recommendations[0].why
        assert "attempts" in response.recommendations[0].evidence
    finally:
        db.close()


def test_recommendations_include_why_and_evidence_on_repeated_errors():
    db = make_db()
    try:
        memory = MemoryService(db)
        for _ in range(2):
            memory.record(
                LearningRecordRequest(
                    subject="mathematics",
                    topic="quadratic",
                    correct=False,
                    mistake_pattern="sign error",
                )
            )
        response = AdaptiveTutor(db).recommendations()
        item = response.recommendations[0]
        assert item.why
        assert item.evidence["consecutive_errors"] == 2
        assert item.recommended_difficulty == "easy"
        assert "Review concept" in item.sequence
    finally:
        db.close()
