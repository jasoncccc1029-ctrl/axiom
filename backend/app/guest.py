"""Public guest identity — isolate per-browser learners without full auth."""

from __future__ import annotations

import re

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import StudentProfile, User

_GUEST_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _email_for_guest(guest_id: str) -> str:
    return f"guest-{guest_id.lower()}@axiom.public"


def get_or_create_guest_user(db: Session, guest_id: str) -> User:
    email = _email_for_guest(guest_id)
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        return user
    try:
        user = User(name="訪客", email=email)
        db.add(user)
        db.flush()
        db.add(StudentProfile(user_id=user.id))
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        existing = db.query(User).filter(User.email == email).one_or_none()
        if existing is not None:
            return existing
        raise


def provide_user_id(
    request: Request,
    db: Session = Depends(get_db),
    x_axiom_guest: str | None = Header(default=None, alias="X-Axiom-Guest"),
) -> int:
    """Resolve learner: guest UUID header → dedicated user; else default demo user."""
    raw = (x_axiom_guest or request.headers.get("x-axiom-guest") or "").strip()
    if raw and _GUEST_RE.match(raw):
        return get_or_create_guest_user(db, raw).id
    return settings.default_user_id
