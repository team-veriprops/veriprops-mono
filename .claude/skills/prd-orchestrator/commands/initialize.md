# Initialize Command

Read PRD.md completely.

Generate:

- docs/prd-analysis.md
- docs/requirements-matrix.md
- docs/decision-log.md
- docs/architecture-spec.md
- docs/execution-plan.md
- docs/progress.md

---

## Clarification Gate (MANDATORY)

If ANY ambiguity exists:
- stop immediately
- ask user structured clarification questions:

Format:

CLARIFICATION REQUIRED:
1. Question
2. Why it matters
3. Options (if any)
4. Default assumption if unanswered

Do NOT proceed until resolved or defaults approved.

---

## Initialize progress state

Set:
status = initialized
next_slice = S1
completed = []
blockers = []

---

STOP after initialization.