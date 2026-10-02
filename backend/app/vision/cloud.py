"""Cloud vision provider placeholder."""

from __future__ import annotations

from app.vision.base import VisionProvider
from app.vision.schemas import VisionAnalysis


class CloudVisionProvider(VisionProvider):
    name = "cloud"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key
        self.model = model

    async def analyze(
        self,
        image_bytes: bytes,
        *,
        mime_type: str,
        filename: str | None = None,
    ) -> VisionAnalysis:
        raise NotImplementedError(
            "CloudVisionProvider is not implemented in v0.3. Use OllamaVisionProvider or mock."
        )
