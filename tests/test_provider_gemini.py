"""Unit tests for GeminiProvider (Google generateContent adapter)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.providers.exceptions import (  # noqa: E402
    ProviderModelMissingError,
    ProviderNotConfiguredError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.gemini import GeminiProvider  # noqa: E402
from app.providers.types import GenerateRequest, ProviderId  # noqa: E402


def test_gemini_identity_and_display_name():
    provider = GeminiProvider(api_key="g-test", model="gemini-2.5-flash")
    assert provider.provider_id == ProviderId.GEMINI
    assert provider.name == "gemini"
    assert provider.model == "gemini-2.5-flash"
    assert provider.identity == "gemini:gemini-2.5-flash"
    assert provider.model_ref().key() == "gemini:gemini-2.5-flash"
    assert provider.display_name == "Axiom Cloud · Gemini · gemini-2.5-flash"
    info = provider.describe()
    assert info.is_local is False
    assert info.label == provider.display_name


@pytest.mark.asyncio
async def test_gemini_missing_key_deferred_to_generate():
    provider = GeminiProvider(api_key="", model="gemini-2.5-flash")
    assert provider.identity == "gemini:gemini-2.5-flash"
    with pytest.raises(ProviderNotConfiguredError) as exc:
        await provider.generate(GenerateRequest(message="hi", purpose="chat"))
    assert exc.value.provider == "gemini"
    assert exc.value.code == "provider_not_configured"


def test_gemini_from_settings(monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod.settings, "gemini_api_key", "g-from-settings")
    monkeypatch.setattr(config_mod.settings, "gemini_model", "gemini-2.5-flash")
    monkeypatch.setattr(
        config_mod.settings,
        "gemini_base_url",
        "https://generativelanguage.googleapis.com/v1beta",
    )
    monkeypatch.setattr(config_mod.settings, "model_timeout_seconds", 90.0)
    monkeypatch.setattr(config_mod.settings, "gemini_temperature", 0.3)
    monkeypatch.setattr(config_mod.settings, "gemini_max_output_tokens", 256)
    provider = GeminiProvider.from_settings()
    assert provider.api_key == "g-from-settings"
    assert provider.model == "gemini-2.5-flash"
    assert provider.timeout == 90.0
    assert provider.max_output_tokens == 256


@pytest.mark.asyncio
async def test_gemini_generate_uses_generate_content():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models/gemini-2.5-flash:generateContent")
        assert request.headers.get("x-goog-api-key") == "g-test"
        body = json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "矩陣是矩形數字陣列。"}],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiProvider(
            api_key="g-test",
            model="gemini-2.5-flash",
            client=client,
        )
        result = await provider.generate(
            GenerateRequest(message="什麼是矩陣？", purpose="chat")
        )
        assert "矩陣" in result.content
        assert result.provider == ProviderId.GEMINI
        assert result.model == "gemini-2.5-flash"
        body = seen["body"]
        assert isinstance(body, dict)
        assert body["contents"][0]["parts"][0]["text"] == "什麼是矩陣？"
        assert body["generationConfig"]["maxOutputTokens"] == 512


@pytest.mark.asyncio
async def test_gemini_solve_shapes_steps():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "步驟一\n步驟二\n答案：4"}],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiProvider(api_key="g-test", model="gemini-2.5-flash", client=client)
        solved = await provider.solve("2+2", subject="mathematics")
        assert solved["provider"] == "gemini"
        assert solved["answer"] == "答案：4"
        assert solved["identity"] == "gemini:gemini-2.5-flash"


@pytest.mark.asyncio
async def test_gemini_unavailable_and_timeout():
    def connect_fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    transport = httpx.MockTransport(connect_fail)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiProvider(api_key="g-test", client=client)
        with pytest.raises(ProviderUnavailableError) as exc:
            await provider.chat("hi")
        assert exc.value.code == "gemini_unavailable"

    def timeout_fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    transport = httpx.MockTransport(timeout_fail)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiProvider(api_key="g-test", client=client)
        with pytest.raises(ProviderTimeoutError) as exc:
            await provider.chat("hi")
        assert exc.value.code == "gemini_timeout"


@pytest.mark.asyncio
async def test_gemini_model_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="model not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiProvider(api_key="g-test", model="nope", client=client)
        with pytest.raises(ProviderModelMissingError) as exc:
            await provider.chat("hi")
        assert exc.value.code == "gemini_model_missing"


@pytest.mark.asyncio
async def test_gemini_blocked_prompt():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"promptFeedback": {"blockReason": "SAFETY"}, "candidates": []},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = GeminiProvider(api_key="g-test", client=client)
        with pytest.raises(ProviderRequestError) as exc:
            await provider.chat("bad")
        assert exc.value.code == "gemini_blocked"


def test_factory_gemini(monkeypatch):
    from app import config as config_mod
    from app.providers.factory import get_provider

    monkeypatch.setattr(config_mod.settings, "ai_provider", "gemini")
    monkeypatch.setattr(config_mod.settings, "gemini_api_key", "")
    monkeypatch.setattr(config_mod.settings, "gemini_model", "gemini-2.5-flash")
    provider = get_provider()
    assert provider.name == "gemini"
    assert provider.model == "gemini-2.5-flash"
