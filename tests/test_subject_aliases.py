"""Subject alias resolution for personalization consistency."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.subject_aliases import (  # noqa: E402
    canonicalize_subject,
    normalize_learning_label,
)


def test_canonicalize_math_aliases():
    assert canonicalize_subject("mathematics") == "高二數學"
    assert canonicalize_subject("MATH") == "高二數學"
    assert canonicalize_subject("高二數學") == "高二數學"
    assert canonicalize_subject("physics") == "物理"
    assert canonicalize_subject("未知科目") == "未知科目"
    assert canonicalize_subject(None) is None


def test_normalize_placeholder_topics():
    assert normalize_learning_label("general") is None
    assert normalize_learning_label("  GENERAL  ") is None
    assert normalize_learning_label("二次函數") == "二次函數"
    assert normalize_learning_label(None) is None
