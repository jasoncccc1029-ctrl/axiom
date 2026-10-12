# AUTONOMOUS DEVELOPMENT REPORT

**Period:** 2026-10-02 → 2026-10-04 (post Phase 4.1 + optimization hour)  
**Operator:** Cursor Agent (autonomous)  
**Product north star:** Personalized AI Learning Agent that understands the learner and adapts teaching — not a chatbot wrapper.

---

## 2026-10-11 Product-intent (初衷) optimization

### Done
1. Solver wired through lean Context Policy (`StudentLearningState` + student model)
2. `topic` on solve request; placeholder labels shared via `normalize_learning_label`
3. Closed-loop UI: Progress / Dashboard why; Recommendation → Tutor + Solver deep links
4. Health: `text_brain` canonical, `ollama` kept as alias
5. README aligned to v1.3.2 / Brain ≠ product

### Major pass (same day)
1. Agent `problem_id` + material/lean focus resolve; scoped mastery; honest orchestrator consult flags
2. Tutor: `text_brain` gate, practice without materials, slim next-problem, empty-state CTAs
3. Progress Error DNA with recommendation focus; Dashboard mistake → Tutor links

### Verification
```text
pytest: 182 passed, 4 skipped
frontend build: OK
```

### Still open
- Phase 5 Anthropic
- Model Selector UI
- Optional: material re-ingest endpoint
- Deeper Phase 7 StudentContext productization beyond lean caps

---

## 2026-10-04 Optimization rounds

### Round A
1. Stop `"general"` topic pollution
2. Recommendations / weak topics → Tutor deep links
3. Empty / error UX
4. Solver handoff

### Round B (continued)
1. Chat outcome chips（已自動／手動／需標記）
2. Manual outcome uses **user** answer (not assistant text)
3. Evaluation → Tutor with `session_id`; Chinese subjects; posttest guard
4. Materials → Tutor practice link; empty copy; delete confirm
5. Agent subject alias (`mathematics` → `高二數學`); TeachingMode 中文
6. Tests: subject aliases

### Verification (historical)
```text
pytest: 168 passed, 4 skipped
frontend build: OK
```

---

## 期間完成的工作

1. **Personalization gap audit** — confirmed Learning Core already stores mastery / Error DNA / recommendations, but Tutor prompt + UI largely ignored them.
2. **Context Policy (Phase 7-lite)** — capped, trusted learner state injected into Tutor context before `model_provider.chat()`.
3. **UI “為什麼” surfaces** — Dashboard / Progress recommendations, Error DNA on Progress, Tutor practice selection reason, Learning Trace next-step why; Tutor chat prefers practice topic over `"general"`.
4. **Docs** — `CHANGELOG.md`, architecture note, this report.
5. **Verification** — full pytest + frontend build.

---

## 核心功能變化

| Area | Change |
|------|--------|
| Tutor personalization | Context now includes topic_state, adaptive why, lean StudentLearningState + Error DNA slice |
| Learning Loop write path | **Unchanged** |
| Mastery / AQE / Error DNA writers | **Unchanged** |
| Providers | **Unchanged** (Ollama default, OpenAI available) |

Flow after change:

```text
Student State (existing services)
  → Context Policy (caps + trust tags)
  → ModelProvider.chat(message, context)
  → Learning outcome (existing loop)
```

---

## UI / UX 改善

- Dashboard「下一步」：顯示推薦原因與掌握度／連續錯誤證據
- Tutor 練習題：顯示「為什麼出這題」
- Learning Trace：下一步附帶 why
- 文案強調建議來自學習狀態，非隨機

---

## Learning Agent 能力改善

**Before:** Tutor saw only weak/strong lists + thin adaptive knobs; UI hid recommendation why.  
**After:** Tutor prompt can address consecutive errors, last mistake pattern, Error DNA patterns, adaptive why, and recommended difficulty — using data Axiom already computed.

This strengthens: Observe → Understand → Adapt → Teach (without inventing new learning schemas).

---

## Provider 狀態

```text
Default Brain: Ollama
Available Brain: OpenAI (Responses API, backend OPENAI_API_KEY)
Phase 4 / 4.1: frozen
Phase 5 Anthropic: not started
```

---

## 測試結果

```text
pytest: 165 passed, 4 skipped
```

New: `tests/test_context_builder.py`

---

## Frontend Build 結果

```text
next build: OK
```

---

## 發現的問題（仍存在）

1. Tutor chat often uses subject/topic `"general"` — weakens consult_student_model / topic_state usefulness for free chat (practice path is better).
2. Progress page still does not show Error DNA API or recommendation why (Dashboard/Tutor improved; Progress less so).
3. System health field is still named `ollama` in the JSON schema while it now means “text brain” (Phase 4.1 tradeoff to keep schema).
4. Low-priority Phase 4 leftovers: usage field, error subclass symmetry, base.solve identity.

---

## 尚未解決的問題 / 刻意未做

- AnthropicProvider (Phase 5)
- Full ModelRouter / Model Selector UI (Phase 6 / 9)
- Full StudentContext productization beyond lean Context Policy
- Solver StudentContext wiring
- DB / Learning Loop redesign
- Auth, PostgreSQL, Docker

---

## 目前架構狀態

```text
Learning Core: stable
Provider Abstraction: stable (Phase 4 + 4.1)
Tutor Context Policy: improved (7-lite)
UI personalization signals: improved (partial)
Roadmap marker: Phase 4 done; Phase 5 not started
```

---

## 修改檔案清單

```text
backend/app/agent/context.py
backend/app/agent/service.py
frontend/src/components/learning/RecommendationCard.tsx
frontend/src/components/learning/LearningTrace.tsx
frontend/src/app/page.tsx
frontend/src/app/tutor/page.tsx
frontend/src/app/progress/page.tsx
frontend/src/lib/api.ts
tests/test_context_builder.py
docs/AXIOM_PRODUCT_ARCHITECTURE.md
docs/CHANGELOG.md
docs/AUTONOMOUS_DEVELOPMENT_REPORT.md
```

```text
pytest: 165 passed, 4 skipped
frontend build: OK
```

---

## 下一階段最值得做的事（建議優先序）

1. **Tutor subject/topic binding** — stop defaulting free chat to `general`; carry active topic from practice / recommendations into AgentRun.
2. **Progress page Error DNA + recommendation why** — complete the “我哪裡錯／為什麼這樣建議／有沒有變好” loop in one place.
3. **Phase 5 AnthropicProvider** — only after you confirm; Learning Core ready.
4. **Model Selector UI** — Brain picker only; keep personalization as the product.

---

## 原則遵守確認

- No Learning Loop rewrite  
- No provider-as-product  
- No irreversible schema / DB / frontend architecture rewrite  
- Changes judged by: does Axiom understand the learner better? → Yes (context + UI why)
