"""Provider factory — process-default Brain selection.

Adapters load secrets / URLs from ``app.config.settings``
(``OllamaProvider.from_settings``, ``OpenAIProvider.from_settings``,
``GeminiProvider.from_settings``).
Agent / Solver / Learning Loop must not read provider env vars themselves.
"""

from __future__ import annotations

import httpx

from app.providers.base import ModelProvider
from app.providers.cloud import CloudProvider
from app.providers.exceptions import ProviderNotConfiguredError
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.providers.openai import OpenAIProvider
from app.providers.types import ProviderId


def get_provider(client: httpx.AsyncClient | None = None) -> ModelProvider:
    from app.config import settings

    provider = (settings.ai_provider or ProviderId.OLLAMA.value).strip().lower()
    if provider in {"google", "google-gemini"}:
        provider = ProviderId.GEMINI.value

    if provider == ProviderId.OPENAI.value:
        return OpenAIProvider.from_settings(client=client)

    if provider == ProviderId.GEMINI.value:
        return GeminiProvider.from_settings(client=client)

    if provider == ProviderId.ANTHROPIC.value:
        raise ProviderNotConfiguredError(
            provider,
            message=(
                "anthropic adapter 尚未啟用（Phase 5）。"
                "目前請使用 AI_PROVIDER=ollama、openai 或 gemini。"
            ),
        )

    if provider == "cloud":
        return CloudProvider()

    return OllamaProvider.from_settings(client=client)
