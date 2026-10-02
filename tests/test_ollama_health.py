"""Ollama health service unit tests (mocked HTTP)."""

import sys
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ollama_health import check_ollama_health, ensure_ollama_ready  # noqa: E402
from app.providers.exceptions import OllamaModelMissingError, OllamaUnavailableError  # noqa: E402


@pytest.mark.asyncio
async def test_ollama_health_ok():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(
            200,
            json={"models": [{"name": "llama3.2:latest"}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        health = await check_ollama_health(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        assert health.ok is True
        assert health.reachable is True
        assert health.model_available is True


@pytest.mark.asyncio
async def test_ollama_health_not_running():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        health = await check_ollama_health(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        assert health.ok is False
        assert health.reachable is False
        assert "ollama serve" in health.message


@pytest.mark.asyncio
async def test_ollama_health_model_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "other:latest"}]})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        health = await check_ollama_health(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        assert health.ok is False
        assert health.reachable is True
        assert health.model_available is False
        assert "找不到 llama3.2:latest" in health.message

        with pytest.raises(OllamaModelMissingError):
            await ensure_ollama_ready(
                base_url="http://127.0.0.1:11434",
                model="llama3.2:latest",
                client=client,
            )


@pytest.mark.asyncio
async def test_ensure_ollama_ready_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        with pytest.raises(OllamaUnavailableError):
            await ensure_ollama_ready(
                base_url="http://127.0.0.1:11434",
                model="llama3.2:latest",
                client=client,
            )
