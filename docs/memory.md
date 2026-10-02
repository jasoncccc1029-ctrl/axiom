# Student memory

`MemoryService` records minimal learning evidence:

- subject/topic and attempt correctness
- optional mistake pattern
- detected misconception and AI explanation
- teaching mode and duration
- smoothed mastery, evidence confidence, review date, and consecutive-error count

It does not collect additional personal data. `StudentProfile` aggregates
actual attempts and study time. `TopicMastery` drives adaptation and
recommendations. Use `POST /api/learning/record` to add evidence.
Use `/api/student`, `/api/topics`, `/api/mastery`, and `/api/memory` to query
the Student Model and repeated mistakes.
