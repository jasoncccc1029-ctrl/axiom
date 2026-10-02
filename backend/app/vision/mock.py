"""Mock vision provider for tests and pipeline smoke without a local VLM."""

from __future__ import annotations

from app.vision.base import VisionProvider
from app.vision.schemas import VisionAnalysis


class MockVisionProvider(VisionProvider):
    name = "mock"

    async def analyze(
        self,
        image_bytes: bytes,
        *,
        mime_type: str,
        filename: str | None = None,
    ) -> VisionAnalysis:
        hint = (filename or "").lower()
        if any(k in hint for k in ("math", "matrix", "題", "算")):
            return VisionAnalysis(
                content_type="math_problem",
                subject="mathematics",
                topic="matrix",
                problem_text="（mock）請根據圖片中的矩陣題目作答。",
                detected_formula=["A = [[a,b],[c,d]]"],
                diagram_description="（mock）偵測到矩陣相關題目圖片。",
                confidence=0.42,
                raw_text="mock vision analysis",
                provider=self.name,
                model="mock-vision",
            )

        return VisionAnalysis(
            content_type="unknown",
            subject="unknown",
            topic="unknown",
            problem_text="",
            detected_formula=[],
            diagram_description=f"（mock）已接收圖片（{mime_type}，{len(image_bytes)} bytes）。",
            confidence=0.2,
            raw_text="mock vision analysis",
            provider=self.name,
            model="mock-vision",
        )
