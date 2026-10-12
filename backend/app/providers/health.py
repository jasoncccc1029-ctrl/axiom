"""Text-brain health for system status — keyed by current AI_PROVIDER.

Keeps OpenAI / Gemini / Ollama probe details out of Learning Loop and routers'
business paths. Vision health remains separate (VisionProvider / Ollama VLM).
"""

from __future__ import annotations

from app.config import settings
from app.providers.types import ProviderId
from app.schemas import SystemComponentHealth
from app.services.ollama_health import check_ollama_health


def check_openai_config_health() -> SystemComponentHealth:
    """Config-level OpenAI Brain check (no network call)."""

    key = (settings.openai_api_key or "").strip()
    model = (settings.openai_model or "").strip() or "gpt-4o-mini"
    if not key:
        return SystemComponentHealth(
            ok=False,
            detail=(
                "OpenAI Brain 未設定 OPENAI_API_KEY。"
                "應用可啟動，但 generate() 會回傳 provider_not_configured。"
            ),
            provider=ProviderId.OPENAI.value,
            model=model,
            reachable=False,
        )
    return SystemComponentHealth(
        ok=True,
        detail=f"OpenAI Brain configured ({model})",
        provider=ProviderId.OPENAI.value,
        model=model,
        reachable=True,
    )


def check_gemini_config_health() -> SystemComponentHealth:
    """Config-level Gemini Brain check (no network call)."""

    key = (settings.gemini_api_key or "").strip()
    model = (settings.gemini_model or "").strip() or "gemini-2.5-flash"
    if not key:
        return SystemComponentHealth(
            ok=False,
            detail=(
                "Gemini Brain 未設定 GEMINI_API_KEY。"
                "應用可啟動，但 generate() 會回傳 provider_not_configured。"
            ),
            provider=ProviderId.GEMINI.value,
            model=model,
            reachable=False,
        )
    return SystemComponentHealth(
        ok=True,
        detail=f"Gemini Brain configured ({model})",
        provider=ProviderId.GEMINI.value,
        model=model,
        reachable=True,
    )


async def check_text_brain_health() -> SystemComponentHealth:
    """Health of the process-default text Brain (AI_PROVIDER)."""

    provider = (settings.ai_provider or ProviderId.OLLAMA.value).strip().lower()
    if provider in {"google", "google-gemini"}:
        provider = ProviderId.GEMINI.value

    if provider == ProviderId.OPENAI.value:
        return check_openai_config_health()

    if provider == ProviderId.GEMINI.value:
        return check_gemini_config_health()

    if provider == ProviderId.ANTHROPIC.value:
        return SystemComponentHealth(
            ok=False,
            detail="Anthropic Brain 尚未啟用（Phase 5）。",
            provider=ProviderId.ANTHROPIC.value,
            model=None,
            reachable=False,
        )

    if provider == "cloud":
        return SystemComponentHealth(
            ok=False,
            detail="通用 CloudProvider 已停用。請使用 ollama、openai 或 gemini。",
            provider="cloud",
            model=None,
            reachable=False,
        )

    ollama = await check_ollama_health()
    return SystemComponentHealth(
        ok=ollama.ok,
        detail=ollama.message,
        provider=ProviderId.OLLAMA.value,
        model=ollama.model,
        reachable=ollama.reachable,
    )
