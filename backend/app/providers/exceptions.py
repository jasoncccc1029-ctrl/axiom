"""Provider-related exceptions with user-facing Chinese messages.

Generic errors are provider-agnostic. Ollama-* subclasses keep existing
codes/messages so current health checks and tests remain stable.
"""

from __future__ import annotations


class ProviderError(Exception):
    """Raised when the AI provider cannot complete a request."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_error",
        provider: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.provider = provider


class ProviderUnavailableError(ProviderError):
    def __init__(
        self,
        message: str = "AI provider 目前無法使用。",
        *,
        code: str = "provider_unavailable",
        provider: str | None = None,
    ) -> None:
        super().__init__(message, code=code, provider=provider)


class ProviderModelMissingError(ProviderError):
    def __init__(
        self,
        model: str,
        *,
        provider: str | None = None,
        message: str | None = None,
        code: str = "provider_model_missing",
    ) -> None:
        super().__init__(
            message or f"找不到模型 {model}。",
            code=code,
            provider=provider,
        )
        self.model = model


class ProviderTimeoutError(ProviderError):
    def __init__(
        self,
        message: str = "AI provider 回應逾時，請稍後再試。",
        *,
        code: str = "provider_timeout",
        provider: str | None = None,
    ) -> None:
        super().__init__(message, code=code, provider=provider)


class ProviderRequestError(ProviderError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "provider_request_error",
        provider: str | None = None,
    ) -> None:
        super().__init__(message, code=code, provider=provider)


class ProviderNotConfiguredError(ProviderError):
    """Cloud adapter present but API key / env not configured."""

    def __init__(
        self,
        provider: str,
        message: str | None = None,
    ) -> None:
        super().__init__(
            message
            or (
                f"{provider} 尚未設定。請在 backend environment 設定對應 API key，"
                "或改用 Ollama 本機模型。"
            ),
            code="provider_not_configured",
            provider=provider,
        )


class OllamaUnavailableError(ProviderUnavailableError):
    def __init__(self) -> None:
        super().__init__(
            "Ollama 未啟動，請執行 ollama serve。",
            code="ollama_unavailable",
            provider="ollama",
        )


class OllamaModelMissingError(ProviderModelMissingError):
    def __init__(self, model: str) -> None:
        super().__init__(
            model,
            provider="ollama",
            message=f"找不到 {model}，請先執行 ollama pull {model}。",
            code="ollama_model_missing",
        )


class OllamaRequestError(ProviderRequestError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="ollama_request_error", provider="ollama")
