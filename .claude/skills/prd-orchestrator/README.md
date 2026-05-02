# PRD Orchestrator Skill

A **Claude Code skill** that turns a `PRD.md` (phased requirements) into a fully implemented system using structured analysis, autonomous execution, clarification loops, and continuous self-audits.

Built for use with **Claude Code** by Anthropic.

---

## 🚀 What it does

* Analyzes your PRD end-to-end
* Generates architecture + execution plan
* Implements in safe, optimal slices
* Asks for clarification when needed
* Self-audits after every run
* Produces a final audit report

---

## 📁 Setup

Place in your repo:

```
.claude/skills/prd-orchestrator/
```

Ensure:

* `PRD.md` exists in repo root
* `/docs` folder is writable
* Git is initialized (recommended)

---

## ⚙️ Commands

### 1. Initialize (once)

```
/skill prd-orchestrator initialize
```

Generates:

* `docs/prd-analysis.md`
* `docs/requirements-matrix.md`
* `docs/decision-log.md`
* `docs/architecture-spec.md`
* `docs/execution-plan.md`
* `docs/progress.md`

May pause for **clarifications**.

---

### 2. Run (start execution)

```
/skill prd-orchestrator run
```

* Selects optimal work batch
* Implements code + tests
* Self-audits
* Updates docs
* Stops at safe checkpoint

---

### 3. Resume (continue anytime)

```
/skill prd-orchestrator resume
```

* Recovers state from docs + git
* Continues unfinished or next slice
* Safe after interruptions/timeouts

---

### 4. Final Audit

```
/skill prd-orchestrator audit
```

Generates:

* `docs/final-audit.md`

---

## 🔁 Workflow

```
initialize → review → commit
run        → review → commit
resume     → review → commit
...repeat...
audit      → fix → done
```

---

## 🧠 Key Features

### Clarification-first

Stops and asks when requirements are ambiguous.

### Autonomous slicing

Chooses how much work to do per run (no micromanagement).

### Self-auditing

Every run validates:

* PRD compliance
* architecture integrity
* security
* test coverage

### Deterministic resume

All state stored in `/docs`, not chat memory.

---

## 📌 Rules

* Always review and commit after each run/resume
* Never ignore clarification prompts
* Do not manually bypass architecture or decision logs

---

## ✅ Completion Criteria

A PRD is complete when:

* All requirements implemented
* No blockers remain
* Final audit passes

---

## 💡 Mental Model

> **Initialize once → Run/Resume until done → Audit at the end**

---

## ⚠️ Tip

Commit after every cycle:

```
git add .
git commit -m "feat: implement slice"
```

This ensures safe recovery and clean progress.

---

## 📄 License

Internal use / customize per project.
