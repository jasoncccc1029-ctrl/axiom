# Agent Core

`AgentService` coordinates `Planner`, `ToolRouter`, `ContextBuilder`,
`Verifier`, and the tutor model.

Every run creates a UUID `trace_id`, a bounded plan, tool-call summaries,
verification status, latency, provider/model metadata, and a final answer.
Raw user input is not stored in trace metadata. The final answer is stored so
the trace endpoint can reproduce the execution result.

Endpoints:

- `POST /api/agent/run`
- `GET /api/agent/{trace_id}`

The orchestrator classifies intent first, then selects only the required
route: Tutor, Solver, RAG, Memory, or Student Model. It does not fan out
every request to every subsystem.

Teaching modes are `hint`, `socratic`, `tutor`, `step_by_step`, `concept`,
`error_diagnosis`, `direct_solve`, and `full_solution`.
