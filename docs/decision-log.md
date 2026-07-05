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

---

## Decision: D10 — Admin-invite acceptance elevates user_type (S8 / Phase 4)

### Context
§3.2 declares `user_type` immutable after creation; §4.1 requires an existing USER who accepts an
admin invite to "merge the admin role". The RBAC helper (`app/domain/user/auth/utils/permissions.py`)
gates every admin endpoint on `user_type == ADMIN`, so admin access cannot be granted by `admin_sub_role`
alone.

### Chosen Option
Treat a validated admin-invite acceptance as the **sanctioned elevation path**: on accept, set
`user_type = ADMIN` and `admin_sub_role = invitation.sub_role`. Acceptance requires an authenticated user
whose email matches the invitation, a non-expired unused token, and is audited (`ADMIN_INVITE_ACCEPTED`).

### Rationale
The §3.2 immutability rule guards against *unsanctioned* self-promotion; an admin invite issued by a
Super Admin (RBAC `INVITE_ADMIN`) is exactly the authorized exception. Keeping admin access keyed on
`user_type == ADMIN` preserves one consistent authorization predicate across the whole admin surface.

### Tradeoffs / Constraints
- A single wire predicate (`user_type == ADMIN`) rather than two (`ADMIN` OR has-sub_role).
- Existing CUSTOMER/AGENT personas are preserved (portal switcher still works).

### Revisit
- If product later wants admin capability without full admin `user_type`, extend `has_permission` to also
  honour `admin_sub_role` on USER rows, and relax this.

---

## Decision: D11 — S11 evidence: full presigned-S3 upload (not ref-only)

### Context
S7 deferred the real presigned-S3 upload UX (stored refs only). S11 (Phase 7) is where evidence
carries proof-of-work weight: server-side GPS+timestamp stamping, per-item SHA-256 content hash
(§4.5), image compression/derivatives, progressive viewing, and the offline upload queue (§7.4).

### Chosen Option
**Full S3 presigned upload** (user direction). S11 wires a real storage facade (presigned PUT +
retained full-res original + served compressed derivatives), the evidence domain (rows with
content-hash + server-set GPS/timestamp/capture-date), and the frontend upload manager + offline
retry queue (Field/Surveyor).

### Tradeoffs
- Pros: §4.5/§7.3a/§7.4 exercised end-to-end; evidence layer (S13) inherits real media.
- Cons: largest S11 sub-scope; storage-facade + upload manager + offline queue are real engineering.

### Constraints
- Deterministic default preserved: a local/stub storage provider backs tests (mirrors the OTP/payment
  stub philosophy); real S3/R2 selected by settings behind the facade.

### Revisit
- If disk/infra constraints block, fall back to ref+hash for the binary path while keeping the domain.

---

## Decision: D12 — Real scheduler for time-based automation (S10/S11)

### Context
Broadcast first-accept-wins expiry, no-show/pool timeouts, starvation backstop (§7.2), and graceful
SLA shedding (§6.4) are time-driven. They need a periodic trigger.

### Chosen Option
**Wire a real scheduler now** (user direction). Timeout/broadcast/shedding logic lives in pure,
tested service methods; a background job-runner fires the sweeps periodically. A non-prod dev
endpoint also triggers each sweep for deterministic tests.

### Tradeoffs
- Pros: exit criteria met with real automation, not just callable methods.
- Cons: adds runtime/infra concerns (lifespan-managed scheduler) and shutdown handling.

### Constraints
- Sweeps must be idempotent and safe to run concurrently with request traffic (claim-based, like the
  payment webhook). Scheduler is disabled under test env; sweeps invoked directly/via dev endpoint.

### Revisit
- If serverless deployment (NullPool) makes an in-process scheduler unsound, move sweeps to an external
  cron hitting the dev/admin sweep endpoints.

---

## Decision: D13 — Pull commission + refund forward into S10/S12

### Context
Chargeback commission-freeze (R6a.2) and FAILED/REFUNDED refunds (R8.5) reference domains sequenced
later (commissions = Phase 15/S19; gateway refunds unwired).

### Chosen Option
**Pull them forward** (user direction). S10 introduces a minimal commission domain (states
CLEARING/AVAILABLE/FROZEN/REVERSED + freeze/reverse ops) so chargeback freeze executes for real;
commission *accrual* wires at task-approval/report-release (S12). Refund execution (gateway refund
call behind the payment facade) lands with FAILED/REFUNDED in S12.

### Tradeoffs
- Pros: R6a.2/R8.5 fully satisfied, not hook-only.
- Cons: front-runs Phase 15/S19 sequencing; S19 becomes earnings/payout + rules maturity over this base.

