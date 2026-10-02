# Axiom v1.3.1 — Problem Repository & Error DNA Foundation

**Status:** IMPLEMENTED  
**Version:** `1.3.1`  
**Preserves:** `v1.3.0` Learning Efficacy Pilot semantics

---

## Architecture Decision

v1.3.1 establishes a clean data foundation for later adaptive selection:

```text
Problem (bank)
   ↓
Attempt.problem_id (nullable FK)
   ↓
Mistake / RepeatedErrorPattern (existing)
   ↓
Error DNA (read-model aggregation)
   ↓
Student Learning State (lean DTO)
```

### Decisions

1. **Keep `Question`** — chat-turn questions remain; `Problem` is the reusable bank. No drop/migration of `Question`.
2. **`Attempt.problem_id` is nullable** — old attempts without a bank link remain valid.
3. **Error DNA is aggregation-only** — does not replace or fork `ErrorIntelligence`. Sources: Attempt, Mistake, RepeatedErrorPattern with explicit evidence refs.
4. **Student Learning State is lean** — for Agent decisions; does not dump chat history; missing fields stay null/empty (no invented mastery).
5. **API prefix `/api/problem-bank`** — avoids colliding with existing `POST /api/problems/solve`.
6. **Out of scope** — Adaptive Question Engine, Training/Exam/Daily Planner, Multi-model UI, LLM difficulty, evaluation core changes.

---

## New Models

### `Problem`

| Field | Notes |
|-------|--------|
| id | PK |
| external_key | optional unique |
| question, answer, explanation | text |
| subject, topic, concept | taxonomy |
| difficulty | float 0–1 |
| metadata_json | JSON object |
| created_at, updated_at | timestamps |

### `Attempt.problem_id`

Nullable FK → `problems.id` (additive via migration `006_problem_repository`).

---

## New Modules

| Module | Role |
|--------|------|
| `application/problem_repository.py` | create / get / list / update |
| `application/error_dna.py` | Error DNA read-model |
| `application/student_learning_state.py` | Lean learning-state DTO |

---

## New APIs

```text
POST   /api/problem-bank
GET    /api/problem-bank?subject=&topic=&concept=
GET    /api/problem-bank/{id}
PATCH  /api/problem-bank/{id}

GET    /api/student/error-dna?subject=&topic=
GET    /api/student/learning-state?subject=&topic=&concept=
```

Optional: `problem_id` on learning record / outcome payloads (additive).

---

## Migration

`006_problem_repository`

- Adds `attempts.problem_id` via ALTER when missing
- Creates `problems` via `Base.metadata.create_all`
- No deletes; no efficacy schema changes
- Framework has no downgrade path (project convention); forward additive only

---

## Tests

`tests/test_problem_repository_v131.py`

- model, repository, attempt relation (with/without problem_id)
- error DNA evidence
- student learning state
- migration 006 on legacy + fresh DB
- API endpoints

---

## Next (not started)

```text
v1.3.2 Adaptive Question Engine
v1.3.3 Training / Challenge Mode
v1.3.4 Multi-Model
…
```
