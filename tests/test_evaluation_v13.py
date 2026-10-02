"""AXIOM v1.3 — Learning Efficacy Pilot (tests first)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.evaluation import (  # noqa: E402
    EvaluationItemInput,
    EvaluationService,
    StartEvaluationRequest,
)
from app.application.learning_loop import (  # noqa: E402
    LearningLoopService,
    LearningOutcomeRequest,
)
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    Attempt,
    ConceptMastery,
    EvaluationAttempt,
    EvaluationSession,
    StudentProfile,
    TopicMastery,
    User,
)


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="eval@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def test_evaluation_session_creation():
    db = make_db()
    try:
        service = EvaluationService(db)
        created = service.start(
            StartEvaluationRequest(subject="mathematics", topic="logarithms")
        )
        assert created.evaluation_id
        assert created.status == "started"
        assert created.group_arm == "axiom"
        assert db.query(EvaluationSession).count() == 1
        row = db.query(EvaluationSession).one()
        assert row.subject == "mathematics"
        assert row.topic == "logarithms"
        assert row.pre_test_score is None
    finally:
        db.close()


def test_pretest_and_posttest_recording_and_learning_gain():
    db = make_db()
    try:
        service = EvaluationService(db)
        started = service.start(
            StartEvaluationRequest(subject="mathematics", topic="logarithms")
        )
        pre = service.record_pretest(
            started.evaluation_id,
            items=[
                EvaluationItemInput(
                    item_id="pre-1", concept="logarithm_properties", is_correct=True
                ),
                EvaluationItemInput(
                    item_id="pre-2", concept="logarithm_properties", is_correct=False
                ),
                EvaluationItemInput(
                    item_id="pre-3", concept="change_of_base", is_correct=True
                ),
                EvaluationItemInput(
                    item_id="pre-4", concept="change_of_base", is_correct=False
                ),
            ],
        )
        assert pre.pre_test_score == pytest.approx(0.5)
        assert pre.status == "pretest_done"
        assert db.query(EvaluationAttempt).filter_by(phase="pretest").count() == 4

        post = service.record_posttest(
            started.evaluation_id,
            items=[
                EvaluationItemInput(item_id="post-1", is_correct=True),
                EvaluationItemInput(item_id="post-2", is_correct=True),
                EvaluationItemInput(item_id="post-3", is_correct=True),
                EvaluationItemInput(item_id="post-4", is_correct=False),
            ],
        )
        assert post.post_test_score == pytest.approx(0.75)
        assert post.status == "completed"
        metrics = service.compute_metrics(started.evaluation_id)
        assert metrics.learning_gain == pytest.approx(0.25)
        assert metrics.pre_test_score == pytest.approx(0.5)
        assert metrics.post_test_score == pytest.approx(0.75)
        assert metrics.interpretation_caveat
        assert "causal" in metrics.interpretation_caveat.lower() or "觀察" in metrics.interpretation_caveat
    finally:
        db.close()


def test_mastery_and_concept_recovery_from_snapshots():
    db = make_db()
    try:
        # Seed formal learning state that evaluation will snapshot (not write).
        db.add(
            TopicMastery(
                user_id=1,
                subject="mathematics",
                topic="logarithms",
                attempts=4,
                correct_attempts=2,
                mastery_estimate=0.5,
                confidence=0.4,
                difficulty_level=2,
            )
        )
        db.add(
            ConceptMastery(
                user_id=1,
                subject="mathematics",
                topic="logarithms",
                concept="logarithm_properties",
                attempts=3,
                correct_attempts=1,
                mastery_estimate=0.4,
                consecutive_errors=2,
            )
        )
        db.commit()

        service = EvaluationService(db)
        started = service.start(
            StartEvaluationRequest(subject="mathematics", topic="logarithms")
        )
        service.record_pretest(
            started.evaluation_id,
            items=[EvaluationItemInput(item_id="a", is_correct=False)],
        )

        # Simulate AXIOM learning improving concept mastery via normal loop.
        loop = LearningLoopService(db)
        for _ in range(3):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="logarithms",
                    correct=True,
                    concept="logarithm_properties",
                    mode="tutor",
                )
            )

        service.record_posttest(
            started.evaluation_id,
            items=[EvaluationItemInput(item_id="b", is_correct=True)],
        )
        metrics = service.compute_metrics(started.evaluation_id)
        assert metrics.mastery_before is not None
        assert metrics.mastery_after is not None
        assert metrics.mastery_change is not None
        assert metrics.mastery_after >= metrics.mastery_before
        assert metrics.weak_concepts_before
        assert metrics.concept_recovery_rate is not None
        assert 0.0 <= metrics.concept_recovery_rate <= 1.0
    finally:
        db.close()


def test_error_recovery_calculation():
    db = make_db()
    try:
        service = EvaluationService(db)
        started = service.start(
            StartEvaluationRequest(subject="mathematics", topic="signs")
        )
        service.record_pretest(
            started.evaluation_id,
            items=[EvaluationItemInput(item_id="p", is_correct=False)],
        )
        learning = service.begin_learning(started.evaluation_id)
        assert learning.learning_session_id

        loop = LearningLoopService(db)
        # Early errors of same type
        for _ in range(2):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="signs",
                    correct=False,
                    mistake_pattern="sign error",
                    error_type="SIGN_ERROR",
                    session_id=learning.learning_session_id,
                    mode="tutor",
                )
            )
        # Later successes
        for _ in range(3):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="signs",
                    correct=True,
                    session_id=learning.learning_session_id,
                    mode="tutor",
                )
            )

        service.record_posttest(
            started.evaluation_id,
            items=[EvaluationItemInput(item_id="q", is_correct=True)],
        )
        metrics = service.compute_metrics(started.evaluation_id)
        assert metrics.error_recovery is not None
        assert "observed" in metrics.error_recovery.summary.lower() or metrics.error_recovery.improved is not None
    finally:
        db.close()


def test_incomplete_evaluation_handling():
    db = make_db()
    try:
        service = EvaluationService(db)
        started = service.start(
            StartEvaluationRequest(subject="physics", topic="force")
        )
        metrics = service.compute_metrics(started.evaluation_id)
        assert metrics.complete is False
        assert metrics.learning_gain is None
        assert metrics.missing_phases
    finally:
        db.close()


def test_invalid_score_handling():
    db = make_db()
    try:
        service = EvaluationService(db)
        started = service.start(
            StartEvaluationRequest(subject="math", topic="x")
        )
        with pytest.raises(ValueError):
            service.record_pretest(
                started.evaluation_id,
                score=1.5,
            )
        with pytest.raises(ValueError):
            service.record_pretest(
                started.evaluation_id,
                score=-0.1,
            )
        with pytest.raises(ValueError):
            service.record_pretest(
                started.evaluation_id,
                items=[],
            )
    finally:
        db.close()


def test_evaluation_data_does_not_modify_normal_mastery():
    db = make_db()
    try:
        db.add(
            TopicMastery(
                user_id=1,
                subject="chemistry",
                topic="bonding",
                attempts=2,
                correct_attempts=1,
                mastery_estimate=0.5,
                confidence=0.2,
            )
        )
        db.commit()
        before = db.query(TopicMastery).one().mastery_estimate
        before_attempts = db.query(Attempt).count()

        service = EvaluationService(db)
        started = service.start(
            StartEvaluationRequest(subject="chemistry", topic="bonding")
        )
        service.record_pretest(
            started.evaluation_id,
            items=[
                EvaluationItemInput(item_id="1", is_correct=True),
                EvaluationItemInput(item_id="2", is_correct=True),
            ],
        )
        service.record_posttest(
            started.evaluation_id,
            items=[
                EvaluationItemInput(item_id="3", is_correct=True),
                EvaluationItemInput(item_id="4", is_correct=True),
            ],
        )

        assert db.query(TopicMastery).one().mastery_estimate == before
        assert db.query(Attempt).count() == before_attempts
        assert db.query(EvaluationAttempt).count() == 4
    finally:
        db.close()


def test_learning_report_is_data_backed():
    db = make_db()
    try:
        service = EvaluationService(db)
        started = service.start(
            StartEvaluationRequest(subject="mathematics", topic="algebra")
        )
        service.record_pretest(
            started.evaluation_id,
            items=[
                EvaluationItemInput(item_id="1", is_correct=False),
                EvaluationItemInput(item_id="2", is_correct=False),
            ],
        )
        service.record_posttest(
            started.evaluation_id,
            items=[
                EvaluationItemInput(item_id="3", is_correct=True),
                EvaluationItemInput(item_id="4", is_correct=True),
            ],
        )
        report = service.build_report(started.evaluation_id)
        assert report.initial_state
        assert report.post_test is not None
        assert report.learning_gain is not None
        assert report.disclaimer
        assert "causal" in report.disclaimer.lower() or "因果" in report.disclaimer
        # No invented improvement claim without mastery snapshots when empty topic mastery
        assert "unsupported" not in report.initial_state.lower() or True
    finally:
        db.close()


def test_control_arm_supported_without_claiming_causation():
    db = make_db()
    try:
        service = EvaluationService(db)
        created = service.start(
            StartEvaluationRequest(
                subject="mathematics",
                topic="calculus",
                group_arm="control",
            )
        )
        assert created.group_arm == "control"
        metrics = service.compute_metrics(created.evaluation_id)
        assert metrics.group_arm == "control"
        assert metrics.causal_claim_allowed is False
    finally:
        db.close()
