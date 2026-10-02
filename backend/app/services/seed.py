"""Database bootstrap and seed data."""

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal, engine
from app.infrastructure.migrations.runner import run_migrations
from app.models import Material, StudentProfile, User


def init_db() -> None:
    run_migrations(engine)
    db = SessionLocal()
    try:
        seed_default_user(db)
    finally:
        db.close()


def seed_default_user(db: Session) -> None:
    user = db.get(User, settings.default_user_id)
    if user is None:
        user = User(
            id=settings.default_user_id,
            name=settings.default_user_name,
            email=settings.default_user_email,
        )
        db.add(user)
        db.flush()

    profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
    if profile is None:
        profile = StudentProfile(
            user_id=user.id,
            weak_subjects=None,
            strengths=None,
            total_study_minutes=0,
            total_questions=0,
            accuracy_rate=0.0,
            preferred_subjects=None,
        )
        db.add(profile)

    if db.query(Material).filter(Material.user_id == user.id).count() == 0:
        defaults = [
            Material(
                user_id=user.id,
                title="二次函數與抛物線",
                subject="高二數學",
                file_type="note",
                description="二次函數頂點、判別式與應用題整理。",
            ),
            Material(
                user_id=user.id,
                title="Reading: Climate & Cities",
                subject="英文",
                file_type="note",
                description="閱讀理解：氣候變遷與都市規劃文章摘要。",
            ),
            Material(
                user_id=user.id,
                title="牛頓運動定律",
                subject="物理",
                file_type="note",
                description="第一定律到第三定律重點與常見題型。",
            ),
        ]
        db.add_all(defaults)

    db.commit()
