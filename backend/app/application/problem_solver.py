"""Application service for LLM proposal -> MathTool -> Verifier."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.agent.schemas import VerificationStatus
from app.agent.verifier import Verifier
from app.providers.base import ModelProvider
from app.tools.math import MathTool
from app.tools.python import PythonTool


class ProblemSolveRequest(BaseModel):
    problem: str = Field(..., min_length=1, max_length=10_000)
    subject: str | None = None
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


class ProblemSolverService:
    def __init__(
        self,
        provider: ModelProvider,
        math_tool: MathTool | None = None,
        verifier: Verifier | None = None,
    ) -> None:
        self.provider = provider
        self.math_tool = math_tool or MathTool()
        self.python_tool = PythonTool()
        self.verifier = verifier or Verifier()

    async def solve(self, request: ProblemSolveRequest) -> ProblemSolveResponse:
        proposal = await self.provider.solve(request.problem, subject=request.subject)
        proposed_answer = str(proposal.get("answer") or "")
        use_python = (request.subject or "").lower() in {"python", "programming", "程式"} or "```" in request.problem
        if use_python:
            result = await self.python_tool.execute({"code": request.problem})
            tool_name = "python"
        else:
            result = await self.math_tool.execute(
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
        status = self.verifier.verify({tool_name: result})
        if not result.ok:
            final_answer = proposed_answer
            status = self.verifier.verify({tool_name: result})
        else:
            final_answer = str(result.output.get("result", result.output.get("stdout", "")))
            if proposed_answer and tool_name == "math" and not self.verifier.check_consistency(
                proposed_answer, result
            ):
                status = VerificationStatus.PARTIALLY_VERIFIED
        return ProblemSolveResponse(
            problem=request.problem,
            proposed_solution=proposed_answer,
            tool=tool_name,
            tool_result=result.output if result.ok else {"error": result.error},
            final_answer=final_answer,
            verification_status=status,
            provider=self.provider.name,
            model=self.provider.model,
        )
