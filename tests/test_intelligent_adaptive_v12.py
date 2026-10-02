"""Axiom v1.2 intelligent adaptive learning scenarios F–N."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.schemas import TeachingMode  # noqa: E402
from app.application.difficulty_policy import DifficultyPolicy, DifficultySignals  # noqa: E402
from app.application.error_intelligence import (  # noqa: E402
    ErrorIntelligenceService,
    ErrorType,
    REPEATED_ERROR_THRESHOLD,
)
from app.application.learning_loop import LearningLoopService, LearningOutcomeRequest  # noqa: E402
from app.application.mastery_graph import MasteryGraphService  # noqa: E402
from app.application.tutor_strategy import TutorStrategy, TutorStrategyPolicy  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import ConceptMastery, StudentProfile, TopicMastery, User, utcnow  # noqa: E402


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="v12@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def test_scenario_f_low_mastery_repeated_failures_diagnosis_and_difficulty_drop():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        last = None
        for _ in range(3):
            last = loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="quadratic_equation",
                    correct=False,
                    mistake_pattern="sign error when transposing",
                    mode="tutor",
                    concept="equation_transformation",
                )
            )
        assert last is not None
        assert last.error_diagnosis is not None
        assert last.error_diagnosis.error_type == ErrorType.SIGN_ERROR
        assert last.tutor_strategy is not None
        assert last.tutor_strategy.strategy in {
            TutorStrategy.ERROR_DIAGNOSIS,
            TutorStrategy.CONCEPT,
        }
        assert last.difficulty_decision is not None
        assert last.difficulty_decision.recommended_difficulty < last.difficulty_decision.previous_difficulty or last.difficulty_decision.recommended_label == "easy"
        assert last.attempt.mastery < 0.5
        assert last.recommendation is not None
        assert last.recommendation.strategy in {"ERROR_DIAGNOSIS", "CONCEPT", "HINT"}
        assert last.learning_trace.mastery_delta is not None
    finally:
        db.close()


def test_scenario_g_verified_streak_raises_mastery_and_difficulty():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        # seed low then recover with verified corrects
        for _ in range(2):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="linear_equation",
                    correct=False,
                    mistake_pattern="arithmetic slip",
                )
            )
        before = loop.snapshot_mastery("mathematics", "linear_equation")["mastery"]
        last = None
        for i in range(5):
            last = loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="linear_equation",
                    correct=True,
                    verified=True,
                    mode="tutor",
                )
            )
        assert last is not None
        assert last.attempt.mastery > before
        assert last.difficulty_decision is not None
        # After strong streak, difficulty should not decrease
        assert last.difficulty_decision.action in {"increase", "hold"}
        assert last.recommendation is not None
        assert last.recommendation.why
    finally:
        db.close()


def test_scenario_h_duplicate_trace_is_idempotent():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        first = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="idempotent_topic",
                correct=True,
                trace_id="trace-same-001",
            )
        )
        second = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="idempotent_topic",
                correct=True,
                trace_id="trace-same-001",
            )
        )
        assert second.idempotent_replay is True
        assert second.attempt.attempt_id == first.attempt.attempt_id
        assert second.attempt.attempts == first.attempt.attempts
        assert second.attempt.mastery == first.attempt.mastery
    finally:
        db.close()


def test_scenario_i_repeated_error_detection_threshold():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        intel = ErrorIntelligenceService(db)
        for _ in range(REPEATED_ERROR_THRESHOLD):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="signs",
                    correct=False,
                    mistake_pattern="sign error",
                    error_type="SIGN_ERROR",
                    concept="equation_transformation",
                )
            )
        patterns = intel.list_patterns(unresolved_only=True)
        assert patterns
        assert patterns[0].error_type == "SIGN_ERROR"
        assert patterns[0].count >= REPEATED_ERROR_THRESHOLD
        assert patterns[0].resolved is False
        last = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="signs",
                correct=False,
                mistake_pattern="sign error",
                error_type="SIGN_ERROR",
                concept="equation_transformation",
            )
        )
        assert last.error_diagnosis is not None
        assert last.error_diagnosis.is_repeated_error is True
        assert last.tutor_strategy.strategy == TutorStrategy.CONCEPT
    finally:
        db.close()


def test_scenario_j_mastery_graph_updates_concept_and_topic():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="quadratic_function",
                correct=True,
                concept="roots",
            )
        )
        loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="quadratic_function",
                correct=False,
                mistake_pattern="discriminant confusion",
                concept="discriminant",
            )
        )
        graph = MasteryGraphService(db).snapshot(
            subject="mathematics",
            topic="quadratic_function",
            topic_mastery=loop.snapshot_mastery("mathematics", "quadratic_function")["mastery"],
        )
        concepts = {item.concept: item.mastery for item in graph.concepts}
        assert "roots" in concepts
        assert "discriminant" in concepts
        assert concepts["roots"] > concepts["discriminant"]
        assert graph.weakest_concept == "discriminant"
    finally:
        db.close()


def test_scenario_k_prerequisite_weakness_redirects_recommendation():
    db = make_db()
    try:
        graph_svc = MasteryGraphService(db)
        # Build topic-level moderate mastery via loop
        loop = LearningLoopService(db)
        for correct in (True, True, False):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="quadratic_function",
                    correct=correct,
                    concept="root_coefficient_relationship",
                    mistake_pattern=None if correct else "root coefficient confusion",
                )
            )
        # Force weaker prerequisite concept
        graph_svc.update_concept(
            subject="mathematics",
            topic="quadratic_function",
            concept="equation_transformation",
            correct=False,
        )
        graph_svc.update_concept(
            subject="mathematics",
            topic="quadratic_function",
            concept="equation_transformation",
            correct=False,
        )
        graph_svc.update_concept(
            subject="mathematics",
            topic="quadratic_function",
            concept="equation_transformation",
            correct=False,
        )
        snap = loop.snapshot_mastery("mathematics", "quadratic_function")
        graph = graph_svc.snapshot(
            subject="mathematics",
            topic="quadratic_function",
            topic_mastery=float(snap["mastery"]),
        )
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="quadratic_function",
                correct=False,
                mistake_pattern="root coefficient confusion",
                concept="root_coefficient_relationship",
            )
        )
        assert outcome.recommendation is not None
        # Bottleneck should surface either in recommendation concept or weakness
        assert (
            outcome.recommendation.concept == "equation_transformation"
            or (outcome.learning_trace.weakness or {}).get("concept")
            == "equation_transformation"
            or graph.bottleneck_concept == "equation_transformation"
        )
    finally:
        db.close()


def test_scenario_l_spaced_review_for_high_mastery_stale_topic():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        for _ in range(4):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="spaced_topic",
                    correct=True,
                    verified=True,
                )
            )
        row = (
            db.query(TopicMastery)
            .filter(TopicMastery.topic == "spaced_topic")
            .one()
        )
        row.mastery_estimate = 0.82
        row.last_practiced_at = utcnow() - timedelta(days=10)
        row.next_review_at = utcnow() - timedelta(days=1)
        db.commit()

        decision = DifficultyPolicy().decide(
            DifficultySignals(
                mastery=0.82,
                recent_accuracy=0.9,
                current_difficulty=4,
                spaced_review_due=True,
            )
        )
        assert decision.action == "review"
        strategy = TutorStrategyPolicy().decide(
            mastery=0.82,
            spaced_review_due=True,
            recent_accuracy=0.9,
            attempts=4,
        )
        assert strategy.strategy == TutorStrategy.REVIEW
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="spaced_topic",
                correct=True,
                verified=True,
            )
        )
        assert outcome.recommendation is not None
        assert outcome.recommendation.due_for_review or outcome.recommendation.strategy == "REVIEW"
        assert "review" in outcome.recommendation.why.lower()
    finally:
        db.close()


def test_scenario_m_learning_trace_persists_full_decision_chain():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="trace_topic",
                correct=False,
                mistake_pattern="sign error",
                answer="-3",
                expected_answer="3",
                question_id=None,
                trace_id="trace-full-m",
                concept="equation_transformation",
            )
        )
        trace = outcome.learning_trace
        assert trace.student_state is not None
        assert trace.error_diagnosis is not None
        assert trace.tutor_decision
        assert trace.difficulty_decision
        assert trace.attempt
        assert trace.mastery_before is not None
        assert trace.mastery_after is not None
        assert trace.mastery_delta is not None
        assert trace.recommendation is not None or trace.next_recommendation is not None
    finally:
        db.close()


def test_scenario_n_cross_topic_isolation():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        for _ in range(3):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="algebra",
                    correct=False,
                    mistake_pattern="sign error",
                )
            )
        physics = loop.record_outcome(
            LearningOutcomeRequest(
                subject="physics",
                topic="forces",
                correct=True,
                verified=True,
            )
        )
        math_state = loop.snapshot_mastery("mathematics", "algebra")
        phys_state = loop.snapshot_mastery("physics", "forces")
        assert math_state["consecutive_errors"] >= 2
        assert phys_state["consecutive_errors"] == 0
        assert phys_state["mastery"] > 0
        assert physics.recommendation is not None
        assert physics.recommendation.subject == "physics"
        assert physics.recommendation.topic == "forces"
        # Math recommendation list may exist, but physics outcome must not rewrite math topic fields
        assert math_state["subject"] == "mathematics"
    finally:
        db.close()


def test_difficulty_policy_bounds():
    policy = DifficultyPolicy()
    decision = policy.decide(
        DifficultySignals(
            mastery=0.1,
            recent_accuracy=0.0,
            consecutive_errors=5,
            repeated_failures=5,
            current_difficulty=1,
        )
    )
    assert decision.recommended_difficulty >= 1
    decision2 = policy.decide(
        DifficultySignals(
            mastery=0.95,
            recent_accuracy=1.0,
            consecutive_verified=5,
            current_difficulty=5,
        )
    )
    assert decision2.recommended_difficulty <= 5
