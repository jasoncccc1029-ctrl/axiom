# Adaptive learning

`AdaptiveTutor` combines selected mode with topic mastery, consecutive errors,
and spaced-review due dates. Two consecutive errors or an elapsed review
interval trigger:

```text
Review concept
→ Solve easy question
→ Solve medium question
→ Diagnose mistakes
→ Re-test later
```

It does not increase difficulty during this recovery path. High mastery can
produce a concise explanation and a harder application. With insufficient
evidence, the baseline policy is used and the API returns
`Not enough data yet.`
