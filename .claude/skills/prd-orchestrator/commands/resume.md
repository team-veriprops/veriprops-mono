# Resume Command (Recovery-first)

## Purpose
Recover interrupted work first, checkpoint safely, then continue.

---

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

If strict:

require clean state OR explicit confirmation.

If advisory:

warn only.

If disabled:

ignore git.

---


## Step 2 — Load state

Read:

- PRD.md
- docs/*
- git status
- git diff
- current branch

---

## Step 3 — Detect interrupted execution

If runtime-state status is:

- running
- interrupted
- recovering

PRIORITIZE recovery.

Do not pick new slices yet.

---

## Step 4 — Recover execution

Reconstruct:

- active slice
- active subtask
- modified files
- created files
- pending tests
- pending self-audit
- discovered findings
- clarification_needed
- next_action

Reconcile with filesystem and git diff.

Filesystem is source of truth if conflict exists.

Update runtime-state.yaml.

---

## Step 5 — Finish interrupted work

Complete:

- incomplete subtask(s)
- pending tests
- pending self-audit
- pending doc updates

If clarification needed:

STOP and ask:

CLARIFICATION REQUIRED DURING RECOVERY

Persist in runtime-state.yaml.

Do not continue until resolved.

---

## Step 6 — Safe checkpoint

Update:

- docs/progress.md
- docs/requirements-matrix.md
- docs/decision-log.md

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

## Step 7 — Continue (optional)

If:

- no blockers
- no clarification pending
- tests green
- context safe

Then continue normal execution:

- select next slice batch
- implement
- self-audit
- checkpoint

Else STOP cleanly.

---

## Rules

Always:

recover → audit → checkpoint → continue

Never:

- abandon interrupted work
- start new work before recovery
- ignore pending audit
- ignore pending clarification