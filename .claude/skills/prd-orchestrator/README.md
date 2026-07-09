# PRD Orchestrator Skill

A Claude Code skill for turning a `PRD.md` into a fully implemented system through structured planning, autonomous execution, clarification loops, self-audits, and recovery-first resume.

## Commands

### Initialize

```bash
/skill prd-orchestrator initialize
```

Generates:

* `docs/prd-analysis.md`
* `docs/requirements-matrix.md`
* `docs/decision-log.md`
* `docs/architecture-spec.md`
* `docs/execution-plan.md`
* `docs/progress.md`
* `docs/runtime-state.yaml`
* `socs/upgrade-log.md`

May stop for clarification.

---

### Run

```bash
/skill prd-orchestrator run
```

The skill:

* selects optimal slice(s)
* implements
* tests
* self-audits
* checkpoints safely

---

### Resume

```bash
/skill prd-orchestrator resume
```

Recovery-first:

1. restore interrupted in-flight state
2. finish pending work
3. complete self-audit
4. surface pending clarification
5. checkpoint safely
6. continue execution

---

### Upgrade

```bash
/skill prd-orchestrator upgrade
```

Run when the skill version changes.

Safely migrates generated docs/state without losing progress.

### Audit

```bash
/skill prd-orchestrator audit
```

Produces:

* `docs/final-audit.md`

---

## Workflow

```text
initialize
run
(interrupted?)
resume
(skill updated?)
upgrade
resume
...
audit
```

---

## Rules

* Review and commit after each cycle
* Answer clarification prompts
* Do not bypass architecture or decision logs
* Resume interrupted work before starting new work

---

## Completion

Done when:

* all requirements implemented
* no blockers remain
* runtime state is checkpointed/idle
* final audit passes

---

## Commit Behavior

The skill does NOT automatically commit.

It operates in one of three modes:

- advisory (default): suggests commits
- strict: requires commits before execution
- disabled: ignores git entirely

Configure via:

.claude/skills/prd-orchestrator/config.yaml

Recommended: advisory
