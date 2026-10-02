"""Ollama health checks for Axiom v0.2."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings
from app.providers.exceptions import OllamaModelMissingError, OllamaUnavailableError


@dataclass
class OllamaHealth:
    ok: bool
    reachable: bool
    model: str
    model_available: bool
    models: list[str]
    message: str


async def check_ollama_health(
    *,
    base_url: str | None = None,
    model: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> OllamaHealth:
    """Confirm Ollama is up and the configured model exists."""
    url = (base_url or settings.ollama_base_url).rstrip("/")
    target_model = model or settings.ollama_model

    try:
        if client is not None:
            response = await client.get(f"{url}/api/tags")
        else:
            async with httpx.AsyncClient(timeout=5.0) as http:
                response = await http.get(f"{url}/api/tags")
    except httpx.HTTPError:
        err = OllamaUnavailableError()
        return OllamaHealth(
            ok=False,
            reachable=False,
            model=target_model,
            model_available=False,
            models=[],
            message=err.message,
        )

    if response.status_code >= 400:
        err = OllamaUnavailableError()
        return OllamaHealth(
            ok=False,
            reachable=False,
            model=target_model,
            model_available=False,
            models=[],
            message=err.message,
        )

    try:
        payload = response.json()
    except ValueError:
        err = OllamaUnavailableError()
        return OllamaHealth(
            ok=False,
            reachable=False,
            model=target_model,
            model_available=False,
            models=[],
            message=err.message,
        )

    models: list[str] = []
    for item in payload.get("models", []) or []:
        name = item.get("name") or item.get("model")
        if name:
            models.append(str(name))

    available = _model_present(target_model, models)
    if not available:
        err = OllamaModelMissingError(target_model)
        return OllamaHealth(
            ok=False,
            reachable=True,
            model=target_model,
            model_available=False,
            models=models,
            message=err.message,
        )

    return OllamaHealth(
        ok=True,
        reachable=True,
        model=target_model,
        model_available=True,
        models=models,
        message=f"Ollama ready · {target_model}",
    )


def _model_present(target: str, models: list[str]) -> bool:
    names = set(models)
    if target in names:
        return True
    # Accept both "llama3.2:latest" and "llama3.2"
    if ":" in target:
        base = target.split(":", 1)[0]
        return any(m == base or m.startswith(f"{base}:") for m in names)
    return any(m == target or m.startswith(f"{target}:") for m in names)


async def ensure_ollama_ready(
    *,
    base_url: str | None = None,
    model: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> None:
    health = await check_ollama_health(base_url=base_url, model=model, client=client)
    if health.ok:
        return
    if not health.reachable:
        raise OllamaUnavailableError()
    raise OllamaModelMissingError(model or settings.ollama_model)
