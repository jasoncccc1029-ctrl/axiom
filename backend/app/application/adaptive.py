"""Rule-based adaptive teaching policy grounded in stored learning evidence."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.schemas import TeachingMode
from app.config import settings
from app.models import RecommendationRecord, TopicMastery, utcnow


class AdaptiveDecision(BaseModel):
    explanation_level: str
    question_difficulty: str
    hint_level: str
    strategy: str
    sequence: list[str] = Field(default_factory=list)
    mastery: float | None = None
    evidence_attempts: int = 0
    enough_data: bool = False
    why: str = ""
    last_mistake_pattern: str | None = None


class Recommendation(BaseModel):
    subject: str
    topic: str
    reason: str
    action: str
    priority: int
    priority_label: str = "MEDIUM"
    concept: str | None = None
    strategy: str | None = None
    difficulty: int | None = None
    sequence: list[str] = Field(default_factory=list)
    due_for_review: bool = False
    why: str = ""
    evidence: dict[str, object] = Field(default_factory=dict)
    recommended_difficulty: str = "current"


class RecommendationsResponse(BaseModel):
    recommendations: list[Recommendation]
    enough_data: bool
    message: str | None = None


REVIEW_SEQUENCE = [
    "Review concept",
    "Solve easy question",
    "Solve medium question",
    "Diagnose mistakes",
    "Re-test later",
]


class AdaptiveTutor:
    def __init__(self, db: Session, user_id: int | None = None) -> None:
        self.db = db
        self.user_id = user_id or settings.default_user_id

    def decide(
        self,
        *,
        subject: str | None,
        topic: str | None,
        mode: TeachingMode,
    ) -> AdaptiveDecision:
        mastery = self._mastery(subject, topic)
        if mastery and mastery.consecutive_errors >= 2:
            why = (
                f"{mastery.consecutive_errors} consecutive errors on "
                f"{mastery.subject}/{mastery.topic}"
            )
            if mastery.last_mistake_pattern:
                why += f"; repeated mistake: {mastery.last_mistake_pattern}"
            return AdaptiveDecision(
                explanation_level="foundational",
                question_difficulty="easy",
                hint_level="high",
                strategy="concept_recovery",
                sequence=REVIEW_SEQUENCE,
                mastery=mastery.mastery_estimate,
                evidence_attempts=mastery.attempts,
                enough_data=True,
                why=why,
                last_mistake_pattern=mastery.last_mistake_pattern,
            )
        due = bool(mastery and mastery.next_review_at and mastery.next_review_at <= utcnow())
        if due and mastery:
            return AdaptiveDecision(
                explanation_level="review",
                question_difficulty="easy",
                hint_level="medium",
                strategy="spaced_review",
                sequence=REVIEW_SEQUENCE,
                mastery=mastery.mastery_estimate,
                evidence_attempts=mastery.attempts,
                enough_data=True,
                why="Spaced-review interval elapsed for this topic.",
                last_mistake_pattern=mastery.last_mistake_pattern,
            )
        if mastery and mastery.attempts >= 3 and mastery.mastery_estimate >= 0.8:
            return AdaptiveDecision(
                explanation_level="concise",
                question_difficulty="challenging",
                hint_level="low" if mode == TeachingMode.HINT else "medium",
                strategy="advance_with_check",
                sequence=["Brief review", "Challenging application", "Check reasoning"],
                mastery=mastery.mastery_estimate,
                evidence_attempts=mastery.attempts,
                enough_data=True,
                why=(
                    f"Mastery {mastery.mastery_estimate:.0%} with "
                    f"{mastery.attempts} attempts; increase difficulty."
                ),
                last_mistake_pattern=mastery.last_mistake_pattern,
            )
        if mastery:
            return AdaptiveDecision(
                explanation_level="standard",
                question_difficulty=mastery.recommended_difficulty or "current",
                hint_level="medium",
                strategy="guided_practice",
                sequence=["Explain one step", "Ask learner to continue", "Check response"],
                mastery=mastery.mastery_estimate,
                evidence_attempts=mastery.attempts,
                enough_data=mastery.attempts >= 3,
                why=f"Current mastery {mastery.mastery_estimate:.0%} from live attempts.",
                last_mistake_pattern=mastery.last_mistake_pattern,
            )
        return AdaptiveDecision(
            explanation_level="standard",
            question_difficulty="current",
            hint_level="medium",
            strategy="baseline",
            sequence=["Explain", "Check understanding"],
            mastery=None,
            evidence_attempts=0,
            enough_data=False,
            why="Not enough topic evidence yet.",
        )

    def recommend_for_topic(
        self,
        subject: str,
        topic: str,
        *,
        session_id: int | None = None,
        strategy=None,
        difficulty_decision=None,
        error_diagnosis=None,
        mastery_graph=None,
        force_review: bool = False,
    ) -> Recommendation | None:
        row = self._mastery(subject, topic)
        if row is None:
            return None
        item = self._to_recommendation(
            row,
            priority=1,
            strategy=strategy,
            difficulty_decision=difficulty_decision,
            error_diagnosis=error_diagnosis,
            mastery_graph=mastery_graph,
            force_review=force_review,
        )
        self.db.query(RecommendationRecord).filter(
            RecommendationRecord.user_id == self.user_id,
            RecommendationRecord.subject == subject,
            RecommendationRecord.topic == topic,
            RecommendationRecord.status == "active",
        ).update({"status": "superseded"})
        self.db.add(
            RecommendationRecord(
                user_id=self.user_id,
                session_id=session_id,
                subject=item.subject,
                topic=item.topic,
                reason=item.reason,
                action=item.action,
                concept=item.concept,
                strategy=item.strategy,
                difficulty_level=item.difficulty,
                evidence_json=json.dumps(item.evidence, ensure_ascii=False),
                status="active",
            )
        )
        self.db.commit()
        return item

    def recommendations(self, limit: int = 5) -> RecommendationsResponse:
        rows = (
            self.db.query(TopicMastery)
            .filter(TopicMastery.user_id == self.user_id)
            .all()
        )
        if not rows:
            return RecommendationsResponse(
                recommendations=[],
                enough_data=False,
                message="Not enough data yet.",
            )
        now = utcnow()
        ranked = sorted(
            rows,
            key=lambda row: (
                0 if (row.next_review_at and row.next_review_at <= now) else 1,
                -row.consecutive_errors,
                row.mastery_estimate,
            ),
        )[:limit]
        recommendations = [
            self._to_recommendation(row, priority=index)
            for index, row in enumerate(ranked, start=1)
        ]
        self.db.query(RecommendationRecord).filter(
            RecommendationRecord.user_id == self.user_id,
            RecommendationRecord.status == "active",
        ).update({"status": "superseded"})
        self.db.add_all(
            [
                RecommendationRecord(
                    user_id=self.user_id,
                    subject=item.subject,
                    topic=item.topic,
                    reason=item.reason,
                    action=item.action,
                    concept=item.concept,
                    strategy=item.strategy,
                    difficulty_level=item.difficulty,
                    evidence_json=json.dumps(item.evidence, ensure_ascii=False),
                    status="active",
                )
                for item in recommendations
            ]
        )
        self.db.commit()
        return RecommendationsResponse(
            recommendations=recommendations,
            enough_data=any(row.attempts >= 3 for row in rows),
            message=None
            if any(row.attempts >= 3 for row in rows)
            else "Not enough data yet.",
        )

    def _to_recommendation(
        self,
        row: TopicMastery,
        *,
        priority: int,
        strategy=None,
        difficulty_decision=None,
        error_diagnosis=None,
        mastery_graph=None,
        force_review: bool = False,
    ) -> Recommendation:
        due = bool(row.next_review_at and row.next_review_at <= utcnow()) or force_review
        concept = None
        if mastery_graph and getattr(mastery_graph, "bottleneck_concept", None):
            concept = mastery_graph.bottleneck_concept
        elif mastery_graph and getattr(mastery_graph, "weakest_concept", None):
            concept = mastery_graph.weakest_concept
        elif error_diagnosis is not None:
            concept = getattr(error_diagnosis, "related_concept", None)

        strategy_name = None
        if strategy is not None:
            strategy_name = getattr(getattr(strategy, "strategy", None), "value", None) or str(
                getattr(strategy, "strategy", strategy)
            )
        difficulty_level = getattr(row, "difficulty_level", None) or 3
        if difficulty_decision is not None:
            difficulty_level = difficulty_decision.recommended_difficulty

        evidence = {
            "mastery": row.mastery_estimate,
            "confidence": row.confidence,
            "attempts": row.attempts,
            "correct_attempts": row.correct_attempts,
            "consecutive_errors": row.consecutive_errors,
            "last_mistake_pattern": row.last_mistake_pattern,
            "recommended_difficulty": row.recommended_difficulty,
            "due_for_review": due,
            "recent_accuracy": (
                row.correct_attempts / row.attempts if row.attempts else 0.0
            ),
            "repeated_errors": getattr(error_diagnosis, "pattern_count", 0)
            if error_diagnosis
            else 0,
            "concept": concept,
            "concept_mastery": None,
        }
        if mastery_graph and concept:
            match = next(
                (c for c in mastery_graph.concepts if c.concept == concept),
                None,
            )
            if match:
                evidence["concept_mastery"] = match.mastery

        if due and row.mastery_estimate >= 0.75:
            action = "Spaced review is due. Revisit the concept, then re-test."
            reason = "Review interval elapsed"
            why = (
                f"Axiom recommends REVIEW because mastery on {row.topic} is "
                f"{row.mastery_estimate:.0%} but the spaced-review timer has elapsed."
            )
            sequence = REVIEW_SEQUENCE
            difficulty = "easy" if difficulty_level <= 2 else row.recommended_difficulty
            strategy_name = strategy_name or "REVIEW"
            priority_label = "MEDIUM"
        elif row.consecutive_errors >= 2 or (
            error_diagnosis and getattr(error_diagnosis, "pattern_count", 0) >= 2
        ):
            action = (
                "Decrease difficulty and run error diagnosis / concept review "
                "before retrying."
            )
            reason = f"{row.consecutive_errors} consecutive errors"
            repeated = getattr(error_diagnosis, "pattern_count", row.consecutive_errors)
            error_type = getattr(
                getattr(error_diagnosis, "error_type", None),
                "value",
                row.last_mistake_pattern or "UNKNOWN",
            )
            why = (
                f"Axiom recommends {strategy_name or 'ERROR_DIAGNOSIS'} because "
                f"the same error ({error_type}) appeared {repeated} times on "
                f"{concept or row.topic}."
            )
            sequence = REVIEW_SEQUENCE
            difficulty = "easy"
            strategy_name = strategy_name or "ERROR_DIAGNOSIS"
            priority_label = "HIGH"
        elif mastery_graph and mastery_graph.bottleneck_concept:
            concept = mastery_graph.bottleneck_concept
            action = (
                f"Target prerequisite/concept '{concept}' before advancing the topic."
            )
            reason = "Prerequisite concept weakness"
            why = mastery_graph.bottleneck_reason or why_fallback(row, concept)
            sequence = ["Review prerequisite concept", "Easy practice", "Re-test topic"]
            difficulty = row.recommended_difficulty or "easy"
            strategy_name = strategy_name or "CONCEPT"
            priority_label = "HIGH"
            evidence["concept"] = concept
        elif row.mastery_estimate < 0.6:
            action = "Practice a guided easy/medium example at reduced pressure."
            reason = f"Topic mastery is {row.mastery_estimate:.0%}"
            why = (
                f"Axiom recommends guided practice because mastery on {row.topic} "
                f"is only {row.mastery_estimate:.0%} after {row.attempts} attempts."
            )
            sequence = ["Concept reminder", "Easy question", "Check understanding"]
            difficulty = row.recommended_difficulty or "easy"
            strategy_name = strategy_name or "PRACTICE"
            priority_label = "MEDIUM"
        elif row.mastery_estimate >= 0.8 and row.attempts >= 3:
            action = "Increase difficulty with a challenging application question."
            reason = f"Topic mastery is {row.mastery_estimate:.0%}"
            why = (
                f"Axiom recommends a harder task because mastery on {row.topic} "
                f"reached {row.mastery_estimate:.0%} with stable recent performance."
            )
            sequence = ["Brief review", "Challenging application", "Check reasoning"]
            difficulty = "challenging"
            strategy_name = strategy_name or "CHALLENGE"
            priority_label = "LOW"
        else:
            action = "Continue guided practice at the current difficulty."
            reason = f"Topic mastery is {row.mastery_estimate:.0%}"
            why = (
                f"Axiom recommends continued practice because {row.topic} mastery "
                f"is {row.mastery_estimate:.0%} and still building confidence."
            )
            sequence = []
            difficulty = row.recommended_difficulty or "current"
            strategy_name = strategy_name or "NORMAL"
            priority_label = "MEDIUM"

        if difficulty_decision is not None:
            difficulty = difficulty_decision.recommended_label

        return Recommendation(
            subject=row.subject,
            topic=row.topic,
            reason=reason,
            action=action,
            priority=priority,
            priority_label=priority_label,
            concept=concept,
            strategy=strategy_name,
            difficulty=int(difficulty_level),
            sequence=sequence,
            due_for_review=due,
            why=why,
            evidence=evidence,
            recommended_difficulty=difficulty,
        )

    def _mastery(self, subject: str | None, topic: str | None) -> TopicMastery | None:
        if not subject or not topic:
            return None
        return (
            self.db.query(TopicMastery)
            .filter(
                TopicMastery.user_id == self.user_id,
                TopicMastery.subject == subject,
                TopicMastery.topic == topic,
            )
            .first()
        )


def why_fallback(row: TopicMastery, concept: str) -> str:
    return (
        f"Axiom recommends focusing on '{concept}' because it is the weakest "
        f"linked concept under {row.topic}."
    )
