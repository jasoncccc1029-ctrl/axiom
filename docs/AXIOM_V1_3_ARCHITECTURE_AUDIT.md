# Axiom v1.3 — Architecture & Evaluation Audit

**Date:** 2026-09-19  
**Scope:** Read-only inspection. No core rewrites.  
**Current `app_version`:** `1.3.0` (`backend/app/config.py`)

---

## 1. Current Architecture (high level)

```text
Frontend (Next.js)
  Dashboard / Materials / Tutor / Solver / Progress / Efficacy Pilot
        ↓
FastAPI routers
        ↓
AgentService ──→ ModelProvider (env: ollama | cloud)
        ↓
Orchestrator / Planner / Tools / Verifier
        ↓
LearningLoopService
  ├── ErrorIntelligence
  ├── DifficultyPolicy (deterministic)
  ├── TutorStrategyPolicy
  ├── MemoryService → Attempt / Mistake / TopicMastery
  ├── MasteryGraph → ConceptMastery
  └── AdaptiveTutor → RecommendationRecord
        ↓
AgentTrace (+ learning_trace_json)
```

**SQLite** via SQLAlchemy; migrations are custom ALTER + `create_all`  
(`backend/app/infrastructure/migrations/runner.py`: `001`–`005`).

---

## 2. Existing Models

| Model | Role | Notes |
|-------|------|--------|
| `User`, `StudentProfile` | Local single-user | `default_user_id=1` |
| `Material`, `DocumentChunk` | RAG materials | |
| `Question` | Ad-hoc question from Tutor turn | **Not** a reusable Problem bank |
| `Attempt` | Student outcome | FK: `question_id` only — **no `problem_id`** |
| `Mistake` | Pattern on failed attempt | |
| `TopicMastery`, `ConceptMastery` | Student model | Includes `next_review_at` (light SRS) |
| `RepeatedErrorPattern` | Aggregated error patterns | Closest to Error DNA |
| `LearningSession`, `LearningRecord` | Session / activity log | Lifecycle: started → active → ended |
| `RecommendationRecord` | Next-action recommendations | |
| `AgentTrace` | Full run trace | Has `provider`, `model` |
| `EvaluationSession`, `EvaluationAttempt` | Efficacy pilot | Isolated from mastery writes |
| `Conversation`, `Message` | Chat | |
| `Subject`, `Topic` | Catalog | |

**NOT FOUND:** `Problem`, Error DNA profile tables, Exam profile, Daily plan, Model capability registry.

---

## 3. Existing Learning Loop (IMPLEMENTED)

Already connected and tested through **v1.2 / v1.2.1**:

```text
Tutor / Agent run
  → Verification (outcome_automation)
  → Attempt (+ Mistake)
  → TopicMastery / ConceptMastery
  → DifficultyPolicy + TutorStrategy
  → Recommendation
  → Learning Trace (on AgentTrace)
```

Key modules (do **not** rewrite):

| Module | Path | Status |
|--------|------|--------|
| Learning loop | `application/learning_loop.py` | IMPLEMENTED |
| Memory / mastery write | `application/memory.py` | IMPLEMENTED |
| Outcome automation | `application/outcome_automation.py` | IMPLEMENTED (v1.2.1) |
| Error intelligence | `application/error_intelligence.py` | IMPLEMENTED (taxonomy + patterns) |
| Difficulty policy | `application/difficulty_policy.py` | IMPLEMENTED (deterministic) |
| Tutor strategy | `application/tutor_strategy.py` | IMPLEMENTED |
| Mastery graph | `application/mastery_graph.py` | IMPLEMENTED |
| Adaptive tutor | `application/adaptive.py` | IMPLEMENTED |
| Evaluation pilot | `application/evaluation.py` | IMPLEMENTED (v1.3 efficacy) |
| Problem solver | `application/problem_solver.py` | IMPLEMENTED (solve API only; no Problem repo) |

**Hard constraints preserved today:** LLM does not own mastery or difficulty; `memory.py` remains primary learning-state writer for attempts.

---

## 4. Existing APIs (selected)

| Area | Endpoints |
|------|-----------|
| Health | `/health`, `/api/system/health`, `/api/ollama/health`, `/api/vision/health` |
| Agent | `POST /api/agent/run`, `GET /api/agent/{trace_id}` |
| Learning | `/api/learning/outcome`, `/api/learning/trace/{id}`, `/api/learning/session/{id}/end`, `/api/learning/record` |
| Student | `/api/student`, `/api/mastery`, `/api/topics`, `/api/memory`, `/api/recommendations`, `/api/progress` |
| Evaluation | `/api/evaluation/start`, `pretest`, `posttest`, `begin-learning`, `{id}`, `{id}/metrics`, `{id}/report` |
| Solver | `POST /api/problems/solve` (name is legacy — **not** a Problem repository) |

