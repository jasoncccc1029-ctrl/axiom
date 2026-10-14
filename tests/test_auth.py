"""Email/password auth and session identity."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import create_access_token, hash_password, verify_password
from app.database import Base, get_db
from app.main import app
from app.models import User


def _client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)

    def _db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _db
    with TestingSession() as db:
        if not db.get(User, 1):
            db.add(User(id=1, name="Student", email="student@axiom.local"))
            db.commit()
    return TestClient(app), TestingSession


def test_password_hash_roundtrip():
    stored = hash_password("secret-pass-1")
    assert verify_password("secret-pass-1", stored)
    assert not verify_password("wrong", stored)


def test_register_login_me_and_identity():
    client, _ = _client()
    try:
        r = client.post(
            "/api/auth/register",
            json={
                "name": "小明",
                "email": "ming@example.com",
                "password": "password12",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "ming@example.com"
        token = data["access_token"]

        dup = client.post(
            "/api/auth/register",
            json={
                "name": "小明",
                "email": "ming@example.com",
                "password": "password12",
            },
        )
        assert dup.status_code == 409

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["id"] == data["user"]["id"]

        student = client.get("/api/student", headers={"Authorization": f"Bearer {token}"})
        assert student.status_code == 200
        assert student.json()["user_id"] == data["user"]["id"]

        # Auth wins over guest header
        guest = "11111111-2222-4333-a444-555555555555"
        mixed = client.get(
            "/api/student",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Axiom-Guest": guest,
            },
        )
        assert mixed.json()["user_id"] == data["user"]["id"]

        login = client.post(
            "/api/auth/login",
            json={"email": "ming@example.com", "password": "password12"},
        )
        assert login.status_code == 200
        assert login.json()["user"]["email"] == "ming@example.com"

        bad = client.post(
            "/api/auth/login",
            json={"email": "ming@example.com", "password": "wrong-password"},
        )
        assert bad.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_guest_still_works_without_auth():
    client, _ = _client()
    try:
        guest = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
        r = client.get("/api/student", headers={"X-Axiom-Guest": guest})
        assert r.status_code == 200
        assert r.json()["user_id"] != 1
    finally:
        app.dependency_overrides.clear()


def test_expired_or_tampered_token_rejected():
    client, Session = _client()
    try:
        with Session() as db:
            user = User(
                name="A",
                email="a@example.com",
                password_hash=hash_password("password12"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            uid = user.id
            email = user.email

        token = create_access_token(uid, email)
        parts = token.split(".")
        tampered = parts[0] + ".AAAA"
        r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered}"})
        assert r.status_code == 401
    finally:
        app.dependency_overrides.clear()
