"""Provider factory — process-default Brain selection.

Ollama is configured via ``app.config.settings`` inside the adapter
(``OllamaProvider.from_settings``). Agent / Solver / Learning Loop must not
read ``OLLAMA_*`` environment variables themselves.
"""

from __future__ import annotations

import httpx

from app.providers.base import ModelProvider
from app.providers.cloud import CloudProvider
from app.providers.exceptions import ProviderNotConfiguredError
from app.providers.ollama import OllamaProvider
from app.providers.types import ProviderId


def get_provider(client: httpx.AsyncClient | None = None) -> ModelProvider:
    from app.config import settings

    provider = (settings.ai_provider or ProviderId.OLLAMA.value).strip().lower()

    if provider in {ProviderId.OPENAI.value, ProviderId.ANTHROPIC.value}:
        raise ProviderNotConfiguredError(
            provider,
            message=(
                f"{provider} adapter 尚未啟用（Phase 4/5）。"
                "目前請使用 AI_PROVIDER=ollama。"
            ),
        )

    if provider == "cloud":
        return CloudProvider()

    return OllamaProvider.from_settings(client=client)
