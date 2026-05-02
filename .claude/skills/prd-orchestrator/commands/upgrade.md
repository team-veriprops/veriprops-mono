# Upgrade Command

## Purpose
Migrate an initialized project from an older skill schema/version to the latest version without losing progress.

---

## Step 1 — Read versions

Read:

- .claude/skills/prd-orchestrator/VERSION
- metadata headers in:
  - docs/prd-analysis.md
  - docs/requirements-matrix.md
  - docs/decision-log.md
  - docs/architecture-spec.md
  - docs/execution-plan.md
  - docs/progress.md
  - docs/runtime-state.yaml (if present)

Determine:

- project_version
- target_version

---

## Step 2 — Detect delta

Identify:

- missing docs
- missing fields
- changed templates
- changed schema
- deprecated fields

---

## Step 3 — Migrate safely

Rules:

Never overwrite:
- decision history
- clarification answers
- completed slices
- requirements completion state
- user decisions

Only:
- merge new schema
- add missing files
- add missing fields
- normalize structure

Infer defaults from:
- progress
- git status
- git diff
- runtime-state
- requirements matrix

---

## Step 4 — Clarification gate

If migration assumption is risky:

STOP and ask:

CLARIFICATION REQUIRED DURING UPGRADE

Persist answer.

---

## Step 5 — Write migration log

Update:

docs/upgrade-log.md

Record:
- from version
- to version
- files changed
- schema changes
- inferred defaults
- manual clarifications
- migration risks

---

## Step 6 — Update metadata

Set all generated docs to latest version.

---

## Step 7 — STOP

Wait for:

resume
