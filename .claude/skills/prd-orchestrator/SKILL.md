# PRD Orchestrator Skill

## Purpose
Convert a `PRD.md` with phased requirements into a fully implemented, production-ready system through:

- structured analysis
- architecture design
- execution planning
- autonomous slice-based implementation
- continuous clarification loops
- self-auditing after every cycle
- recovery-first resumption
- final system audit

---

## Core Lifecycle

1. initialize
2. run
3. resume
4. audit

---

## Key Principles

### 1) No silent assumptions
If anything is unclear:
→ STOP and ask the user.

---

### 2) Continuous clarification
Clarifications may be triggered during:

- initialize
- run
- resume

---

### 3) Self-audit is mandatory
Every run/resume must validate:

- correctness
- PRD compliance
- architecture compliance
- security
- migration safety
- API consistency
- test coverage

Fix issues before stopping.

---

### 4) State-driven execution
Never rely on chat memory.

Always read:

- PRD.md
- docs/*
- git status
- git diff

---

## Recovery-first Resume

Persist in-flight execution state in:

`docs/runtime-state.yaml`

This stores:

- active slice
- active subtask
- modified files
- created files
- test state
- self-audit state
- discovered findings
- clarification questions
- next action

Resume must:

recover → complete audit → checkpoint → continue

Never start new work before recovering interrupted work.

---

## Batch Sizing

Skill decides dynamically:

Small batches:
- schema
- auth
- integrations
- concurrency-sensitive work

Medium batches:
- service logic
- APIs
- validations

Large batches:
- CRUD
- tests
- docs
- UI wiring

Prefer safe checkpoints over large output.

---

## Stop Conditions

Stop immediately when:

- ambiguity is detected
- conflicting requirements exist
- business rule is unclear
- security implications are unclear
- migration correctness is uncertain

Ask:

CLARIFICATION REQUIRED

---

## Outputs Required

Maintain:

- docs/prd-analysis.md
- docs/requirements-matrix.md
- docs/decision-log.md
- docs/architecture-spec.md
- docs/execution-plan.md
- docs/progress.md
- docs/runtime-state.yaml
- docs/final-audit.md

---

## Completion Definition

A PRD is complete only when:

- all slices completed
- all requirements marked complete
- no blockers remain
- runtime state is checkpointed or idle
- final audit passes (or remediation completed)

---

## Commit Policy

Commit behavior is configurable via:

.claude/skills/prd-orchestrator/config.yaml

Modes:

- advisory (default): suggest commits, do not block execution
- strict: require commits before run/resume
- disabled: ignore git state entirely

The skill must:

- never force commits
- respect user workflow
- warn when recovery safety is reduced due to uncommitted changes

---

## Golden Rule

1. Always prefer correctness, traceability, and architectural integrity over speed.