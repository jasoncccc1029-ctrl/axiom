"""AI model providers — Axiom Brains.

Import adapters and the ``ModelProvider`` contract from here.
Never import OpenAI / Anthropic SDKs from Agent or Learning Loop modules.
"""

from app.providers.base import ModelProvider
from app.providers.cloud import CloudProvider
from app.providers.exceptions import (
    OllamaModelMissingError,
    OllamaRequestError,
    OllamaUnavailableError,
    ProviderError,
    ProviderModelMissingError,
    ProviderNotConfiguredError,
    ProviderRequestError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.providers.factory import get_provider
from app.providers.ollama import OllamaProvider
from app.providers.types import (
    GenerateRequest,
    GenerateResponse,
    ModelRef,
    ProviderId,
    ProviderModelInfo,
)

__all__ = [
    "ModelProvider",
    "OllamaProvider",
    "CloudProvider",
    "get_provider",
    "ProviderId",
    "ModelRef",
    "GenerateRequest",
    "GenerateResponse",
    "ProviderModelInfo",
    "ProviderError",
    "ProviderUnavailableError",
    "ProviderModelMissingError",
    "ProviderTimeoutError",
    "ProviderRequestError",
    "ProviderNotConfiguredError",
    "OllamaUnavailableError",
    "OllamaModelMissingError",
    "OllamaRequestError",
]
