# Axiom Product Architecture

**Status:** Canonical product principles (Phase 2+)  
**Audience:** Anyone extending ModelProvider, Context, or Agent behaviour

---

## What Axiom is (and is not)

```text
Axiom ≠ AI Chatbot
Axiom ≠ “pick GPT or Claude and chat”

Axiom = Student Model
      + Memory
      + Context
      + Policy
      + Agent
      + Learning Loop

Model  = Brain
User   = Learner
```

**Core value:**  
As a learner uses Axiom, the system understands them better — mastery, errors,
history, preferences — and uses that understanding to decide **how** to employ
an AI brain to help them.

Choosing Ollama / OpenAI / Anthropic only selects the **Brain**.  
It must never replace Axiom’s responsibility to understand the Learner.

---

## Target control flow

```text
User (Learner)
  ↓
Axiom Agent
  ↓
Student Model  (mastery, learning state, preferences)
  ↓
Context Builder + Context Policy   ← compact StudentContext (not the whole DB)
  ↓
Learning Policy  (TutorStrategy / AdaptiveTutor / Difficulty — existing)
  ↓
Model Router     (Phase 6: user-selected provider/model first)
  ↓
┌─────────────┬─────────────┬─────────────┐
│ Ollama      │ OpenAI      │ Anthropic   │
│ Local Brain │ Cloud Brain │ Cloud Brain │
└─────────────┴─────────────┴─────────────┘
  ↓
Response
  ↓
Learning Outcome → Mastery / Error DNA / Student State
  ↓
Axiom understands the learner again
```

Vision (images) remains on `VisionProvider` (currently Ollama + moondream).  
Text Brains implement `ModelProvider`.

---

## Non-negotiable boundaries

1. **No frontend API keys** — secrets only in backend environment.
2. **No SDK imports in business logic** — Agent / Tutor / Solver / Learning Loop
   depend on `ModelProvider` + `app.providers.types` only.
3. **Do not rewrite** Learning Loop, Mastery, Error DNA, Adaptive Question Engine,
   Problem Repository, or Attempt semantics when adding providers.
4. **StudentContext** must be built via Context Policy (field caps, top-N errors,
   recent attempts summary). Never dump the entire database into the prompt.
5. **Model selector UI** is a Brain picker, not the product. Personalization
   (StudentContext + Policy) is the product.

---

## ModelProvider (Phase 2 contract)

| Piece | Role |
|-------|------|
| `ProviderId` | `ollama` \| `openai` \| `anthropic` |
| `ModelRef` | `{provider, model}` identity |
| `GenerateRequest` / `GenerateResponse` | Unified generate API |
| `ModelProvider.generate()` | Required adapter entry |
| `ModelProvider.chat()` / `solve()` | Helpers for existing Agent / Solver |
| `ProviderError` hierarchy | Unavailable / missing model / timeout / not configured |

Adapters live under `backend/app/providers/`.  
Factory (`get_provider`) returns the process-default Brain; ModelRouter (later)
will resolve per-user preference without touching the Learning Loop.

---

## Roadmap (do not skip phases)

1. ~~Architecture audit~~  
2. ~~ModelProvider interface~~  
3. ~~OllamaProvider refactor (reference Brain)~~ ← current  
4. OpenAIProvider (Responses API)  
5. AnthropicProvider  
6. ModelRouter (user selection first)  
7. StudentContext + Context Policy  
8. Tutor integration  
9. Model Selector UI  
10. Tests / regression  

### Phase 3 Ollama identity (canonical)

| Field | Value | Use |
|-------|--------|-----|
| `name` / `provider_id` | `ollama` | AgentTrace.provider, APIs |
| `model` | e.g. `llama3.2:latest` | AgentTrace.model, config `OLLAMA_MODEL` |
| `identity` / `model_ref().key()` | `ollama:llama3.2:latest` | Stable cross-layer key |
| `display_name` | `Axiom Local · llama3.2:latest` | UI / human logs |

Flow: `chat`/`solve` → `generate()` → Ollama HTTP → `GenerateResponse`.  


---

## Related modules (do not casually rewrite)

| Concern | Module |
|---------|--------|
| Learning outcomes | `application/learning_loop.py` |
| Mastery writes | `application/memory.py` |
| Error DNA | `application/error_dna.py` |
| Next problem | `application/adaptive_question_engine.py` |
| Agent | `agent/service.py` |
| Thin context today | `agent/context.py` (to be extended in Phase 7–8) |
