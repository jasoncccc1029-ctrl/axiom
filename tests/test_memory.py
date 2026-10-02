"""Student memory, learning records and mastery update tests."""

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.memory import LearningRecordRequest, MemoryService  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import Attempt, StudentProfile, TopicMastery, User  # noqa: E402
from app.services.progress import get_progress  # noqa: E402
from app.application.student_model import StudentModelService  # noqa: E402


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="memory@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def test_memory_updates_mastery_and_consecutive_errors():
    db = make_db()
    try:
        service = MemoryService(db)
        first = service.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="quadratic",
                correct=False,
                mistake_pattern="sign error",
                duration_minutes=5,
            )
        )
        second = service.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="quadratic",
                correct=False,
                mistake_pattern="sign error",
                duration_minutes=4,
            )
        )
        assert first.consecutive_errors == 1
        assert second.consecutive_errors == 2
        assert second.mastery < 0.5
        assert db.query(Attempt).count() == 2
        row = db.query(TopicMastery).one()
        assert row.last_mistake_pattern == "sign error"
        assert row.confidence == 0.2
        profile = db.query(StudentProfile).one()
        assert profile.total_questions == 2
        assert profile.weak_subjects == "mathematics"
        memory = StudentModelService(db).memory()
        assert memory.repeated_mistakes[0]["pattern"] == "sign error"
        assert memory.repeated_mistakes[0]["count"] == 2
    finally:
        db.close()


def test_correct_attempt_resets_error_streak_and_progress_is_real():
    db = make_db()
    try:
        service = MemoryService(db)
        service.record(
            LearningRecordRequest(subject="physics", topic="force", correct=False)
        )
        result = service.record(
            LearningRecordRequest(subject="physics", topic="force", correct=True)
        )
        assert result.consecutive_errors == 0
        progress = get_progress(db)
        assert progress.total_questions == 2
        assert progress.accuracy_rate == 0.5
        assert progress.enough_data is False
        assert progress.data_message == "Not enough data yet."
    finally:
        db.close()
