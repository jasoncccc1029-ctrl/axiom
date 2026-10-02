"""Concept-level mastery graph with optional prerequisite edges."""

from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ConceptMastery, utcnow

# Future-ready prerequisite map: concept -> list of prerequisite concepts
PREREQUISITES: dict[str, list[str]] = {
    "quadratic_equation": ["linear_equation", "equation_transformation"],
    "quadratic_function": ["quadratic_equation", "root_coefficient_relationship"],
    "root_coefficient_relationship": ["quadratic_equation", "equation_transformation"],
    "discriminant": ["quadratic_equation"],
    "vertex": ["quadratic_function"],
    "calculus": ["quadratic_function"],
}


class ConceptMasteryItem(BaseModel):
    subject: str
    topic: str
    concept: str
    mastery: float
    confidence: float
    attempts: int
    correct_attempts: int
    consecutive_errors: int
    weakest: bool = False
    strongest: bool = False
    prerequisite_of: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)


class MasteryGraphSnapshot(BaseModel):
    subject: str
    topic: str
    topic_mastery: float
    concepts: list[ConceptMasteryItem] = Field(default_factory=list)
    weakest_concept: str | None = None
    strongest_concept: str | None = None
    bottleneck_concept: str | None = None
    bottleneck_reason: str | None = None


class MasteryGraphService:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id

    def update_concept(
        self,
        *,
        subject: str,
        topic: str,
        concept: str,
        correct: bool,
    ) -> ConceptMastery:
        row = (
            self.db.query(ConceptMastery)
            .filter(
                ConceptMastery.user_id == self.user_id,
                ConceptMastery.subject == subject,
                ConceptMastery.topic == topic,
                ConceptMastery.concept == concept,
            )
            .first()
        )
        if row is None:
            row = ConceptMastery(
                user_id=self.user_id,
                subject=subject,
                topic=topic,
                concept=concept,
                attempts=0,
                correct_attempts=0,
                consecutive_errors=0,
                mastery_estimate=0.0,
                confidence=0.0,
            )
            self.db.add(row)
        row.attempts += 1
        if correct:
            row.correct_attempts += 1
            row.consecutive_errors = 0
        else:
            row.consecutive_errors += 1
        row.mastery_estimate = round(
            (row.correct_attempts + 1) / (row.attempts + 2), 4
        )
        row.confidence = round(min(0.95, row.attempts / 10), 4)
        row.last_practiced_at = utcnow()
        review_days = max(1, round(1 + row.mastery_estimate * 13))
        if row.consecutive_errors >= 2:
            review_days = 1
        row.next_review_at = utcnow() + timedelta(days=review_days)
        row.review_count = int(row.review_count or 0)
        self.db.flush()
        return row

    def snapshot(
        self,
        *,
        subject: str,
        topic: str,
        topic_mastery: float,
    ) -> MasteryGraphSnapshot:
        rows = (
            self.db.query(ConceptMastery)
            .filter(
                ConceptMastery.user_id == self.user_id,
                ConceptMastery.subject == subject,
                ConceptMastery.topic == topic,
            )
            .all()
        )
        items: list[ConceptMasteryItem] = []
        for row in rows:
            items.append(
                ConceptMasteryItem(
                    subject=row.subject,
                    topic=row.topic,
                    concept=row.concept,
                    mastery=row.mastery_estimate,
                    confidence=row.confidence,
                    attempts=row.attempts,
                    correct_attempts=row.correct_attempts,
                    consecutive_errors=row.consecutive_errors,
                    prerequisites=list(PREREQUISITES.get(row.concept, [])),
                    prerequisite_of=[
                        parent
                        for parent, deps in PREREQUISITES.items()
                        if row.concept in deps
                    ],
                )
            )
        if not items:
            return MasteryGraphSnapshot(
                subject=subject,
                topic=topic,
                topic_mastery=topic_mastery,
            )

        weakest = min(items, key=lambda x: x.mastery)
        strongest = max(items, key=lambda x: x.mastery)
        for item in items:
            item.weakest = item.concept == weakest.concept
            item.strongest = item.concept == strongest.concept

        bottleneck = None
        bottleneck_reason = None
        # Prerequisite weakness: if a prereq concept is much weaker than topic mastery
        for item in items:
            for prereq_name in PREREQUISITES.get(item.concept, []):
                prereq = next((c for c in items if c.concept == prereq_name), None)
                if prereq and prereq.mastery + 0.15 < topic_mastery and prereq.mastery < 0.5:
                    if bottleneck is None or prereq.mastery < (
                        next(c.mastery for c in items if c.concept == bottleneck)
                    ):
                        bottleneck = prereq.concept
                        bottleneck_reason = (
                            f"Topic mastery looks moderate ({topic_mastery:.0%}), but "
                            f"prerequisite '{prereq.concept}' is only {prereq.mastery:.0%}."
                        )
        if bottleneck is None and weakest.mastery < 0.5 and topic_mastery >= 0.5:
            bottleneck = weakest.concept
            bottleneck_reason = (
                f"Main bottleneck is concept '{weakest.concept}' "
                f"at {weakest.mastery:.0%}."
            )

        return MasteryGraphSnapshot(
            subject=subject,
            topic=topic,
            topic_mastery=topic_mastery,
            concepts=items,
            weakest_concept=weakest.concept,
            strongest_concept=strongest.concept,
            bottleneck_concept=bottleneck,
            bottleneck_reason=bottleneck_reason,
        )

    def get_concept(
        self, subject: str, topic: str, concept: str
    ) -> ConceptMastery | None:
        return (
            self.db.query(ConceptMastery)
            .filter(
                ConceptMastery.user_id == self.user_id,
                ConceptMastery.subject == subject,
                ConceptMastery.topic == topic,
                ConceptMastery.concept == concept,
            )
            .first()
        )
