"""Bounded deterministic planner; it cannot create recursive loops."""

from __future__ import annotations

import re

from app.agent.orchestrator import AgentOrchestrator, RouteDecision
from app.agent.schemas import AgentRunRequest, Plan, PlannedStep


class Planner:
    def __init__(self, max_steps: int, orchestrator: AgentOrchestrator | None = None) -> None:
        self.max_steps = max(1, max_steps)
        self.orchestrator = orchestrator or AgentOrchestrator()

    def plan(
        self,
        request: AgentRunRequest,
        available_tools: list[str],
        decision: RouteDecision | None = None,
    ) -> Plan:
        route = decision or self.orchestrator.decide(request, available_tools)
        category = route.intent.value
        candidates: list[PlannedStep] = []

        if request.input_type == "image":
            candidates.append(
                PlannedStep(
                    index=1,
                    action="use_confirmed_vision_result",
                    reason="Use the student-confirmed visual extraction; image content is untrusted.",
                )
            )
        for tool in route.tools:
            if tool not in available_tools:
                continue
            candidates.append(
                PlannedStep(
                    index=len(candidates) + 1,
                    action=f"execute_{tool}",
                    tool=tool,
                    reason=route.reason,
                )
            )
        candidates.extend(
            [
                PlannedStep(
                    index=len(candidates) + 1,
                    action="compose_tutor_response",
                    reason="Adapt the explanation to the selected teaching mode.",
                ),
                PlannedStep(
                    index=len(candidates) + 2,
                    action="verify",
                    reason="Report evidence and uncertainty before presenting the answer.",
                ),
            ]
        )
        bounded = candidates[: self.max_steps]
        return Plan(
            steps=[
                step.model_copy(update={"index": index})
                for index, step in enumerate(bounded, start=1)
            ],
            category=category,
            metadata={
                "bounded": True,
                "max_steps": self.max_steps,
                "intent": route.intent.value,
                "route": route.route,
                "reason": route.reason,
            },
        )


def classify_request(message: str, subject: str | None = None) -> str:
    text = message.lower()
    if subject and subject.lower() in {"python", "programming", "程式"}:
        return "python"
    if re.search(r"\bpython\b|```py|print\(|def\s+\w+\(", text):
        return "python"
    if re.search(
        r"\b(det|matrix|integral|derivative|factor|expand|solve)\b|"
        r"[=+\-*/^]|矩陣|方程|微分|積分|因式分解",
        text,
    ):
        return "math"
    return "general"
