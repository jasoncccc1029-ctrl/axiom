"""OllamaVisionProvider unit tests with mocked HTTP."""

import sys
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.vision.exceptions import VisionModelMissingError, VisionUnavailableError  # noqa: E402
from app.vision.ollama import OllamaVisionProvider  # noqa: E402


@pytest.mark.asyncio
async def test_ollama_vision_provider_success():
    payload = {
        "message": {
            "role": "assistant",
            "content": (
                '{"content_type":"math_problem","subject":"mathematics","topic":"matrix",'
                '"problem_text":"Find det(A)","detected_formula":["det(A)"],'
                '"diagram_description":"2x2 matrix","confidence":0.81}'
            ),
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaVisionProvider(
            base_url="http://127.0.0.1:11434",
            model="moondream:latest",
            client=client,
        )
        result = await provider.analyze(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, mime_type="image/png")
        assert result.content_type == "math_problem"
        assert result.topic == "matrix"
        assert result.confidence == 0.81
        assert result.provider == "ollama"


@pytest.mark.asyncio
async def test_ollama_vision_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaVisionProvider(
            base_url="http://127.0.0.1:11434",
            model="moondream:latest",
            client=client,
        )
        with pytest.raises(VisionUnavailableError):
            await provider.analyze(b"\xff\xd8\xff" + b"\x00" * 8, mime_type="image/jpeg")


@pytest.mark.asyncio
async def test_ollama_vision_model_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="model not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaVisionProvider(
            base_url="http://127.0.0.1:11434",
            model="moondream:latest",
            client=client,
        )
        with pytest.raises(VisionModelMissingError):
            await provider.analyze(b"\xff\xd8\xff" + b"\x00" * 8, mime_type="image/jpeg")
