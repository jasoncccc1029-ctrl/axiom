# Database and migrations

Axiom uses SQLite and SQLAlchemy. v1 tables are:

- `users`, `materials`, `document_chunks`
- `questions`, `attempts`, `learning_records`
- `student_profiles`, `topic_mastery`, `agent_traces`
- `subjects`, `topics`, `mistakes`, `learning_sessions`
- `conversations`, `messages`, `recommendations`
- `schema_migrations`

`run_migrations()` performs the idempotent v0.x-to-v1 foundation migration,
adds missing columns, creates new tables, and copies the legacy
`student_profile` row into `student_profiles`. It never drops the existing
database. Alembic is installed for subsequent generated revision files.

Back up `database/axiom.db` before production migrations.
# Database notes

SQLite database file is created automatically at:

`database/axiom.db`

On first backend startup, Axiom seeds:

- 1 local student user
- sample materials (高二數學 / 英文 / 物理)
- learning records + student profile

Schema tables:

- `users`
- `materials`
- `questions`
- `learning_records`
- `student_profile`
