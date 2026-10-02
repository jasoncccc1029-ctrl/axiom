"""Progress aggregation helpers."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Attempt, LearningRecord, TopicMastery
from app.schemas import (
    AccuracyTrendPoint,
    LearningHistoryOut,
    MistakePatternOut,
    ProgressResponse,
    SubjectAbility,
    TopicMasteryOut,
)


def get_progress(db: Session, user_id: int | None = None) -> ProgressResponse:
    uid = user_id or settings.default_user_id
    now = datetime.now(UTC).replace(tzinfo=None)
    start_today = datetime(now.year, now.month, now.day)
    start_week = start_today - timedelta(days=start_today.weekday())

    today_minutes = (
        db.query(func.coalesce(func.sum(LearningRecord.duration_minutes), 0))
        .filter(LearningRecord.user_id == uid, LearningRecord.created_at >= start_today)
        .scalar()
        or 0
    )

    week_q = (
        db.query(func.coalesce(func.sum(LearningRecord.questions_attempted), 0))
        .filter(LearningRecord.user_id == uid, LearningRecord.created_at >= start_week)
        .scalar()
        or 0
    )

    subject_rows = (
        db.query(
            LearningRecord.subject,
            func.coalesce(func.sum(LearningRecord.questions_correct), 0),
            func.coalesce(func.sum(LearningRecord.questions_attempted), 0),
        )
        .filter(LearningRecord.user_id == uid, LearningRecord.subject.isnot(None))
        .group_by(LearningRecord.subject)
        .all()
    )

    abilities: list[SubjectAbility] = []
    for subject, correct, attempted in subject_rows:
        score = (float(correct) / float(attempted) * 100.0) if attempted else 0.0
        abilities.append(
            SubjectAbility(subject=subject or "未分類", score=round(score, 1), questions=int(attempted))
        )

    mastery_rows = (
        db.query(TopicMastery)
        .filter(TopicMastery.user_id == uid)
        .order_by(TopicMastery.mastery_estimate.asc())
        .all()
    )
    weak = sorted(
        {row.subject for row in mastery_rows if row.attempts >= 2 and row.mastery_estimate < 0.6}
    )
    strengths = sorted(
        {row.subject for row in mastery_rows if row.attempts >= 2 and row.mastery_estimate >= 0.8}
    )

    total_study = (
        db.query(func.coalesce(func.sum(LearningRecord.duration_minutes), 0))
        .filter(LearningRecord.user_id == uid)
        .scalar()
        or 0
    )
    total_questions = (
        db.query(func.coalesce(func.sum(LearningRecord.questions_attempted), 0))
        .filter(LearningRecord.user_id == uid)
        .scalar()
        or 0
    )
    total_correct = (
        db.query(func.coalesce(func.sum(LearningRecord.questions_correct), 0))
        .filter(LearningRecord.user_id == uid)
        .scalar()
        or 0
    )
    accuracy = float(total_correct) / float(total_questions) if total_questions else 0.0

    trend_rows = (
        db.query(
            func.date(LearningRecord.created_at),
            func.sum(LearningRecord.questions_attempted),
            func.sum(LearningRecord.questions_correct),
        )
        .filter(
            LearningRecord.user_id == uid,
            LearningRecord.created_at >= start_today - timedelta(days=13),
            LearningRecord.questions_attempted > 0,
        )
        .group_by(func.date(LearningRecord.created_at))
        .order_by(func.date(LearningRecord.created_at))
        .all()
    )
    trend = [
        AccuracyTrendPoint(
            date=str(day),
            attempted=int(attempted or 0),
            correct=int(correct or 0),
            accuracy=round(float(correct or 0) / float(attempted), 4) if attempted else 0.0,
        )
        for day, attempted, correct in trend_rows
    ]

    pattern_rows = (
        db.query(
            Attempt.mistake_pattern,
            Attempt.subject,
            Attempt.topic,
            func.count(Attempt.id),
        )
        .filter(
            Attempt.user_id == uid,
            Attempt.is_correct.is_(False),
            Attempt.mistake_pattern.isnot(None),
        )
        .group_by(Attempt.mistake_pattern, Attempt.subject, Attempt.topic)
        .order_by(func.count(Attempt.id).desc())
        .limit(10)
        .all()
    )
    history_rows = (
        db.query(LearningRecord)
        .filter(LearningRecord.user_id == uid)
        .order_by(LearningRecord.created_at.desc())
        .limit(20)
        .all()
    )
    enough_data = len(mastery_rows) > 0 and int(total_questions) >= 3

    return ProgressResponse(
        today_study_minutes=int(today_minutes),
        week_questions_completed=int(week_q),
        accuracy_rate=accuracy,
        weak_subjects=weak,
        recommended=[],
        total_study_minutes=int(total_study),
        total_questions=int(total_questions),
        subject_abilities=abilities,
        strengths=strengths,
        topic_mastery=[
            TopicMasteryOut(
                subject=row.subject,
                topic=row.topic,
                mastery=row.mastery_estimate,
                attempts=row.attempts,
                consecutive_errors=row.consecutive_errors,
            )
            for row in mastery_rows
        ],
        accuracy_trend=trend,
        mistake_patterns=[
            MistakePatternOut(
                pattern=pattern,
                subject=subject,
                topic=topic,
                count=int(count),
            )
            for pattern, subject, topic, count in pattern_rows
        ],
        learning_history=[
            LearningHistoryOut(
                activity_type=row.activity_type,
                subject=row.subject,
                topic=row.topic,
                duration_minutes=row.duration_minutes,
                questions_attempted=row.questions_attempted,
                questions_correct=row.questions_correct,
                created_at=row.created_at,
            )
            for row in history_rows
        ],
        enough_data=enough_data,
        data_message=None if enough_data else "Not enough data yet.",
    )
