# Final Audit Command

## Step 0 — Version check

Compare:

project version vs skill version

If mismatch:

STOP:

SKILL UPGRADE REQUIRED

Run:

/skill prd-orchestrator upgrade

---

## Step 1 — Runtime check

Ensure docs/runtime-state.yaml status is:

- checkpointed
or
- idle

If status is:

- running
- interrupted
- recovering

STOP.

Require:

resume

before final audit.

---


## Step 2 — Read all state

- PRD.md
- docs/*
- git status
- git diff

---

## Step 3 — Produce final audit

docs/final-audit.md

Include:

- requirement coverage
- missing items
- partial implementations
- security review
- performance review
- architecture deviations
- migration safety
- test coverage
- production readiness
- remediation steps

---

## Step 4 Completion

Only complete when:

- all requirements satisfied
- no critical risk remains

## Step 5 — STOP