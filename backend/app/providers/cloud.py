"""Legacy cloud placeholder — use dedicated OpenAI / Anthropic adapters (Phase 4+).

Kept so ``AI_PROVIDER=cloud`` fails with a clear ProviderNotConfiguredError
instead of a bare NotImplementedError.
"""

from __future__ import annotations

from typing import Any

from app.providers.base import ModelProvider
from app.providers.exceptions import ProviderNotConfiguredError
from app.providers.types import GenerateRequest, GenerateResponse, ProviderId


class CloudProvider(ModelProvider):
    """Deprecated umbrella stub. Prefer OpenAIProvider / AnthropicProvider."""

    provider_id = ProviderId.OPENAI

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key
        self.model = model or "unconfigured"
        self._error = ProviderNotConfiguredError(
            "cloud",
            message=(
                "通用 CloudProvider 已停用。請使用 AI_PROVIDER=ollama、"
                "AI_PROVIDER=openai（OPENAI_API_KEY），"
                "或 AI_PROVIDER=gemini（GEMINI_API_KEY）。"
            ),
        )

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        raise self._error

    async def chat(self, message: str, context: str | None = None) -> str:
        raise self._error

    async def solve(
        self,
        problem: str,
        subject: str | None = None,
        context: str | None = None,
    ) -> dict[str, Any]:
        raise self._error
