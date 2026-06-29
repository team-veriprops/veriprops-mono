# Decision Log

> Decisions captured at the `initialize` clarification gate. Each follows the skill template:
> Context / Options / Chosen / Rationale / Tradeoffs / Constraints / Revisit.

---

## Decision: D1 — Treatment of existing code

### Context
The repo is mid-refactor. The foundation layer (`appodus_utils`) and `audit` / `message` / `user`-core-auth
survive, frontend auth is ~95% and marketing ~40%, but most domain code (verification, payment, payout,
commission, referral, notification, broadcast, content, analytics, admin_config, retention, thread+fraud, dev,
and user subdomains agent / admin_invitation / admin_team) is **staged for deletion** — while migration
`0001_initial_schema.py` still defines their tables.

### Options Considered
1. Brownfield — build forward on surviving assets; rebuild deleted domains phase-by-phase.
2. Restore deleted domains from git history, reconcile to PRD, then build forward.
3. Greenfield rebuild — ignore current implementation status.

### Chosen Option
**Option 1 — Brownfield, build forward.**

### Rationale
The surviving foundation (BaseEntity, GenericRepo, Money, Auth, Consent, AuditLog) is high-quality and PRD-aligned;
discarding it wastes real work. The deletions are treated as intentional clearing for a PRD-aligned rebuild.

### Tradeoffs
- Pros: maximum reuse; fastest path to MVP; preserves working auth + design system.
- Cons: must reconcile rebuilt models against the `0001` schema (see D6); risk of partial/stale survivors.

### Constraints Introduced
- Requirements matrix status is seeded from the brownfield audit (done/partial/pending).
- New domain models must align to existing schema; prefer additive migrations.

### Revisit Conditions
- If surviving code proves incompatible with PRD v2.4 contracts, or if the `0001` schema diverges materially
  from PRD entities, reconsider a targeted restore (Option 2) for specific domains.

---

## Decision: D2 — Scope

### Context
The PRD marks Phases 0–10 as the MVP cut line; 11–19 harden and scale.

### Options Considered
1. Analyze all 19 phases; execute MVP (0–10) first, then 11–19.
2. MVP only (0–10); defer 11–19 entirely.

### Chosen Option
**Option 1 — Analyze all 19; execute MVP-first.**

### Rationale
Full traceability now avoids re-analysis later and keeps cross-phase dependencies visible; execution still
prioritises the MVP so delivery is demoable end-to-end early.

### Tradeoffs
- Pros: complete requirements matrix; no surprises from later phases; MVP-prioritised delivery.
- Cons: larger upfront analysis artifacts.

### Constraints Introduced
- `requirements-matrix.md` and `prd-analysis.md` cover all 19 phases; `execution-plan.md` sequences MVP first.

### Revisit Conditions
- If priorities shift to ship MVP and stop, prune 11–19 slices from the execution plan.

---

## Decision: D3 — Commit policy

### Context
`.claude/skills/prd-orchestrator/config.yaml` is set to `mode: strict` with
`require_clean_worktree_before_run: true`. The worktree is very dirty (large staged deletions + edits).

### Options Considered
1. Switch to advisory (suggest commits, never block).
2. Keep strict — user commits/cleans the worktree before `run`.
3. Disabled — ignore git state entirely.

### Chosen Option
**Option 2 — Keep strict.**

### Rationale
Strict mode maximises recovery safety. The user will commit the in-flight refactor before invoking `run`,
giving the orchestrator a clean checkpoint to build on.

### Tradeoffs
- Pros: clean recovery checkpoints; no work lost mid-slice.
- Cons: `run` is blocked until the worktree is committed/clean — a manual gate.

### Constraints Introduced
- `config.yaml` is **unchanged**. `run` will refuse to start while the worktree is dirty.
- `runtime-state.yaml` records `git.dirty: true`; `progress.md` carries the warning.

### Revisit Conditions
- If the manual commit gate becomes a friction point, switch to advisory (D3 → Option 1).

---

## Decision: D4 — Database engine

### Context
PRD.md states PostgreSQL; CLAUDE.md line 1 states MySQL. Code (`asyncpg`, `ACTIVE_DB=POSTGRES`, JSONB in `0001`)
is PostgreSQL.

### Chosen Option
**PostgreSQL is the source of truth.**

### Rationale
Code and PRD agree; CLAUDE.md is stale.

### Constraints Introduced
- All schema/migration work targets PostgreSQL (async SQLAlchemy + asyncpg).
- CLAUDE.md correction is **flagged only** (not applied during `initialize`, which touches `docs/` only).

### Revisit Conditions
- N/A — apply the CLAUDE.md fix in an early `run` slice.

---

## Decision: D5 — Frontend directory

### Context
PRD references `web/`; the actual directory is `frontend/` (confirmed by CLAUDE.md and the tree).

### Chosen Option
**`frontend/` is the source of truth** (`web/` is stale PRD naming).

### Constraints Introduced
- All frontend paths in artifacts use `frontend/`.

### Revisit Conditions
- N/A.

---

## Decision: D6 — Migration vs deleted domains (reconciliation risk)

