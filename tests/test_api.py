"""Backend API tests for Axiom (v0.1 + v0.2 chat)."""

import io
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402
from app.dependencies import provide_model_provider, provide_vision_provider  # noqa: E402
from app.vision.mock import MockVisionProvider  # noqa: E402
from app.providers.exceptions import OllamaUnavailableError  # noqa: E402
from app.services.seed import init_db  # noqa: E402


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["app"] == "Axiom"
    assert data["version"] == "1.3.2"


def test_list_materials(client):
    res = client.get("/api/materials")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    # Seed may have been edited locally; ensure endpoint works and create if empty.
    if len(data) == 0:
        created = client.post(
            "/api/materials",
            json={"title": "Seed Probe", "subject": "數學", "description": "pytest"},
        )
        assert created.status_code == 200
        client.delete(f"/api/materials/{created.json()['id']}")


def test_create_and_delete_material(client):
    create = client.post(
        "/api/materials",
        json={"title": "Test Note", "subject": "英文", "description": "pytest"},
    )
    assert create.status_code == 200
    material_id = create.json()["id"]
    assert create.json()["ingestion_status"] == "ready"

    delete = client.delete(f"/api/materials/{material_id}")
    assert delete.status_code == 200
    assert delete.json()["status"] == "deleted"


def test_upload_material(client):
    files = {
        "file": ("sample.png", io.BytesIO(b"\x89PNG\r\n\x1a\nfake"), "image/png"),
    }
    data = {"title": "Uploaded Image", "subject": "物理", "description": "phone photo"}
    app.dependency_overrides[provide_vision_provider] = lambda: MockVisionProvider()
    try:
        res = client.post("/api/materials/upload", files=files, data=data)
    finally:
        app.dependency_overrides.pop(provide_vision_provider, None)
    assert res.status_code == 200
    body = res.json()
    assert body["file_type"] == "image"
    assert body["title"] == "Uploaded Image"
    assert body["ingestion_status"] == "ready"
    client.delete(f"/api/materials/{body['id']}")


def test_chat_api_with_mocked_provider(client):
    mock_provider = MagicMock()
    mock_provider.name = "ollama"
    mock_provider.model = "llama3.2:latest"
    mock_provider.chat = AsyncMock(return_value="矩陣是由數字排列成的矩形陣列。")

    app.dependency_overrides[provide_model_provider] = lambda: mock_provider
    try:
        res = client.post("/api/chat", json={"message": "什麼是矩陣？", "material_id": 1})
    finally:
        app.dependency_overrides.pop(provide_model_provider, None)

    assert res.status_code == 200
    body = res.json()
    assert body["reply"].startswith("矩陣")
    assert body["provider"] == "ollama"
    assert body["model"] == "llama3.2:latest"
    mock_provider.chat.assert_awaited()


def test_chat_api_ollama_unavailable(client):
    mock_provider = MagicMock()
    mock_provider.name = "ollama"
    mock_provider.model = "llama3.2:latest"
    mock_provider.chat = AsyncMock(side_effect=OllamaUnavailableError())

    app.dependency_overrides[provide_model_provider] = lambda: mock_provider
    try:
        res = client.post("/api/chat", json={"message": "hello"})
    finally:
        app.dependency_overrides.pop(provide_model_provider, None)

    assert res.status_code == 503
    assert "ollama serve" in res.json()["detail"]


def test_solve_with_mocked_provider(client):
    mock_provider = MagicMock()
    mock_provider.name = "ollama"
    mock_provider.model = "llama3.2:latest"
    mock_provider.solve = AsyncMock(
        return_value={
            "steps": [
                {"step": 1, "title": "理解題意", "content": "a"},
                {"step": 2, "title": "推導過程", "content": "b"},
                {"step": 3, "title": "整理答案", "content": "c"},
            ],
            "answer": "x=3",
            "verification": {"status": "correct", "message": "ok"},
            "model": "llama3.2:latest",
        }
    )

    app.dependency_overrides[provide_model_provider] = lambda: mock_provider
    try:
        res = client.post(
            "/api/solve",
            json={"problem": "求 2x + 4 = 10 的 x", "subject": "高二數學"},
        )
    finally:
        app.dependency_overrides.pop(provide_model_provider, None)

    assert res.status_code == 200
    body = res.json()
    assert len(body["steps"]) == 3
    assert body["model"] == "llama3.2:latest"
    assert "verification" in body


def test_progress(client):
    res = client.get("/api/progress")
    assert res.status_code == 200
    body = res.json()
    assert "accuracy_rate" in body
    assert "weak_subjects" in body
    assert "recommended" in body


def test_ollama_health_endpoint_mocked(client):
    fake = MagicMock(
        ok=True,
        reachable=True,
        model="llama3.2:latest",
        model_available=True,
        models=["llama3.2:latest"],
        message="Ollama ready · llama3.2:latest",
    )

    with patch("app.routers.check_ollama_health", AsyncMock(return_value=fake)):
        res = client.get("/api/ollama/health")

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["model"] == "llama3.2:latest"
