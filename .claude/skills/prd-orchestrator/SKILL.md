# PRD Orchestrator Skill

## Purpose
Convert a PRD.md with phased requirements (e.g., 1–19) into a fully implemented, production-ready system through:

- structured analysis
- architecture design
- execution planning
- autonomous slice-based implementation
- continuous clarification loops
- self-auditing after every cycle
- final system audit

---

## Core Lifecycle

0. initialize (bootstrap + clarification)
1. run (execute optimal work batch)
2. resume (recover + continue execution)
3. audit (final validation)

---

## Key Principles

### 1. No silent assumptions
If anything is unclear:
→ STOP and ask the user.

### 2. Continuous clarification allowed
Clarifications can be triggered:
- during initialization
- during run
- during resume

### 3. Self-audit is mandatory
Every run/resume cycle must:
- validate correctness
- validate PRD compliance
- validate architecture compliance
- validate security constraints
- validate test coverage
- fix issues before stopping

### 4. State-driven execution
Never rely on chat memory.

Always read:
- docs/prd-analysis.md
- docs/requirements-matrix.md
- docs/decision-log.md
- docs/architecture-spec.md
- docs/execution-plan.md
- docs/progress.md
- git status + diff

---

## Execution Rules

### Batch sizing
Skill decides dynamically:

- large slice → simple CRUD / UI / docs
- medium slice → service + tests
- small slice → schema/auth/integration work

Never overfill context.

---

## Safety Rules

Stop execution immediately if:
- ambiguity is detected
- conflicting requirements exist
- missing business rules affect correctness
- schema or auth implications are unclear

Ask user:

> CLARIFICATION REQUIRED

---

## Outputs Required

The skill must generate and maintain:

- docs/prd-analysis.md
- docs/requirements-matrix.md
- docs/decision-log.md
- docs/architecture-spec.md
- docs/execution-plan.md
- docs/progress.md
- docs/final-audit.md (only at end)

---

## Completion Definition

A PRD is complete only when:

- all slices executed
- all requirements marked complete
- no open blockers
- final audit passes or remediation completed

---

## Commands Overview

- initialize → bootstrap + docs + clarification
- run → execute next optimal slice batch
- resume → recover + continue safely
- audit → final validation report

---

## Golden Rule

> "Always prefer correctness, traceability, and architectural integrity over speed."