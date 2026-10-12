"""Application service for LLM proposal -> MathTool -> Verifier.

Solver uses the same lean Context Policy path as Tutor: understand the
learner (when subject is present), then call the Brain.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.context import ContextBuilder
from app.agent.schemas import VerificationStatus
from app.agent.verifier import Verifier
from app.application.student_learning_state import StudentLearningStateService
from app.application.student_model import StudentModelService
from app.application.subject_aliases import (
    canonicalize_subject,
    normalize_learning_label,
)
from app.providers.base import ModelProvider
from app.tools.math import MathTool
from app.tools.python import PythonTool


class ProblemSolveRequest(BaseModel):
    problem: str = Field(..., min_length=1, max_length=10_000)
    subject: str | None = None
    topic: str | None = None
    operation: str | None = None
    expression: str | None = None
    variable: str | None = None
    matrix: list[list[float]] | None = None
    values: list[float] | None = None


class ProblemSolveResponse(BaseModel):
    problem: str
    proposed_solution: str
    tool: str
    tool_result: dict[str, Any]
    final_answer: str
    verification_status: VerificationStatus
    provider: str
    model: str
    subject: str | None = None
    topic: str | None = None
    personalized: bool = False


class ProblemSolverService:
    def __init__(
        self,
        provider: ModelProvider,
        *,
        db: Session | None = None,
        math_tool: MathTool | None = None,
        verifier: Verifier | None = None,
        context_builder: ContextBuilder | None = None,
        learning_state: StudentLearningStateService | None = None,
        student_model: StudentModelService | None = None,
    ) -> None:
        self.provider = provider
        self.db = db
        self.math_tool = math_tool or MathTool()
        self.python_tool = PythonTool()
        self.verifier = verifier or Verifier()
        self.context_builder = context_builder or ContextBuilder()
        if db is not None:
            self.learning_state = learning_state or StudentLearningStateService(db)
            self.student_model = student_model or StudentModelService(db)
        else:
            self.learning_state = learning_state
            self.student_model = student_model

    def _build_learner_context(
        self, *, subject: str | None, topic: str | None
    ) -> tuple[str | None, bool]:
        """Lean StudentContext for solve — never dump the full database."""

        if self.learning_state is None or not subject:
            return None, False

        learning_snapshot = self.learning_state.get(
            subject=subject, topic=topic
        ).model_dump()
        student_snapshot: dict[str, Any] | None = None
        if self.student_model is not None:
            student = self.student_model.student()
            topic_state = None
            if topic:
                for row in student.mastery:
                    if row.subject == subject and row.topic == topic:
                        topic_state = {
                            "mastery": row.mastery,
                            "confidence": row.confidence,
                            "consecutive_errors": row.consecutive_errors,
                            "attempts": row.attempts,
                        }
                        break
            student_snapshot = {
                "weak_concepts": student.weak_concepts[:6],
                "strong_concepts": student.strong_concepts[:4],
                "topic_state": topic_state,
                "mastery": [
                    {
                        "subject": item.subject,
                        "topic": item.topic,
                        "mastery": item.mastery,
                        "consecutive_errors": item.consecutive_errors,
                    }
                    for item in student.mastery[:8]
                    if item.subject == subject
                ],
            }
        context = self.context_builder.build(
            tool_outputs={},
            mode="direct_solve",
            student_model=student_snapshot,
            learning_state=learning_snapshot,
            intent=(
                "solve: use TRUSTED learner state to tailor explanation depth "
                "and warn about known error patterns; still solve the problem."
            ),
        )
        return context, True

    async def solve(self, request: ProblemSolveRequest) -> ProblemSolveResponse:
        subject = canonicalize_subject(normalize_learning_label(request.subject))
        topic = normalize_learning_label(request.topic)
        context, personalized = self._build_learner_context(
            subject=subject, topic=topic
        )

        proposal = await self.provider.solve(
            request.problem, subject=subject, context=context
        )
        proposed_answer = str(proposal.get("answer") or "")

        use_python = (subject or "").lower() in {
            "python",
            "programming",
            "程式",
        } or "```" in request.problem
        if use_python:
            tool_result = await self.python_tool.execute({"code": request.problem})
            tool_name = "python"
        else:
            tool_result = await self.math_tool.execute(
                {
                    "problem": request.problem,
                    "expression": request.expression or request.problem,
                    "operation": request.operation,
                    "variable": request.variable,
                    "matrix": request.matrix,
                    "values": request.values,
                }
            )
            tool_name = "math"
        status = self.verifier.verify({tool_name: tool_result})
        if not tool_result.ok:
            final_answer = proposed_answer
            status = self.verifier.verify({tool_name: tool_result})
        else:
            final_answer = str(
                tool_result.output.get("result", tool_result.output.get("stdout", ""))
            )
            if (
                proposed_answer
                and tool_name == "math"
                and not self.verifier.check_consistency(proposed_answer, tool_result)
            ):
                status = VerificationStatus.PARTIALLY_VERIFIED
        return ProblemSolveResponse(
            problem=request.problem,
            proposed_solution=proposed_answer,
            tool=tool_name,
            tool_result=(
                tool_result.output if tool_result.ok else {"error": tool_result.error}
            ),
            final_answer=final_answer,
            verification_status=status,
            provider=self.provider.name,
            model=self.provider.model,
            subject=subject,
            topic=topic,
            personalized=personalized,
        )
