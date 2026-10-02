"""Safe image validation helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.vision.exceptions import InvalidImageError

ALLOWED_MIME_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}

MIME_BY_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # needs WEBP at offset 8
}


@dataclass
class ValidatedImage:
    content: bytes
    mime_type: str
    extension: str
    size: int


def detect_mime(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image_bytes(
    content: bytes,
    *,
    declared_mime: str | None = None,
    max_bytes: int | None = None,
) -> ValidatedImage:
    limit = max_bytes if max_bytes is not None else settings.max_image_bytes
    if not content:
        raise InvalidImageError("空的圖片檔案。")
    if len(content) > limit:
        mb = limit / (1024 * 1024)
        raise InvalidImageError(f"圖片過大，上限為 {mb:.0f} MB。")

    detected = detect_mime(content)
    if detected is None:
        raise InvalidImageError("不支援的圖片格式，請使用 JPG / PNG / WEBP。")

    if declared_mime:
        normalized = declared_mime.lower().split(";")[0].strip()
        if normalized in {"image/jpg"}:
            normalized = "image/jpeg"
        if normalized and normalized != detected:
            # Allow image/jpg alias already handled; otherwise reject mismatch
            raise InvalidImageError("檔案內容與 MIME type 不符。")

    extension = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }[detected]

    return ValidatedImage(
        content=content,
        mime_type=detected,
        extension=extension,
        size=len(content),
    )


def safe_extension_from_name(filename: str | None) -> str | None:
    if not filename:
        return None
    name = filename.replace("\\", "/").split("/")[-1]
    if ".." in name or name.startswith("."):
        return None
    lower = name.lower()
    for ext in (".jpeg", ".jpg", ".png", ".webp"):
        if lower.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return None
