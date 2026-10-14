"""Verification coordinator; specialized checks are added by tool adapters."""

from __future__ import annotations

from app.agent.schemas import VerificationStatus
from app.tools.base import ToolResult


class Verifier:
    def verify(self, tool_results: dict[str, ToolResult]) -> VerificationStatus:
        if not tool_results:
            return VerificationStatus.NOT_VERIFIABLE
        if any(not result.ok for result in tool_results.values()):
            return VerificationStatus.FAILED
        verification_tools = {
            name: result
            for name, result in tool_results.items()
            if name in {"math", "calculator", "python"}
        }
        if verification_tools and all(
            result.output.get("verified") is True for result in verification_tools.values()
        ):
            return VerificationStatus.VERIFIED
        if verification_tools:
            return VerificationStatus.PARTIALLY_VERIFIED
        # Tools ran but none are math/calculator/python verifiers (e.g. knowledge only).
        return VerificationStatus.NOT_VERIFIABLE

    def check_consistency(self, proposed_answer: str, tool_result: ToolResult) -> bool:
        if not tool_result.ok:
            return False
        expected = str(tool_result.output.get("result", "")).strip()
        if not expected:
            return False
        normalized_answer = _normalize(proposed_answer)
        normalized_expected = _normalize(expected)
        return normalized_expected in normalized_answer or normalized_answer in normalized_expected


def _normalize(value: str) -> str:
    return "".join(value.lower().split()).replace("[", "").replace("]", "")
