"""Agent Core tests: bounded planning, tools, trace persistence and uncertainty."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.planner import Planner  # noqa: E402
from app.agent.schemas import AgentRunRequest, TeachingMode  # noqa: E402
from app.agent.service import AgentService  # noqa: E402
from app.application.subject_aliases import normalize_learning_label  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import Attempt, User  # noqa: E402
from app.providers.base import ModelProvider  # noqa: E402
from app.providers.types import GenerateRequest, GenerateResponse, ProviderId  # noqa: E402
from app.tools.base import Tool, ToolResult  # noqa: E402
from app.tools.router import ToolRouter  # noqa: E402


class FakeProvider(ModelProvider):
    provider_id = ProviderId.OLLAMA
    model = "fake-model"

    @property
    def name(self) -> str:
        return "fake"

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            content=f"guided: {request.message}",
            provider=self.provider_id,
            model=self.model,
        )


class FakeKnowledgeTool(Tool):
    name = "knowledge_search"
    description = "test"
    input_schema = {}
    output_schema = {}

    async def execute(self, payload):
        return ToolResult(
            ok=True,
            output={
                "results": [
                    {
                        "document_title": "Notes",
                        "page": 1,
                        "text": "Untrusted matrix notes",
                    }
                ]
            },
            execution_time_ms=1.0,
        )


def test_planner_is_bounded():
    plan = Planner(max_steps=2).plan(
        AgentRunRequest(
            message="solve x + 2 = 3",
            material_id=1,
            mode=TeachingMode.TUTOR,
        ),
        ["knowledge_search", "math"],
    )
    assert len(plan.steps) == 2
    assert plan.metadata["bounded"] is True


@pytest.mark.asyncio
async def test_agent_run_persists_trace_and_marks_partial_verification():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id=1, name="Student", email="student@example.local"))
        db.commit()
        service = AgentService(
            db,
            FakeProvider(),
            ToolRouter([FakeKnowledgeTool()]),
            planner=Planner(max_steps=4),
        )
        result = await service.run(
            AgentRunRequest(
                message="Explain matrix",
                material_id=1,
                mode=TeachingMode.HINT,
            )
        )
        assert result.trace_id
        assert result.provider == "fake"
        assert result.tool_calls[0].tool == "knowledge_search"
        # Knowledge-only tools are not math verifiers → NOT_VERIFIABLE, no scary footer.
        assert result.verification_status.value == "NOT_VERIFIABLE"
        assert "驗證狀態" not in result.final_answer
        assert "未獲完整工具驗證" not in result.final_answer
        stored = service.get_trace(result.trace_id)
        assert stored is not None
        assert stored.status == "completed"
        assert stored.trace_id == result.trace_id


@pytest.mark.asyncio
async def test_agent_without_tools_is_not_verifiable():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id=1, name="Student", email="student2@example.local"))
        db.commit()
        result = await AgentService(db, FakeProvider(), ToolRouter()).run(
            AgentRunRequest(message="What is history?")
        )
        assert result.verification_status.value == "NOT_VERIFIABLE"


def test_normalize_learning_label_treats_general_as_missing():
    assert normalize_learning_label("general") is None
    assert normalize_learning_label("GENERAL") is None
    assert normalize_learning_label("分數") == "分數"
    assert normalize_learning_label("  ") is None


@pytest.mark.asyncio
async def test_agent_general_topic_does_not_auto_record_attempt():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(User(id=1, name="Student", email="student3@example.local"))
        db.commit()
        result = await AgentService(db, FakeProvider(), ToolRouter()).run(
            AgentRunRequest(
                message="幫我複習",
                subject="mathematics",
                topic="general",
                mode=TeachingMode.TUTOR,
            )
        )
        assert result.trace_id
        attempts = db.query(Attempt).count()
        assert attempts == 0
