"""Phase 2 — ModelProvider contract and identity types."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.providers.base import ModelProvider  # noqa: E402
from app.providers.exceptions import (  # noqa: E402
    ProviderNotConfiguredError,
    ProviderUnavailableError,
)
from app.providers.factory import get_provider  # noqa: E402
from app.providers.ollama import OllamaProvider  # noqa: E402
from app.providers.types import (  # noqa: E402
    GenerateRequest,
    GenerateResponse,
    ModelRef,
    ProviderId,
)


class StubProvider(ModelProvider):
    provider_id = ProviderId.OPENAI
    model = "gpt-test"

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        return GenerateResponse(
            content=f"echo:{request.message}",
            provider=self.provider_id,
            model=self.model,
            raw={"purpose": request.purpose},
        )


@pytest.mark.asyncio
async def test_generate_is_unified_entry_and_chat_helper_works():
    provider = StubProvider()
    assert provider.name == "openai"
    assert provider.model_ref() == ModelRef(provider=ProviderId.OPENAI, model="gpt-test")
    assert provider.model_ref().key() == "openai:gpt-test"

    direct = await provider.generate(GenerateRequest(message="hi", purpose="chat"))
    assert direct.content == "echo:hi"
    assert direct.provider == ProviderId.OPENAI

    via_chat = await provider.chat("hi", context="ctx")
    assert via_chat == "echo:hi"


@pytest.mark.asyncio
async def test_default_solve_helper_returns_structured_dict():
    provider = StubProvider()
    result = await provider.solve("2+2", subject="mathematics")
    assert result["answer"]
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-test"
    assert isinstance(result["steps"], list)


def test_ollama_provider_identity():
    provider = OllamaProvider(base_url="http://127.0.0.1:11434", model="llama3.2:latest")
    assert provider.provider_id == ProviderId.OLLAMA
    assert provider.name == "ollama"  # traces
    assert provider.identity == "ollama:llama3.2:latest"
    assert provider.model_ref().key() == "ollama:llama3.2:latest"
    assert provider.display_name.startswith("Axiom Local")
    info = provider.describe()
    assert info.is_local is True
    assert info.available is True
    assert info.model == "llama3.2:latest"
    assert info.label == provider.display_name


def test_factory_default_is_ollama(monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod.settings, "ai_provider", "ollama")
    monkeypatch.setattr(config_mod.settings, "ollama_model", "llama3.2:latest")
    provider = get_provider()
    assert isinstance(provider, OllamaProvider)
    assert provider.provider_id == ProviderId.OLLAMA


def test_factory_openai_not_configured_yet(monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod.settings, "ai_provider", "openai")
    with pytest.raises(ProviderNotConfiguredError) as exc:
        get_provider()
    assert exc.value.provider == "openai"


def test_ollama_unavailable_is_provider_unavailable_subclass():
    assert issubclass(
        __import__("app.providers.exceptions", fromlist=["OllamaUnavailableError"]).OllamaUnavailableError,
        ProviderUnavailableError,
    )


@pytest.mark.asyncio
async def test_ollama_generate_chat_purpose_uses_chat_api():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": "ok"}},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:11434") as client:
        provider = OllamaProvider(
            base_url="http://127.0.0.1:11434",
            model="llama3.2:latest",
            client=client,
        )
        result = await provider.generate(GenerateRequest(message="hello", purpose="chat"))
        assert result.content == "ok"
        assert result.provider == ProviderId.OLLAMA
        assert result.model == "llama3.2:latest"
