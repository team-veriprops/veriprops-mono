# PRD Orchestrator Skill

## Version
Read current version from:

`.claude/skills/prd-orchestrator/VERSION`

---

## Purpose
Convert a `PRD.md` with phased requirements into a fully implemented, production-ready system through:

- structured analysis
- architecture design
- execution planning
- autonomous slice-based implementation
- continuous clarification loops
- self-auditing after every cycle
- recovery-first resumption
- version-aware upgrades
- final system audit

---

## Core Lifecycle

1. initialize
2. run
3. resume
4. upgrade
5. audit

---

## Key Principles

### 1) No silent assumptions
If anything is unclear:
→ STOP and ask the user.

### 2) Continuous clarification
Clarifications may be triggered during:
- initialize
- run
- resume
- upgrade

### 3) Self-audit is mandatory
Every run/resume validates:
- correctness
- PRD compliance
- architecture compliance
- security
- migration safety
- API consistency
- test coverage

Fix issues before stopping.

### 4) State-driven execution
Never rely on chat memory.

Always read:
- PRD.md
- docs/prd-analysis.md
- docs/requirements-matrix.md
- docs/decision-log.md
- docs/architecture-spec.md
- docs/execution-plan.md
- docs/progress.md
- docs/runtime-state.yaml
- docs/upgrade-log.md
- git status
- git diff

### 5) Version compatibility
Before run/resume/audit:

compare project skill version vs current skill version.

If mismatch:
STOP and require:

/skill prd-orchestrator upgrade

No silent schema drift.

---

## Recovery-first Resume

Persist in-flight execution state in:

`docs/runtime-state.yaml`

Resume must:

recover → complete audit → checkpoint → continue

Never start new work before recovering interrupted work.

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
- docs/upgrade-log.md
- docs/final-audit.md

---

## Completion Definition

A PRD is complete only when:
- all slices completed
- all requirements marked complete
- no blockers remain
- runtime state is checkpointed or idle
- project docs are on latest skill version
- final audit passes

---

## Golden Rule

Always prefer correctness, traceability, and architectural integrity over speed.