**PARTIAL:** `EvaluationService.record_delayed_test` exists; **no HTTP route** yet.

---

## 5. Existing Frontend

| Page | Status |
|------|--------|
| Tutor | Teaching **mode** selector (Hint/Tutor/…); Ollama health badge; **no model selector** |
| Solver | One-shot solve |
| Progress | Mastery / weak topics |
| Efficacy Pilot (`/evaluation`) | Pre → learn → post → observed metrics + report |
| Materials / Dashboard | Present |

**NOT FOUND:** Training Mode UI, Exam Mode, Daily Planner, Multi-model selector.

---

## 6. ModelProvider (current)

```text
settings.ai_provider → get_provider()
  ├── ollama  → OllamaProvider (live)
  └── cloud   → CloudProvider (stub / NotImplemented)
```

| Capability | Status |
|------------|--------|
| Provider abstraction | EXISTS (`providers/base.py`) |
| Per-request model override | NOT FOUND (`AgentRunRequest` has no `model`) |
| Model Router (task-aware) | NOT FOUND |
| Capability registry | NOT FOUND |
| AgentTrace `provider`/`model` | EXISTS |
| Frontend Model Selector | NOT FOUND |

---

## 7. Existing Tests

| Suite | Focus |
|-------|--------|
| `test_closed_loop_learning.py` | Closed-loop A–E |
| `test_intelligent_adaptive_v12.py` | Adaptive / error / graph F–N |
| `test_outcome_automation_v121.py` | Outcome automation + idempotency |
| `test_evaluation_v13.py` | Efficacy pilot (isolated evaluation data) |
| Agent / memory / adaptive / API / vision / tools | Supporting coverage |

Last known full suite (prior session): **104 passed, 4 skipped** (re-run before any v1.3.1 implementation).

---

## 8. Requirement Checklist (Master Prompt)

| Requirement | Status | Evidence / gap |
|-------------|--------|----------------|
| Closed-loop learning | **IMPLEMENTED** | v1.1–v1.2.1 |
| Outcome automation / idempotency | **IMPLEMENTED** | v1.2.1 |
| Evaluation pre/post pilot | **IMPLEMENTED** | EvaluationSession + UI (labeled 1.3.0 in config) |
| **Problem repository** | **NOT FOUND** | Only ephemeral `Question` |
| **Attempt → Problem** | **NOT FOUND** | Only `question_id` |
| Error DNA | **PARTIAL** | ErrorType + RepeatedErrorPattern; no learner Error DNA aggregate |
| Clean Student Context | **PARTIAL** | Snapshots in traces/context; not a dedicated lean DTO |
| Adaptive Question Engine | **PARTIAL** | Difficulty/strategy/recs exist; no next-problem selector from bank |
| Spaced Relearning | **PARTIAL** | `next_review_at` + REVIEW strategy; not full SRS product |
| Training Mode | **NOT FOUND** | |
| Error Challenge product mode | **PARTIAL** | Strategy `CHALLENGE` / ERROR_DIAGNOSIS; no dedicated mode |
| Exam Mode | **NOT FOUND** | |
| Daily Planner | **NOT FOUND** | |
| Multi-model + Router + Selector | **PARTIAL** | Env factory + trace metadata only |
| AgentTrace model metadata | **IMPLEMENTED** | `provider`, `model` |

---

## 9. Version Naming Collision (important)

| Source | Meaning of “v1.3.0” |
|--------|---------------------|
| **Current repo** | Learning Efficacy Pilot already shipped as `app_version=1.3.0` |
| **Master prompt** | Proposes v1.3.0 = Problem / Error DNA / Student State foundation |

**Recommendation:** Keep shipped efficacy pilot as **1.3.0**. Next implementation slice should be:

```text
v1.3.1 — Problem Repository & Error DNA Foundation
```

Do **not** reset version or rewrite the evaluation pilot.

---

## 10. Missing Components (priority for next confirmed slice)

### Must-have for true Problem-centric learning (proposed v1.3.1)

1. **`Problem` entity + repository** (bank independent of chat `Question`)
2. **`Attempt.problem_id`** (nullable FK; keep `question_id` for backward compatibility)
3. **Error DNA foundation** (aggregate profile per user/topic/concept — built from existing Attempt/Mistake/RepeatedErrorPattern; do not replace ErrorIntelligence)
4. **Lean Student Learning State DTO** for Agent context (topic/concept/mastery/recent errors/difficulty — no full chat dump)

### Explicitly defer (later versions)

