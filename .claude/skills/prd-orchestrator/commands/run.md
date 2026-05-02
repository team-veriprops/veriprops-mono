# Run Command

## Step 0 — Version check

Compare:

project version vs skill version

If mismatch:

STOP:

SKILL UPGRADE REQUIRED

Run:

/skill prd-orchestrator upgrade

---

## Step 1 — Commit policy check

Read config.yaml

If mode = strict:

If git working tree is dirty:

STOP:

COMMIT REQUIRED BEFORE RUN

Suggested commit:
- message: "checkpoint: pre-run state"

If mode = advisory:

If dirty:

WARN:

Uncommitted changes detected.
Recovery may be less deterministic.

If mode = disabled:

Skip all git checks.

---

## Step 2 — Start execution journal

Populate docs/runtime-state.yaml:

- session_id
- command: run
- status: running
- phase: implementation
- current_slice
- current_subtask
- modified_files: []
- created_files: []
- tests state
- self_audit.started: false
- clarification_needed: []
- next_action

---

## Step 3 — Load full state

Read:

- PRD.md
- docs/*
- git status
- git diff

---

## Step 4 — Select optimal work batch

Choose dependency-safe slice(s) based on:

- dependency readiness
- risk
- complexity
- schema impact
- auth impact
- integration impact
- context budget

---

## Step 5 — Implement

For each slice:

- implement code
- write migrations if needed
- add tests
- update docs

Continuously update runtime-state.yaml:

- modified_files
- created_files
- tests
- findings
- clarification_needed
- next_action

---

## Step 6 — Self-audit (MANDATORY)

Validate:

- correctness
- PRD compliance
- architecture compliance
- security
- race conditions
- migration safety
- API consistency
- test completeness

Fix discovered issues.

Update self_audit state.

---

## Step 7 — Clarification Gate

If ambiguity discovered:

STOP and ask:

CLARIFICATION REQUIRED DURING EXECUTION

Persist in:

docs/runtime-state.yaml

Do not continue until resolved.

---

## Step 8 — Checkpoint

Update:

- docs/progress.md
- docs/requirements-matrix.md
- docs/decision-log.md (if needed)

Set runtime-state:

- status: checkpointed
- last_checkpoint

Record:

- completed work
- remaining work
- suggested commit


### Suggested Commit

If config.commit.suggest_commit_messages = true:

Provide:

git add .
git commit -m "<message>"

Message format:

feat(slice): implement S3 user profile

or

checkpoint: completed recovery for S14

or

fix(audit): resolve CSRF vulnerability

---

## Step 9 — STOP