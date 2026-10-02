"""Vision provider factory."""

from __future__ import annotations

import httpx

from app.vision.base import VisionProvider
from app.vision.cloud import CloudVisionProvider
from app.vision.mock import MockVisionProvider
from app.vision.ollama import OllamaVisionProvider


def get_vision_provider(client: httpx.AsyncClient | None = None) -> VisionProvider:
    from app.config import settings

    if settings.vision_provider == "cloud":
        return CloudVisionProvider()
    if settings.vision_provider == "mock":
        return MockVisionProvider()

    return OllamaVisionProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_vision_model,
        timeout=settings.vision_timeout_seconds,
        client=client,
    )
