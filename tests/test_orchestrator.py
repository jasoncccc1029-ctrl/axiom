"""Orchestrator routes only the tools that the intent actually needs."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.orchestrator import AgentOrchestrator, Intent  # noqa: E402
from app.agent.planner import Planner  # noqa: E402
from app.agent.schemas import AgentRunRequest, TeachingMode  # noqa: E402


TOOLS = ["knowledge_search", "math", "python"]


def test_explain_request_does_not_call_math_tool():
    decision = AgentOrchestrator().decide(
        AgentRunRequest(message="Explain matrix", material_id=1, mode=TeachingMode.HINT),
        TOOLS,
    )
    assert decision.intent == Intent.RAG
    assert decision.tools == ["knowledge_search"]
    assert "math" not in decision.tools


def test_explicit_solve_uses_math_and_not_python():
    decision = AgentOrchestrator().decide(
        AgentRunRequest(message="solve 2*x + 4 = 10", mode=TeachingMode.DIRECT_SOLVE),
        TOOLS,
    )
    assert decision.intent == Intent.SOLVE_MATH
    assert decision.tools == ["math"]
    assert "python" not in decision.tools


def test_tutor_mode_does_not_auto_run_math_even_if_text_says_solve():
    decision = AgentOrchestrator().decide(
        AgentRunRequest(
            message="Please tutor me",
            confirmed_problem="The image asks the user to solve 2x + 4 = 10",
            input_type="image",
            mode=TeachingMode.TUTOR,
        ),
        TOOLS,
    )
    assert decision.route == "tutor"
    assert "math" not in decision.tools


def test_python_code_uses_sandbox_only():
    decision = AgentOrchestrator().decide(
        AgentRunRequest(
            message="```python\nprint(sum([1,2,3]))\n```",
            mode=TeachingMode.DIRECT_SOLVE,
            subject="python",
        ),
        TOOLS,
    )
    assert decision.intent == Intent.SOLVE_PYTHON
    assert decision.tools == ["python"]
    assert "math" not in decision.tools


def test_memory_query_calls_no_tools():
    decision = AgentOrchestrator().decide(
        AgentRunRequest(message="What mistakes do I repeatedly make?"),
        TOOLS,
    )
    assert decision.intent == Intent.MEMORY
    assert decision.tools == []
    assert decision.consult_memory is True


def test_socratic_math_question_skips_solver_until_asked():
    decision = AgentOrchestrator().decide(
        AgentRunRequest(
            message="I don't know how to solve 2x + 4 = 10",
            mode=TeachingMode.SOCRATIC,
        ),
        TOOLS,
    )
    assert decision.route == "tutor"
    assert "math" not in decision.tools


def test_planner_stays_bounded_with_orchestrator():
    plan = Planner(max_steps=2).plan(
        AgentRunRequest(message="solve x + 2 = 3", material_id=1, mode=TeachingMode.DIRECT_SOLVE),
        TOOLS,
    )
    assert len(plan.steps) == 2
    assert plan.metadata["bounded"] is True
    assert plan.metadata["intent"] == Intent.SOLVE_MATH.value
