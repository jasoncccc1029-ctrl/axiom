# Axiom Changelog

## Major personalization pass — 2026-10-11 (continued)

### Goal
Close remaining gaps so every Brain call is honest about learner understanding.

### Changes
- Agent: `problem_id` on run/outcome; resolve subject/topic from material + lean state; scope mastery/mistakes by subject; orchestrator only consults student model with focus or status/memory intent
- Context: explicit “no invent mastery” note when no scoped learner state
- Tutor: gate on `text_brain` (not Ollama-only); practice without materials; slim `next-problem` fetch; pass `problem_id`; empty-state CTAs
- Progress: Error DNA queried with top recommendation focus; practice link always resolvable
- Dashboard: mistake rows deep-link to Tutor

---

## Product-intent optimization — 2026-10-11

### Goal
Align the system with Axiom’s 初衷: understand the learner, then decide how to use the Brain — not a chatbot wrapper.

### Changes
- Solver: lean Context Policy + `StudentLearningState` / student model slice; request `topic`; `personalized` flag
- Shared `normalize_learning_label` (strip `general` etc.) for Agent + Solver
- UI: Solver focus fields + URL deep links; RecommendationCard → Tutor / Solver; Progress / Dashboard “為什麼”
- Health: canonical `text_brain` (+ legacy `ollama` alias)
- Docs: README → v1.3.2 product framing
- Tests: `test_problem_solver_context.py`, alias normalize, health `text_brain`

---

## Gemini Brain — 2026-10-04

### Goal
Add Google Gemini as a cloud text Brain (faster than local CPU Ollama).

### Changes
- `ProviderId.GEMINI` + `GeminiProvider` (generateContent via httpx)
- Factory / health / config: `AI_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`
- Tests: `test_provider_gemini.py`

---

## Optimization round — 2026-10-04 (continued)

### Goal
Outcome clarity in chat, fix polluted attempt answers, align subjects across evaluation/solver/mastery, connect materials → tutor.

### Changes
- Chat: inline outcome chips（已自動／手動記錄、需標記、無法記錄）
- Tutor: manual outcome uses **user** message as answer; evaluation session banner; `material_id` / `session_id` URL support
- Subject aliases helper + Agent entry canonicalize (`mathematics` → `高二數學`); UI defaults use Chinese subjects
- Evaluation: Chinese subjects, deep link to Tutor with session, warn before posttest
- Materials: practice link, empty copy, delete confirm, subject union
- Solver / TeachingMode: Chinese labels & subjects
- Tests: `test_subject_aliases.py`

---

## Autonomous optimization hour — 2026-10-04

### Goal
Close personalization friction: stop `"general"` topic pollution, make recommendations actionable, improve empty/error UX.

### Changes
- Backend: `_normalize_learning_label` — `topic/subject=general` treated as unspecified (`agent/service.py`)
- Tutor: focus subject/topic from URL + practice resolution; chat no longer defaults to `"general"`
- RecommendationCard / WeakTopicCard → deep link `/tutor?subject=&topic=`
- Dashboard / Progress: empty recommendation states with guidance
- Tutor: empty materials state; practice loading/error/message clarity; show current focus
- Solver: prefills subject from top recommendation; error panel; “在教學中繼續”
- Tests: general-topic does not auto-record Attempt

### Verification
- pytest + frontend build (see AUTONOMOUS report update)

---

## Autonomous session — 2026-10-02 (after Phase 4.1)

### Goal
Make Axiom act more like a personalized Learning Agent by **using** existing Student Model / Error DNA / Adaptive signals in Tutor context and making “why” visible in the UI — without rewriting the Learning Loop or adding new providers.

### Changes

#### Learning Agent capability
- **Context Policy (Phase 7-lite)** in `backend/app/agent/context.py`
  - Caps field sizes (weak/strong/mastery/errors/patterns)
  - Injects `topic_state`, adaptive `why`, `last_mistake_pattern`
  - Injects lean `[TRUSTED LEARNING STATE]` (mastery, recent performance, Error DNA slice)
- **AgentService** loads `StudentLearningStateService.get()` before chat when subject/topic present

#### UI / UX
- `RecommendationCard` shows **為什麼** + evidence (mastery / consecutive errors / difficulty)
- Dashboard “下一步” explains recommendations are state-driven
- Tutor practice strip shows **為什麼出這題** from `selection_reason`
- Tutor chat binds subject/topic from practice preview when available (less `"general"`)
- Progress page: Error DNA + recommendations with why + clearer section copy
- `LearningTrace` appends recommendation why next to action

#### Docs / tests
- `docs/AXIOM_PRODUCT_ARCHITECTURE.md` — Context Policy note
- `tests/test_context_builder.py` — context policy coverage

### Not changed
- Learning Loop / Mastery / Error DNA / AQE core write paths
- Provider layer (Ollama default, OpenAI available)
- No Anthropic / Phase 5
- No DB schema rewrite

### Verification
- See `docs/AUTONOMOUS_DEVELOPMENT_REPORT.md`
