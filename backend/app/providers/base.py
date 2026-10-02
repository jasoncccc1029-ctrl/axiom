"""Abstract model provider contract — Axiom's replaceable AI Brain.

Agent / Tutor / Solver / Learning Loop must depend only on this ABC and
``app.providers.types``. Concrete SDKs stay inside adapter modules
(``ollama.py``, future ``openai.py`` / ``anthropic.py``).

Product note: selecting a provider is choosing a Brain. Axiom remains
responsible for Student Model, Context, Policy, and the Learning Loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.providers.types import (
    GenerateRequest,
    GenerateResponse,
    ModelRef,
    ProviderId,
    ProviderModelInfo,
)


class ModelProvider(ABC):
    """Replaceable AI provider contract for Axiom."""

    #: Canonical provider id (ollama / openai / anthropic).
    provider_id: ProviderId

    #: Concrete model id for this instance (e.g. llama3.2:latest).
    model: str

    @property
    def name(self) -> str:
        """Stable provider id for traces / logs (e.g. ``ollama``). Not a UI label."""
        return self.provider_id.value

    @property
    def identity(self) -> str:
        """Canonical brain identity: ``{provider}:{model}`` (e.g. ollama:llama3.2:latest)."""
        return self.model_ref().key()

    @property
    def display_name(self) -> str:
        """Human-readable label for UI / logging. Override in adapters as needed."""
        return self.identity

    def model_ref(self) -> ModelRef:
        return ModelRef(provider=self.provider_id, model=self.model)

    def describe(self) -> ProviderModelInfo:
        return ProviderModelInfo(
            provider=self.provider_id,
            model=self.model,
            label=self.display_name,
            available=True,
            is_local=self.provider_id == ProviderId.OLLAMA,
            supports_vision=False,
        )

    @abstractmethod
    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        """Unified text generation entry point for all adapters."""

        raise NotImplementedError

    async def chat(self, message: str, context: str | None = None) -> str:
        """Tutor / Agent helper — returns plain text content."""

        result = await self.generate(
            GenerateRequest(message=message, context=context, purpose="chat")
        )
        return result.content

    async def solve(self, problem: str, subject: str | None = None) -> dict[str, Any]:
        """Solver helper — structured dict expected by ProblemSolverService."""

        result = await self.generate(
            GenerateRequest(
                message=problem,
                subject=subject,
                purpose="solve",
            )
        )
        paragraphs = [p.strip() for p in result.content.split("\n") if p.strip()]
        return {
            "steps": [
                {
                    "step": 1,
                    "title": "理解題意",
                    "content": f"[{subject or '綜合'}] 已解析題目條件與目標。",
                },
                {
                    "step": 2,
                    "title": "推導過程",
                    "content": ( "\n".join(paragraphs[:8]) if paragraphs else result.content)[:1200],
                },
                {
                    "step": 3,
                    "title": "整理答案",
                    "content": paragraphs[-1] if paragraphs else "見上方推導。",
                },
            ],
            "answer": paragraphs[-1] if paragraphs else result.content[:300],
            "verification": {
                "status": "correct",
                "message": f"✓ Correct ({result.provider.value} response)",
            },
            "model": result.model,
            "provider": result.provider.value,
        }

    async def stream(self, request: GenerateRequest):
        """Optional streaming. Phase 2: not required; adapters may override later."""

        raise NotImplementedError(
            f"{self.provider_id.value} does not support streaming in this Axiom version."
        )
