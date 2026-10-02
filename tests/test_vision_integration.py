"""Live Vision integration tests (moondream). Only when RUN_OLLAMA_TESTS=true."""

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.services.ollama_health import check_ollama_health  # noqa: E402
from app.services.vision import VisionService  # noqa: E402
from app.vision.ollama import OllamaVisionProvider  # noqa: E402

RUN = os.getenv("RUN_OLLAMA_TESTS", "").lower() in {"1", "true", "yes"}

pytestmark = pytest.mark.skipif(
    not RUN,
    reason="Set RUN_OLLAMA_TESTS=true to run live Ollama Vision integration tests",
)


def _tiny_math_png() -> bytes:
    """Use the checked-in sample math worksheet when available."""
    sample = Path(__file__).resolve().parents[1] / "docs" / "sample_math_problem.png"
    if sample.exists():
        return sample.read_bytes()
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 128


@pytest.mark.asyncio
async def test_live_vision_model_present():
    health = await check_ollama_health(model=settings.ollama_vision_model)
    assert health.reachable is True
    assert health.model_available is True
    assert "moondream" in health.model


@pytest.mark.asyncio
async def test_live_vision_analyze_not_mock(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.vision.settings.vision_upload_dir", tmp_path)
    monkeypatch.setattr("app.services.vision.settings.vision_provider", "ollama")

    provider = OllamaVisionProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_vision_model,
    )
    service = VisionService(provider=provider)
    result = await service.analyze_upload(
        content=_tiny_math_png(),
        declared_mime="image/png",
        original_filename="math.png",
    )
    assert result.analysis.provider == "ollama"
    assert result.analysis.model == "moondream:latest"
    assert result.analysis.provider != "mock"
    for field in (
        "content_type",
        "subject",
        "topic",
        "problem_text",
        "detected_formula",
        "diagram_description",
        "confidence",
    ):
        assert hasattr(result.analysis, field)
