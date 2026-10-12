"""Unit tests for OllamaProvider (Phase 3 reference adapter)."""

import json
import sys
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.providers.exceptions import (  # noqa: E402
    OllamaModelMissingError,
    OllamaRequestError,
    OllamaUnavailableError,
    ProviderNotConfiguredError,
    ProviderTimeoutError,
)
from app.providers.ollama import OllamaProvider  # noqa: E402
from app.providers.types import GenerateRequest, ProviderId  # noqa: E402


def test_ollama_identity_and_display_name():
    provider = OllamaProvider(base_url="http://127.0.0.1:11434", model="llama3.2:latest")
    assert provider.provider_id == ProviderId.OLLAMA
    assert provider.name == "ollama"
    assert provider.model == "llama3.2:latest"
    assert provider.identity == "ollama:llama3.2:latest"
    assert provider.model_ref().key() == "ollama:llama3.2:latest"
    assert provider.display_name == "Axiom Local · llama3.2:latest"
    info = provider.describe()
    assert info.label == provider.display_name
    assert info.is_local is True
    assert info.model == "llama3.2:latest"


def test_ollama_rejects_missing_config():
    with pytest.raises(ProviderNotConfiguredError):
        OllamaProvider(base_url="", model="llama3.2:latest")
    with pytest.raises(ProviderNotConfiguredError):
        OllamaProvider(base_url="http://127.0.0.1:11434", model="  ")


def test_ollama_from_settings(monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod.settings, "ollama_base_url", "http://127.0.0.1:11434")
    monkeypatch.setattr(config_mod.settings, "ollama_model", "llama3.2:latest")
    monkeypatch.setattr(config_mod.settings, "model_timeout_seconds", 90.0)
    provider = OllamaProvider.from_settings()
    assert provider.base_url == "http://127.0.0.1:11434"
    assert provider.model == "llama3.2:latest"
    assert provider.timeout == 90.0


@pytest.mark.asyncio
async def test_ollama_provider_chat_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content.decode())
        assert body["stream"] is False
        assert body["keep_alive"] == "30m"
        assert body["options"]["num_predict"] == 384
        assert body["options"]["num_ctx"] == 2048
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "矩陣是矩形數字陣列。"}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        reply = await provider.chat("什麼是矩陣？")
        assert "矩陣" in reply


@pytest.mark.asyncio
async def test_chat_and_solve_delegate_to_generate():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/api/chat":
            return httpx.Response(
                200,
                json={"message": {"role": "assistant", "content": "chat-ok"}},
            )
        assert request.url.path == "/api/generate"
        return httpx.Response(200, json={"response": "line1\nfinal-answer"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        assert await provider.chat("hi") == "chat-ok"
        solved = await provider.solve("2+2", subject="mathematics")
        assert solved["answer"] == "final-answer"
        assert solved["provider"] == "ollama"
        assert solved["model"] == "llama3.2:latest"
        assert solved["identity"] == "ollama:llama3.2:latest"
        assert solved["verification"]["message"] == "✓ Correct (Ollama response)"
        assert seen == ["/api/chat", "/api/generate"]

        gen = await provider.generate(GenerateRequest(message="x", purpose="chat"))
        assert gen.provider == ProviderId.OLLAMA
        assert gen.model == "llama3.2:latest"
        assert gen.raw.get("endpoint") == "/api/chat"


@pytest.mark.asyncio
async def test_ollama_provider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        with pytest.raises(OllamaUnavailableError) as exc:
            await provider.chat("hello")
        assert "ollama serve" in str(exc.value)
        assert exc.value.code == "ollama_unavailable"


@pytest.mark.asyncio
async def test_ollama_provider_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        with pytest.raises(ProviderTimeoutError) as exc:
            await provider.generate(GenerateRequest(message="hello"))
        assert exc.value.provider == "ollama"


@pytest.mark.asyncio
async def test_ollama_provider_model_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text='{"error":"model \'llama3.2:latest\' not found"}')

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        with pytest.raises(OllamaModelMissingError) as exc:
            await provider.chat("hello")
        assert "llama3.2:latest" in str(exc.value)
        assert "ollama pull" in str(exc.value)
        assert exc.value.code == "ollama_model_missing"


@pytest.mark.asyncio
async def test_ollama_provider_no_silent_mock_on_empty():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "   "}})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        with pytest.raises(OllamaRequestError) as exc:
            await provider.chat("hello")
        assert "mock" not in str(exc.value).lower()


@pytest.mark.asyncio
async def test_ollama_invalid_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not-json")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        with pytest.raises(OllamaRequestError):
            await provider.chat("hello")
