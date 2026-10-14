"""Application error taxonomy and trust-boundary-safe public messages."""

from __future__ import annotations


class AxiomError(Exception):
    status_code = 500
    code = "axiom_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class ProviderUnavailable(AxiomError):
    status_code = 503
    code = "provider_unavailable"


class ModelUnavailable(AxiomError):
    status_code = 503
    code = "model_unavailable"


class DocumentParseError(AxiomError):
    status_code = 422
    code = "document_parse_error"


class ToolExecutionError(AxiomError):
    status_code = 422
    code = "tool_execution_error"


class VerificationError(AxiomError):
    status_code = 422
    code = "verification_error"


class ValidationError(AxiomError):
    status_code = 400
    code = "validation_error"


class NotFoundError(AxiomError):
    status_code = 404
    code = "not_found"


class QuotaExceededError(AxiomError):
    status_code = 429
    code = "ai_quota_exceeded"
