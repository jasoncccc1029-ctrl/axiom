"""Public guest identity isolation."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.guest import get_or_create_guest_user
from app.main import app
from app.models import User
from app.services.seed import init_db


def test_guest_header_creates_isolated_user():
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
        init_db_session = db
        # ensure default user exists like production seed
        if not db.get(User, 1):
            db.add(User(id=1, name="Student", email="student@axiom.local"))
            db.commit()

    client = TestClient(app)
    guest = "11111111-2222-4333-a444-555555555555"
    r1 = client.get("/api/student", headers={"X-Axiom-Guest": guest})
    assert r1.status_code == 200
    uid1 = r1.json()["user_id"]
    assert uid1 != 1

    r2 = client.get("/api/student", headers={"X-Axiom-Guest": guest})
    assert r2.json()["user_id"] == uid1

    other = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
    r3 = client.get("/api/student", headers={"X-Axiom-Guest": other})
    assert r3.json()["user_id"] != uid1

    app.dependency_overrides.clear()


def test_get_or_create_guest_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
    with Session() as db:
        a = get_or_create_guest_user(db, "12345678-1234-4234-8234-123456789abc")
        b = get_or_create_guest_user(db, "12345678-1234-4234-8234-123456789abc")
        assert a.id == b.id
        assert a.email.startswith("guest-")
