"""Intent detection and selective tool routing.

The orchestrator decides which subsystems are necessary. It never fans out
every request to every agent or tool.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, Field

from app.agent.schemas import AgentRunRequest, TeachingMode


class Intent(StrEnum):
    MEMORY = "memory"
    STUDENT_STATUS = "student_status"
    SOLVE_MATH = "solve_math"
    SOLVE_PYTHON = "solve_python"
    VISION_TUTOR = "vision_tutor"
    RAG = "rag"
    TUTOR = "tutor"


SOLVE_MODES = {
    TeachingMode.DIRECT_SOLVE,
    TeachingMode.FULL_SOLUTION,
    TeachingMode.STEP_BY_STEP,
}

GUIDANCE_MODES = {
    TeachingMode.HINT,
    TeachingMode.SOCRATIC,
    TeachingMode.CONCEPT,
    TeachingMode.ERROR_DIAGNOSIS,
    TeachingMode.TUTOR,
}


class RouteDecision(BaseModel):
    intent: Intent
    route: str
    tools: list[str] = Field(default_factory=list)
    reason: str
    consult_memory: bool = False
    consult_student_model: bool = False


class AgentOrchestrator:
    def decide(self, request: AgentRunRequest, available_tools: list[str]) -> RouteDecision:
        text = (request.confirmed_problem or request.message).strip()
        available = set(available_tools)

        if _is_memory_query(text):
            return RouteDecision(
                intent=Intent.MEMORY,
                route="memory",
                reason="Student asked about repeated mistakes or learning history.",
                consult_memory=True,
            )
        if _is_status_query(text):
            return RouteDecision(
                intent=Intent.STUDENT_STATUS,
                route="student_model",
                reason="Student asked about mastery, weak topics, or progress.",
                consult_student_model=True,
            )

        python_needed = _looks_like_python(text, request.subject) and "python" in available
        math_needed = _looks_like_math(text, request.subject) and "math" in available
        wants_solution = _wants_solution(text, request.mode)
        use_rag = request.material_id is not None and "knowledge_search" in available

        tools: list[str] = []
        if use_rag:
            tools.append("knowledge_search")

        if python_needed and wants_solution:
            tools.append("python")
            intent = Intent.SOLVE_PYTHON
            route = "solver"
            reason = "Programming request requires the restricted Python sandbox."
        elif math_needed and wants_solution:
            tools.append("math")
            intent = Intent.SOLVE_MATH
            route = "solver"
            reason = "Mathematical request requires SymPy verification instead of LLM arithmetic."
        elif request.input_type == "image":
            intent = Intent.VISION_TUTOR
            route = "tutor"
            reason = "Use confirmed Vision extraction; Vision does not produce the final answer."
            if math_needed and request.mode in SOLVE_MODES:
                tools.append("math")
                route = "solver"
                reason = "Confirmed image problem is solved with Math Tool after Vision extraction."
        elif use_rag:
            intent = Intent.RAG
            route = "tutor"
            reason = "Ground the tutor in the selected uploaded material."
        else:
            intent = Intent.TUTOR
            route = "tutor"
            reason = "Guide the student without unnecessary tool calls."

        if request.mode in GUIDANCE_MODES:
            # Keep Hint/Tutor/Socratic/Concept/Diagnose from auto-running Math/Python.
            # Vision captions often contain "solve", which would otherwise trigger tools
            # with prose that is not a formal expression.
            had_solver = any(name in {"math", "python"} for name in tools)
            tools = [name for name in tools if name == "knowledge_search"]
            if had_solver or intent in {Intent.SOLVE_MATH, Intent.SOLVE_PYTHON}:
                intent = Intent.VISION_TUTOR if request.input_type == "image" else Intent.TUTOR
                route = "tutor"
                reason = (
                    "Guidance mode: teach from confirmed problem text and student model; "
                    "defer Math/Python verification until Solve mode."
                )

        return RouteDecision(
            intent=intent,
            route=route,
            tools=[name for name in tools if name in available],
            reason=reason,
            consult_memory=request.mode == TeachingMode.ERROR_DIAGNOSIS,
            consult_student_model=True,
        )


def _is_memory_query(text: str) -> bool:
    return bool(
        re.search(
            r"repeated mistake|what mistakes|一再|重複.*錯|常犯|錯題|misconception",
            text,
            flags=re.IGNORECASE,
        )
    )


def _is_status_query(text: str) -> bool:
    return bool(
        re.search(
            r"\bmastery\b|weak topic|my progress|學習進度|弱點|掌握度|how am i doing",
            text,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_python(text: str, subject: str | None) -> bool:
    if subject and subject.lower() in {"python", "programming", "程式"}:
        return True
    return bool(re.search(r"```(?:python|py)\b|\bpython\b|print\(|def\s+\w+\(", text, re.I))


def _looks_like_math(text: str, subject: str | None) -> bool:
    if subject and subject.lower() in {"mathematics", "math", "數學", "高二數學", "physics", "物理"}:
        if re.search(r"[=+\-*/^]|方程|矩陣|微分|積分|vector|force|newton", text, re.I):
            return True
    return bool(
        re.search(
            r"\b(det|matrix|integral|derivative|factor|expand|solve)\b|"
            r"[=+\-*/^]|矩陣|方程|微分|積分|因式分解",
            text,
            flags=re.IGNORECASE,
        )
    )


def _wants_solution(text: str, mode: TeachingMode) -> bool:
    if re.search(r"don't know|不知道|不會解|how to start|怎麼開始", text, flags=re.IGNORECASE):
        return mode in SOLVE_MODES
    if mode in SOLVE_MODES:
        return True
    return bool(
        re.search(
            r"\b(solve|compute|calculate|evaluate|simplify|factor|integrate|differentiate)\b|"
            r"求解|計算|算出|驗算|請解",
            text,
            flags=re.IGNORECASE,
        )
    )
