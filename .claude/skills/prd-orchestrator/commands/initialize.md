# Initialize Command

## Purpose
Bootstrap implementation state from PRD.md.

---

## Step 1 — Read inputs

Read:

- PRD.md
- existing docs/
- repository structure
- git status

---

## Step 2 — Generate artifacts

Create:

- docs/prd-analysis.md
- docs/requirements-matrix.md
- docs/decision-log.md
- docs/architecture-spec.md
- docs/execution-plan.md
- docs/progress.md
- docs/runtime-state.yaml

---

## Step 3 — Clarification Gate (MANDATORY)

If ambiguity exists:

STOP and ask:

CLARIFICATION REQUIRED:

1. Question
2. Why it matters
3. Options (if applicable)
4. Default assumption (if unanswered)

Do not proceed until resolved or defaults approved.

Persist answers in:

docs/decision-log.md

---

## Step 4 — Initialize progress

Set docs/progress.md:

- status: initialized
- completed_slices: []
- current_slice: none
- blockers: []
- pending_recovery: none

---

## Step 5 — Initialize runtime state

Set docs/runtime-state.yaml:

- status: idle
- phase: idle
- current_slice: null
- current_subtask: null
- modified_files: []
- created_files: []
- tests: default false
- self_audit: default false
- clarification_needed: []
- next_action: null

---

## Step 6 — STOP

No implementation.

Wait for:

run