"""Adaptive Question Engine — deterministic next-problem selection.

Uses Student Learning State, Error DNA, and existing DifficultyPolicy.
LLM never selects difficulty or the next problem.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.difficulty_policy import (
    DifficultyPolicy,
    DifficultySignals,
    label_to_level,
)
from app.application.error_dna import ErrorDNAService
from app.application.problem_repository import ProblemOut, ProblemRepository
from app.application.student_learning_state import StudentLearningStateService
from app.config import settings
from app.models import Attempt, Problem, RecommendationRecord, TopicMastery


# Map DifficultyPolicy levels (1–5) to Problem.difficulty float targets (0–1).
LEVEL_TO_FLOAT = {
    1: 0.2,
    2: 0.35,
    3: 0.5,
    4: 0.65,
    5: 0.8,
}

# Learning-zone bands around each policy level. Not a second difficulty formula.
LEVEL_TO_BAND = {
    1: (0.10, 0.30),
    2: (0.25, 0.45),
    3: (0.40, 0.60),
    4: (0.55, 0.75),
    5: (0.70, 0.90),
}

RECENT_WINDOW = 8
REPETITION_HARD_EXCLUDE = 3
RECENT_CORRECT_EXCLUDE = 5


class SelectionReason(BaseModel):
    topic_match: bool = False
    concept_match: bool = False
    difficulty_match: bool = False
    error_pattern_match: bool = False
    recent_repetition_penalty: float = 0.0
    target_difficulty: float | None = None
    difficulty_level: int | None = None
    difficulty_policy_action: str | None = None
    difficulty_policy_reason: str | None = None
    student_reasons: list[str] = Field(default_factory=list)
    score: float | None = None
    recommendation_used: bool = False
    error_concept: str | None = None


class PracticeProblemOut(BaseModel):
    """Problem payload for practice UI — no answer/explanation leak."""

    id: int
    question: str
    subject: str
    topic: str
    concept: str | None = None
    difficulty: float
    gradable: bool = False


class NextProblemResponse(BaseModel):
    problem: PracticeProblemOut | None = None
    selection_reason: SelectionReason | None = None
    message: str | None = None


def answers_match(student: str | None, expected: str | None) -> bool | None:
    """Deterministic bank-answer check. None = not enough evidence to grade."""
    if student is None or expected is None:
        return None
    left = _normalize_answer(student)
    right = _normalize_answer(expected)
    if not left or not right:
        return None
    if left == right:
        return True
    try:
        return abs(float(left) - float(right)) < 1e-6
    except ValueError:
        return False


def _normalize_answer(raw: str) -> str:
    text = raw.strip().lower()
    text = text.replace("π", "pi")
    text = re.sub(r"[\s,，。、；;:：'\"“”‘’`]+", "", text)
    text = re.sub(r"[.!?]+$", "", text)
    return text


class AdaptiveQuestionEngine:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id
        self.state_service = StudentLearningStateService(db, self.user_id)
        self.error_dna = ErrorDNAService(db, self.user_id)
        self.problems = ProblemRepository(db)
        self.difficulty_policy = DifficultyPolicy()

    def select_next_problem(
        self,
        *,
        subject: str | None = None,
        topic: str | None = None,
        concept: str | None = None,
        session_id: int | None = None,
    ) -> NextProblemResponse:
        rec = self._active_recommendation(subject)
        state = self.state_service.get(subject=subject, topic=topic, concept=concept)

        resolved_subject = subject or (rec.subject if rec else None) or state.subject
        # Explicit query args win; otherwise recommendation drives topic/concept.
        resolved_topic = topic or (rec.topic if rec else None) or state.current_topic
        resolved_concept = (
            concept or (rec.concept if rec else None) or state.current_concept
        )

        # Common case: material supplies subject, state has concept but no topic yet.
        if resolved_subject and not resolved_topic:
            resolved_topic = self._infer_topic(
                resolved_subject, concept=resolved_concept
            )
        # Subject-scoped recommendation missed (e.g. active rec is another subject):
        # only fall back when the caller did not pin a subject.
        if (not resolved_subject or not resolved_topic) and not subject:
            fallback = self._active_recommendation(None)
            if fallback:
                resolved_subject = resolved_subject or fallback.subject
                resolved_topic = resolved_topic or fallback.topic
                if not resolved_concept:
                    resolved_concept = fallback.concept
                rec = fallback

        recommendation_used = bool(
            rec
            and (
                (topic is None and rec.topic == resolved_topic)
                or (concept is None and rec.concept and rec.concept == resolved_concept)
            )
        )

        if not resolved_subject or not resolved_topic:
            return NextProblemResponse(
                message="尚無科目／主題焦點，請從總覽的推薦進入練習，或先選擇有主題的教材。"
            )

        dna = self.error_dna.profile(
            subject=resolved_subject, topic=resolved_topic, recent_limit=8
        )
        if resolved_concept is None and dna.concept_distribution:
            resolved_concept = dna.concept_distribution[0].concept

        target_level, decision = self._target_difficulty_level(state)
        target_float = LEVEL_TO_FLOAT[target_level]
        band_low, band_high = LEVEL_TO_BAND[target_level]

        candidates = self._load_candidates(
            resolved_subject, resolved_topic, resolved_concept
        )
        if not candidates:
            return NextProblemResponse(
                message="這個科目／主題還沒有題庫題目，仍可直接在下方對話練習。"
            )

        recent = self._recent_problem_stats(
            resolved_subject, resolved_topic, session_id=session_id
        )
        error_concepts = self._error_concepts(dna)
        error_types = self._error_types(dna)

        filtered = self._filter_candidates(
            candidates,
            recent,
            resolved_concept,
            error_concepts,
            allow_same_item_repair=False,
        )
        if not filtered:
            filtered = self._filter_candidates(
                candidates,
                recent,
                resolved_concept,
                error_concepts,
                allow_same_item_repair=True,
            )
        if not filtered:
            return NextProblemResponse(
                message="No suitable candidate problems after filtering recent attempts."
            )

        scored: list[tuple[float, int, int, ProblemOut, SelectionReason]] = []
        for problem in filtered:
            reason, score = self._score_candidate(
                problem=problem,
                topic=resolved_topic,
                concept=resolved_concept,
                target_float=target_float,
                band_low=band_low,
                band_high=band_high,
                target_level=target_level,
                decision_action=decision.action,
                decision_reason=decision.reason,
                recent=recent,
                error_concepts=error_concepts,
                error_types=error_types,
                recommendation_used=recommendation_used,
            )
            priority = self._attempt_priority(problem, recent)
            scored.append((score, priority, problem.id, problem, reason))

        # Deterministic: highest score, then never-attempted, then lowest id.
        scored.sort(key=lambda item: (-item[0], item[1], item[2]))
        best_score, _, _, best, reason = scored[0]
        reason.score = round(best_score, 4)
        reason.student_reasons = self._student_reasons(reason)

        return NextProblemResponse(
            problem=PracticeProblemOut(
                id=best.id,
                question=best.question,
                subject=best.subject,
                topic=best.topic,
                concept=best.concept,
                difficulty=best.difficulty,
                gradable=bool(best.answer and str(best.answer).strip()),
            ),
            selection_reason=reason,
        )

    def _active_recommendation(self, subject: str | None) -> RecommendationRecord | None:
        query = self.db.query(RecommendationRecord).filter(
            RecommendationRecord.user_id == self.user_id,
            RecommendationRecord.status == "active",
        )
        if subject:
            query = query.filter(RecommendationRecord.subject == subject)
        return query.order_by(RecommendationRecord.id.desc()).first()

    def _infer_topic(self, subject: str, *, concept: str | None) -> str | None:
        """Best-effort topic when only subject (and maybe concept) is known."""
        if concept:
            from_problem = (
                self.db.query(Problem.topic)
                .filter(
                    Problem.subject == subject,
                    Problem.concept == concept,
                    Problem.topic.isnot(None),
                    Problem.topic != "",
                )
                .order_by(Problem.id.asc())
                .first()
            )
            if from_problem and from_problem[0]:
                return str(from_problem[0])
        weak = (
            self.db.query(TopicMastery)
            .filter(
                TopicMastery.user_id == self.user_id,
                TopicMastery.subject == subject,
                TopicMastery.topic.isnot(None),
                TopicMastery.topic != "",
            )
            .order_by(TopicMastery.mastery.asc(), TopicMastery.consecutive_errors.desc())
            .first()
        )
        if weak and weak.topic:
            return str(weak.topic)
        any_problem = (
            self.db.query(Problem.topic)
            .filter(
                Problem.subject == subject,
                Problem.topic.isnot(None),
                Problem.topic != "",
            )
            .order_by(Problem.id.asc())
            .first()
        )
        if any_problem and any_problem[0]:
            return str(any_problem[0])
        return None

    def _load_candidates(
        self, subject: str, topic: str, concept: str | None
    ) -> list[ProblemOut]:
        if concept:
            focused = self.problems.list(
                subject=subject, topic=topic, concept=concept, limit=200, offset=0
            )
            if focused:
                return focused
        topical = self.problems.list(
            subject=subject, topic=topic, limit=200, offset=0
        )
        if topical:
            return topical
        return self.problems.list(subject=subject, limit=200, offset=0)

    def _filter_candidates(
        self,
        candidates: list[ProblemOut],
        recent: dict[str, Any],
        concept: str | None,
        error_concepts: set[str],
        *,
        allow_same_item_repair: bool,
    ) -> list[ProblemOut]:
        session_ids: set[int] = recent["session_ids"]
        recent_correct = set(recent["recent_correct_ids"][:RECENT_CORRECT_EXCLUDE])
        hard_exclude = set(recent["recent_ids"][:REPETITION_HARD_EXCLUDE])
        same_concept_available = any(
            (concept and item.concept == concept) or (item.concept or "").lower() in error_concepts
            for item in candidates
            if item.id not in session_ids
            and item.id not in recent_correct
            and item.id not in hard_exclude
        )

        kept: list[ProblemOut] = []
        for problem in candidates:
            if problem.id in session_ids:
                continue
            if problem.id in recent_correct:
                continue
            if problem.id in hard_exclude:
                if not allow_same_item_repair:
                    continue
                if same_concept_available:
                    continue
                if not self._allows_repair_repeat(
                    problem, recent, concept, error_concepts
                ):
                    continue
            kept.append(problem)
        return kept

    def _target_difficulty_level(self, state) -> tuple[int, Any]:
        mastery = float(state.mastery if state.mastery is not None else 0.0)
        recent_accuracy = float(
            (state.recent_performance or {}).get("recent_accuracy") or 0.0
        )
        consecutive_errors = int(
            (state.recent_performance or {}).get("consecutive_errors") or 0
        )
        current = int(state.difficulty_level or label_to_level(state.current_difficulty))
        repeated = len(
            [
                p
                for p in state.repeated_error_patterns
                if isinstance(p, dict) and not p.get("resolved")
            ]
        )
        decision = self.difficulty_policy.decide(
            DifficultySignals(
                mastery=mastery,
                recent_accuracy=recent_accuracy,
                consecutive_errors=consecutive_errors,
                repeated_failures=repeated,
                current_difficulty=current,
                learning_trend=(
                    "declining"
                    if consecutive_errors >= 2
                    else ("improving" if recent_accuracy >= 0.7 else "stable")
                ),
            )
        )
        return decision.recommended_difficulty, decision

    def _recent_problem_stats(
        self,
        subject: str,
        topic: str,
        session_id: int | None = None,
    ) -> dict[str, Any]:
        rows = (
            self.db.query(Attempt)
            .filter(
                Attempt.user_id == self.user_id,
                Attempt.subject == subject,
                Attempt.topic == topic,
                Attempt.problem_id.isnot(None),
            )
            .order_by(Attempt.id.desc())
            .limit(30)
            .all()
        )
        recent_ids: list[int] = []
        recent_correct_ids: list[int] = []
        failed_ids: set[int] = set()
        correct_ids: set[int] = set()
        session_ids: set[int] = set()
        for row in rows:
            if row.problem_id is None:
                continue
            if row.problem_id not in recent_ids:
                recent_ids.append(row.problem_id)
            if row.is_correct is False:
                failed_ids.add(row.problem_id)
            if row.is_correct is True:
                correct_ids.add(row.problem_id)
                if row.problem_id not in recent_correct_ids:
                    recent_correct_ids.append(row.problem_id)
            if session_id is not None and row.session_id == session_id:
                session_ids.add(row.problem_id)
        if session_id is not None:
            extra = (
                self.db.query(Attempt.problem_id)
                .filter(
                    Attempt.user_id == self.user_id,
                    Attempt.session_id == session_id,
                    Attempt.problem_id.isnot(None),
                )
                .all()
            )
            for (pid,) in extra:
                if pid is not None:
                    session_ids.add(pid)
        return {
            "recent_ids": recent_ids,
            "recent_correct_ids": recent_correct_ids,
            "failed_ids": failed_ids,
            "correct_ids": correct_ids,
            "session_ids": session_ids,
        }

    def _allows_repair_repeat(
        self,
        problem: ProblemOut,
        recent: dict[str, Any],
        concept: str | None,
        error_concepts: set[str],
    ) -> bool:
        if problem.id not in recent["failed_ids"]:
            return False
        if problem.id in recent["correct_ids"]:
            return False
        if concept and problem.concept == concept:
            return True
        if problem.concept and problem.concept.lower() in error_concepts:
            return True
        return False

    def _attempt_priority(self, problem: ProblemOut, recent: dict[str, Any]) -> int:
        if problem.id not in recent["recent_ids"]:
            return 0
        if (
            problem.id in recent["failed_ids"]
            and problem.id not in recent["recent_ids"][:REPETITION_HARD_EXCLUDE]
        ):
            return 1
        if problem.id in recent["correct_ids"]:
            return 2
        return 3

    def _score_candidate(
        self,
        *,
        problem: ProblemOut,
        topic: str,
        concept: str | None,
        target_float: float,
        band_low: float,
        band_high: float,
        target_level: int,
        decision_action: str,
        decision_reason: str,
        recent: dict[str, Any],
        error_concepts: set[str],
        error_types: set[str],
        recommendation_used: bool,
    ) -> tuple[SelectionReason, float]:
        topic_match = problem.topic == topic
        concept_match = bool(concept) and problem.concept == concept
        difficulty = float(problem.difficulty)
        diff_delta = abs(difficulty - target_float)
        difficulty_match = band_low <= difficulty <= band_high

        meta_targets = self._problem_error_targets(problem)
        problem_concept = (problem.concept or "").lower()
        error_pattern_match = bool(
            (problem_concept and problem_concept in error_concepts)
            or (meta_targets & error_concepts)
            or (meta_targets & error_types)
        )
        error_concept = None
        if error_pattern_match:
            if problem.concept and problem.concept.lower() in error_concepts:
                error_concept = problem.concept
            elif concept and concept.lower() in error_concepts:
                error_concept = concept

        repetition_penalty = 0.0
        if problem.id in recent["recent_ids"][:RECENT_WINDOW]:
            idx = recent["recent_ids"].index(problem.id)
            repetition_penalty = round(1.0 - (idx * 0.08), 4)
            repetition_penalty = max(0.15, min(1.0, repetition_penalty))
        if problem.id in recent["correct_ids"] and problem.id in recent["recent_ids"][:5]:
            repetition_penalty = max(repetition_penalty, 0.85)

        score = 0.0
        if topic_match:
            score += 40.0
        else:
            score -= 20.0
        if concept_match:
            score += 30.0
        elif concept and problem.concept:
            score -= 5.0
        score += max(0.0, 25.0 * (1.0 - min(1.0, diff_delta / 0.5)))
        if difficulty_match:
            score += 5.0
        if error_pattern_match:
            score += 20.0
        score -= repetition_penalty * 35.0

        reason = SelectionReason(
            topic_match=topic_match,
            concept_match=concept_match,
            difficulty_match=difficulty_match,
            error_pattern_match=error_pattern_match,
            recent_repetition_penalty=repetition_penalty,
            target_difficulty=target_float,
            difficulty_level=target_level,
            difficulty_policy_action=decision_action,
            difficulty_policy_reason=decision_reason,
            recommendation_used=recommendation_used,
            error_concept=error_concept,
        )
        return reason, score

    def _problem_error_targets(self, problem: ProblemOut) -> set[str]:
        tokens: set[str] = set()
        meta = problem.metadata or {}
        raw = meta.get("error_targets") or meta.get("skills") or []
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, list):
            for item in raw:
                if item:
                    tokens.add(str(item).lower())
        return tokens

    def _error_concepts(self, dna) -> set[str]:
        tokens: set[str] = set()
        for item in dna.repeated_errors + dna.recent_errors:
            if isinstance(item, dict) and item.get("concept"):
                tokens.add(str(item["concept"]).lower())
        for dist in dna.concept_distribution:
            tokens.add(dist.concept.lower())
        return tokens

    def _error_types(self, dna) -> set[str]:
        tokens: set[str] = set()
        for item in dna.repeated_errors + dna.recent_errors:
            if isinstance(item, dict) and item.get("error_type"):
                tokens.add(str(item["error_type"]).lower())
        for row in dna.most_frequent_error_types:
            tokens.add(row.error_type.lower())
        return tokens

    def _student_reasons(self, reason: SelectionReason) -> list[str]:
        lines: list[str] = []
        if reason.error_pattern_match:
            if reason.error_concept:
                lines.append(f"近期弱點：{reason.error_concept}")
            else:
                lines.append("針對近期錯誤")
        elif reason.concept_match:
            lines.append("對應目前概念")
        if reason.difficulty_match:
            lines.append("難度合適")
        return lines[:2]