### Constraints
- Commission money in integer minor units, NGN-contractual, reconciling to the kobo (§4.4).
- Gateway refund goes through the provider facade with the deterministic stub default (§PAYMENT_STUB_MODE).
- S19 (Phase 15) is re-scoped in the plan to build on this base rather than introduce commissions cold.

### Revisit
- N/A — S19 slice objective updated at its run.

---

## Decision: D14 — Build admin Trust Score Weights CRUD in S12

### Context
Report release (§8.3) computes the composite trust score from admin-defined Trust Score Weights
(per tier × role, summing to 100%). Full admin config is nominally Phase 18 (R18.5).

### Chosen Option
**Build the admin weights CRUD now** (user direction). S12 recreates `trust_score_weight_config` in
`0001`, ships default weights, and builds the admin management UI + endpoints with sum-to-100
validation. Composite computed deterministically at release; recompute only at release (§8.6).

### Tradeoffs
- Pros: §8.3 fully admin-configurable at MVP; R18.5's weights portion delivered early.
- Cons: pulls part of Phase 18 forward; S22 keeps the remaining system-config surface.

### Constraints
- Weights referenced via enums (tier/role); sum-to-100 enforced at save (per tier).
- Default weights seeded idempotently (like consent docs), editable via admin CRUD.

### Revisit
- N/A — S22 (Phase 18) objective updated to exclude the weights CRUD delivered here.

---

## Decision: D15 — SSE transport now, event bus deferred (S13 / Phase 9)

### Context
§9 needs live tracking over §4.9 SSE, but the §4.8 in-process event bus is Phase 12 (S16). No SSE,
emitter, or event bus exists in the backend today.

### Chosen Option
**In-process asyncio pub/sub emitter (`app/core/realtime`) + a real `text/event-stream` endpoint now,
with the 60-second poll endpoint sharing one identical snapshot shape** as the durable fallback. Redis
multi-instance fan-out is deferred to the Phase-12 event bus (S16). Publishing is **best-effort** and
never breaks the emitting transaction; **poll is the source of truth, SSE is a latency-reducing hint**.

### Tradeoffs
- Pros: meets the "watch status advance in real time" exit criterion now; single-process (`python
  veriprops.py`) is the demo reality; poll fallback keeps correctness anywhere (incl. serverless/NullPool).
- Cons: no cross-worker fan-out until S16; emit happens pre-commit (a dropped/early push only costs a
  60s reconciliation, never correctness).

### Revisit
- S16 replaces the emitter's internals with the §4.8 event bus without changing this public API.

---

## Decision: D16 — fpdf2 behind a stub-first facade for the report PDF (S14 / Phase 10)

### Context
§10 requires a server-side branded PDF with a per-page legal footer + QR. No PDF library exists; the dev
platform is Windows, where WeasyPrint's GTK/cairo native deps are painful and Playwright is heavy.

### Chosen Option
**`fpdf2` (pure-Python, zero native deps) behind a `report_pdf` facade** with a deterministic stub default,
mirroring the storage/payment/kyc facades. Per-page footer via `footer()`; QR via a pure-Python lib.

### Tradeoffs
- Pros: cross-platform/CI-safe, deterministic tests, satisfies the footer-parity exit criterion now.
- Cons: not pixel-for-pixel with the HTML view; a WeasyPrint/Playwright renderer is a later enhancement
  behind the same facade.

### Revisit
- Swap in an HTML-CSS renderer behind the facade if pixel parity becomes a requirement.

---

## Decision: D17 — Evidence visible only after review-approval (S13 / Phase 9)

### Context
§9.4 shows customers a chronological evidence feed; §9.3 mandates risk-bearing interim signal be withheld
until admin review so a negative is delivered only with context.

### Chosen Option
**A role's evidence (and its interim milestone) surfaces to the customer only once that task is admin
review-approved** (`review_decision == APPROVED`). Before then the task reads the collapsed "In Progress".

### Tradeoffs
- Pros: the §9.3 guardrail holds automatically at the API layer; positives are contextualised.
- Cons: less immediate than a live-as-uploaded feed (deferred as a possible future toggle).

### Revisit
- Could add an admin per-item "release early" control if product wants selectively-live evidence.

---

## Decision: D18 — Build the Legal Opinion section, gate its go-live (S14 / Phase 10)

### Context
The Premium Legal Opinion framing is a hard go-live gate pending NBA counsel + lawyer-role PI insurance
(§3.5/§B). It does not block MVP build, only go-live.

