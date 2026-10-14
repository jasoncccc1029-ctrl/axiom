"""Per-user AI request quota (UTC daily) — stats + hard caps for shared Brain keys."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.guest import provide_user_id
from app.models import AiUsageDaily, AiUsageEvent, User


class AiUsageStatus(BaseModel):
    enabled: bool
    user_id: int
    is_guest: bool
    day: str
    used: int
    limit: int
    remaining: int
    resets_at: str


def utc_today() -> date:
    return datetime.now(UTC).date()


def is_guest_account(user: User | None) -> bool:
    if user is None:
        return True
    email = (user.email or "").lower()
    if email.endswith("@axiom.public") or email.endswith("@axiom.local"):
        return True
    return not bool(user.password_hash)


def daily_limit_for(user: User | None) -> int:
    if is_guest_account(user):
        return max(0, int(settings.ai_daily_limit_guest))
    return max(0, int(settings.ai_daily_limit_user))


def _row_for_today(db: Session, user_id: int, day: date) -> AiUsageDaily:
    row = (
        db.query(AiUsageDaily)
        .filter(AiUsageDaily.user_id == user_id, AiUsageDaily.day == day)
        .one_or_none()
    )
    if row is not None:
        return row
    row = AiUsageDaily(user_id=user_id, day=day, request_count=0)
    db.add(row)
    db.flush()
    return row


def get_usage_status(db: Session, user_id: int) -> AiUsageStatus:
    day = utc_today()
    user = db.get(User, user_id)
    limit = daily_limit_for(user) if settings.ai_quota_enabled else 0
    row = (
        db.query(AiUsageDaily)
        .filter(AiUsageDaily.user_id == user_id, AiUsageDaily.day == day)
        .one_or_none()
    )
    used = int(row.request_count) if row else 0
    if not settings.ai_quota_enabled:
        remaining = 999_999
        limit_out = 0
    else:
        remaining = max(0, limit - used)
        limit_out = limit
    resets = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    return AiUsageStatus(
        enabled=bool(settings.ai_quota_enabled),
        user_id=user_id,
        is_guest=is_guest_account(user),
        day=day.isoformat(),
        used=used,
        limit=limit_out,
        remaining=remaining,
        resets_at=resets.isoformat().replace("+00:00", "Z"),
    )


def _exceeded_detail(status: AiUsageStatus) -> str:
    if status.is_guest:
        return (
            f"今日訪客 AI 額度已用完（{status.used}/{status.limit}）。"
            "請註冊／登入以獲得更多免費次數（登入用戶每日較高額度）。"
        )
    return (
        f"今日 AI 額度已用完（{status.used}/{status.limit}）。"
        "額度於 UTC 午夜重置；請明天再來，或稍後再試。"
    )


def ensure_ai_quota(db: Session, user_id: int) -> AiUsageStatus:
    """Raise 429 if over daily limit. Does not consume a slot."""
    status = get_usage_status(db, user_id)
    if not settings.ai_quota_enabled:
        return status
    if status.used >= status.limit:
        raise HTTPException(
            status_code=429,
            detail=_exceeded_detail(status),
            headers={"Retry-After": "3600"},
        )
    return status


def record_ai_usage(db: Session, user_id: int, purpose: str) -> AiUsageStatus:
    """Count one successful AI request (call only after Brain succeeds)."""
    if not settings.ai_quota_enabled:
        return get_usage_status(db, user_id)
    day = utc_today()
    row = _row_for_today(db, user_id, day)
    row.request_count = int(row.request_count) + 1
    db.add(AiUsageEvent(user_id=user_id, purpose=(purpose or "ai")[:40]))
    db.commit()
    return get_usage_status(db, user_id)


def consume_ai_request(db: Session, user_id: int, purpose: str) -> AiUsageStatus:
    """Check quota then record (kept for tests / simple call sites)."""
    ensure_ai_quota(db, user_id)
    return record_ai_usage(db, user_id, purpose)


def make_ai_quota_dep(purpose: str):
    """FastAPI dependency — ensure capacity; caller records after success."""

    def _dep(
        db: Session = Depends(get_db),
        user_id: int = Depends(provide_user_id),
    ) -> tuple[Session, int, str]:
        ensure_ai_quota(db, user_id)
        return db, user_id, purpose

    return _dep
