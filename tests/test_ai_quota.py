"""AI daily quota enforcement."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.ai_quota import consume_ai_request, get_usage_status
from app.auth import create_access_token, hash_password
from app.config import settings
from app.database import Base, get_db
from app.main import app
from app.models import User


def _engine_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    return TestingSession


def test_guest_quota_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(settings, "ai_quota_enabled", True)
    monkeypatch.setattr(settings, "ai_daily_limit_guest", 2)
    monkeypatch.setattr(settings, "ai_daily_limit_user", 40)
    Session = _engine_session()
    with Session() as db:
        guest = User(name="訪客", email="guest-aaaa@axiom.public")
        db.add(guest)
        db.commit()
        db.refresh(guest)
        uid = guest.id

        consume_ai_request(db, uid, "chat")
        consume_ai_request(db, uid, "tutor")
        status = get_usage_status(db, uid)
        assert status.used == 2
        assert status.remaining == 0
        assert status.is_guest is True

        with pytest.raises(HTTPException) as exc:
            consume_ai_request(db, uid, "chat")
        assert exc.value.status_code == 429
        assert "訪客" in str(exc.value.detail)


def test_registered_user_higher_limit(monkeypatch):
    monkeypatch.setattr(settings, "ai_quota_enabled", True)
    monkeypatch.setattr(settings, "ai_daily_limit_guest", 1)
    monkeypatch.setattr(settings, "ai_daily_limit_user", 5)
    Session = _engine_session()
    with Session() as db:
        user = User(
            name="Learner",
            email="quota@example.com",
            password_hash=hash_password("password12"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        for _ in range(5):
            consume_ai_request(db, user.id, "solve")
        status = get_usage_status(db, user.id)
        assert status.limit == 5
        assert status.is_guest is False
        assert status.remaining == 0

        with pytest.raises(HTTPException) as exc:
            consume_ai_request(db, user.id, "solve")
        assert exc.value.status_code == 429
        assert "訪客" not in str(exc.value.detail)


def test_usage_api_reflects_identity(monkeypatch):
    monkeypatch.setattr(settings, "ai_quota_enabled", True)
    monkeypatch.setattr(settings, "ai_daily_limit_guest", 3)
    monkeypatch.setattr(settings, "ai_daily_limit_user", 40)
    Session = _engine_session()

    def _db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    with Session() as db:
        if not db.get(User, 1):
            db.add(User(id=1, name="Student", email="student@axiom.local"))
        user = User(
            name="A",
            email="a@example.com",
            password_hash=hash_password("password12"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id, user.email)

    client = TestClient(app)
    try:
        guest = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
        g = client.get("/api/ai/usage", headers={"X-Axiom-Guest": guest})
        assert g.status_code == 200
        assert g.json()["limit"] == 3
        assert g.json()["is_guest"] is True

        u = client.get("/api/ai/usage", headers={"Authorization": f"Bearer {token}"})
        assert u.status_code == 200
        assert u.json()["limit"] == 40
        assert u.json()["is_guest"] is False
    finally:
        app.dependency_overrides.clear()
