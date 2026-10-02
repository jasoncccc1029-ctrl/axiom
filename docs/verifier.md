# Verifier

Statuses:

- `VERIFIED`: a successful verification tool returned explicit evidence.
- `PARTIALLY_VERIFIED`: some evidence exists, or a model proposal differs
  from the exact tool result.
- `FAILED`: a required tool failed.
- `NOT_VERIFIABLE`: no verification tool was applicable.

Math results come from SymPy. Python results come from the restricted
interpreter. LLM claims alone are never considered verified, and the Tutor
adds an uncertainty notice for partial or non-verifiable answers.
