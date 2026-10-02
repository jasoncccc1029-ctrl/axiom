"""VisionProvider abstraction — separate from text ModelProvider."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.vision.schemas import VisionAnalysis


class VisionProvider(ABC):
    name: str

    @abstractmethod
    async def analyze(
        self,
        image_bytes: bytes,
        *,
        mime_type: str,
        filename: str | None = None,
    ) -> VisionAnalysis:
        raise NotImplementedError
