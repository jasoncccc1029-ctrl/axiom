"""Axiom v1.3.1 — Problem Repository & Error DNA Foundation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.error_dna import ErrorDNAService  # noqa: E402
from app.application.learning_loop import (  # noqa: E402
    LearningLoopService,
    LearningOutcomeRequest,
)
from app.application.memory import LearningRecordRequest, MemoryService  # noqa: E402
from app.application.problem_repository import (  # noqa: E402
    ProblemCreate,
    ProblemRepository,
    ProblemUpdate,
)
from app.application.student_learning_state import StudentLearningStateService  # noqa: E402
from app.database import Base  # noqa: E402
from app.infrastructure.migrations.runner import run_migrations  # noqa: E402
from app.models import Attempt, Problem, StudentProfile, User  # noqa: E402


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(User(id=1, name="Student", email="v131@example.local"))
    db.add(StudentProfile(user_id=1))
    db.commit()
    return db


def test_problem_model():
    db = make_db()
    try:
        row = Problem(
            question="若 f(x)=x²-4x+3，求其最小值。",
            answer="-1",
            explanation="vertex",
            subject="mathematics",
            topic="quadratic",
            concept="vertex_min",
            difficulty=0.45,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        assert row.id > 0
        assert row.answer == "-1"
        assert row.updated_at is not None
    finally:
        db.close()


def test_problem_repository():
    db = make_db()
    try:
        repo = ProblemRepository(db)
        created = repo.create(
            ProblemCreate(
                question="1+1=?",
                answer="2",
                subject="mathematics",
                topic="arithmetic",
                concept="addition",
                difficulty=0.2,
                metadata={"source": "unit-test"},
            )
        )
        assert created.id
        assert created.metadata["source"] == "unit-test"
        fetched = repo.get(created.id)
        assert fetched is not None
        assert fetched.question == "1+1=?"
        listed = repo.list(subject="mathematics", topic="arithmetic")
        assert len(listed) == 1
        updated = repo.update(
            created.id, ProblemUpdate(difficulty=0.3, concept="basic_addition")
        )
        assert updated is not None
        assert updated.difficulty == 0.3
        assert updated.concept == "basic_addition"
    finally:
        db.close()


def test_attempt_problem_relation_and_old_attempt_without_problem_id():
    db = make_db()
    try:
        repo = ProblemRepository(db)
        problem = repo.create(
            ProblemCreate(
                question="2+2",
                answer="4",
                subject="mathematics",
                topic="arithmetic",
            )
        )
        memory = MemoryService(db)
        # Old-style attempt: no problem_id
        old = memory.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="arithmetic",
                correct=True,
                mode="tutor",
            )
        )
        attempt_old = db.get(Attempt, old.attempt_id)
        assert attempt_old is not None
        assert attempt_old.problem_id is None

        linked = memory.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="arithmetic",
                correct=False,
                mistake_pattern="calc slip",
                error_type="CALCULATION_ERROR",
                mode="tutor",
                problem_id=problem.id,
            )
        )
        attempt_new = db.get(Attempt, linked.attempt_id)
        assert attempt_new is not None
        assert attempt_new.problem_id == problem.id

        # Learning loop still works without problem_id
        loop = LearningLoopService(db)
        outcome = loop.record_outcome(
            LearningOutcomeRequest(
                subject="mathematics",
                topic="arithmetic",
                correct=True,
                mode="tutor",
            )
        )
        assert outcome.attempt.attempt_id
        assert db.get(Attempt, outcome.attempt.attempt_id).problem_id is None
    finally:
        db.close()


def test_error_dna():
    db = make_db()
    try:
        memory = MemoryService(db)
        for _ in range(2):
            memory.record(
                LearningRecordRequest(
                    subject="mathematics",
                    topic="quadratic",
                    correct=False,
                    mistake_pattern="vertex confusion",
                    error_type="MISCONCEPTION",
                    related_concept="vertex_min",
                    mode="tutor",
                )
            )
        memory.record(
            LearningRecordRequest(
                subject="mathematics",
                topic="quadratic",
                correct=False,
                mistake_pattern="sign error",
                error_type="SIGN_ERROR",
                related_concept="vertex_min",
                mode="tutor",
            )
        )
        dna = ErrorDNAService(db).profile(subject="mathematics", topic="quadratic")
        assert dna.evidence_count > 0
        assert dna.most_frequent_error_types
        assert dna.recent_errors
        assert dna.topic_distribution
        assert dna.concept_distribution
        assert any(item.error_type == "MISCONCEPTION" for item in dna.most_frequent_error_types)
        # evidence references present
        assert dna.most_frequent_error_types[0].evidence
        assert dna.most_frequent_error_types[0].evidence[0].source in {
            "attempt",
            "mistake",
        }
    finally:
        db.close()


def test_student_learning_state():
    db = make_db()
    try:
        memory = MemoryService(db)
        memory.record(
            LearningRecordRequest(
                subject="physics",
                topic="force",
                correct=True,
                mode="tutor",
            )
        )
        memory.record(
            LearningRecordRequest(
                subject="physics",
                topic="force",
                correct=False,
                mistake_pattern="free body",
                error_type="CONCEPT_GAP",
                related_concept="newton2",
                mode="tutor",
            )
        )
        state = StudentLearningStateService(db).get(
            subject="physics", topic="force"
        )
        assert state.student_id == 1
        assert state.current_topic == "force"
        assert state.mastery is not None
        assert state.recent_performance.get("recent_attempt_count", 0) >= 1
        assert isinstance(state.recent_errors, list)
        assert state.current_difficulty is not None or state.difficulty_level is not None
        # no invented mastery when empty topic
        empty = StudentLearningStateService(db).get(
            subject="chemistry", topic="unknown_topic_xyz"
        )
        assert empty.mastery is None
    finally:
        db.close()


def test_migration_006_problem_repository_additive():
    engine = create_engine("sqlite:///:memory:")
    # Simulate pre-006 DB: create core tables without problem_id
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(120) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    created_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE attempts (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    question_id INTEGER,
                    subject VARCHAR(120),
                    topic VARCHAR(160),
                    answer TEXT,
                    is_correct BOOLEAN,
                    mode VARCHAR(40) DEFAULT 'tutor',
                    created_at DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO users(id, name, email) VALUES (1, 'S', 'm006@example.local')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO attempts(id, user_id, subject, topic, is_correct, mode) "
                "VALUES (1, 1, 'math', 'a', 1, 'tutor')"
            )
        )

    run_migrations(engine)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert "problems" in tables
    attempt_cols = {c["name"] for c in inspector.get_columns("attempts")}
    assert "problem_id" in attempt_cols

    with engine.begin() as conn:
        versions = {
            row[0]
            for row in conn.execute(text("SELECT version FROM schema_migrations")).all()
        }
        assert "006_problem_repository" in versions
        # Old row still readable; problem_id null
        row = conn.execute(
            text("SELECT id, problem_id FROM attempts WHERE id = 1")
        ).one()
        assert row[0] == 1
        assert row[1] is None

    # Fresh DB path
    engine2 = create_engine("sqlite:///:memory:")
    run_migrations(engine2)
    assert "problems" in set(inspect(engine2).get_table_names())


def test_problem_api_and_student_endpoints():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services.seed import init_db

    init_db()
    with TestClient(app) as client:
        created = client.post(
            "/api/problem-bank",
            json={
                "question": "API problem?",
                "answer": "yes",
                "subject": "mathematics",
                "topic": "api",
                "difficulty": 0.4,
            },
        )
        assert created.status_code == 200, created.text
        pid = created.json()["id"]
        listed = client.get("/api/problem-bank", params={"subject": "mathematics"})
        assert listed.status_code == 200
        assert any(item["id"] == pid for item in listed.json())
        got = client.get(f"/api/problem-bank/{pid}")
        assert got.status_code == 200
        patched = client.patch(
            f"/api/problem-bank/{pid}", json={"difficulty": 0.55}
        )
        assert patched.status_code == 200
        assert patched.json()["difficulty"] == 0.55

        dna = client.get("/api/student/error-dna")
        assert dna.status_code == 200
        assert "most_frequent_error_types" in dna.json()

        state = client.get(
            "/api/student/learning-state",
            params={"subject": "mathematics", "topic": "api"},
        )
        assert state.status_code == 200
        body = state.json()
        assert body["student_id"] == 1
        assert "recent_performance" in body
