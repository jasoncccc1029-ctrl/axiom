"""Solver leans on Context Policy when subject/topic are present."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.problem_solver import (  # noqa: E402
    ProblemSolveRequest,
    ProblemSolverService,
)
from app.tools.base import ToolResult  # noqa: E402


@pytest.mark.asyncio
async def test_solver_passes_learner_context_when_subject_present():
    seen: dict[str, object] = {}

    provider = MagicMock()
    provider.name = "ollama"
    provider.model = "llama3.2:latest"

    async def _solve(problem, subject=None, context=None):
        seen["subject"] = subject
        seen["context"] = context
        return {"answer": "x=3"}

    provider.solve = AsyncMock(side_effect=_solve)

    learning_state = MagicMock()
    learning_state.get.return_value = MagicMock(
        model_dump=lambda: {
            "subject": "高二數學",
            "current_topic": "二次函數",
            "mastery": 0.4,
            "repeated_error_patterns": [{"pattern": "sign_error", "count": 2}],
            "recent_errors": [],
            "recent_learning_activity": [],
        }
    )
    student_model = MagicMock()
    student_model.student.return_value = MagicMock(
        weak_concepts=["二次函數"],
        strong_concepts=["一次式"],
        mastery=[],
    )

    math_tool = MagicMock()
    math_tool.execute = AsyncMock(
        return_value=ToolResult(ok=True, output={"result": "3"}, execution_time_ms=1)
    )

    service = ProblemSolverService(
        provider,
        learning_state=learning_state,
        student_model=student_model,
        math_tool=math_tool,
    )
    response = await service.solve(
        ProblemSolveRequest(
            problem="solve 2*x+4=10",
            subject="mathematics",
            topic="general",
        )
    )

    assert response.personalized is True
    assert response.subject == "高二數學"
    assert response.topic is None  # placeholder stripped
    assert seen["subject"] == "高二數學"
    assert isinstance(seen["context"], str)
    assert "TRUSTED" in seen["context"]
    assert "二次函數" in seen["context"] or "sign_error" in seen["context"]


@pytest.mark.asyncio
async def test_solver_without_subject_is_not_personalized():
    provider = MagicMock()
    provider.name = "ollama"
    provider.model = "m"
    provider.solve = AsyncMock(return_value={"answer": "4"})

    math_tool = MagicMock()
    math_tool.execute = AsyncMock(
        return_value=ToolResult(ok=True, output={"result": "4"}, execution_time_ms=1)
    )

    service = ProblemSolverService(provider, math_tool=math_tool)
    response = await service.solve(ProblemSolveRequest(problem="2+2"))
    assert response.personalized is False
    provider.solve.assert_awaited()
    call = provider.solve.await_args
    assert call.kwargs.get("context") is None
