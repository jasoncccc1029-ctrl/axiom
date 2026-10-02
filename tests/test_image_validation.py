"""Image validation unit tests."""

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.image_validation import detect_mime, validate_image_bytes  # noqa: E402
from app.vision.exceptions import InvalidImageError  # noqa: E402


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 32


def test_detect_png_and_jpeg():
    assert detect_mime(_png_bytes()) == "image/png"
    assert detect_mime(_jpeg_bytes()) == "image/jpeg"


def test_validate_image_ok():
    result = validate_image_bytes(_png_bytes(), declared_mime="image/png")
    assert result.mime_type == "image/png"
    assert result.extension == ".png"
    assert result.size > 0


def test_validate_rejects_empty():
    with pytest.raises(InvalidImageError):
        validate_image_bytes(b"")


def test_validate_rejects_unknown_bytes():
    with pytest.raises(InvalidImageError):
        validate_image_bytes(b"not-an-image")


def test_validate_rejects_mime_mismatch():
    with pytest.raises(InvalidImageError):
        validate_image_bytes(_png_bytes(), declared_mime="image/jpeg")


def test_validate_rejects_oversized(monkeypatch):
    monkeypatch.setattr("app.services.image_validation.settings.max_image_bytes", 16)
    with pytest.raises(InvalidImageError):
        validate_image_bytes(_png_bytes())