### Context
Migration `0001_initial_schema.py` defines and seeds tables for domains whose code is staged for deletion
(verification tiers, trust-score weights, property, consent docs, etc.).

### Chosen Option
**Treat `0001` as the schema contract.** Rebuilt domain models must align to it; prefer additive migrations
over recreating tables.

### Rationale
The schema is the most complete surviving description of the intended data model; aligning to it minimises churn
and keeps the migration history coherent.

### Tradeoffs
- Pros: coherent migration history; less rework; schema already PRD-shaped.
- Cons: rebuilt code must match an existing schema it did not generate — drift risk.

### Constraints Introduced
- Each rebuilt domain slice includes a schema-reconciliation check (model ↔ `0001`) and round-trip tests.

### Revisit Conditions
- If `0001` proves materially wrong vs PRD v2.4, author a corrective migration in the relevant slice rather than
  editing `0001`.

---

## Decision: D7 — Foundation primitives live under `app/core`

### Context
The execution plan named S2–S4 primitives under `app/domain/verification/*`, but that package was deleted in the
consolidation and will be fully rebuilt in S9. A surviving `app/state/machine.py` already held the state-machine
validator + transition tables.

### Chosen Option
Create a cross-cutting **`app/core`** package and **move `app/state` → `app/core/state`**. S2–S4 primitives live there:
`app/core/state/{status,derive,dependencies}.py`, `app/core/{vid,evidence,sla}.py`, `app/core/idempotency/`.

### Rationale
These are genuinely cross-cutting (state derivation, idempotency, VID, evidence-hash, SLA are consumed by multiple
future domains). Housing them in `app/core` gives one source of truth and avoids churn/collision when S9 rebuilds the
full verification domain (which will *import* these, not redefine them).

### Constraints Introduced
- `app/core/__init__.py` imports model-bearing sub-packages (idempotency) so Alembic `env.py` (`from main.app import core`)
  registers them on `BaseEntity.metadata`. Status enums in `app/core/state/status.py` are the canonical source.

### Revisit Conditions
- N/A.

---

## Decision: D8 — Clean orphaned seeds from `0001`

### Context
After consolidation, `0001_initial_schema.py` creates only the surviving tables (auth/message/audit/consent) but still
contained `_seed_pricing` / `_seed_trust_score_weights` writing to `pricing_tier_configs`, `pricing_line_items`,
`trust_score_weight_config` — tables it no longer creates (the seeds were silently skipped by `table_exists` guards).

### Chosen Option
Remove the orphaned pricing + trust-weight seeds (and `_SEED_WEIGHTS`); keep consent-document, verification-consent,
and super-admin seeds (their tables ARE created here). Behaviour-preserving dead-code removal.

### Revisit Conditions
- Pricing + trust-weight seeds are reintroduced (with their CREATE TABLEs) when those domains are rebuilt (S9 pricing, S12 scoring).

---

## Decision: D9 — Greenfield foundation posture (relaxes D6)

### Context
User direction: a total rewrite was preferred; only **user-auth (backend + frontend)** and the **home page** are worth
preserving. Nothing has shipped to production.

### Chosen Option
Build the foundation **greenfield/clean** rather than reconciling to brownfield survivors. Treat `0001` as the single
**editable** initial migration: add new foundation tables *into* `0001` (e.g. `idempotency_keys` in S3) using the
per-table `_create_*` + `AlembicUtils` + DRY pattern (backend/CLAUDE.md), instead of incremental migrations.

### Rationale
With no shipped database, a single coherent initial schema is cleaner than a chain of additive migrations for the
foundation phase. This relaxes **D6** (which treated `0001` as an immutable contract).

### Tradeoffs
- Pros: one coherent initial schema; less migration noise during the foundation rebuild.
- Cons: `0001` changes until the schema stabilises; once real data exists, revert to additive-only migrations.

### Revisit Conditions
- Once a non-throwaway database exists (staging/prod), stop editing `0001` and switch to additive migrations.

---

## Decision: D10 — Enum references over free literals (codebase-wide convention)

### Context
`app/core/state/machine.py` defined its transition tables with raw string literals, predating the canonical enums
in `app/core/state/status.py`. A codebase-wide audit found `machine.py` was the **sole** offender (derivation,
dependencies, surviving domains, `appodus_utils`, and the frontend already reference their enums).

### Chosen Option
Refactor `machine.py` to reference `VerificationStatus` / `TaskState` / `ReportState` members (tables annotated
`Dict[str, Set[str]]` since the enums subclass `str`, so `StateMachine` still accepts DB strings at the boundary —
behaviour-preserving, 363 tests unchanged). Codify the rule in [CLAUDE.md](../CLAUDE.md),
[backend/CLAUDE.md](../backend/CLAUDE.md), and [frontend/CLAUDE.md](../frontend/CLAUDE.md): **any value with a
defining enum must be referenced via its enum member in app code; free string literals duplicating an enum value
are prohibited.**

### Constraints Introduced
- Exceptions: enum *definitions*, Alembic migrations (decoupled by design), and tests asserting wire/DB-string
  compatibility. Future rebuilt domains (S5+) inherit the rule.

### Revisit Conditions
- N/A.
