"""Optional live Ollama integration tests.

Run only when:
  RUN_OLLAMA_TESTS=true

Example:
  $env:RUN_OLLAMA_TESTS='true'; pytest tests/test_ollama_integration.py -q
"""

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings  # noqa: E402
from app.providers.ollama import OllamaProvider  # noqa: E402
from app.services.ollama_health import check_ollama_health  # noqa: E402

RUN = os.getenv("RUN_OLLAMA_TESTS", "").lower() in {"1", "true", "yes"}

pytestmark = pytest.mark.skipif(
    not RUN,
    reason="Set RUN_OLLAMA_TESTS=true to run live Ollama integration tests",
)


@pytest.mark.asyncio
async def test_live_ollama_health():
    health = await check_ollama_health()
    assert health.reachable is True
    assert health.model_available is True
    assert health.ok is True


@pytest.mark.asyncio
async def test_live_ollama_chat_matrix():
    provider = OllamaProvider(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
    )
    reply = await provider.chat("什麼是矩陣？請用兩句話簡短回答。")
    assert isinstance(reply, str)
    assert len(reply.strip()) > 10
    assert "mock" not in reply.lower()
    assert "v0.1" not in reply.lower()
