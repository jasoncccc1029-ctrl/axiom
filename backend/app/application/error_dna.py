"""Error DNA — read-model aggregation over existing error tables.

Does not replace ErrorIntelligence. Builds an evidence-backed profile from:
Attempt + Mistake + RepeatedErrorPattern.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Attempt, Mistake, RepeatedErrorPattern


class ErrorEvidence(BaseModel):
    source: str
    source_id: int | None = None
    detail: str
    subject: str | None = None
    topic: str | None = None
    concept: str | None = None


class ErrorTypeCount(BaseModel):
    error_type: str
    count: int
    evidence: list[ErrorEvidence] = Field(default_factory=list)


class TopicErrorDistribution(BaseModel):
    subject: str
    topic: str
    error_count: int
    by_type: dict[str, int] = Field(default_factory=dict)


class ConceptErrorDistribution(BaseModel):
    subject: str
    topic: str
    concept: str
    error_count: int
    by_type: dict[str, int] = Field(default_factory=dict)


class ErrorDNAProfile(BaseModel):
    user_id: int
    subject: str | None = None
    topic: str | None = None
    most_frequent_error_types: list[ErrorTypeCount] = Field(default_factory=list)
    repeated_errors: list[dict[str, Any]] = Field(default_factory=list)
    recent_errors: list[dict[str, Any]] = Field(default_factory=list)
    topic_distribution: list[TopicErrorDistribution] = Field(default_factory=list)
    concept_distribution: list[ConceptErrorDistribution] = Field(default_factory=list)
    evidence_count: int = 0
    notes: str = (
        "Aggregated from Attempt / Mistake / RepeatedErrorPattern. "
        "Not a causal diagnosis score."
    )


class ErrorDNAService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id

    def profile(
        self,
        *,
        subject: str | None = None,
        topic: str | None = None,
        recent_limit: int = 10,
    ) -> ErrorDNAProfile:
        attempts_q = self.db.query(Attempt).filter(
            Attempt.user_id == self.user_id,
            Attempt.is_correct.is_(False),
        )
        if subject:
            attempts_q = attempts_q.filter(Attempt.subject == subject)
        if topic:
            attempts_q = attempts_q.filter(Attempt.topic == topic)
        failed = attempts_q.order_by(Attempt.id.desc()).all()

        type_counter: Counter[str] = Counter()
        type_evidence: dict[str, list[ErrorEvidence]] = {}
        topic_map: dict[tuple[str, str], Counter[str]] = {}
        concept_map: dict[tuple[str, str, str], Counter[str]] = {}

        for attempt in failed:
            et = attempt.error_type or "UNKNOWN"
            type_counter[et] += 1
            evidence = ErrorEvidence(
                source="attempt",
                source_id=attempt.id,
                detail=attempt.mistake_pattern
                or attempt.detected_misconception
                or et,
                subject=attempt.subject,
                topic=attempt.topic,
                concept=attempt.related_concept,
            )
            type_evidence.setdefault(et, []).append(evidence)
            if attempt.subject and attempt.topic:
                key = (attempt.subject, attempt.topic)
                topic_map.setdefault(key, Counter())[et] += 1
            if attempt.subject and attempt.topic and attempt.related_concept:
                ckey = (attempt.subject, attempt.topic, attempt.related_concept)
                concept_map.setdefault(ckey, Counter())[et] += 1

            for mistake in (
                self.db.query(Mistake).filter(Mistake.attempt_id == attempt.id).all()
            ):
                type_evidence.setdefault(et, []).append(
                    ErrorEvidence(
                        source="mistake",
                        source_id=mistake.id,
                        detail=mistake.pattern
                        + (f" · {mistake.misconception}" if mistake.misconception else ""),
                        subject=attempt.subject,
                        topic=attempt.topic,
                        concept=attempt.related_concept,
                    )
                )

        patterns_q = self.db.query(RepeatedErrorPattern).filter(
            RepeatedErrorPattern.user_id == self.user_id
        )
        if subject:
            patterns_q = patterns_q.filter(RepeatedErrorPattern.subject == subject)
        if topic:
            patterns_q = patterns_q.filter(RepeatedErrorPattern.topic == topic)
        patterns = patterns_q.order_by(RepeatedErrorPattern.count.desc()).all()

        most_frequent = [
            ErrorTypeCount(
                error_type=name,
                count=count,
                evidence=(type_evidence.get(name) or [])[:5],
            )
            for name, count in type_counter.most_common(8)
        ]

        recent_errors = [
            {
                "attempt_id": a.id,
                "subject": a.subject,
                "topic": a.topic,
                "concept": a.related_concept,
                "error_type": a.error_type,
                "mistake_pattern": a.mistake_pattern,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "problem_id": a.problem_id,
            }
            for a in failed[: max(1, recent_limit)]
        ]

        repeated = [
            {
                "pattern": p.pattern,
                "error_type": p.error_type,
                "subject": p.subject,
                "topic": p.topic,
                "concept": p.concept,
                "count": p.count,
                "resolved": p.resolved,
                "first_seen": p.first_seen.isoformat() if p.first_seen else None,
                "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                "source": "repeated_error_pattern",
                "source_id": p.id,
            }
            for p in patterns
            if p.count >= 1
        ]

        topic_distribution = [
            TopicErrorDistribution(
                subject=subj,
                topic=top,
                error_count=sum(counter.values()),
                by_type=dict(counter),
            )
            for (subj, top), counter in sorted(
                topic_map.items(), key=lambda item: sum(item[1].values()), reverse=True
            )
        ]
        concept_distribution = [
            ConceptErrorDistribution(
                subject=subj,
                topic=top,
                concept=concept,
                error_count=sum(counter.values()),
                by_type=dict(counter),
            )
            for (subj, top, concept), counter in sorted(
                concept_map.items(),
                key=lambda item: sum(item[1].values()),
                reverse=True,
            )
        ]

        evidence_count = sum(len(v) for v in type_evidence.values()) + len(repeated)

        return ErrorDNAProfile(
            user_id=self.user_id,
            subject=subject,
            topic=topic,
            most_frequent_error_types=most_frequent,
            repeated_errors=repeated,
            recent_errors=recent_errors,
            topic_distribution=topic_distribution,
            concept_distribution=concept_distribution,
            evidence_count=evidence_count,
        )
