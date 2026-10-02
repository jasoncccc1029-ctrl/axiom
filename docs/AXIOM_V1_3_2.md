# Axiom v1.3.2 — Adaptive Question Engine

**Status:** Implemented  
**Version:** `1.3.2`  
**Depends on:** v1.3.1 (Problem Repository & Error DNA Foundation)

---

## Version map

| Version | Focus |
|---------|--------|
| v1.3.0 | Learning Efficacy Pilot |
| v1.3.1 | Problem Repository & Error DNA Foundation |
| v1.3.2 | Adaptive Question Engine |

---

## Architecture

```text
Student Learning State
        ↓
Adaptive Question Engine  (deterministic)
        ↓
Candidate Problems (Problem Bank)
        ↓
Filtering + Scoring
        ↓
Selected Problem + SelectionReason
        ↓
Tutor / Practice UI
        ↓
Attempt (problem_id)
        ↓
Verification / Outcome
        ↓
Mastery + Error DNA update
        ↓
Next selection
```

Core module: `backend/app/application/adaptive_question_engine.py`

Distinction:

| Layer | Role |
|-------|------|
| **RecommendationRecord** | What to study next (topic/concept strategy) |
| **Adaptive Question Engine** | Which concrete Problem to practice now |

LLM is **not** used for difficulty or problem selection.

---

## Selection Pipeline

1. Resolve target `subject` / `topic` / `concept` from request args, Student Learning State, Error DNA concept distribution, or active Recommendation.
2. Ask existing `DifficultyPolicy.decide(...)` for a recommended **level** (1–5).
3. Map level → float target via fixed `LEVEL_TO_FLOAT`, and a **learning-zone band** via `LEVEL_TO_BAND` (not a second policy).
4. Load candidate Problems from the bank (concept → topic → subject fallback).
5. Filter: this session, recently correct, last 3 attempts (same-item repair only if no other same-concept candidate).
6. Score remaining candidates deterministically; ties prefer never-attempted, then lowest `problem.id`.
7. Practice answers are compared against `Problem.answer` when both exist; otherwise student mark is the fallback.

Same Student State + same Problem pool + same policy ⇒ **same selection**.

---

## Candidate Filtering

Considered signals:

- subject / topic / concept alignment
- difficulty vs policy target
- recently seen / recently correct / recently failed
- Error DNA concepts and `metadata.error_targets`

Repair exception: a recently **failed** problem may reappear when its concept matches the current repair target.

---

## Scoring

Additive score (no randomness):

| Signal | Effect |
|--------|--------|
| Topic match | +40 / mismatch −20 |
| Concept match | +30 |
| Difficulty proximity | up to +25 (+5 if within ±0.2 of target) |
| Error pattern / error_targets match | +20 |
| Recent repetition | −penalty × 35 |

Machine-readable `SelectionReason` always includes:

- `topic_match`, `concept_match`, `difficulty_match`, `error_pattern_match`
- `recent_repetition_penalty`
- policy action / target difficulty
- `student_reasons` (UI-facing bullets)

Internal `score` is kept for tests/debug; Practice UI does not display it.

---

## Difficulty Policy integration

- Reuses `DifficultyPolicy` from v1.2+ unchanged.
- Engine does **not** invent a second mastery→difficulty formula.
- Policy outputs level 1–5; engine maps to Problem float targets only for bank matching.

---

## Error DNA integration

- Loads Error DNA for the resolved subject/topic.
- Prefers concepts from recent/repeated errors.
- Matches Problem `concept` and optional `metadata.error_targets` / `skills`.
- No hardcoded ErrorType → problem-type tables.

---

## API

```http
GET /api/student/next-problem?subject=&topic=&concept=&session_id=
```

Response (practice-safe — no answer/explanation):

```json
{
  "problem": {
    "id": 1,
    "question": "...",
    "subject": "mathematics",
    "topic": "trigonometry",
    "concept": "period",
    "difficulty": 0.55
  },
  "selection_reason": {
    "topic_match": true,
    "concept_match": true,
    "difficulty_match": true,
    "error_pattern_match": true,
    "recent_repetition_penalty": 0,
    "student_reasons": ["..."]
  },
  "message": null
}
```

Outcome recording continues via `POST /api/learning/outcome` with `problem_id`.

---

## Frontend flow

Tutor page **Practice** panel:

1. Fetch `/api/student/next-problem`
2. Show topic / concept / difficulty label + “Why this problem?”
3. **Start** reveals the question
4. Student answers / marks correct|incorrect → outcome with `problem_id`
5. Optional “Ask tutor for hint” uses TeachingMode (forces hint when Solve/Full would leak answers)
6. Refresh recommendation after outcome

---

## Tests

`tests/test_adaptive_question_engine.py`:

1. matching topic  
2. matching concept  
3. difficulty policy reuse  
4. avoid recently attempted  
5. Error DNA preference  
6. no candidate message  
7. deterministic reason  
8. old attempts without `problem_id`  
9. Attempt creation integration  
10. learning loop still works  
11. HTTP endpoint smoke (no answer leak)

---

## Known limitations

- Candidate pool is still capped at 200 per query.
- Same-item repair is last-resort only (when no other same-concept problem remains).
- Bank grading is a normalized string / numeric compare, not a CAS checker.
- No spaced-relearning scheduler, exam mode, or multi-model routing in this version.
- Hint turns do not write mastery until the student submits or marks the attempt.
