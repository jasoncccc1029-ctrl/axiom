"""Unified provider / model identity for Axiom ModelProvider adapters.

Business logic (Agent, Tutor, Solver, Learning Loop) must depend on these
types and on ``ModelProvider`` — never on OpenAI / Anthropic / Ollama SDKs.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ProviderId(StrEnum):
    """Canonical AI brain identifiers (ModelRouter will select among these)."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"


GeneratePurpose = Literal["chat", "solve", "generate"]


class ModelRef(BaseModel):
    """Stable reference to a concrete model under a provider."""

    provider: ProviderId
    model: str = Field(..., min_length=1, max_length=160)

    def key(self) -> str:
        return f"{self.provider.value}:{self.model}"


class GenerateRequest(BaseModel):
    """Provider-agnostic generation request.

    ``context`` is Axiom-built trusted/untrusted text (StudentContext later).
    Adapters must treat document excerpts inside context as data, not instructions.
    """

    message: str = Field(..., min_length=1)
    context: str | None = None
    system: str | None = None
    subject: str | None = None
    purpose: GeneratePurpose = "chat"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerateResponse(BaseModel):
    """Provider-agnostic generation result."""

    content: str
    provider: ProviderId
    model: str
    raw: dict[str, Any] = Field(default_factory=dict)


class ProviderModelInfo(BaseModel):
    """Descriptor for UI / ModelRouter listing (no secrets)."""

    provider: ProviderId
    model: str
    label: str
    available: bool = True
    is_local: bool = False
    supports_vision: bool = False
