"""Axiom v1.3.2 — Adaptive Question Engine."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.adaptive_question_engine import AdaptiveQuestionEngine  # noqa: E402
from app.application.learning_loop import (  # noqa: E402
    LearningLoopService,
    LearningOutcomeRequest,
)
from app.application.memory import LearningRecordRequest, MemoryService  # noqa: E402
from app.application.problem_repository import ProblemCreate, ProblemRepository  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import StudentProfile, TopicMastery, User  # noqa: E402


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="v132@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def seed_problems(db: Session) -> dict[str, int]:
    repo = ProblemRepository(db)
    ids: dict[str, int] = {}
    specs = [
        ("period_low", "trig period easy", "trigonometry", "period", 0.35, ["period"]),
        ("period_mid", "trig period mid", "trigonometry", "period", 0.55, ["period", "MISCONCEPTION"]),
        ("period_high", "trig period hard", "trigonometry", "period", 0.8, ["period"]),
        ("amplitude", "trig amplitude", "trigonometry", "amplitude", 0.55, ["amplitude"]),
        ("quadratic", "vertex problem", "quadratic", "vertex_min", 0.5, ["vertex_min"]),
        ("period_alt", "trig period alt", "trigonometry", "period", 0.5, ["period"]),
    ]
    for key, question, topic, concept, difficulty, targets in specs:
        created = repo.create(
            ProblemCreate(
                question=question,
                answer="x",
                subject="mathematics",
                topic=topic,
                concept=concept,
                difficulty=difficulty,
                metadata={"error_targets": targets},
            )
        )
        ids[key] = created.id
    return ids


def set_mastery(
    db: Session,
    subject: str,
    topic: str,
    mastery: float,
    difficulty: str = "medium",
    difficulty_level: int = 3,
) -> None:
    row = TopicMastery(
        user_id=1,
        subject=subject,
        topic=topic,
        mastery_estimate=mastery,
        attempts=4,
        correct_attempts=2,
        consecutive_errors=0,
        recommended_difficulty=difficulty,
        difficulty_level=difficulty_level,
        confidence=0.5,
    )
    db.add(row)
    db.commit()


def test_selects_matching_topic():
    db = make_db()
    try:
        seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.5)
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(subject="mathematics", topic="trigonometry")
        assert result.problem is not None
        assert result.problem.topic == "trigonometry"
        assert result.selection_reason is not None
        assert result.selection_reason.topic_match is True
    finally:
        db.close()


def test_selects_matching_concept():
    db = make_db()
    try:
        seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.5)
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        assert result.problem is not None
        assert result.problem.concept == "period"
        assert result.selection_reason.concept_match is True
    finally:
        db.close()


def test_respects_difficulty_policy():
    db = make_db()
    try:
        seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.3, difficulty="easy", difficulty_level=2)
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        assert result.problem is not None
        assert result.selection_reason is not None
        assert result.selection_reason.difficulty_level is not None
        assert result.selection_reason.target_difficulty is not None
        assert result.selection_reason.difficulty_policy_action in {
            "hold",
            "decrease",
            "increase",
            "review",
        }
        # Low mastery + easy current → target float near lower band
        assert result.selection_reason.target_difficulty <= 0.5
    finally:
        db.close()


def test_avoids_recently_attempted_problems():
    db = make_db()
    try:
        ids = seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.55)
        memory = MemoryService(db)
        # Attempt the mid difficulty period problem recently
        memory.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="trigonometry",
                correct=True,
                mode="tutor",
                problem_id=ids["period_mid"],
            )
        )
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        assert result.problem is not None
        assert result.problem.id != ids["period_mid"]
        assert result.selection_reason.recent_repetition_penalty == 0 or (
            result.problem.id != ids["period_mid"]
        )
    finally:
        db.close()


def test_uses_error_dna():
    db = make_db()
    try:
        ids = seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.4)
        memory = MemoryService(db)
        for _ in range(2):
            memory.record(
                LearningRecordRequest(
                    subject="mathematics",
                    topic="trigonometry",
                    correct=False,
                    mistake_pattern="period confusion",
                    error_type="MISCONCEPTION",
                    related_concept="period",
                    mode="tutor",
                    problem_id=ids["period_high"],
                )
            )
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(subject="mathematics", topic="trigonometry")
        assert result.problem is not None
        assert result.problem.concept == "period"
        assert result.selection_reason is not None
        assert result.selection_reason.error_pattern_match is True
    finally:
        db.close()


def test_handles_no_candidate_problem():
    db = make_db()
    try:
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(
            subject="mathematics", topic="nonexistent_topic_xyz"
        )
        assert result.problem is None
        assert result.message
        assert "No problems" in result.message or "Not enough" in result.message
    finally:
        db.close()


def test_returns_deterministic_selection_reason():
    db = make_db()
    try:
        seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.55)
        engine = AdaptiveQuestionEngine(db)
        a = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        b = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        assert a.problem is not None and b.problem is not None
        assert a.problem.id == b.problem.id
        assert a.selection_reason is not None and b.selection_reason is not None
        assert a.selection_reason.topic_match == b.selection_reason.topic_match
        assert a.selection_reason.concept_match == b.selection_reason.concept_match
        assert a.selection_reason.difficulty_match == b.selection_reason.difficulty_match
        assert (
            a.selection_reason.recent_repetition_penalty
            == b.selection_reason.recent_repetition_penalty
        )
        assert a.selection_reason.score == b.selection_reason.score
        assert a.selection_reason.student_reasons == b.selection_reason.student_reasons
    finally:
        db.close()


def test_handles_old_attempts_without_problem_id():
    db = make_db()
    try:
        ids = seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.5)
        memory = MemoryService(db)
        # Legacy attempt — must not crash selection
        memory.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="trigonometry",
                correct=False,
                mistake_pattern="legacy",
                mode="tutor",
            )
        )
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        assert result.problem is not None
        assert result.problem.id in ids.values()
    finally:
        db.close()


def test_integrates_with_attempt_creation():
    db = make_db()
    try:
        ids = seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.5)
        engine = AdaptiveQuestionEngine(db)
        selected = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        assert selected.problem is not None
        loop = LearningLoopService(db)
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="trigonometry",
                concept="period",
                correct=False,
                mistake_pattern="period slip",
                error_type="MISCONCEPTION",
                mode="tutor",
                problem_id=selected.problem.id,
            )
        )
        assert outcome.attempt.attempt_id
        from app.models import Attempt

        attempt = db.get(Attempt, outcome.attempt.attempt_id)
        assert attempt is not None
        assert attempt.problem_id == selected.problem.id

        # Next selection should avoid the just-attempted problem by default
        nxt = engine.select_next_problem(
            subject="mathematics", topic="trigonometry", concept="period"
        )
        assert nxt.problem is not None
        assert nxt.problem.id != selected.problem.id
        assert ids  # pool still present
    finally:
        db.close()


def test_existing_learning_loop_remains_passing():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="arithmetic",
                correct=True,
                mode="tutor",
            )
        )
        assert outcome.attempt.attempt_id
        assert outcome.learning_trace is not None
    finally:
        db.close()


def test_next_problem_api_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.seed import init_db

    init_db()
    with TestClient(app) as client:
        created = client.post(
            "/api/problem-bank",
            json={
                "question": "Find the period of sin(2x).",
                "answer": "pi",
                "subject": "mathematics",
                "topic": "trigonometry",
                "concept": "period",
                "difficulty": 0.5,
                "metadata": {"error_targets": ["period"]},
            },
        )
        assert created.status_code == 200, created.text
        res = client.get(
            "/api/student/next-problem",
            params={"subject": "mathematics", "topic": "trigonometry", "concept": "period"},
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["problem"] is not None
        assert body["problem"]["topic"] == "trigonometry"
        assert "answer" not in body["problem"]
        assert body["selection_reason"]["topic_match"] is True
        assert isinstance(body["selection_reason"].get("student_reasons"), list)
        assert body["problem"]["gradable"] is True


def test_recommendation_drives_topic_and_concept():
    db = make_db()
    try:
        ids = seed_problems(db)
        set_mastery(db, "mathematics", "quadratic", 0.5)
        from app.models import RecommendationRecord

        db.add(
            RecommendationRecord(
                user_id=1,
                subject="mathematics",
                topic="trigonometry",
                reason="Review trigonometric period",
                action="practice",
                concept="period",
                status="active",
            )
        )
        db.commit()
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(subject="mathematics")
        assert result.problem is not None
        assert result.problem.topic == "trigonometry"
        assert result.problem.concept == "period"
        assert result.selection_reason is not None
        assert result.selection_reason.recommendation_used is True
        assert result.problem.id in {
            ids["period_low"],
            ids["period_mid"],
            ids["period_high"],
            ids["period_alt"],
        }
    finally:
        db.close()


def test_session_id_excludes_attempted_problem():
    db = make_db()
    try:
        ids = seed_problems(db)
        set_mastery(db, "mathematics", "trigonometry", 0.55)
        from app.models import LearningSession

        session = LearningSession(user_id=1, subject="mathematics", topic="trigonometry", status="active")
        db.add(session)
        db.commit()
        db.refresh(session)
        memory = MemoryService(db)
        memory.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="trigonometry",
                correct=False,
                mode="tutor",
                problem_id=ids["period_alt"],
                session_id=session.id,
            )
        )
        engine = AdaptiveQuestionEngine(db)
        result = engine.select_next_problem(
            subject="mathematics",
            topic="trigonometry",
            concept="period",
            session_id=session.id,
        )
        assert result.problem is not None
        assert result.problem.id != ids["period_alt"]
    finally:
        db.close()


def test_bank_answer_overrides_student_mark():
    db = make_db()
    try:
        ids = seed_problems(db)
        loop = LearningLoopService(db)
        wrong = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="trigonometry",
                concept="period",
                correct=True,
                answer="definitely-wrong",
                mode="tutor",
                problem_id=ids["period_mid"],
            )
        )
        assert wrong.bank_verified is True
        from app.models import Attempt

        attempt = db.get(Attempt, wrong.attempt.attempt_id)
        assert attempt is not None
        assert attempt.is_correct is False
        assert attempt.expected_answer == "x"

        right = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="trigonometry",
                concept="period",
                answer="X",
                mode="tutor",
                problem_id=ids["period_low"],
            )
        )
        assert right.bank_verified is True
        attempt2 = db.get(Attempt, right.attempt.attempt_id)
        assert attempt2 is not None
        assert attempt2.is_correct is True
    finally:
        db.close()


def test_empty_answer_falls_back_to_student_mark():
    db = make_db()
    try:
        ids = seed_problems(db)
        loop = LearningLoopService(db)
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="trigonometry",
                correct=True,
                mode="tutor",
                problem_id=ids["period_mid"],
            )
        )
        assert outcome.bank_verified is None
        from app.models import Attempt

        attempt = db.get(Attempt, outcome.attempt.attempt_id)
        assert attempt is not None
        assert attempt.is_correct is True
    finally:
        db.close()


def test_answers_match_is_deterministic():
    from app.application.adaptive_question_engine import answers_match

    assert answers_match("Pi", "pi") is True
    assert answers_match("  2.0 ", "2") is True
    assert answers_match("nope", "pi") is False
    assert answers_match("", "pi") is None
    assert answers_match("pi", None) is None
