"""VisionService unit tests with mocked provider."""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.vision import VisionService  # noqa: E402
from app.vision.mock import MockVisionProvider  # noqa: E402
from app.vision.exceptions import InvalidImageError  # noqa: E402


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.mark.asyncio
async def test_vision_service_analyze_with_mock(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.vision.settings.vision_upload_dir", tmp_path)
    service = VisionService(provider=MockVisionProvider())
    result = await service.analyze_upload(
        content=_png_bytes(),
        declared_mime="image/png",
        original_filename="matrix_problem.png",
    )
    assert result.mime_type == "image/png"
    assert result.stored_filename.endswith(".png")
    assert (tmp_path / result.stored_filename).exists()
    assert result.analysis.provider == "mock"
    assert result.analysis.content_type in {
        "math_problem",
        "lecture",
        "note",
        "diagram",
        "text",
        "unknown",
    }


@pytest.mark.asyncio
async def test_vision_service_rejects_bad_image(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.vision.settings.vision_upload_dir", tmp_path)
    service = VisionService(provider=MockVisionProvider())
    with pytest.raises(InvalidImageError):
        await service.analyze_upload(content=b"hello", declared_mime="text/plain")
