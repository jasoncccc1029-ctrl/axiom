"""Tutor strategy policy — backend decides strategy; LLM only verbalizes it."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.agent.schemas import TeachingMode
from app.application.difficulty_policy import DifficultyDecision
from app.application.error_intelligence import ErrorDiagnosis, ErrorType, REPEATED_ERROR_THRESHOLD


class TutorStrategy(StrEnum):
    NORMAL = "NORMAL"
    HINT = "HINT"
    CONCEPT = "CONCEPT"
    ERROR_DIAGNOSIS = "ERROR_DIAGNOSIS"
    EXAMPLE = "EXAMPLE"
    PRACTICE = "PRACTICE"
    REVIEW = "REVIEW"
    CHALLENGE = "CHALLENGE"


class TutorStrategyDecision(BaseModel):
    strategy: TutorStrategy
    teaching_mode: TeachingMode
    reason: str
    signals: dict[str, object] = Field(default_factory=dict)


class TutorStrategyPolicy:
    def decide(
        self,
        *,
        requested_mode: TeachingMode | None = None,
        mastery: float = 0.0,
        concept_mastery: float | None = None,
        consecutive_errors: int = 0,
        repeated_error_count: int = 0,
        error_diagnosis: ErrorDiagnosis | None = None,
        difficulty_decision: DifficultyDecision | None = None,
        spaced_review_due: bool = False,
        recent_accuracy: float = 0.0,
        attempts: int = 0,
    ) -> TutorStrategyDecision:
        concept = concept_mastery if concept_mastery is not None else mastery
        repeated = repeated_error_count
        if error_diagnosis and error_diagnosis.error_type != ErrorType.NONE:
            repeated = max(repeated, error_diagnosis.pattern_count)

        if spaced_review_due and mastery >= 0.75:
            return TutorStrategyDecision(
                strategy=TutorStrategy.REVIEW,
                teaching_mode=TeachingMode.CONCEPT,
                reason="Spaced-review interval elapsed at high mastery; review before advancing.",
                signals={"mastery": mastery, "spaced_review_due": True},
            )

        if repeated >= REPEATED_ERROR_THRESHOLD:
            return TutorStrategyDecision(
                strategy=TutorStrategy.CONCEPT,
                teaching_mode=TeachingMode.CONCEPT,
                reason=(
                    f"Same error pattern repeated {repeated} times; switch to concept review."
                ),
                signals={"repeated_error_count": repeated, "concept_mastery": concept},
            )

        if consecutive_errors >= 2 or repeated >= 2:
            return TutorStrategyDecision(
                strategy=TutorStrategy.ERROR_DIAGNOSIS,
                teaching_mode=TeachingMode.ERROR_DIAGNOSIS,
                reason="Consecutive or repeated failures require error diagnosis.",
                signals={
                    "consecutive_errors": consecutive_errors,
                    "repeated_error_count": repeated,
                },
            )

        if consecutive_errors == 1:
            return TutorStrategyDecision(
                strategy=TutorStrategy.HINT,
                teaching_mode=TeachingMode.HINT,
                reason="First recent miss; use a targeted hint before full reteach.",
                signals={"consecutive_errors": consecutive_errors},
            )

        if concept < 0.4 and attempts >= 2:
            return TutorStrategyDecision(
                strategy=TutorStrategy.EXAMPLE,
                teaching_mode=TeachingMode.CONCEPT,
                reason="Weak prerequisite/concept mastery; teach with a worked example.",
                signals={"concept_mastery": concept, "attempts": attempts},
            )

        if mastery >= 0.85 and recent_accuracy >= 0.8:
            return TutorStrategyDecision(
                strategy=TutorStrategy.CHALLENGE,
                teaching_mode=TeachingMode.STEP_BY_STEP,
                reason="High mastery and accuracy; increase challenge.",
                signals={"mastery": mastery, "recent_accuracy": recent_accuracy},
            )

        if (
            difficulty_decision
            and difficulty_decision.action == "hold"
            and mastery >= 0.55
            and consecutive_errors == 0
        ):
            return TutorStrategyDecision(
                strategy=TutorStrategy.PRACTICE,
                teaching_mode=requested_mode or TeachingMode.TUTOR,
                reason="Stable performance; continue guided practice.",
                signals={"mastery": mastery},
            )

        if requested_mode is not None:
            mapped = _mode_to_strategy(requested_mode)
            return TutorStrategyDecision(
                strategy=mapped,
                teaching_mode=requested_mode,
                reason="Keep student-selected teaching mode.",
                signals={"requested_mode": requested_mode.value},
            )

        return TutorStrategyDecision(
            strategy=TutorStrategy.NORMAL,
            teaching_mode=TeachingMode.TUTOR,
            reason="Baseline tutoring strategy.",
            signals={"mastery": mastery},
        )


def _mode_to_strategy(mode: TeachingMode) -> TutorStrategy:
    return {
        TeachingMode.HINT: TutorStrategy.HINT,
        TeachingMode.CONCEPT: TutorStrategy.CONCEPT,
        TeachingMode.ERROR_DIAGNOSIS: TutorStrategy.ERROR_DIAGNOSIS,
        TeachingMode.STEP_BY_STEP: TutorStrategy.PRACTICE,
        TeachingMode.SOCRATIC: TutorStrategy.NORMAL,
        TeachingMode.TUTOR: TutorStrategy.NORMAL,
        TeachingMode.DIRECT_SOLVE: TutorStrategy.PRACTICE,
        TeachingMode.FULL_SOLUTION: TutorStrategy.EXAMPLE,
    }.get(mode, TutorStrategy.NORMAL)
