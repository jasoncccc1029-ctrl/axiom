"""v1 API contract tests with application-service dependencies mocked."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.schemas import (  # noqa: E402
    AgentRunResponse,
    AgentTraceResponse,
    TeachingMode,
    VerificationStatus,
)
from app.application.adaptive import RecommendationsResponse  # noqa: E402
from app.application.memory import LearningRecordResponse  # noqa: E402
from app.dependencies import (  # noqa: E402
    provide_adaptive_tutor,
    provide_agent_service,
    provide_memory_service,
)
from app.main import app  # noqa: E402


def agent_response(trace_id: str = "a" * 32):
    return AgentRunResponse(
        trace_id=trace_id,
        steps=[
            {
                "index": 1,
                "action": "compose_tutor_response",
                "tool": None,
                "reason": "test",
            }
        ],
        tool_calls=[],
        final_answer="Tutor response",
        verification_status=VerificationStatus.NOT_VERIFIABLE,
        mode=TeachingMode.TUTOR,
        provider="fake",
        model="fake-model",
        latency_ms=1.2,
    )


def test_v1_openapi_contains_required_endpoints():
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/health",
        "/api/chat",
        "/api/vision/analyze",
        "/api/materials/upload",
        "/api/materials",
        "/api/materials/{material_id}",
        "/api/problems/solve",
        "/api/agent/run",
        "/api/learning/record",
        "/api/progress",
        "/api/recommendations",
        "/api/agent/{trace_id}",
        "/api/learning/trace/{trace_id}",
        "/api/learning/outcome",
        "/api/student",
        "/api/topics",
        "/api/mastery",
        "/api/memory",
    ):
        assert path in paths


def test_agent_run_and_trace_api_are_service_driven():
    service = MagicMock()
    service.run = AsyncMock(return_value=agent_response())
    service.get_trace.return_value = AgentTraceResponse(
        **agent_response().model_dump(),
        status="completed",
    )
    app.dependency_overrides[provide_agent_service] = lambda: service
    try:
        with TestClient(app) as client:
            run = client.post("/api/agent/run", json={"message": "Explain matrices"})
            trace = client.get(f"/api/agent/{'a' * 32}")
    finally:
        app.dependency_overrides.pop(provide_agent_service, None)
    assert run.status_code == 200
    assert run.json()["trace_id"] == "a" * 32
    assert trace.status_code == 200
    assert trace.json()["status"] == "completed"


def test_learning_and_recommendation_api_contracts():
    memory = MagicMock()
    memory.record.return_value = LearningRecordResponse(
        attempt_id=10,
        mastery=0.4,
        attempts=2,
        correct_attempts=0,
        consecutive_errors=2,
    )
    adaptive = MagicMock()
    adaptive.recommendations.return_value = RecommendationsResponse(
        recommendations=[],
        enough_data=False,
        message="Not enough data yet.",
    )
    app.dependency_overrides[provide_memory_service] = lambda: memory
    app.dependency_overrides[provide_adaptive_tutor] = lambda: adaptive
    try:
        with TestClient(app) as client:
            record = client.post(
                "/api/learning/record",
                json={
                    "subject": "math",
                    "topic": "equations",
                    "correct": False,
                },
            )
            recommendations = client.get("/api/recommendations")
    finally:
        app.dependency_overrides.pop(provide_memory_service, None)
        app.dependency_overrides.pop(provide_adaptive_tutor, None)
    assert record.status_code == 200
    assert record.json()["consecutive_errors"] == 2
    assert recommendations.json()["message"] == "Not enough data yet."
