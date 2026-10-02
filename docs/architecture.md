# Axiom v1.0 architecture

Request flow:

```text
Next.js UI
  -> FastAPI API
  -> Application Services
  -> Agent Core
  -> Providers / Tools
  -> SQLite / Ollama / safe file storage
```

FastAPI dependencies resolve long-lived provider clients from `AppContainer`.
Routers depend on abstractions and application services, not Ollama classes.
The database engine, HTTP client and embedding provider are initialized once.

Trust boundaries:

- System policy: trusted.
- User input and uploaded documents: untrusted data.
- Tool output: semi-trusted evidence.
- Document excerpts are delimited and cannot replace system instructions.

The Agent is bounded by `MAX_AGENT_STEPS`; it has no recursive execution loop.
# Architecture (v0.1)

```
studyos/
├── frontend/          # Next.js + TypeScript + Tailwind
├── backend/           # FastAPI + SQLAlchemy
├── database/          # SQLite file (axiom.db)
├── tests/             # API tests
└── docs/              # Extra documentation
```

## AI provider

```
ModelProvider
├── OllamaProvider   # default path (mock enabled in v0.1)
└── CloudProvider    # interface only
```

Set `USE_MOCK_AI=false` in backend env to call a local Ollama instance.

## Intentionally deferred

RAG, vector DB, long-term memory, multi-agent orchestration, LoRA, custom LLM training.
