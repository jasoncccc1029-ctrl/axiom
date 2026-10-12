"""Phase 4.1 — system health vs AI_PROVIDER + lazy OpenAI key."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app import config as config_mod  # noqa: E402
from app.dependencies import AppContainer  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.exceptions import ProviderNotConfiguredError  # noqa: E402
from app.providers.health import check_text_brain_health  # noqa: E402
from app.providers.openai import OpenAIProvider  # noqa: E402
from app.providers.types import GenerateRequest, ProviderId  # noqa: E402
from app.schemas import SystemComponentHealth  # noqa: E402
from app.services.ollama_health import OllamaHealth  # noqa: E402
from app.services.seed import init_db  # noqa: E402


def _ollama_up() -> OllamaHealth:
    return OllamaHealth(
        ok=True,
        reachable=True,
        model="llama3.2:latest",
        model_available=True,
        models=["llama3.2:latest"],
        message="Ollama ready",
    )


def _ollama_down() -> OllamaHealth:
    return OllamaHealth(
        ok=False,
        reachable=False,
        model="llama3.2:latest",
        model_available=False,
        models=[],
        message="Ollama 未啟動，請執行 ollama serve。",
    )


@pytest.mark.asyncio
async def test_text_brain_health_ollama_reachable(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "ollama")
    with patch(
        "app.providers.health.check_ollama_health",
        new=AsyncMock(return_value=_ollama_up()),
    ):
        health = await check_text_brain_health()
    assert health.provider == "ollama"
    assert health.ok is True
    assert health.reachable is True


@pytest.mark.asyncio
async def test_text_brain_health_ollama_unreachable(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "ollama")
    with patch(
        "app.providers.health.check_ollama_health",
        new=AsyncMock(return_value=_ollama_down()),
    ):
        health = await check_text_brain_health()
    assert health.provider == "ollama"
    assert health.ok is False
    assert health.reachable is False


@pytest.mark.asyncio
async def test_text_brain_health_openai_ignores_ollama_down(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "openai")
    monkeypatch.setattr(config_mod.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(config_mod.settings, "openai_model", "gpt-4o-mini")
    with patch(
        "app.providers.health.check_ollama_health",
        new=AsyncMock(return_value=_ollama_down()),
    ) as mocked:
        health = await check_text_brain_health()
        mocked.assert_not_awaited()
    assert health.provider == "openai"
    assert health.ok is True
    assert health.reachable is True


@pytest.mark.asyncio
async def test_system_health_openai_ok_when_ollama_down(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "openai")
    monkeypatch.setattr(config_mod.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(config_mod.settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(config_mod.settings, "vision_provider", "mock")

    async def _brain() -> SystemComponentHealth:
        return SystemComponentHealth(
            ok=True,
            detail="OpenAI Brain configured (gpt-4o-mini)",
            provider="openai",
            model="gpt-4o-mini",
            reachable=True,
        )

    with patch(
        "app.routers.check_text_brain_health",
        new=AsyncMock(side_effect=_brain),
    ):
        init_db()
        with TestClient(app) as client:
            res = client.get("/api/system/health")
    assert res.status_code == 200
    body = res.json()
    assert body["text_brain"]["provider"] == "openai"
    assert body["text_brain"]["ok"] is True
    assert body["ollama"]["provider"] == "openai"  # legacy alias
    assert body["ollama"]["ok"] is True
    assert body["ok"] is True


@pytest.mark.asyncio
async def test_system_health_ollama_regression_unreachable(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "ollama")
    monkeypatch.setattr(config_mod.settings, "vision_provider", "mock")

    with patch(
        "app.providers.health.check_ollama_health",
        new=AsyncMock(return_value=_ollama_down()),
    ):
        init_db()
        with TestClient(app) as client:
            res = client.get("/api/system/health")
    assert res.status_code == 200
    body = res.json()
    assert body["ollama"]["provider"] == "ollama"
    assert body["ollama"]["reachable"] is False
    assert body["ok"] is False


@pytest.mark.asyncio
async def test_app_container_boots_with_openai_missing_key(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "openai")
    monkeypatch.setattr(config_mod.settings, "openai_api_key", "")
    monkeypatch.setattr(config_mod.settings, "openai_model", "gpt-4o-mini")
    monkeypatch.setattr(config_mod.settings, "vision_provider", "mock")

    container = AppContainer()
    try:
        assert isinstance(container.model_provider, OpenAIProvider)
        assert container.model_provider.provider_id == ProviderId.OPENAI
    finally:
        await container.close()


@pytest.mark.asyncio
async def test_openai_generate_missing_key_raises(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "openai")
    monkeypatch.setattr(config_mod.settings, "openai_api_key", "")
    provider = OpenAIProvider.from_settings()
    with pytest.raises(ProviderNotConfiguredError) as exc:
        await provider.generate(GenerateRequest(message="hi", purpose="chat"))
    assert exc.value.provider == "openai"
    assert "OPENAI_API_KEY" in exc.value.message


def test_app_boots_via_testclient_with_openai_missing_key(monkeypatch):
    monkeypatch.setattr(config_mod.settings, "ai_provider", "openai")
    monkeypatch.setattr(config_mod.settings, "openai_api_key", "")
    monkeypatch.setattr(config_mod.settings, "vision_provider", "mock")
    init_db()
    with TestClient(app) as client:
        res = client.get("/health")
        assert res.status_code == 200
        assert isinstance(client.app.state.container.model_provider, OpenAIProvider)


@pytest.mark.asyncio
async def test_ollama_default_factory_unchanged(monkeypatch):
    from app.providers.factory import get_provider
    from app.providers.ollama import OllamaProvider

    monkeypatch.setattr(config_mod.settings, "ai_provider", "ollama")
    monkeypatch.setattr(config_mod.settings, "ollama_model", "llama3.2:latest")
    provider = get_provider()
    assert isinstance(provider, OllamaProvider)
    assert provider.identity == "ollama:llama3.2:latest"