### Chosen Option
**Build the Premium Legal Opinion report section fully, but gate its customer display behind
`LEGAL_OPINION_ENABLED` (default off)** surfaced via `/config/public`. Build, do not go live.

### Tradeoffs
- Pros: the tier is demoably complete; flipping one flag ships it post-sign-off.
- Cons: the section is dark in prod until legal clears — intended.

### Revisit
- Enable the flag once NBA sign-off + lawyer PI cover are recorded (§B items 15, 17).

---

## Decision: D19 — S15 delivers full Phase 11, including structured clarifications

### Context
Phase 11 spans the Customer↔Admin thread, the task-tagged Admin↔Agent thread, general support,
and the §11.1 "structured, fraud-scanned clarification request/response" refinement.

### Chosen Option
**Full Phase 11** (user direction): all channels plus the clarification flow. Clarifications are
modelled as `ChatMessage`s with `message_kind = CLARIFICATION_REQUEST/RESPONSE` and a
`clarification_status` (OPEN→ANSWERED) — they run the same send-time fraud scan, so no separate
pipeline is needed.

### Tradeoffs
- Pros: the whole mediated-comms surface ships together; clarifications reuse the message machine.
- Cons: larger S15 UI + state than a threads-only cut.

### Revisit
- N/A.

---

## Decision: D20 — S16 routes the existing emitter + external dispatch through the event bus

### Context
S13 scattered `publish_verification_event(...)` calls at every mutation, and the outbound
`VerificationMessages.send_*` methods are called ad hoc. §4.8 wants each domain event published
**once**, with subscribers deciding surfacing. D15 promised the emitter's internals would be
swapped for the bus without changing its public behaviour.

### Chosen Option
**Full refactor** (user direction): S16 introduces `app/core/events` and replaces the scattered
emitter calls and the best-effort external-dispatch calls with a single `event_bus.publish(...)`.
A `RealtimeSubscriber` re-emits the same SSE event names (S13 frontend hooks untouched); a
`NotificationSubscriber` fans out per the rule table; a `ChatCounterSubscriber` handles §12.3.

### Tradeoffs
- Pros: one publish point; honours the no-orphan/refactor-everything non-negotiable.
- Cons: touches task/review/payment/tracking services — more churn now.

### Revisit
- Redis fan-out replaces the in-process dispatcher internals later without an API change.

---

## Decision: D21 — Rule table covers all §12.2 events; publish only what exists today

### Context
Several §12.2 notification triggers (dispute, payout, re-check) reference source domains not yet
built (S18/S19).

### Chosen Option
**Declare the full §12.2 set** in the event enum + declarative rule table, but wire `publish(...)`
calls only at choke points that exist today (payment, status, agents-assigned, evidence, report
ready/versioned, task-rejected, conflict, no-show, fraud-message, new chat message). Dispute /
payout / re-check entries are declared-but-unfired until their slices add the sources.

### Tradeoffs
- Pros: the routing table is complete and reviewable now; later slices just publish an existing event.
- Cons: some rule-table rows are dormant until S17–S19.

### Revisit
- N/A — later slices publish the already-declared events.

---

## Decision: D22 — Chat is text + fraud-scan only in S15; attachments deferred

### Context
§11.1 allows attachments in the Customer↔Admin thread. Full presigned upload is a real sub-surface.

### Chosen Option
**Text + fraud-scan only** this slice (user direction). The `attachments` JSONB column is kept on
`chat_messages` for forward-compat, but no upload UI/endpoint is built. Attachment upload is a
documented follow-up (reuses the S11 storage facade when built).

### Tradeoffs
- Pros: S15 stays focused on the state-machine + routing correctness (the risky part).
- Cons: attachments arrive in a follow-up, not this slice.

### Revisit
- Wire presigned attachment upload behind the existing storage facade in a later slice.

---

## Decision: D23 — Minimal SLA-breach emitter sweep so the notification actually fires

### Context
There is no SLA-breach detector firing today — only the S4 business-day calculator and the admin
SLA-health projection. Without an emitter the §12.2 SLA-breach notification would be dark.

### Chosen Option
**Add a minimal SLA-breach sweep** (S16) reusing the S10 scheduler pattern (`ALWAYS_NEW` session,
disabled under test, on-demand dev endpoint): a periodic job finds newly-overdue verifications and
publishes `SlaBreached` **once** per verification through the event bus.

### Tradeoffs
- Pros: the SLA-breach notification is real, not a dormant rule-table row.
- Cons: adds one more scheduled sweep to maintain.

### Revisit
- Fold into a richer ops/analytics scheduler in S22 if needed.
