"""Vision API tests (mocked provider / no real VLM required)."""

import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.dependencies import provide_vision_service  # noqa: E402
from app.services.seed import init_db  # noqa: E402
from app.services.vision import VisionAnalyzeResult  # noqa: E402
from app.vision.schemas import VisionAnalysis  # noqa: E402


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def _png_file():
    return ("matrix.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 48), "image/png")


def test_vision_analyze_api(client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.vision_provider", "mock")
    monkeypatch.setattr("app.routers.settings.vision_provider", "mock")

    instance = AsyncMock()
    instance.analyze_upload.return_value = VisionAnalyzeResult(
                analysis=VisionAnalysis(
                    content_type="math_problem",
                    subject="mathematics",
                    topic="matrix",
                    problem_text="Find det(A)",
                    detected_formula=["det(A)"],
                    diagram_description="matrix",
                    confidence=0.5,
                    provider="mock",
                    model="mock-vision",
                ),
                stored_path=str(tmp_path / "x.png"),
                stored_filename="x.png",
                mime_type="image/png",
                size=64,
            )
    app.dependency_overrides[provide_vision_service] = lambda: instance
    try:
        res = client.post("/api/vision/analyze", files={"file": _png_file()})
    finally:
        app.dependency_overrides.pop(provide_vision_service, None)

    assert res.status_code == 200
    body = res.json()
    assert body["analysis"]["provider"] == "mock"
    assert body["mime_type"] == "image/png"
    assert "timing" in body
    assert isinstance(body["analysis"]["detected_formula"], list)
    assert "content_type" in body["analysis"]


def test_vision_analyze_rejects_invalid(client):
    res = client.post(
        "/api/vision/analyze",
        files={"file": ("bad.txt", io.BytesIO(b"not-image"), "text/plain")},
    )
    assert res.status_code == 400


def test_vision_analyze_provider_error(client):
    from app.vision.exceptions import VisionModelMissingError

    fake = VisionAnalyzeResult(
        analysis=VisionAnalysis(provider="ollama"),
        stored_path="x",
        stored_filename="x.png",
        mime_type="image/png",
        size=1,
    )
    # Force service path to raise VisionError after validation by patching analyze_upload
    instance = AsyncMock()
    instance.analyze_upload.side_effect = VisionModelMissingError("moondream:latest")
    app.dependency_overrides[provide_vision_service] = lambda: instance
    try:
        res = client.post("/api/vision/analyze", files={"file": _png_file()})
    finally:
        app.dependency_overrides.pop(provide_vision_service, None)
    assert res.status_code == 503
    assert "moondream" in res.json()["detail"]
    assert fake.stored_filename == "x.png"  # silence unused lint mentally
