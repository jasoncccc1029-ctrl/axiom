"""Small idempotent migration runner for the existing local SQLite database.

The project keeps SQL migrations explicit and versioned without recreating or
deleting the user's database. Alembic is included for future generated
migrations; this bootstrap handles upgrading the pre-v1 prototype safely.
"""

from __future__ import annotations

from sqlalchemy import Engine, inspect, text

from app.database import Base

MIGRATION_IDS = (
    "001_v1_foundation",
    "002_ultimate_student_model",
    "003_closed_loop_learning",
    "004_intelligent_adaptive_learning",
    "005_learning_efficacy_pilot",
    "006_problem_repository",
)

ALTER_COLUMNS: dict[str, dict[str, str]] = {
    "materials": {
        "mime_type": "VARCHAR(120)",
        "size_bytes": "INTEGER NOT NULL DEFAULT 0",
        "ingestion_status": "VARCHAR(40) NOT NULL DEFAULT 'pending'",
        "page_count": "INTEGER NOT NULL DEFAULT 0",
        "content_text": "TEXT",
        "updated_at": "DATETIME",
    },
    "questions": {
        "topic": "VARCHAR(160)",
    },
    "learning_records": {
        "topic": "VARCHAR(160)",
        "mode": "VARCHAR(40)",
        "trace_id": "VARCHAR(64)",
        "session_id": "INTEGER",
    },
    "attempts": {
        "detected_misconception": "VARCHAR(500)",
        "ai_explanation": "TEXT",
        "difficulty": "VARCHAR(40)",
        "conversation_id": "INTEGER REFERENCES conversations(id)",
        "session_id": "INTEGER",
        "trace_id": "VARCHAR(64)",
        "error_type": "VARCHAR(60)",
        "related_concept": "VARCHAR(160)",
        "expected_answer": "TEXT",
        "diagnosis_json": "TEXT NOT NULL DEFAULT '{}'",
        "problem_id": "INTEGER",
    },
    "topic_mastery": {
        "confidence": "FLOAT NOT NULL DEFAULT 0.0",
        "recommended_difficulty": "VARCHAR(40) NOT NULL DEFAULT 'current'",
        "difficulty_level": "INTEGER NOT NULL DEFAULT 3",
        "review_count": "INTEGER NOT NULL DEFAULT 0",
        "last_verified_at": "DATETIME",
        "last_practiced_at": "DATETIME",
        "next_review_at": "DATETIME",
    },
    "agent_traces": {
        "sources_json": "TEXT NOT NULL DEFAULT '[]'",
        "adaptive_json": "TEXT NOT NULL DEFAULT '{}'",
        "learning_trace_json": "TEXT NOT NULL DEFAULT '{}'",
        "conversation_id": "INTEGER REFERENCES conversations(id)",
        "session_id": "INTEGER",
        "question_id": "INTEGER",
    },
    "learning_sessions": {
        "subject": "VARCHAR(120)",
        "topic": "VARCHAR(160)",
        "status": "VARCHAR(40) NOT NULL DEFAULT 'active'",
        "conversation_id": "INTEGER",
    },
    "recommendations": {
        "session_id": "INTEGER",
        "evidence_json": "TEXT NOT NULL DEFAULT '{}'",
        "concept": "VARCHAR(160)",
        "strategy": "VARCHAR(60)",
        "difficulty_level": "INTEGER",
    },
}


def run_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version VARCHAR(80) PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
        )
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        for table, columns in ALTER_COLUMNS.items():
            if table not in tables:
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}'))

    # Creates new v1 tables and indexes, but never drops existing objects.
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        _copy_legacy_profile(connection)
        for version in MIGRATION_IDS:
            connection.execute(
                text("INSERT OR IGNORE INTO schema_migrations(version) VALUES (:version)"),
                {"version": version},
            )


def _copy_legacy_profile(connection) -> None:  # type: ignore[no-untyped-def]
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if "student_profile" not in tables or "student_profiles" not in tables:
        return
    new_count = connection.execute(text("SELECT COUNT(*) FROM student_profiles")).scalar_one()
    if new_count:
        return
    connection.execute(
        text(
            """
            INSERT INTO student_profiles (
                id, user_id, weak_subjects, strengths, total_study_minutes,
                total_questions, accuracy_rate, preferred_subjects, settings_json, updated_at
            )
            SELECT
                id, user_id, weak_subjects, strengths, total_study_minutes,
                total_questions, accuracy_rate, preferred_subjects, '{}', updated_at
            FROM student_profile
            """
        )
    )
