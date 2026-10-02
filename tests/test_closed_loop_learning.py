"""Closed-loop learning integration scenarios A–E."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.schemas import AgentRunRequest, TeachingMode, VerificationStatus  # noqa: E402
from app.agent.service import AgentService  # noqa: E402
from app.application.adaptive import AdaptiveTutor  # noqa: E402
from app.application.learning_loop import (  # noqa: E402
    LearningLoopService,
    LearningOutcomeRequest,
)
from app.application.memory import LearningRecordRequest, MemoryService  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    AgentTrace,
    Attempt,
    LearningSession,
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


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="loop@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def test_scenario_a_correct_answer_increases_mastery():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        first = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="linear",
                correct=True,
                mode="tutor",
            )
        )
        second = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="linear",
                correct=True,
                mode="tutor",
                session_id=first.attempt.session_id,
            )
        )
        assert second.attempt.mastery > first.attempt.mastery
        assert second.attempt.session_id == first.attempt.session_id
        assert db.query(LearningSession).count() == 1
        assert second.recommendation is not None
        assert second.recommendation.why
        assert second.learning_trace.mastery_update["after"] == second.attempt.mastery
    finally:
        db.close()


def test_scenario_b_repeated_mistake_detects_misconception_and_changes_recommendation():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        first = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="signs",
                correct=False,
                mistake_pattern="sign error",
                mode="tutor",
            )
        )
        second = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="signs",
                correct=False,
                mistake_pattern="sign error",
                mode="tutor",
                session_id=first.attempt.session_id,
            )
        )
        assert second.attempt.misconception
        assert "sign error" in second.attempt.misconception
        assert second.recommendation is not None
        why = second.recommendation.why.lower()
        assert (
            "concept review" in why
            or "failed" in why
            or "error" in why
            or "sign" in why
        )
        assert second.recommendation.recommended_difficulty == "easy"
        assert second.recommendation.sequence
        assert first.recommendation.action != second.recommendation.action or first.recommendation.why != second.recommendation.why
    finally:
        db.close()


def test_scenario_c_repeated_failure_decreases_difficulty_and_recommends_concept_review():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        session_id = None
        for _ in range(3):
            result = loop.record_outcome(
                LearningOutcomeRequest(
                    subject="physics",
                    topic="newton",
                    correct=False,
                    mistake_pattern="force direction",
                    mode="direct_solve",
                    session_id=session_id,
                )
            )
            session_id = result.attempt.session_id
        mastery = db.query(TopicMastery).one()
        assert mastery.consecutive_errors >= 2
        assert mastery.recommended_difficulty == "easy"
        assert result.recommendation.recommended_difficulty == "easy"
        assert "Review concept" in result.recommendation.sequence
        adapted, reason = loop.adapt_teaching_mode(
            TeachingMode.DIRECT_SOLVE,
            subject="physics",
            topic="newton",
        )
        assert adapted in {TeachingMode.CONCEPT, TeachingMode.ERROR_DIAGNOSIS}
        assert (
            "concept" in reason.lower()
            or "error" in reason.lower()
            or "diagnos" in reason.lower()
            or "lower" in reason.lower()
            or "fail" in reason.lower()
        )
    finally:
        db.close()


def test_scenario_d_success_after_review_recovers_mastery_and_changes_recommendation():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        fail = None
        for _ in range(2):
            fail = loop.record_outcome(
                LearningOutcomeRequest(
                    subject="chemistry",
                    topic="stoichiometry",
                    correct=False,
                    mistake_pattern="mole ratio",
                    mode="concept",
                )
            )
        assert fail.recommendation.recommended_difficulty == "easy"
        recoveries = []
        for _ in range(4):
            recoveries.append(
                loop.record_outcome(
                    LearningOutcomeRequest(
                        subject="chemistry",
                        topic="stoichiometry",
                        correct=True,
                        mode="tutor",
                        session_id=fail.attempt.session_id,
                    )
                )
            )
        last = recoveries[-1]
        assert last.attempt.mastery > fail.attempt.mastery
        assert last.attempt.consecutive_errors == 0
        assert last.recommendation is not None
        assert last.recommendation.action != fail.recommendation.action
        if last.attempt.mastery >= 0.8 and last.attempt.attempts >= 3:
            assert last.recommendation.recommended_difficulty == "challenging"
    finally:
        db.close()


@pytest.mark.asyncio
async def test_scenario_e_image_vision_agent_solver_verification_attempt_mastery_recommendation():
    db = make_db()
    try:
        service = AgentService(
            db,
            FakeProvider(),
            ToolRouter([FakeMathTool()]),
        )
        result = await service.run(
            AgentRunRequest(
                message="solve 1+1",
                confirmed_problem="Compute 1 + 1",
                input_type="image",
                subject="mathematics",
                topic="arithmetic",
                mode=TeachingMode.DIRECT_SOLVE,
                record_attempt=True,
            )
        )
        assert result.session_id is not None
        assert result.question_id is not None
        assert result.learning_trace
        assert "math" in result.learning_trace.get("selected_tools", [])
        assert result.verification_status == VerificationStatus.VERIFIED
        assert result.learning_trace.get("mastery_update") is not None
        assert result.recommendation is not None
        assert result.recommendation["why"]
        assert result.learning_trace["mastery_update"]["after"] > result.learning_trace["mastery_update"]["before"]

        stored = db.query(AgentTrace).filter_by(trace_id=result.trace_id).one()
        assert stored.session_id == result.session_id
        assert stored.question_id == result.question_id
        assert stored.learning_trace_json
        assert db.query(Attempt).filter_by(session_id=result.session_id).count() >= 1
        assert db.query(RecommendationRecord).filter_by(status="active").count() >= 1
        learning = service.get_learning_trace(result.trace_id)
        assert learning is not None
        assert learning.get("session_id") == result.session_id
        assert learning.get("verification") == "VERIFIED"
    finally:
        db.close()


def test_tutor_receives_student_model_before_mode_and_repeated_mistakes_change_behavior():
    db = make_db()
    try:
        loop = LearningLoopService(db)
        for _ in range(2):
            loop.record_outcome(
                LearningOutcomeRequest(
                    subject="mathematics",
                    topic="fractions",
                    correct=False,
                    mistake_pattern="common denominator",
                    mode="tutor",
                )
            )
        adapted, reason = loop.adapt_teaching_mode(
            TeachingMode.TUTOR,
            subject="mathematics",
            topic="fractions",
        )
        assert adapted in {TeachingMode.CONCEPT, TeachingMode.ERROR_DIAGNOSIS}
        decision = AdaptiveTutor(db).decide(
            subject="mathematics",
            topic="fractions",
            mode=adapted,
        )
        assert decision.strategy == "concept_recovery"
        assert decision.question_difficulty == "easy"
        assert "consecutive" in decision.why.lower() or "mistake" in decision.why.lower()
        assert (
            "concept" in reason.lower()
            or "diagnos" in reason.lower()
            or "fail" in reason.lower()
        )
    finally:
        db.close()


@pytest.mark.asyncio
async def test_agent_run_links_session_question_and_learning_trace():
    db = make_db()
    try:
        result = await AgentService(db, FakeProvider(), ToolRouter()).run(
            AgentRunRequest(
                message="Explain gravity",
                subject="physics",
                topic="gravity",
                mode=TeachingMode.TUTOR,
            )
        )
        assert result.session_id
        assert result.question_id
        assert result.learning_trace["student_state"]["topic"] == "gravity"
        assert result.learning_trace["agent_decision"]["adapted_mode"]
        assert db.query(LearningSession).filter_by(id=result.session_id).one().activity_count >= 1
    finally:
        db.close()
