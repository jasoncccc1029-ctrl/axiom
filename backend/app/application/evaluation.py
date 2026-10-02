"""AXIOM v1.3 Learning Efficacy Pilot — evaluation protocol and observed metrics.

IMPORTANT
---------
All metrics describe *observed* change. They must never be phrased as proof that
AXIOM *caused* improvement unless a controlled comparison is present.

Evaluation attempts are stored only in evaluation_* tables and must never call
MemoryService / LearningLoopService.record_outcome (no accidental mastery writes).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.learning_loop import LearningLoopService
from app.config import settings
from app.models import (
    Attempt,
    ConceptMastery,
    EvaluationAttempt,
    EvaluationSession,
    RecommendationRecord,
    RepeatedErrorPattern,
    TopicMastery,
    utcnow,
)

WEAK_MASTERY_THRESHOLD = 0.6
CAVEAT = (
    "這些指標描述觀察到的變化（observed improvement），"
    "不能自動推論為 AXIOM 造成的因果改善（causal improvement）。"
    "若要主張因果，需要 control group / randomized experiment。"
)


class StartEvaluationRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=120)
    topic: str = Field(..., min_length=1, max_length=160)
    group_arm: Literal["axiom", "control"] = "axiom"
    notes: str | None = None


class EvaluationItemInput(BaseModel):
    item_id: str | None = None
    concept: str | None = None
    prompt: str | None = None
    student_answer: str | None = None
    is_correct: bool | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class EvaluationSessionOut(BaseModel):
    evaluation_id: str
    subject: str
    topic: str
    group_arm: str
    status: str
    learning_session_id: int | None = None
    pre_test_score: float | None = None
    post_test_score: float | None = None
    delayed_test_score: float | None = None
    started_at: str | None = None
    learning_started_at: str | None = None
    ended_at: str | None = None
    notes: str | None = None


class ErrorRecoveryMetrics(BaseModel):
    improved: bool | None = None
    early_error_rate: float | None = None
    late_error_rate: float | None = None
    patterns_resolved: int = 0
    patterns_open: int = 0
    summary: str


class DifficultyProgressionMetrics(BaseModel):
    start_level: int | None = None
    end_level: int | None = None
    max_level_reached: int | None = None
    progression: str | None = None
    summary: str


class RecommendationEffectivenessMetrics(BaseModel):
    recommendations_count: int = 0
    accuracy_after_recommendation: float | None = None
    summary: str


class EvaluationMetrics(BaseModel):
    evaluation_id: str
    group_arm: str
    complete: bool
    missing_phases: list[str] = Field(default_factory=list)
    pre_test_score: float | None = None
    post_test_score: float | None = None
    delayed_test_score: float | None = None
    learning_gain: float | None = None
    retention_delta: float | None = None
    mastery_before: float | None = None
    mastery_after: float | None = None
    mastery_change: float | None = None
    weak_concepts_before: list[dict[str, Any]] = Field(default_factory=list)
    weak_concepts_after: list[dict[str, Any]] = Field(default_factory=list)
    concepts_recovered: list[str] = Field(default_factory=list)
    concept_recovery_rate: float | None = None
    error_recovery: ErrorRecoveryMetrics | None = None
    difficulty_progression: DifficultyProgressionMetrics | None = None
    recommendation_effectiveness: RecommendationEffectivenessMetrics | None = None
    causal_claim_allowed: bool = False
    interpretation_caveat: str = CAVEAT


class LearningReport(BaseModel):
    evaluation_id: str
    subject: str
    topic: str
    group_arm: str
    initial_state: str
    weak_concepts: list[str] = Field(default_factory=list)
    learning_interventions: list[str] = Field(default_factory=list)
    mastery_changes: str
    post_test: str | None = None
    learning_gain: float | None = None
    concept_recovery: str
    remaining_weaknesses: list[str] = Field(default_factory=list)
    disclaimer: str = CAVEAT
    evidence_refs: list[str] = Field(default_factory=list)


class EvaluationService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id

    def start(self, payload: StartEvaluationRequest) -> EvaluationSessionOut:
        evaluation_id = uuid.uuid4().hex
        row = EvaluationSession(
            evaluation_id=evaluation_id,
            user_id=self.user_id,
            subject=payload.subject,
            topic=payload.topic,
            group_arm=payload.group_arm,
            status="started",
            notes=payload.notes,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._session_out(row)

    def get(self, evaluation_id: str) -> EvaluationSessionOut | None:
        row = self._get(evaluation_id)
        return self._session_out(row) if row else None

    def record_pretest(
        self,
        evaluation_id: str,
        *,
        items: list[EvaluationItemInput] | None = None,
        score: float | None = None,
    ) -> EvaluationSessionOut:
        row = self._require(evaluation_id)
        computed = self._score_phase(row, "pretest", items=items, score=score)
        row.pre_test_score = computed
        row.status = "pretest_done"
        row.mastery_before_json = json.dumps(
            self._snapshot_mastery(row.subject, row.topic), ensure_ascii=False
        )
        weak = self._weak_concepts(row.subject, row.topic)
        row.weak_concepts_before_json = json.dumps(weak, ensure_ascii=False)
        self.db.commit()
        self.db.refresh(row)
        return self._session_out(row)

    def begin_learning(self, evaluation_id: str) -> EvaluationSessionOut:
        row = self._require(evaluation_id)
        if row.pre_test_score is None:
            raise ValueError("Pre-test must be recorded before learning begins.")
        if row.learning_session_id is None:
            loop = LearningLoopService(self.db, self.user_id)
            session = loop.get_or_create_session(
                subject=row.subject, topic=row.topic
            )
            loop.bump_session(session, 0)
            row.learning_session_id = session.id
        row.learning_started_at = utcnow()
        row.status = "learning"
        self.db.commit()
        self.db.refresh(row)
        return self._session_out(row)

    def record_posttest(
        self,
        evaluation_id: str,
        *,
        items: list[EvaluationItemInput] | None = None,
        score: float | None = None,
    ) -> EvaluationSessionOut:
        row = self._require(evaluation_id)
        if row.pre_test_score is None:
            raise ValueError("Pre-test must be recorded before post-test.")
        computed = self._score_phase(row, "posttest", items=items, score=score)
        row.post_test_score = computed
        row.mastery_after_json = json.dumps(
            self._snapshot_mastery(row.subject, row.topic), ensure_ascii=False
        )
        weak = self._weak_concepts(row.subject, row.topic)
        row.weak_concepts_after_json = json.dumps(weak, ensure_ascii=False)
        row.status = "completed"
        row.ended_at = utcnow()
        metrics = self.compute_metrics(evaluation_id, persist=False)
        row.metrics_json = json.dumps(metrics.model_dump(mode="json"), ensure_ascii=False)
        report = self.build_report(evaluation_id, persist=False)
        row.report_json = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
        self.db.commit()
        self.db.refresh(row)
        return self._session_out(row)

    def record_delayed_test(
        self,
        evaluation_id: str,
        *,
        items: list[EvaluationItemInput] | None = None,
        score: float | None = None,
    ) -> EvaluationSessionOut:
        row = self._require(evaluation_id)
        if row.post_test_score is None:
            raise ValueError("Post-test must be recorded before delayed test.")
        computed = self._score_phase(row, "delayed", items=items, score=score)
        row.delayed_test_score = computed
        metrics = self.compute_metrics(evaluation_id, persist=False)
        row.metrics_json = json.dumps(metrics.model_dump(mode="json"), ensure_ascii=False)
        self.db.commit()
        self.db.refresh(row)
        return self._session_out(row)

    def compute_metrics(
        self, evaluation_id: str, *, persist: bool = True
    ) -> EvaluationMetrics:
        row = self._require(evaluation_id)
        missing: list[str] = []
        if row.pre_test_score is None:
            missing.append("pretest")
        if row.post_test_score is None:
            missing.append("posttest")

        mastery_before = _load_json(row.mastery_before_json, {})
        mastery_after = _load_json(row.mastery_after_json, {})
        weak_before = _load_json(row.weak_concepts_before_json, [])
        weak_after = _load_json(row.weak_concepts_after_json, [])

        m_before = mastery_before.get("topic_mastery")
        m_after = mastery_after.get("topic_mastery")
        mastery_change = None
        if isinstance(m_before, (int, float)) and isinstance(m_after, (int, float)):
            mastery_change = round(float(m_after) - float(m_before), 4)

        recovered: list[str] = []
        if isinstance(weak_before, list):
            after_map = {
                item.get("concept"): item
                for item in weak_after
                if isinstance(item, dict)
            } if isinstance(weak_after, list) else {}
            # Also consider current concept mastery for recovery check
            current_concepts = {
                c["concept"]: c
                for c in mastery_after.get("concepts", [])
                if isinstance(c, dict) and c.get("concept")
            }
            for item in weak_before:
                if not isinstance(item, dict):
                    continue
                name = item.get("concept")
                if not name:
                    continue
                after = current_concepts.get(name) or after_map.get(name)
                if after and float(after.get("mastery", 0)) >= WEAK_MASTERY_THRESHOLD:
                    if float(after.get("mastery", 0)) > float(item.get("mastery", 0)):
                        recovered.append(str(name))

        recovery_rate = None
        if isinstance(weak_before, list) and weak_before:
            recovery_rate = round(len(recovered) / len(weak_before), 4)

        learning_gain = None
        if row.pre_test_score is not None and row.post_test_score is not None:
            learning_gain = round(row.post_test_score - row.pre_test_score, 4)

        retention_delta = None
        if row.post_test_score is not None and row.delayed_test_score is not None:
            retention_delta = round(row.delayed_test_score - row.post_test_score, 4)

        metrics = EvaluationMetrics(
            evaluation_id=row.evaluation_id,
            group_arm=row.group_arm,
            complete=not missing,
            missing_phases=missing,
            pre_test_score=row.pre_test_score,
            post_test_score=row.post_test_score,
            delayed_test_score=row.delayed_test_score,
            learning_gain=learning_gain,
            retention_delta=retention_delta,
            mastery_before=float(m_before) if isinstance(m_before, (int, float)) else None,
            mastery_after=float(m_after) if isinstance(m_after, (int, float)) else None,
            mastery_change=mastery_change,
            weak_concepts_before=list(weak_before) if isinstance(weak_before, list) else [],
            weak_concepts_after=list(weak_after) if isinstance(weak_after, list) else [],
            concepts_recovered=recovered,
            concept_recovery_rate=recovery_rate,
            error_recovery=self._error_recovery(row),
            difficulty_progression=self._difficulty_progression(row),
            recommendation_effectiveness=self._recommendation_effectiveness(row),
            causal_claim_allowed=False,
            interpretation_caveat=CAVEAT,
        )
        if persist:
            row.metrics_json = json.dumps(metrics.model_dump(mode="json"), ensure_ascii=False)
            self.db.commit()
        return metrics

    def build_report(
        self, evaluation_id: str, *, persist: bool = True
    ) -> LearningReport:
        row = self._require(evaluation_id)
        metrics = self.compute_metrics(evaluation_id, persist=False)
        mastery_before = _load_json(row.mastery_before_json, {})
        mastery_after = _load_json(row.mastery_after_json, {})

        initial = (
            f"{row.topic} mastery = {metrics.mastery_before:.2f}"
            if metrics.mastery_before is not None
            else f"{row.topic}: no prior TopicMastery snapshot (mastery unknown)."
        )
        weak_names = [
            str(item.get("concept"))
            for item in metrics.weak_concepts_before
            if isinstance(item, dict) and item.get("concept")
        ]
        interventions = self._intervention_lines(row)
        if metrics.mastery_before is not None and metrics.mastery_after is not None:
            mastery_changes = (
                f"{row.topic} mastery {metrics.mastery_before:.2f} → {metrics.mastery_after:.2f}"
                f" (Δ {metrics.mastery_change:+.2f})"
            )
        else:
            mastery_changes = "Insufficient mastery snapshots to report change."

        post_line = None
        if metrics.pre_test_score is not None and metrics.post_test_score is not None:
            post_line = (
                f"Pre-test {metrics.pre_test_score:.0%} → "
                f"Post-test {metrics.post_test_score:.0%}"
            )
            if metrics.learning_gain is not None:
                post_line += f" (learning gain {metrics.learning_gain:+.0%})"

        if metrics.concept_recovery_rate is None:
            recovery = "No weak concepts identified at pre-test; recovery rate not computed."
        else:
            recovery = (
                f"Recovered {len(metrics.concepts_recovered)}/"
                f"{len(metrics.weak_concepts_before)} weak concepts "
                f"({metrics.concept_recovery_rate:.0%})"
            )

        remaining = [
            str(item.get("concept"))
            for item in metrics.weak_concepts_after
            if isinstance(item, dict) and item.get("concept")
        ]
        # Prefer after-snapshot; if empty, weak that were not recovered
        if not remaining:
            remaining = [c for c in weak_names if c not in metrics.concepts_recovered]

        evidence = [
            f"evaluation_id={row.evaluation_id}",
            f"pre_test_score={row.pre_test_score}",
            f"post_test_score={row.post_test_score}",
        ]
        if row.learning_session_id:
            evidence.append(f"learning_session_id={row.learning_session_id}")
        if mastery_before:
            evidence.append("mastery_before_snapshot")
        if mastery_after:
            evidence.append("mastery_after_snapshot")

        report = LearningReport(
            evaluation_id=row.evaluation_id,
            subject=row.subject,
            topic=row.topic,
            group_arm=row.group_arm,
            initial_state=initial,
            weak_concepts=weak_names,
            learning_interventions=interventions,
            mastery_changes=mastery_changes,
            post_test=post_line,
            learning_gain=metrics.learning_gain,
            concept_recovery=recovery,
            remaining_weaknesses=remaining,
            disclaimer=CAVEAT,
            evidence_refs=evidence,
        )
        if persist:
            row.report_json = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
            self.db.commit()
        return report

    def _score_phase(
        self,
        row: EvaluationSession,
        phase: str,
        *,
        items: list[EvaluationItemInput] | None,
        score: float | None,
    ) -> float:
        if score is not None:
            if score < 0.0 or score > 1.0:
                raise ValueError("Score must be between 0 and 1 inclusive.")
            # Store a single aggregate attempt for auditability
            self.db.add(
                EvaluationAttempt(
                    evaluation_id=row.evaluation_id,
                    phase=phase,
                    item_id=f"{phase}-aggregate",
                    prompt="aggregate_score",
                    is_correct=score >= 0.5,
                    score=float(score),
                )
            )
            self.db.flush()
            return float(score)

        if not items:
            raise ValueError("Provide items or an explicit score.")

        total = 0.0
        for item in items:
            item_score = item.score
            if item_score is None:
                if item.is_correct is None:
                    raise ValueError("Each item needs is_correct or score.")
                item_score = 1.0 if item.is_correct else 0.0
            if item_score < 0.0 or item_score > 1.0:
                raise ValueError("Item score must be between 0 and 1 inclusive.")
            self.db.add(
                EvaluationAttempt(
                    evaluation_id=row.evaluation_id,
                    phase=phase,
                    item_id=item.item_id,
                    concept=item.concept,
                    prompt=item.prompt,
                    student_answer=item.student_answer,
                    is_correct=item.is_correct
                    if item.is_correct is not None
                    else item_score >= 0.5,
                    score=float(item_score),
                )
            )
            total += float(item_score)
        self.db.flush()
        return round(total / len(items), 4)

    def _snapshot_mastery(self, subject: str, topic: str) -> dict[str, Any]:
        topic_row = (
            self.db.query(TopicMastery)
            .filter(
                TopicMastery.user_id == self.user_id,
                TopicMastery.subject == subject,
                TopicMastery.topic == topic,
            )
            .first()
        )
        concepts = (
            self.db.query(ConceptMastery)
            .filter(
                ConceptMastery.user_id == self.user_id,
                ConceptMastery.subject == subject,
                ConceptMastery.topic == topic,
            )
            .all()
        )
        return {
            "subject": subject,
            "topic": topic,
            "topic_mastery": topic_row.mastery_estimate if topic_row else None,
            "topic_attempts": topic_row.attempts if topic_row else 0,
            "difficulty_level": topic_row.difficulty_level if topic_row else None,
            "consecutive_errors": topic_row.consecutive_errors if topic_row else 0,
            "concepts": [
                {
                    "concept": c.concept,
                    "mastery": c.mastery_estimate,
                    "attempts": c.attempts,
                    "consecutive_errors": c.consecutive_errors,
                }
                for c in concepts
            ],
            "snapshotted_at": utcnow().isoformat(),
        }

    def _weak_concepts(self, subject: str, topic: str) -> list[dict[str, Any]]:
        rows = (
            self.db.query(ConceptMastery)
            .filter(
                ConceptMastery.user_id == self.user_id,
                ConceptMastery.subject == subject,
                ConceptMastery.topic == topic,
            )
            .all()
        )
        weak = []
        for row in rows:
            if row.mastery_estimate < WEAK_MASTERY_THRESHOLD or row.consecutive_errors >= 2:
                weak.append(
                    {
                        "concept": row.concept,
                        "mastery": row.mastery_estimate,
                        "consecutive_errors": row.consecutive_errors,
                        "attempts": row.attempts,
                    }
                )
        return weak

    def _error_recovery(self, row: EvaluationSession) -> ErrorRecoveryMetrics:
        attempts = self._learning_attempts(row)
        if len(attempts) < 2:
            patterns = (
                self.db.query(RepeatedErrorPattern)
                .filter(
                    RepeatedErrorPattern.user_id == self.user_id,
                    RepeatedErrorPattern.subject == row.subject,
                    RepeatedErrorPattern.topic == row.topic,
                )
                .all()
            )
            resolved = sum(1 for p in patterns if p.resolved)
            open_n = sum(1 for p in patterns if not p.resolved)
            return ErrorRecoveryMetrics(
                improved=None,
                early_error_rate=None,
                late_error_rate=None,
                patterns_resolved=resolved,
                patterns_open=open_n,
                summary=(
                    "Insufficient learning attempts in evaluation window to compare "
                    "early vs late error rates (observed only)."
                ),
            )

        mid = len(attempts) // 2
        early = attempts[:mid] or attempts[:1]
        late = attempts[mid:] or attempts[-1:]
        early_err = sum(1 for a in early if not a.is_correct) / len(early)
        late_err = sum(1 for a in late if not a.is_correct) / len(late)
        improved = late_err < early_err
        return ErrorRecoveryMetrics(
            improved=improved,
            early_error_rate=round(early_err, 4),
            late_error_rate=round(late_err, 4),
            patterns_resolved=0,
            patterns_open=0,
            summary=(
                f"Observed early error rate {early_err:.0%} → late {late_err:.0%} "
                f"during linked learning session (not a causal claim)."
            ),
        )

    def _difficulty_progression(
        self, row: EvaluationSession
    ) -> DifficultyProgressionMetrics:
        attempts = self._learning_attempts(row)
        levels: list[int] = []
        for attempt in attempts:
            if attempt.difficulty:
                mapped = _label_to_level(attempt.difficulty)
                if mapped is not None:
                    levels.append(mapped)
        before = _load_json(row.mastery_before_json, {})
        after = _load_json(row.mastery_after_json, {})
        start = before.get("difficulty_level")
        end = after.get("difficulty_level")
        if levels:
            start = start if start is not None else levels[0]
            end = end if end is not None else levels[-1]
            max_level = max(levels)
        else:
            max_level = end if isinstance(end, int) else None

        progression = None
        if isinstance(start, int) and isinstance(end, int):
            if end > start:
                progression = "increased"
            elif end < start:
                progression = "decreased"
            else:
                progression = "stable"

        return DifficultyProgressionMetrics(
            start_level=int(start) if isinstance(start, int) else None,
            end_level=int(end) if isinstance(end, int) else None,
            max_level_reached=int(max_level) if isinstance(max_level, int) else None,
            progression=progression,
            summary=(
                f"Observed difficulty level {start} → {end}"
                if start is not None and end is not None
                else "No difficulty trajectory data in evaluation window."
            ),
        )

    def _recommendation_effectiveness(
        self, row: EvaluationSession
    ) -> RecommendationEffectivenessMetrics:
        query = self.db.query(RecommendationRecord).filter(
            RecommendationRecord.user_id == self.user_id,
            RecommendationRecord.subject == row.subject,
            RecommendationRecord.topic == row.topic,
        )
        if row.learning_session_id:
            query = query.filter(
                RecommendationRecord.session_id == row.learning_session_id
            )
        recs = query.order_by(RecommendationRecord.created_at.asc()).all()
        if not recs:
            return RecommendationEffectivenessMetrics(
                recommendations_count=0,
                accuracy_after_recommendation=None,
                summary="No recommendations recorded during this evaluation.",
            )
        first_rec_at = recs[0].created_at
        after = [
            a
            for a in self._learning_attempts(row)
            if a.created_at >= first_rec_at and a.is_correct is not None
        ]
        accuracy = None
        if after:
            accuracy = round(sum(1 for a in after if a.is_correct) / len(after), 4)
        return RecommendationEffectivenessMetrics(
            recommendations_count=len(recs),
            accuracy_after_recommendation=accuracy,
            summary=(
                f"Observed accuracy after first recommendation: {accuracy:.0%} "
                f"({len(after)} attempts). Correlation only — not causation."
                if accuracy is not None
                else "Recommendations exist but no subsequent attempts to score."
            ),
        )

    def _learning_attempts(self, row: EvaluationSession) -> list[Attempt]:
        query = self.db.query(Attempt).filter(
            Attempt.user_id == self.user_id,
            Attempt.subject == row.subject,
            Attempt.topic == row.topic,
        )
        if row.learning_session_id:
            query = query.filter(Attempt.session_id == row.learning_session_id)
        elif row.learning_started_at:
            query = query.filter(Attempt.created_at >= row.learning_started_at)
        else:
            return []
        if row.ended_at:
            query = query.filter(Attempt.created_at <= row.ended_at)
        return query.order_by(Attempt.id.asc()).all()

    def _intervention_lines(self, row: EvaluationSession) -> list[str]:
        query = self.db.query(RecommendationRecord).filter(
            RecommendationRecord.user_id == self.user_id,
            RecommendationRecord.subject == row.subject,
            RecommendationRecord.topic == row.topic,
        )
        if row.learning_session_id:
            query = query.filter(
                RecommendationRecord.session_id == row.learning_session_id
            )
        lines = []
        for rec in query.order_by(RecommendationRecord.created_at.asc()).all():
            lines.append(f"{rec.strategy or 'strategy'}: {rec.action} ({rec.reason})")
        return lines

    def _get(self, evaluation_id: str) -> EvaluationSession | None:
        return (
            self.db.query(EvaluationSession)
            .filter(
                EvaluationSession.evaluation_id == evaluation_id,
                EvaluationSession.user_id == self.user_id,
            )
            .first()
        )

    def _require(self, evaluation_id: str) -> EvaluationSession:
        row = self._get(evaluation_id)
        if row is None:
            raise KeyError(f"Evaluation not found: {evaluation_id}")
        return row

    def _session_out(self, row: EvaluationSession) -> EvaluationSessionOut:
        return EvaluationSessionOut(
            evaluation_id=row.evaluation_id,
            subject=row.subject,
            topic=row.topic,
            group_arm=row.group_arm,
            status=row.status,
            learning_session_id=row.learning_session_id,
            pre_test_score=row.pre_test_score,
            post_test_score=row.post_test_score,
            delayed_test_score=row.delayed_test_score,
            started_at=row.started_at.isoformat() if row.started_at else None,
            learning_started_at=(
                row.learning_started_at.isoformat() if row.learning_started_at else None
            ),
            ended_at=row.ended_at.isoformat() if row.ended_at else None,
            notes=row.notes,
        )


def _load_json(raw: str | None, default: Any) -> Any:
    try:
        return json.loads(raw or "") if raw else default
    except json.JSONDecodeError:
        return default


def _label_to_level(label: str | None) -> int | None:
    mapping = {
        "easiest": 1,
        "easy": 2,
        "current": 3,
        "medium": 3,
        "harder": 4,
        "challenging": 4,
        "hardest": 5,
    }
    if not label:
        return None
    return mapping.get(label.lower())
