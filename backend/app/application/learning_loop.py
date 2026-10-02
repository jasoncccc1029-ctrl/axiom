"""Closed-loop learning: sessions, outcomes, policies, and Axiom Learning Trace."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent.schemas import TeachingMode
from app.application.adaptive import AdaptiveTutor, Recommendation
from app.application.difficulty_policy import (
    DifficultyDecision,
    DifficultyPolicy,
    DifficultySignals,
    label_to_level,
)
from app.application.error_intelligence import (
    ErrorDiagnosis,
    ErrorIntelligenceService,
    ErrorType,
)
from app.application.mastery_graph import MasteryGraphService
from app.application.adaptive_question_engine import answers_match
from app.application.memory import LearningRecordRequest, LearningRecordResponse, MemoryService
from app.application.outcome_automation import (
    LearningOutcomeStatus,
    OutcomeDecision,
    OutcomeEvidenceKind,
    decide_from_bank_answer,
    decide_from_student_mark,
)
from app.application.problem_repository import ProblemRepository
from app.application.tutor_strategy import TutorStrategyDecision, TutorStrategyPolicy
from app.config import settings
from app.models import Attempt, LearningSession, RecommendationRecord, TopicMastery, utcnow


class LearningTrace(BaseModel):
    session_id: int
    trace_id: str | None = None
    student_state: dict[str, Any] = Field(default_factory=dict)
    detected_weakness: str | None = None
    weakness: dict[str, Any] | None = None
    error_diagnosis: dict[str, Any] | None = None
    tutor_decision: dict[str, Any] = Field(default_factory=dict)
    difficulty_decision: dict[str, Any] | None = None
    agent_decision: dict[str, Any] = Field(default_factory=dict)
    selected_tools: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    verification: str | None = None
    outcome_status: str | None = None
    outcome_reason: str | None = None
    outcome_evidence: list[str] = Field(default_factory=list)
    outcome_student_message: str | None = None
    mastery_updated: bool = False
    attempt: dict[str, Any] | None = None
    learning_result: dict[str, Any] = Field(default_factory=dict)
    mastery_before: dict[str, Any] | None = None
    mastery_after: dict[str, Any] | None = None
    mastery_update: dict[str, Any] | None = None
    mastery_delta: dict[str, Any] | None = None
    next_recommendation: Recommendation | None = None
    recommendation: Recommendation | None = None


class LearningOutcomeRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=120)
    topic: str = Field(..., min_length=1, max_length=160)
    correct: bool | None = None
    mistake_pattern: str | None = Field(default=None, max_length=255)
    detected_misconception: str | None = Field(default=None, max_length=500)
    answer: str | None = Field(default=None, max_length=10_000)
    expected_answer: str | None = Field(default=None, max_length=10_000)
    ai_explanation: str | None = Field(default=None, max_length=20_000)
    mode: str = Field(default="tutor")
    difficulty: str | None = None
    session_id: int | None = None
    conversation_id: int | None = None
    question_id: int | None = None
    trace_id: str | None = None
    duration_minutes: int = Field(default=2, ge=0, le=1440)
    concept: str | None = None
    error_type: str | None = None
    diagnosis_text: str | None = None
    verified: bool | None = None
    hint_usage: int = 0
    retry_count: int = 0
    # "student_mark" (default API Mark) | "tool_verifier" (agent auto-record)
    outcome_source: str | None = None
    problem_id: int | None = None


class LearningOutcomeResponse(BaseModel):
    attempt: LearningRecordResponse
    recommendation: Recommendation | None = None
    learning_trace: LearningTrace
    error_diagnosis: ErrorDiagnosis | None = None
    difficulty_decision: DifficultyDecision | None = None
    tutor_strategy: TutorStrategyDecision | None = None
    idempotent_replay: bool = False
    bank_verified: bool | None = None


class LearningLoopService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id
        self.memory = MemoryService(db, self.user_id)
        self.adaptive = AdaptiveTutor(db, self.user_id)
        self.errors = ErrorIntelligenceService(db, self.user_id)
        self.graph = MasteryGraphService(db, self.user_id)
        self.difficulty_policy = DifficultyPolicy()
        self.tutor_strategy_policy = TutorStrategyPolicy()

    def get_or_create_session(
        self,
        *,
        subject: str | None,
        topic: str | None,
        conversation_id: int | None = None,
        session_id: int | None = None,
    ) -> LearningSession:
        if session_id is not None:
            existing = self.db.get(LearningSession, session_id)
            if existing and existing.user_id == self.user_id:
                return existing
        active = (
            self.db.query(LearningSession)
            .filter(
                LearningSession.user_id == self.user_id,
                LearningSession.status.in_(("started", "active")),
            )
            .order_by(LearningSession.started_at.desc())
            .first()
        )
        if active and (
            (not subject or active.subject in {None, subject})
            and (not topic or active.topic in {None, topic})
        ):
            if subject and not active.subject:
                active.subject = subject
            if topic and not active.topic:
                active.topic = topic
            if conversation_id and not active.conversation_id:
                active.conversation_id = conversation_id
            self.db.flush()
            return active
        session = LearningSession(
            user_id=self.user_id,
            subject=subject,
            topic=topic,
            status="started",
            conversation_id=conversation_id,
        )
        self.db.add(session)
        self.db.flush()
        return session

    def bump_session(self, session: LearningSession, minutes: int = 2) -> None:
        if session.status == "started":
            session.status = "active"
        elif session.status == "ended":
            # Re-open only when explicitly reused by session_id.
            session.status = "active"
        session.activity_count += 1
        session.duration_minutes += max(0, minutes)
        session.ended_at = None
        self.db.flush()

    def end_session(self, session_id: int) -> LearningSession | None:
        session = self.db.get(LearningSession, session_id)
        if session is None or session.user_id != self.user_id:
            return None
        session.status = "ended"
        session.ended_at = utcnow()
        self.db.commit()
        self.db.refresh(session)
        return session

    def snapshot_mastery(self, subject: str | None, topic: str | None) -> dict[str, Any]:
        if not subject or not topic:
            return {}
        row = (
            self.db.query(TopicMastery)
            .filter(
                TopicMastery.user_id == self.user_id,
                TopicMastery.subject == subject,
                TopicMastery.topic == topic,
            )
            .first()
        )
        if not row:
            return {
                "subject": subject,
                "topic": topic,
                "mastery": 0.0,
                "confidence": 0.0,
                "attempts": 0,
                "correct_attempts": 0,
                "consecutive_errors": 0,
                "recommended_difficulty": "current",
                "difficulty_level": 3,
                "last_mistake_pattern": None,
                "days_since_practice": None,
                "spaced_review_due": False,
            }
        days = None
        spaced = False
        if row.last_practiced_at:
            days = (utcnow() - row.last_practiced_at).total_seconds() / 86400.0
        if row.next_review_at and row.next_review_at <= utcnow():
            spaced = True
        return {
            "subject": row.subject,
            "topic": row.topic,
            "mastery": row.mastery_estimate,
            "confidence": row.confidence,
            "attempts": row.attempts,
            "correct_attempts": row.correct_attempts,
            "consecutive_errors": row.consecutive_errors,
            "recommended_difficulty": row.recommended_difficulty,
            "difficulty_level": row.difficulty_level or label_to_level(row.recommended_difficulty),
            "last_mistake_pattern": row.last_mistake_pattern,
            "days_since_practice": days,
            "spaced_review_due": spaced,
            "review_count": row.review_count,
        }

    def adapt_teaching_mode(
        self,
        requested: TeachingMode,
        *,
        subject: str | None,
        topic: str | None,
    ) -> tuple[TeachingMode, str]:
        state = self.snapshot_mastery(subject, topic)
        if not state:
            return requested, "No topic mastery yet; keep requested mode."
        decision = self.tutor_strategy_policy.decide(
            requested_mode=requested,
            mastery=float(state.get("mastery") or 0),
            consecutive_errors=int(state.get("consecutive_errors") or 0),
            spaced_review_due=bool(state.get("spaced_review_due")),
            attempts=int(state.get("attempts") or 0),
            recent_accuracy=_recent_accuracy(state),
        )
        return decision.teaching_mode, decision.reason

    def record_outcome(self, payload: LearningOutcomeRequest) -> LearningOutcomeResponse:
        session = self.get_or_create_session(
            subject=payload.subject,
            topic=payload.topic,
            conversation_id=payload.conversation_id,
            session_id=payload.session_id,
        )
        before = self.snapshot_mastery(payload.subject, payload.topic)
        bank_verified = self._apply_bank_verification(payload)
        if payload.correct is None:
            raise ValueError(
                "Provide an answer to verify, or mark the attempt correct/incorrect."
            )
        if bank_verified:
            outcome_decision = decide_from_bank_answer(correct=payload.correct)
        elif payload.outcome_source == "tool_verifier":
            outcome_decision = OutcomeDecision(
                status=(
                    LearningOutcomeStatus.VERIFIED
                    if payload.correct
                    else LearningOutcomeStatus.FAILED
                ),
                should_record_attempt=True,
                should_update_mastery=True,
                correct=payload.correct,
                evidence=[OutcomeEvidenceKind.TOOL_VERIFIER],
                reason=(
                    "Trusted verifier evidence from agent run; "
                    "recording attempt and updating mastery."
                ),
                student_message=(
                    "這次作答已通過可靠驗證，學習進度已更新。"
                    if payload.correct
                    else "這次作答未通過驗證，系統已記錄錯誤並調整下一步建議。"
                ),
            )
        else:
            outcome_decision = decide_from_student_mark(correct=payload.correct)

        diagnosis = self.errors.classify(
            correct=payload.correct,
            subject=payload.subject,
            topic=payload.topic,
            mistake_pattern=payload.mistake_pattern,
            detected_misconception=payload.detected_misconception,
            student_answer=payload.answer,
            expected_answer=payload.expected_answer,
            concept=payload.concept,
            question_id=payload.question_id,
            provided_error_type=payload.error_type,
            diagnosis_text=payload.diagnosis_text,
        )
        concept_name = diagnosis.related_concept or diagnosis.concept or payload.topic
        concept_before = self.graph.get_concept(
            payload.subject, payload.topic, concept_name
        )
        concept_mastery_before = (
            concept_before.mastery_estimate if concept_before else None
        )

        recent_accuracy = _recent_accuracy(before)
        consecutive_verified = self._consecutive_verified(
            payload.subject, payload.topic
        )
        difficulty_decision = self.difficulty_policy.decide(
            DifficultySignals(
                mastery=float(before.get("mastery") or 0),
                concept_mastery=concept_mastery_before,
                recent_accuracy=recent_accuracy,
                consecutive_errors=int(before.get("consecutive_errors") or 0)
                + (0 if payload.correct else 1),
                repeated_failures=diagnosis.pattern_count if not payload.correct else 0,
                hint_usage=payload.hint_usage,
                retry_count=payload.retry_count,
                last_verified=payload.verified if payload.verified is not None else payload.correct,
                consecutive_verified=consecutive_verified + (1 if payload.correct else 0),
                current_difficulty=int(before.get("difficulty_level") or 3),
                days_since_practice=before.get("days_since_practice"),
                learning_trend=_learning_trend(before, payload.correct),
                spaced_review_due=bool(before.get("spaced_review_due")),
            )
        )

        strategy = self.tutor_strategy_policy.decide(
            requested_mode=_safe_mode(payload.mode),
            mastery=float(before.get("mastery") or 0),
            concept_mastery=concept_mastery_before,
            consecutive_errors=int(before.get("consecutive_errors") or 0)
            + (0 if payload.correct else 1),
            repeated_error_count=diagnosis.pattern_count,
            error_diagnosis=diagnosis,
            difficulty_decision=difficulty_decision,
            spaced_review_due=bool(before.get("spaced_review_due")),
            recent_accuracy=recent_accuracy,
            attempts=int(before.get("attempts") or 0) + 1,
        )

        attempt = self.memory.record(
            LearningRecordRequest(
                subject=payload.subject,
                topic=payload.topic,
                correct=payload.correct,
                mistake_pattern=payload.mistake_pattern,
                detected_misconception=diagnosis.diagnosis
                if not payload.correct
                else payload.detected_misconception,
                answer=payload.answer,
                ai_explanation=payload.ai_explanation,
                mode=strategy.teaching_mode.value,
                difficulty=difficulty_decision.recommended_label,
                difficulty_level=difficulty_decision.recommended_difficulty,
                question_id=payload.question_id,
                problem_id=payload.problem_id,
                trace_id=payload.trace_id,
                conversation_id=payload.conversation_id,
                session_id=session.id,
                duration_minutes=payload.duration_minutes,
                error_type=diagnosis.error_type.value,
                related_concept=concept_name,
                expected_answer=payload.expected_answer,
                diagnosis_json=diagnosis.model_dump(mode="json"),
                verified=payload.verified if payload.verified is not None else payload.correct,
            )
        )

        if not attempt.idempotent_replay:
            if payload.correct:
                self.errors.mark_resolved_on_success(
                    subject=payload.subject,
                    topic=payload.topic,
                    concept=concept_name,
                )
            else:
                self.errors.upsert_repeated_pattern(diagnosis)
            self.graph.update_concept(
                subject=payload.subject,
                topic=payload.topic,
                concept=concept_name,
                correct=payload.correct,
            )
            # Ensure prerequisite concepts exist for graph scenarios when explicitly related.
            if not payload.correct and concept_name == "root_coefficient_relationship":
                # Seed equation_transformation lightly as related prereq observation.
                pass
            self.bump_session(session, payload.duration_minutes)
            self.db.commit()

        after = self.snapshot_mastery(payload.subject, payload.topic)
        graph = self.graph.snapshot(
            subject=payload.subject,
            topic=payload.topic,
            topic_mastery=float(after.get("mastery") or 0),
        )
        if attempt.idempotent_replay:
            recommendation = self._latest_recommendation(
                payload.subject, payload.topic
            )
        else:
            recommendation = self.adaptive.recommend_for_topic(
                payload.subject,
                payload.topic,
                session_id=session.id,
                strategy=strategy,
                difficulty_decision=difficulty_decision,
                error_diagnosis=diagnosis,
                mastery_graph=graph,
                force_review=bool(before.get("spaced_review_due")) and payload.correct,
            )

        weakness = None
        weakness_obj = None
        if graph.bottleneck_concept:
            weakness = graph.bottleneck_reason
            weakness_obj = {
                "type": "prerequisite_or_concept",
                "concept": graph.bottleneck_concept,
                "reason": graph.bottleneck_reason,
            }
        elif after.get("consecutive_errors", 0) >= 2:
            weakness = (
                f"{payload.subject}/{payload.topic}: "
                f"{after['consecutive_errors']} consecutive errors"
                + (
                    f" ({diagnosis.error_type.value})"
                    if diagnosis.error_type != ErrorType.NONE
                    else ""
                )
            )
            weakness_obj = {
                "type": "consecutive_errors",
                "count": after["consecutive_errors"],
                "error_type": diagnosis.error_type.value,
            }

        mastery_before = {
            "topic": before.get("mastery"),
            "confidence": before.get("confidence"),
            "concept": concept_mastery_before,
            "difficulty_level": before.get("difficulty_level"),
        }
        concept_after_row = self.graph.get_concept(
            payload.subject, payload.topic, concept_name
        )
        mastery_after = {
            "topic": after.get("mastery"),
            "confidence": after.get("confidence"),
            "concept": concept_after_row.mastery_estimate if concept_after_row else None,
            "difficulty_level": after.get("difficulty_level"),
        }
        mastery_delta = {
            "topic": round(
                float(mastery_after["topic"] or 0) - float(mastery_before["topic"] or 0), 4
            ),
            "concept": (
                round(
                    float(mastery_after["concept"] or 0)
                    - float(mastery_before["concept"] or 0),
                    4,
                )
                if mastery_after["concept"] is not None
                else None
            ),
            "difficulty_level": int(mastery_after["difficulty_level"] or 3)
            - int(mastery_before["difficulty_level"] or 3),
        }

        learning_trace = LearningTrace(
            session_id=session.id,
            trace_id=payload.trace_id,
            student_state=before,
            detected_weakness=weakness,
            weakness=weakness_obj,
            error_diagnosis=diagnosis.model_dump(mode="json"),
            tutor_decision=strategy.model_dump(mode="json"),
            difficulty_decision=difficulty_decision.model_dump(mode="json"),
            agent_decision={
                "mode": strategy.teaching_mode.value,
                "strategy": strategy.strategy.value,
                "difficulty_before": before.get("recommended_difficulty"),
                "difficulty_after": after.get("recommended_difficulty"),
            },
            selected_tools=[],
            tools=[],
            verification=(
                "VERIFIED"
                if payload.verified
                else ("FAILED" if payload.correct is False else None)
            ),
            outcome_status=outcome_decision.status.value,
            outcome_reason=outcome_decision.reason,
            outcome_evidence=[item.value for item in outcome_decision.evidence],
            outcome_student_message=outcome_decision.student_message,
            mastery_updated=not attempt.idempotent_replay,
            attempt={
                "attempt_id": attempt.attempt_id,
                "correct": payload.correct,
                "idempotent_replay": attempt.idempotent_replay,
            },
            learning_result={
                "attempt_id": attempt.attempt_id,
                "correct": payload.correct,
                "mistake_pattern": payload.mistake_pattern,
                "misconception": attempt.misconception,
                "error_type": diagnosis.error_type.value,
                "concept": concept_name,
                "idempotent_replay": attempt.idempotent_replay,
            },
            mastery_before=mastery_before,
            mastery_after=mastery_after,
            mastery_update={
                "before": before.get("mastery"),
                "after": after.get("mastery"),
                "confidence_before": before.get("confidence"),
                "confidence_after": after.get("confidence"),
                "consecutive_errors": after.get("consecutive_errors"),
                "recommended_difficulty": after.get("recommended_difficulty"),
                "difficulty_level": after.get("difficulty_level"),
                "concept": concept_name,
                "concept_mastery_before": concept_mastery_before,
                "concept_mastery_after": mastery_after.get("concept"),
                "graph": graph.model_dump(mode="json"),
            },
            mastery_delta=mastery_delta,
            next_recommendation=recommendation,
            recommendation=recommendation,
        )
        return LearningOutcomeResponse(
            attempt=attempt,
            recommendation=recommendation,
            learning_trace=learning_trace,
            error_diagnosis=diagnosis,
            difficulty_decision=difficulty_decision,
            tutor_strategy=strategy,
            idempotent_replay=attempt.idempotent_replay,
            bank_verified=True if bank_verified else None,
        )

    def _apply_bank_verification(self, payload: LearningOutcomeRequest) -> bool:
        if not payload.problem_id:
            return False
        problem = ProblemRepository(self.db).get(payload.problem_id)
        if problem is None:
            return False
        if not payload.concept and problem.concept:
            payload.concept = problem.concept
        if not payload.expected_answer and problem.answer:
            payload.expected_answer = problem.answer
        matched = answers_match(payload.answer, problem.answer)
        if matched is None:
            return False
        payload.correct = matched
        payload.verified = True
        if matched:
            payload.error_type = None
            payload.mistake_pattern = None
        else:
            if not payload.mistake_pattern or payload.mistake_pattern in {
                "practice_incorrect",
                "student_marked_incorrect",
            }:
                payload.mistake_pattern = "answer_mismatch"
            if payload.error_type == "MISCONCEPTION":
                payload.error_type = None
        return True

    def build_agent_trace(
        self,
        *,
        session_id: int,
        trace_id: str,
        student_state: dict[str, Any],
        detected_weakness: str | None,
        agent_decision: dict[str, Any],
        selected_tools: list[str],
        verification: str | None,
        learning_result: dict[str, Any] | None = None,
        mastery_update: dict[str, Any] | None = None,
        recommendation: Recommendation | None = None,
        error_diagnosis: dict[str, Any] | None = None,
        tutor_decision: dict[str, Any] | None = None,
        difficulty_decision: dict[str, Any] | None = None,
        mastery_before: dict[str, Any] | None = None,
        mastery_after: dict[str, Any] | None = None,
        mastery_delta: dict[str, Any] | None = None,
        weakness: dict[str, Any] | None = None,
        attempt: dict[str, Any] | None = None,
        outcome_status: str | None = None,
        outcome_reason: str | None = None,
        outcome_evidence: list[str] | None = None,
        outcome_student_message: str | None = None,
        mastery_updated: bool = False,
    ) -> LearningTrace:
        return LearningTrace(
            session_id=session_id,
            trace_id=trace_id,
            student_state=student_state,
            detected_weakness=detected_weakness,
            weakness=weakness,
            error_diagnosis=error_diagnosis,
            tutor_decision=tutor_decision or agent_decision,
            difficulty_decision=difficulty_decision,
            agent_decision=agent_decision,
            selected_tools=selected_tools,
            tools=selected_tools,
            verification=verification,
            outcome_status=outcome_status,
            outcome_reason=outcome_reason,
            outcome_evidence=outcome_evidence or [],
            outcome_student_message=outcome_student_message,
            mastery_updated=mastery_updated,
            attempt=attempt,
            learning_result=learning_result or {},
            mastery_before=mastery_before,
            mastery_after=mastery_after,
            mastery_update=mastery_update,
            mastery_delta=mastery_delta,
            next_recommendation=recommendation,
            recommendation=recommendation,
        )

    def _latest_recommendation(
        self, subject: str, topic: str
    ) -> Recommendation | None:
        row = (
            self.db.query(RecommendationRecord)
            .filter(
                RecommendationRecord.user_id == self.user_id,
                RecommendationRecord.subject == subject,
                RecommendationRecord.topic == topic,
            )
            .order_by(RecommendationRecord.id.desc())
            .first()
        )
        if row is None:
            return None
        evidence = {}
        try:
            evidence = json.loads(row.evidence_json or "{}")
        except json.JSONDecodeError:
            evidence = {}
        return Recommendation(
            subject=row.subject,
            topic=row.topic,
            reason=row.reason,
            action=row.action,
            priority=1,
            concept=row.concept,
            strategy=row.strategy,
            difficulty=row.difficulty_level,
            why=row.reason,
            evidence=evidence if isinstance(evidence, dict) else {},
            recommended_difficulty=(
                evidence.get("recommended_difficulty", "current")
                if isinstance(evidence, dict)
                else "current"
            ),
        )

    def _consecutive_verified(self, subject: str, topic: str) -> int:
        rows = (
            self.db.query(Attempt)
            .filter(
                Attempt.user_id == self.user_id,
                Attempt.subject == subject,
                Attempt.topic == topic,
            )
            .order_by(Attempt.id.desc())
            .limit(5)
            .all()
        )
        count = 0
        for row in rows:
            if row.is_correct:
                count += 1
            else:
                break
        return count

    def _pattern_count(self, subject: str, topic: str, pattern: str) -> int:
        return (
            self.db.query(func.count(Attempt.id))
            .filter(
                Attempt.user_id == self.user_id,
                Attempt.subject == subject,
                Attempt.topic == topic,
                Attempt.is_correct.is_(False),
                Attempt.mistake_pattern == pattern,
            )
            .scalar()
            or 0
        )


def _safe_mode(mode: str | None) -> TeachingMode:
    try:
        return TeachingMode(mode or "tutor")
    except ValueError:
        return TeachingMode.TUTOR


def _recent_accuracy(state: dict[str, Any]) -> float:
    attempts = int(state.get("attempts") or 0)
    correct = int(state.get("correct_attempts") or 0)
    if attempts <= 0:
        return 0.0
    return correct / attempts


def _learning_trend(state: dict[str, Any], latest_correct: bool) -> str:
    consecutive = int(state.get("consecutive_errors") or 0)
    if latest_correct and consecutive == 0:
        return "improving"
    if not latest_correct and consecutive >= 1:
        return "declining"
    return "stable"