| Slice | Contents |
|-------|----------|
| v1.3.2 | Adaptive Question Engine (select next Problem by policy) |
| v1.3.3 | Training Mode / Error Challenge UX |
| v1.3.4 | Multi-model selector + capability registry + optional router |
| v1.4.x | Exam Mode, Daily Planner; deepen efficacy (item bank linkage, delayed-test API route) |

---

## 11. Potential Breaking Changes (avoid)

| Risk | Mitigation |
|------|------------|
| Replacing `Question` with `Problem` | Keep both; Tutor still creates Question; Problem is bank |
| Changing mastery formula | **Forbidden** without separate milestone |
| LLM owns difficulty | **Forbidden** |
| Evaluation writes into Attempt/TopicMastery | Already isolated — keep it |
| Dropping existing APIs | **Forbidden** — additive only |
| Unique constraint races on Attempt.trace_id | App-level idempotency exists; DB unique is optional later |

---

## 12. Recommended v1.3.1 Changes (minimal, additive)

### Database

```text
problems
  id, external_key?, question, answer, explanation,
  subject, topic, concept, difficulty (float or level),
  metadata_json, created_at

attempts
  ADD problem_id NULLABLE FK → problems.id
```

Migration: `006_problem_repository` via existing runner pattern + `create_all`.

### Backend (new / thin)

- `application/problem_repository.py` — CRUD + query by subject/topic/difficulty
- Extend ErrorIntelligence / new `error_dna.py` — **read aggregate** API from existing tables first; optional `error_dna_json` on profile only if needed
- `student_context.py` — build lean context from TopicMastery + recent Attempts (no prompt rewrite of Orchestrator beyond injecting lean context)

### API (additive)

```text
POST   /api/problems
GET    /api/problems
GET    /api/problems/{id}
GET    /api/student/error-dna?subject=&topic=
GET    /api/student/learning-state?subject=&topic=
```

Optional: allow `problem_id` on `/api/learning/outcome`.

### Frontend

- Minimal Problems admin or Materials-adjacent list (**not** required for first backend-only PR)
- Tutor: optional “practice from bank” later (v1.3.2)

### Tests

- Problem CRUD + Attempt.problem_id link
- Error DNA aggregate from seeded mistakes
- Learning-state DTO shape
- Full regression: closed-loop + v12 + v121 + evaluation v13

### Explicitly out of scope for v1.3.1

- Multi-model UI/router  
- Exam / Daily Planner  
- Rewriting evaluation  
- Replacing DifficultyPolicy with LLM  

---

## 13. Files Likely Touched (when approved)

```text
backend/app/models.py
backend/app/infrastructure/migrations/runner.py
backend/app/application/problem_repository.py          (new)
backend/app/application/error_dna.py                   (new, thin)
backend/app/application/student_context.py             (new, thin)
backend/app/application/memory.py                      (optional problem_id pass-through)
backend/app/application/learning_loop.py               (optional problem_id on outcome)
backend/app/routers/__init__.py
backend/app/config.py                                  (version → 1.3.1)
tests/test_problem_repository_v131.py                  (new)
docs/CHANGELOG.md or docs update                       (if present)
```

---

## 14. Evaluation Architecture (already present)

```text
EvaluationSession (group_arm: axiom | control)
  → EvaluationAttempt (pretest | posttest | delayed)
  → snapshots of mastery / weak concepts (JSON)
  → metrics + Learning Report (observed, not causal)

Formal learning data remains in Attempt / TopicMastery
Evaluation data MUST stay separate (already enforced in tests)
```

Next efficacy improvements (later): link EvaluationAttempt to `Problem.id`; expose delayed-test HTTP route; never claim causation without control comparison (`causal_claim_allowed=false` already).

---

## 15. Decision Gate

**Audit complete. No core implementation started.**

Await confirmation to proceed with **v1.3.1 — Problem Repository & Error DNA Foundation** as specified in §12.

If preferred naming differs (e.g. call next slice `v1.4.0`), specify before coding.

---

## 16. v1.3.1 Implementation Status

**Status: IMPLEMENTED** (2026-09-19)

| Item | Result |
|------|--------|
| `Problem` model | Done — `problems` table; `Question` retained |
| `Attempt.problem_id` | Done — nullable FK; old rows OK |
| Problem repository | Done — create/get/list/update |
| Error DNA aggregation | Done — read-model over Attempt/Mistake/RepeatedErrorPattern |
| Student Learning State DTO | Done — lean nullable fields |
| APIs | Done — `/api/problem-bank*`, `/api/student/error-dna`, `/api/student/learning-state` |
| Migration `006_problem_repository` | Done — additive |
| Version | `1.3.1` (v1.3.0 efficacy semantics preserved) |
| Docs | `docs/AXIOM_V1_3_1.md` |

Not implemented (deferred by design): Adaptive Question Engine, Training/Exam/Daily Planner, Multi-model UI/router.
