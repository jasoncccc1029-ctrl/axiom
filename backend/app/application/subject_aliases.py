"""Canonical subject labels so UI English slugs map to seeded mastery rows.

No schema change — resolve aliases at read/write boundaries only.
"""

from __future__ import annotations

# UI / solver / evaluation slugs → seeded / materials subjects
_SUBJECT_ALIASES: dict[str, str] = {
    "mathematics": "高二數學",
    "math": "高二數學",
    "數學": "高二數學",
    "physics": "物理",
    "english": "英文",
    "python": "程式",
}

_PLACEHOLDER_LABELS = frozenset({"general", "unknown", "n/a", "none", "null"})


def normalize_learning_label(value: str | None) -> str | None:
    """Treat placeholder topics like ``general`` as unspecified."""

    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in _PLACEHOLDER_LABELS:
        return None
    return text


def canonicalize_subject(subject: str | None) -> str | None:
    if subject is None:
        return None
    text = str(subject).strip()
    if not text:
        return None
    return _SUBJECT_ALIASES.get(text.lower(), text)
