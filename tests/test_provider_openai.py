"""Unit tests for OpenAIProvider (Phase 4 Responses API adapter)."""

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
from app.providers.openai import OpenAIProvider  # noqa: E402
from app.providers.types import GenerateRequest, ProviderId  # noqa: E402


def test_openai_identity_and_display_name():
    provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini")
    assert provider.provider_id == ProviderId.OPENAI
    assert provider.name == "openai"
    assert provider.model == "gpt-4o-mini"
    assert provider.identity == "openai:gpt-4o-mini"
    assert provider.model_ref().key() == "openai:gpt-4o-mini"
    assert provider.display_name == "Axiom Cloud · OpenAI · gpt-4o-mini"
    info = provider.describe()
    assert info.is_local is False
    assert info.label == provider.display_name


@pytest.mark.asyncio
async def test_openai_missing_key_deferred_to_generate():
    """Phase 4.1: construct without key; fail clearly on generate()."""

    provider = OpenAIProvider(api_key="", model="gpt-4o-mini")
    assert provider.provider_id == ProviderId.OPENAI
    assert provider.identity == "openai:gpt-4o-mini"
    with pytest.raises(ProviderNotConfiguredError) as exc:
        await provider.generate(GenerateRequest(message="hi", purpose="chat"))
    assert exc.value.provider == "openai"
    assert exc.value.code == "provider_not_configured"


def test_openai_from_settings(monkeypatch):
    from app import config as config_mod

    monkeypatch.setattr(config_mod.settings, "openai_api_key", "sk-from-settings")
    monkeypatch.setattr(config_mod.settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(config_mod.settings, "openai_base_url", "https://api.openai.com/v1")
    monkeypatch.setattr(config_mod.settings, "model_timeout_seconds", 90.0)
    provider = OpenAIProvider.from_settings()
    assert provider.api_key == "sk-from-settings"
    assert provider.model == "gpt-4o-mini"
    assert provider.timeout == 90.0


@pytest.mark.asyncio
async def test_openai_generate_uses_responses_api():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/responses")
        assert request.headers.get("Authorization") == "Bearer sk-test"
        body = json.loads(request.content.decode())
        seen["body"] = body
        return httpx.Response(
            200,
            json={
                "id": "resp_1",
                "output_text": "矩陣是矩形數字陣列。",
                "output": [],
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(
            api_key="sk-test",
            model="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
            client=client,
        )
        result = await provider.generate(
            GenerateRequest(message="什麼是矩陣？", purpose="chat")
        )
        assert "矩陣" in result.content
        assert result.provider == ProviderId.OPENAI
        assert result.model == "gpt-4o-mini"
        body = seen["body"]
        assert isinstance(body, dict)
        assert body["model"] == "gpt-4o-mini"
        assert body["input"] == "什麼是矩陣？"
        assert "instructions" in body


@pytest.mark.asyncio
async def test_chat_and_solve_delegate_to_generate():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        seen.append(str(body.get("input", "")))
        return httpx.Response(200, json={"output_text": f"ok:{body['input']}"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
        chat = await provider.chat("hello")
        solve = await provider.solve("2+2", subject="數學")
        assert chat == "ok:hello"
        assert solve["provider"] == "openai"
        assert solve["identity"] == "openai:gpt-4o-mini"
        assert solve["answer"]
        assert seen == ["hello", "2+2"]


@pytest.mark.asyncio
async def test_extract_text_from_output_items():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "output": [
                    {"type": "reasoning", "content": []},
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": "從 output items 取出"},
                        ],
                    },
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
        result = await provider.generate(GenerateRequest(message="hi", purpose="chat"))
        assert result.content == "從 output items 取出"


@pytest.mark.asyncio
async def test_openai_auth_error_maps_to_not_configured():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="invalid api key")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-bad", model="gpt-4o-mini", client=client)
        with pytest.raises(ProviderNotConfiguredError) as exc:
            await provider.chat("hi")
        assert exc.value.provider == "openai"


@pytest.mark.asyncio
async def test_openai_model_missing():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="model not found")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-test", model="no-such-model", client=client)
        with pytest.raises(ProviderModelMissingError) as exc:
            await provider.chat("hi")
        assert exc.value.model == "no-such-model"


@pytest.mark.asyncio
async def test_openai_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
        with pytest.raises(ProviderTimeoutError):
            await provider.chat("hi")


@pytest.mark.asyncio
async def test_openai_connect_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
        with pytest.raises(ProviderUnavailableError):
            await provider.chat("hi")


@pytest.mark.asyncio
async def test_openai_empty_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
        with pytest.raises(ProviderRequestError):
            await provider.chat("hi")


@pytest.mark.asyncio
async def test_context_appended_to_instructions():
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"output_text": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
        await provider.chat("q", context="UNTRUSTED DOC")
        body = seen["body"]
        assert isinstance(body, dict)
        assert "UNTRUSTED DOC" in body["instructions"]
        assert "不可信" in body["instructions"]
