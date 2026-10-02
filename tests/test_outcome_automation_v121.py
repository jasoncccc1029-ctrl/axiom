"""AXIOM v1.2.1 — Outcome Automation & Loop Integrity."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.schemas import AgentRunRequest, TeachingMode, VerificationStatus  # noqa: E402
from app.agent.service import AgentService, _should_auto_record  # noqa: E402
from app.application.learning_loop import (  # noqa: E402
    LearningLoopService,
    LearningOutcomeRequest,
)
from app.application.outcome_automation import (  # noqa: E402
    LearningOutcomeStatus,
    decide_from_student_mark,
    decide_from_verification,
)
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    Attempt,
    LearningSession,
    Mistake,
    RecommendationRecord,
    StudentProfile,
    TopicMastery,
    User,
)
from app.providers.base import ModelProvider  # noqa: E402
from app.providers.types import GenerateRequest, GenerateResponse, ProviderId  # noqa: E402
from app.tools.base import Tool, ToolResult  # noqa: E402
from app.tools.router import ToolRouter  # noqa: E402


class FakeProvider(ModelProvider):
    provider_id = ProviderId.OLLAMA
    model = "fake-model"

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            content=f"tutor:{request.message[:80]}",
            provider=self.provider_id,
            model=self.model,
        )


class FakeMathTool(Tool):
    name = "math"
    description = "fake math"
    input_schema = {}
    output_schema = {}

    async def execute(self, payload):
        return ToolResult(
            ok=True,
            output={"result": "2", "expression": "1+1", "verified": True},
            execution_time_ms=1.0,
        )


class FakeFailMathTool(Tool):
    name = "math"
    description = "fake failing math"
    input_schema = {}
    output_schema = {}

    async def execute(self, payload):
        return ToolResult(
            ok=False,
            output={},
            error="compute failed",
            execution_time_ms=1.0,
        )


class FakePartialMathTool(Tool):
    name = "math"
    description = "fake partial math"
    input_schema = {}
    output_schema = {}

    async def execute(self, payload):
        return ToolResult(
            ok=True,
            output={"result": "2", "expression": "1+1", "verified": False},
            execution_time_ms=1.0,
        )


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="v121@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def test_outcome_rules_verified_failed_partial_needs_review():
    verified = decide_from_verification(
        verification=VerificationStatus.VERIFIED,
        route="solver",
        tool_names=["math"],
    )
    assert verified.status == LearningOutcomeStatus.VERIFIED
    assert verified.should_update_mastery is True

    failed = decide_from_verification(
        verification=VerificationStatus.FAILED,
        route="solver",
        tool_names=["math"],
    )
    assert failed.status == LearningOutcomeStatus.FAILED
    assert failed.should_update_mastery is True

    partial = decide_from_verification(
        verification=VerificationStatus.PARTIALLY_VERIFIED,
        route="tutor",
        tool_names=["math"],
    )
    assert partial.status == LearningOutcomeStatus.PARTIALLY_VERIFIED
    assert partial.should_update_mastery is False
    assert "不足以判定" in partial.student_message

    needs = decide_from_verification(
        verification=VerificationStatus.NOT_VERIFIABLE,
        route="tutor",
        tool_names=[],
    )
    assert needs.status == LearningOutcomeStatus.NEEDS_REVIEW
    assert needs.should_update_mastery is False

    mark = decide_from_student_mark(correct=True)
    assert mark.status == LearningOutcomeStatus.VERIFIED
    assert mark.should_update_mastery is True


def test_tutor_route_with_trusted_tools_can_auto_record():
    assert (
        _should_auto_record(
            AgentRunRequest(message="1+1", record_attempt=None),
            "tutor",
            VerificationStatus.VERIFIED,
            tool_names=["math"],
        )
        is True
    )
    assert (
        _should_auto_record(
            AgentRunRequest(message="explain", record_attempt=None),
            "tutor",
            VerificationStatus.NOT_VERIFIABLE,
            tool_names=[],
        )
        is False
    )


@pytest.mark.asyncio
async def test_tutor_successful_outcome_records_attempt_and_mastery():
    db = make_db()
    try:
        result = await AgentService(
            db, FakeProvider(), ToolRouter([FakeMathTool()])
        ).run(
            AgentRunRequest(
                message="solve 1+1",
                subject="mathematics",
                topic="arithmetic",
                mode=TeachingMode.DIRECT_SOLVE,
                record_attempt=True,
            )
        )
        assert result.verification_status == VerificationStatus.VERIFIED
        assert result.learning_trace["outcome_status"] == "VERIFIED"
        assert result.learning_trace["mastery_update"] is not None
        assert result.learning_trace["mastery_updated"] is True
        assert db.query(Attempt).count() == 1
        mastery = db.query(TopicMastery).one()
        assert mastery.correct_attempts == 1
        assert mastery.attempts == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_tutor_failed_outcome_records_mistake():
    db = make_db()
    try:
        result = await AgentService(
            db, FakeProvider(), ToolRouter([FakeFailMathTool()])
        ).run(
            AgentRunRequest(
                message="solve broken",
                subject="mathematics",
                topic="arithmetic",
                mode=TeachingMode.DIRECT_SOLVE,
                record_attempt=True,
            )
        )
        assert result.verification_status == VerificationStatus.FAILED
        assert result.learning_trace["outcome_status"] == "FAILED"
        assert db.query(Attempt).filter_by(is_correct=False).count() == 1
        assert db.query(Mistake).count() >= 1
        mastery = db.query(TopicMastery).one()
        assert mastery.consecutive_errors >= 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_e2e_tutor_outcome_attempt_mastery_difficulty_recommendation_trace():
    db = make_db()
    try:
        service = AgentService(db, FakeProvider(), ToolRouter([FakeMathTool()]))
        result = await service.run(
            AgentRunRequest(
                message="solve 1+1",
                subject="mathematics",
                topic="algebra",
                mode=TeachingMode.DIRECT_SOLVE,
                record_attempt=True,
            )
        )
        assert result.session_id
        assert result.learning_trace["mastery_update"] is not None
        assert result.learning_trace["difficulty_decision"] is not None
        assert result.recommendation is not None
        assert result.recommendation["why"]
        assert result.learning_trace["outcome_status"] == "VERIFIED"
        assert result.learning_trace["verification"] == "VERIFIED"
        assert db.query(Attempt).count() == 1
        assert db.query(RecommendationRecord).filter_by(status="active").count() == 1
        mastery = db.query(TopicMastery).one()
        assert mastery.mastery_estimate > 0
        assert mastery.difficulty_level is not None
        learning = service.get_learning_trace(result.trace_id)
        assert learning["mastery_update"]["after"] == mastery.mastery_estimate
    finally:
        db.close()


@pytest.mark.asyncio
async def test_same_trace_id_twice_no_duplicate_learning_update():
    db = make_db()
    try:
        service = AgentService(db, FakeProvider(), ToolRouter([FakeMathTool()]))
        first = await service.run(
            AgentRunRequest(
                message="solve 1+1",
                subject="mathematics",
                topic="idempotent",
                mode=TeachingMode.DIRECT_SOLVE,
                record_attempt=True,
            )
        )
        loop = LearningLoopService(db)
        before_attempts = db.query(Attempt).count()
        before_mastery = db.query(TopicMastery).one().mastery_estimate
        before_recs = db.query(RecommendationRecord).count()

        replay = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="idempotent",
                correct=True,
                session_id=first.session_id,
                trace_id=first.trace_id,
                outcome_source="tool_verifier",
            )
        )
        assert replay.idempotent_replay is True
        assert db.query(Attempt).count() == before_attempts
        assert db.query(TopicMastery).one().mastery_estimate == before_mastery
        assert db.query(RecommendationRecord).count() == before_recs
        assert replay.learning_trace.attempt["idempotent_replay"] is True
    finally:
        db.close()


@pytest.mark.asyncio
async def test_partially_verified_does_not_increase_mastery():
    db = make_db()
    try:
        result = await AgentService(
            db, FakeProvider(), ToolRouter([FakePartialMathTool()])
        ).run(
            AgentRunRequest(
                message="solve 1+1",
                subject="mathematics",
                topic="partial",
                mode=TeachingMode.DIRECT_SOLVE,
                record_attempt=True,
            )
        )
        assert result.verification_status == VerificationStatus.PARTIALLY_VERIFIED
        assert result.learning_trace["outcome_status"] == "PARTIALLY_VERIFIED"
        assert result.learning_trace.get("mastery_update") is None
        assert result.learning_trace["mastery_updated"] is False
        assert db.query(Attempt).count() == 0
        assert db.query(TopicMastery).count() == 0
        assert "不足以判定" in (result.learning_trace.get("outcome_student_message") or "")
    finally:
        db.close()


@pytest.mark.asyncio
async def test_needs_review_does_not_increase_mastery():
    db = make_db()
    try:
        result = await AgentService(db, FakeProvider(), ToolRouter()).run(
            AgentRunRequest(
                message="Explain the concept of gravity gently",
                subject="physics",
                topic="gravity",
                mode=TeachingMode.TUTOR,
            )
        )
        assert result.learning_trace["outcome_status"] == "NEEDS_REVIEW"
        assert result.learning_trace.get("mastery_update") is None
        assert result.learning_trace["mastery_updated"] is False
        assert db.query(Attempt).count() == 0
        assert db.query(TopicMastery).count() == 0
    finally:
        db.close()


def test_learning_session_lifecycle_started_active_ended():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        session = loop.get_or_create_session(subject="math", topic="life")
        assert session.status == "started"
        loop.bump_session(session, 2)
        assert session.status == "active"
        db.commit()
        ended = loop.end_session(session.id)
        assert ended is not None
        assert ended.status == "ended"
        assert ended.ended_at is not None
    finally:
        db.close()


def test_student_mark_still_updates_mastery_after_needs_review():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        session = loop.get_or_create_session(subject="math", topic="mark")
        loop.bump_session(session, 1)
        db.commit()
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="math",
                topic="mark",
                correct=True,
                session_id=session.id,
                trace_id="mark-trace-001",
            )
        )
        assert outcome.learning_trace.outcome_status == "VERIFIED"
        assert outcome.learning_trace.outcome_evidence == ["student_mark"]
        assert outcome.attempt.mastery > 0
        assert db.query(Attempt).count() == 1
    finally:
        db.close()
