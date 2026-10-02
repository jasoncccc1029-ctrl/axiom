"""Deterministic difficulty policy for Axiom v1.2.

Numeric levels 1–5 map to legacy string labels for TopicMastery compatibility.
LLM never decides difficulty.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


DIFFICULTY_MIN = 1
DIFFICULTY_MAX = 5

LEVEL_TO_LABEL = {
    1: "easy",
    2: "easy",
    3: "medium",
    4: "challenging",
    5: "challenging",
}

LABEL_TO_LEVEL = {
    "easy": 2,
    "current": 3,
    "medium": 3,
    "challenging": 4,
    "hard": 5,
}


class DifficultySignals(BaseModel):
    mastery: float = 0.0
    concept_mastery: float | None = None
    recent_accuracy: float = 0.0
    consecutive_errors: int = 0
    repeated_failures: int = 0
    hint_usage: int = 0
    retry_count: int = 0
    last_verified: bool | None = None
    consecutive_verified: int = 0
    current_difficulty: int = 3
    days_since_practice: float | None = None
    learning_trend: str = "stable"  # improving | declining | stable
    spaced_review_due: bool = False


class DifficultyDecision(BaseModel):
    previous_difficulty: int
    recommended_difficulty: int
    recommended_label: str
    reason: str
    signals: dict[str, object] = Field(default_factory=dict)
    action: str = "hold"  # increase | decrease | hold | review


class DifficultyPolicy:
    def decide(self, signals: DifficultySignals) -> DifficultyDecision:
        previous = _clamp(signals.current_difficulty)
        recommended = previous
        reason_parts: list[str] = []
        action = "hold"

        concept = (
            signals.concept_mastery
            if signals.concept_mastery is not None
            else signals.mastery
        )

        if signals.spaced_review_due and signals.mastery >= 0.75:
            action = "review"
            reason_parts.append(
                "High mastery with elapsed spaced-review interval; prefer REVIEW, not lower difficulty."
            )
        elif signals.repeated_failures >= 2 or signals.consecutive_errors >= 2:
            recommended = previous - 1
            action = "decrease"
            reason_parts.append(
                f"Repeated failures ({max(signals.repeated_failures, signals.consecutive_errors)}) "
                "require lower difficulty."
            )
        elif concept < 0.45 and signals.recent_accuracy < 0.5:
            recommended = previous - 1
            action = "decrease"
            reason_parts.append(
                f"Low concept mastery ({concept:.0%}) and recent accuracy "
                f"({signals.recent_accuracy:.0%})."
            )
        elif (
            signals.mastery >= 0.8
            and signals.recent_accuracy >= 0.8
            and signals.consecutive_verified >= 2
            and signals.consecutive_errors == 0
        ):
            recommended = previous + 1
            action = "increase"
            reason_parts.append(
                "High mastery, strong recent accuracy, and consecutive VERIFIED results."
            )
        elif signals.learning_trend == "improving" and signals.mastery < 0.7:
            action = "hold"
            reason_parts.append("Low mastery but improving trend; keep current difficulty.")
        elif signals.hint_usage >= 3 and signals.recent_accuracy < 0.6:
            recommended = previous - 1
            action = "decrease"
            reason_parts.append("Heavy hint usage with weak accuracy.")
        else:
            reason_parts.append("Signals do not justify a difficulty change.")

        recommended = _clamp(recommended)
        return DifficultyDecision(
            previous_difficulty=previous,
            recommended_difficulty=recommended,
            recommended_label=LEVEL_TO_LABEL[recommended],
            reason=" ".join(reason_parts),
            signals={
                "mastery": signals.mastery,
                "concept_mastery": concept,
                "recent_accuracy": signals.recent_accuracy,
                "repeated_failures": signals.repeated_failures,
                "consecutive_errors": signals.consecutive_errors,
                "consecutive_verified": signals.consecutive_verified,
                "hint_usage": signals.hint_usage,
                "retry_count": signals.retry_count,
                "last_verified": signals.last_verified,
                "days_since_practice": signals.days_since_practice,
                "learning_trend": signals.learning_trend,
                "spaced_review_due": signals.spaced_review_due,
            },
            action=action,
        )


def label_to_level(label: str | None) -> int:
    if not label:
        return 3
    return LABEL_TO_LEVEL.get(label.lower(), 3)


def level_to_label(level: int) -> str:
    return LEVEL_TO_LABEL[_clamp(level)]


def _clamp(value: int) -> int:
    return max(DIFFICULTY_MIN, min(DIFFICULTY_MAX, int(value)))
