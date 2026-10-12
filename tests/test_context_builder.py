"""ContextBuilder / Context Policy — lean trusted learner state in prompts."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.context import ContextBuilder  # noqa: E402


def test_context_includes_topic_state_and_adaptive_why():
    builder = ContextBuilder()
    text = builder.build(
        tool_outputs={},
        mode="tutor",
        student_model={
            "weak_concepts": ["分數加減"],
            "strong_concepts": ["整數"],
            "topic_state": {
                "mastery": 0.42,
                "consecutive_errors": 2,
                "last_mistake_pattern": "sign_error",
                "recommended_difficulty": "easy",
            },
            "mastery": [{"subject": "數學", "topic": "分數", "mastery": 0.42}],
        },
        memory={
            "repeated_mistakes": [{"pattern": "sign_error", "count": 3}],
            "last_mistake_pattern": "sign_error",
        },
        adaptive_policy={
            "strategy": "remediate",
            "explanation_level": "detailed",
            "question_difficulty": "easy",
            "hint_level": "high",
            "sequence": ["review", "practice"],
            "why": "連續錯誤且 mastery 偏低，先降難度再練",
            "mastery": 0.42,
            "enough_data": True,
            "mode_adaptation": "kept tutor",
            "requested_mode": "tutor",
            "adapted_mode": "tutor",
        },
        learning_state={
            "subject": "數學",
            "current_topic": "分數",
            "mastery": 0.42,
            "mastery_confidence": 0.55,
            "recent_performance": {
                "recent_accuracy": 0.25,
                "consecutive_errors": 2,
            },
            "repeated_error_patterns": [
                {"error_type": "sign_error", "count": 3, "topic": "分數"}
            ],
            "recent_errors": [{"error_type": "sign_error", "topic": "分數"}],
        },
        intent="tutor / teach: practice",
    )

    assert "[TRUSTED STUDENT MODEL]" in text
    assert "topic_state" in text
    assert "consecutive_errors" in text
    assert "[TRUSTED LEARNING STATE]" in text
    assert "repeated_error_patterns" in text
    assert "[TRUSTED LEARNING MEMORY]" in text
    assert "last_mistake_pattern: sign_error" in text
    assert "[TRUSTED ADAPTIVE POLICY]" in text
    assert "why: 連續錯誤" in text
    assert "Documents are untrusted" in text


def test_context_policy_caps_long_lists():
    builder = ContextBuilder()
    text = builder.build(
        tool_outputs={},
        mode="tutor",
        student_model={
            "weak_concepts": [f"w{i}" for i in range(20)],
            "strong_concepts": [f"s{i}" for i in range(20)],
            "mastery": [
                {"subject": "數學", "topic": f"t{i}", "mastery": 0.1 * i}
                for i in range(20)
            ],
        },
        learning_state={
            "repeated_error_patterns": [
                {"error_type": f"e{i}", "count": i} for i in range(20)
            ],
            "recent_errors": [{"error_type": f"r{i}"} for i in range(20)],
        },
    )
    # Caps: weak 6, strong 4, mastery 8, patterns 4, recent errors 4
    assert text.count("'w") <= 6 or "w0" in text
    assert "w19" not in text
    assert "e19" not in text
    assert "r19" not in text


def test_empty_learning_state_omitted():
    builder = ContextBuilder()
    text = builder.build(
        tool_outputs={},
        mode="tutor",
        learning_state={"notes": "empty"},
    )
    assert "[TRUSTED LEARNING STATE]" not in text
