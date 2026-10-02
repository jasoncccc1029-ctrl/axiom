"""Deterministic, conservative learning-outcome decisions for Tutor/Agent runs.

Mastery updates require reliable evidence. Ambiguous tool/LLM-only turns must
never pretend the student mastered a concept.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.agent.schemas import VerificationStatus


class LearningOutcomeStatus(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class OutcomeEvidenceKind(StrEnum):
    TOOL_VERIFIER = "tool_verifier"
    BANK_ANSWER = "bank_answer"
    STUDENT_MARK = "student_mark"
    RECORD_ATTEMPT_FLAG = "record_attempt_flag"
    NONE = "none"


# Tools whose verified=True/False is trusted for mastery writes.
TRUSTED_VERIFIER_TOOLS = frozenset({"math", "calculator", "python"})


class OutcomeDecision(BaseModel):
    status: LearningOutcomeStatus
    should_record_attempt: bool
    should_update_mastery: bool
    correct: bool | None = None
    evidence: list[OutcomeEvidenceKind] = Field(default_factory=list)
    reason: str
    student_message: str


def decide_from_verification(
    *,
    verification: VerificationStatus,
    route: str,
    tool_names: list[str] | None = None,
    record_attempt: bool | None = None,
) -> OutcomeDecision:
    """Map agent verification + evidence into a conservative learning outcome."""
    tools = set(tool_names or [])
    has_trusted_tools = bool(tools & TRUSTED_VERIFIER_TOOLS)

    if record_attempt is False:
        return OutcomeDecision(
            status=_status_without_mastery(verification),
            should_record_attempt=False,
            should_update_mastery=False,
            correct=None,
            evidence=[OutcomeEvidenceKind.NONE],
            reason="record_attempt=false; skip automatic learning-state write.",
            student_message=_student_message(_status_without_mastery(verification)),
        )

    if verification == VerificationStatus.VERIFIED and (
        record_attempt is True or has_trusted_tools or route == "solver"
    ):
        evidence = [OutcomeEvidenceKind.TOOL_VERIFIER]
        if record_attempt is True:
            evidence.append(OutcomeEvidenceKind.RECORD_ATTEMPT_FLAG)
        return OutcomeDecision(
            status=LearningOutcomeStatus.VERIFIED,
            should_record_attempt=True,
            should_update_mastery=True,
            correct=True,
            evidence=evidence,
            reason=(
                "Trusted verifier returned VERIFIED; "
                "safe to record a correct attempt and update mastery."
            ),
            student_message=_student_message(LearningOutcomeStatus.VERIFIED),
        )

    if verification == VerificationStatus.FAILED and (
        record_attempt is True or has_trusted_tools or route == "solver"
    ):
        evidence = [OutcomeEvidenceKind.TOOL_VERIFIER]
        if record_attempt is True:
            evidence.append(OutcomeEvidenceKind.RECORD_ATTEMPT_FLAG)
        return OutcomeDecision(
            status=LearningOutcomeStatus.FAILED,
            should_record_attempt=True,
            should_update_mastery=True,
            correct=False,
            evidence=evidence,
            reason=(
                "Trusted verifier returned FAILED; "
                "safe to record an incorrect attempt and update mastery."
            ),
            student_message=_student_message(LearningOutcomeStatus.FAILED),
        )

    if verification == VerificationStatus.PARTIALLY_VERIFIED:
        return OutcomeDecision(
            status=LearningOutcomeStatus.PARTIALLY_VERIFIED,
            should_record_attempt=False,
            should_update_mastery=False,
            correct=None,
            evidence=[OutcomeEvidenceKind.NONE],
            reason=(
                "Only partial tool evidence; do not treat explanation or "
                "partial checks as student mastery."
            ),
            student_message=_student_message(LearningOutcomeStatus.PARTIALLY_VERIFIED),
        )

    # NOT_VERIFIABLE, tutor-only LLM answers, or VERIFIED/FAILED without evidence.
    return OutcomeDecision(
        status=LearningOutcomeStatus.NEEDS_REVIEW,
        should_record_attempt=False,
        should_update_mastery=False,
        correct=None,
        evidence=[OutcomeEvidenceKind.NONE],
        reason=(
            "No reliable verifier evidence that the student answered correctly "
            "or incorrectly; keep Mark correct/incorrect for confirmation."
        ),
        student_message=_student_message(LearningOutcomeStatus.NEEDS_REVIEW),
    )


def decide_from_student_mark(*, correct: bool) -> OutcomeDecision:
    """Explicit student confirmation is reliable evidence for mastery writes."""
    status = (
        LearningOutcomeStatus.VERIFIED if correct else LearningOutcomeStatus.FAILED
    )
    return OutcomeDecision(
        status=status,
        should_record_attempt=True,
        should_update_mastery=True,
        correct=correct,
        evidence=[OutcomeEvidenceKind.STUDENT_MARK],
        reason="Student explicitly marked the attempt; treat as confirmed outcome.",
        student_message=_student_message(status),
    )


def decide_from_bank_answer(*, correct: bool) -> OutcomeDecision:
    """Problem-bank answer comparison is deterministic evidence for mastery writes."""
    status = (
        LearningOutcomeStatus.VERIFIED if correct else LearningOutcomeStatus.FAILED
    )
    return OutcomeDecision(
        status=status,
        should_record_attempt=True,
        should_update_mastery=True,
        correct=correct,
        evidence=[OutcomeEvidenceKind.BANK_ANSWER],
        reason="Student answer compared against Problem.answer; treat as verified outcome.",
        student_message=_student_message(status),
    )


def _status_without_mastery(verification: VerificationStatus) -> LearningOutcomeStatus:
    if verification == VerificationStatus.PARTIALLY_VERIFIED:
        return LearningOutcomeStatus.PARTIALLY_VERIFIED
    if verification == VerificationStatus.VERIFIED:
        return LearningOutcomeStatus.NEEDS_REVIEW
    if verification == VerificationStatus.FAILED:
        return LearningOutcomeStatus.NEEDS_REVIEW
    return LearningOutcomeStatus.NEEDS_REVIEW


def _student_message(status: LearningOutcomeStatus) -> str:
    if status == LearningOutcomeStatus.VERIFIED:
        return "這次作答已通過可靠驗證，學習進度已更新。"
    if status == LearningOutcomeStatus.FAILED:
        return "這次作答未通過驗證，系統已記錄錯誤並調整下一步建議。"
    if status == LearningOutcomeStatus.PARTIALLY_VERIFIED:
        return (
            "系統目前可以確認部分內容，但還不足以判定你已完全掌握。"
            "若這是你自己的作答結果，請標示正確或錯誤，學習進度才會更新。"
        )
    return (
        "這次回覆還無法可靠判斷你是否答對。"
        "請標示正確或錯誤，系統才會更新你的學習狀態。"
    )
