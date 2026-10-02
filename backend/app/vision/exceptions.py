"""Vision provider exceptions."""


class VisionError(Exception):
    def __init__(self, message: str, *, code: str = "vision_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class VisionModelMissingError(VisionError):
    def __init__(self, model: str) -> None:
        super().__init__(
            f"找不到 Vision 模型 {model}，請先執行 ollama pull {model}。",
            code="vision_model_missing",
        )


class VisionUnavailableError(VisionError):
    def __init__(self) -> None:
        super().__init__(
            "Ollama 未啟動，請執行 ollama serve。",
            code="vision_unavailable",
        )


class InvalidImageError(VisionError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="invalid_image")
