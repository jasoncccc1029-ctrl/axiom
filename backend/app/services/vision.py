"""Vision analysis service — orchestration only, no router logic."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.services.image_validation import validate_image_bytes
from app.vision.base import VisionProvider
from app.vision.factory import get_vision_provider
from app.vision.schemas import VisionAnalysis


@dataclass
class VisionAnalyzeResult:
    analysis: VisionAnalysis
    stored_path: str
    stored_filename: str
    mime_type: str
    size: int


class VisionService:
    def __init__(self, provider: VisionProvider | None = None) -> None:
        self.provider = provider or get_vision_provider()
        self.upload_dir = Path(settings.vision_upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def analyze_upload(
        self,
        *,
        content: bytes,
        declared_mime: str | None = None,
        original_filename: str | None = None,
    ) -> VisionAnalyzeResult:
        validated = validate_image_bytes(content, declared_mime=declared_mime)

        stored_name = f"{uuid.uuid4().hex}{validated.extension}"
        dest = self.upload_dir / stored_name
        # Guard against any unexpected path traversal in constructed path
        if dest.resolve().parent != self.upload_dir.resolve():
            raise RuntimeError("Invalid storage path")

        dest.write_bytes(validated.content)

        analysis = await self.provider.analyze(
            validated.content,
            mime_type=validated.mime_type,
            filename=original_filename,
        )

        return VisionAnalyzeResult(
            analysis=analysis,
            stored_path=str(dest),
            stored_filename=stored_name,
            mime_type=validated.mime_type,
            size=validated.size,
        )
