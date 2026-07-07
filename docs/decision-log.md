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

---

## Decision: D24 — Restore the `/dev/reset` + `/dev/seed` contract (gap-closure follow-up)

### Context
CLAUDE.md's automation-determinism section declares `POST /dev/reset` + `POST /dev/seed` as a
permanent contract for autonomous QA, but the `dev` domain was cleared in the greenfield rebuild
and never restored — so a deterministic live drive-through had no way to seed data.

### Chosen Option
**Rebuild `app/domain/dev/`** (controller + service, no entity), production-gated twice (router
mounts only in non-prod; `_require_non_prod()` 404s in prod). `reset()` clears domain rows keeping
the super-admin + reference seeds; `seed()` builds a deterministic scenario (customer + approved
agents + a `PAID`/`UNDER_REVIEW` verification with review-approved tasks, SLA overdue) and returns
credentials/ids. Reuses `Utils.get_password_hash`, the domain models, and `VerificationTaskService`.

### Tradeoffs
- Pros: restores the documented QA contract; enables the live HTTP drive-through + future automation.
- Cons: a seed must stay in step with the domain schema (it writes rows directly for determinism).

### Revisit
- Extend the seed as later slices add domains (disputes, payouts).

---

## Decision: D25 — Admin Chat counter is a shared-inbox model (gap-closure follow-up)

### Context
The §N.3 Chat counter is per-participant, but admins are not enrolled as participants of every
verification thread — so without special handling an admin would see no Chat counter.

### Chosen Option
**Treat admins as a shared inbox:** `CommunicationService` detects `user_type == ADMIN` and returns
*all* verification threads (`ConversationRepo.list_verification_threads`) with unread computed from
that admin's own `ConversationParticipant.last_read_at` (a never-opened thread reads as unread).
Admins bypass participant-membership on read/mark-read. Live SSE bumps for admins ride the 60-second
poll rather than per-message fan-out (bounded).

### Tradeoffs
- Pros: admins get a meaningful, per-admin Chat counter without enrolling every admin per thread.
- Cons: an extra id-type branch; admin counter latency is poll-bound (≤60s), not instant.

### Revisit
- Add per-admin SSE fan-out if instant admin counters become important.

---

## Note: three runtime bugs the live drive-through surfaced (mocked tests couldn't)

The first real end-to-end run against a live backend caught defects unit tests (mocked repos) missed,
all now fixed:
1. **UUID-vs-String references.** `BaseEntity.id` is a native `UUID(as_uuid=True)` (so `entity.id` is
   a `uuid.UUID`), but reference columns are `String(36)`; the wire form is `.hex` (32-char) for
   entities and `str(uuid)` (36-char) for user ids (JWT). Communication/notification code now coerces
   with `Utils.uuid_to_hex` (entity refs) / `str` (user refs) at the repo/DTO boundaries.
2. **ORM models into `build_page`.** `build_page` validates its items as DTOs; the chat/notification
   list repos were passing ORM models. They now return `(rows, total)` and the service builds the
   typed page from DTOs.
3. **Get-after-create returns None.** `ReportService.release` re-fetched a report created in the same
   uncommitted transaction (`get_model(report.id)` → `None` → crash). It now sets the timestamp on the
   attached row and returns it directly.

---

## Decision: D26 — Re-check pricing = % of original; tier-upgrade = tier-price delta (S18 / Phase 14)

### Context
PRD Open Question #4 (line 1554) explicitly leaves the Phase-14 re-check pricing model unresolved
(flat / per-agent / % of original). §14.2 fixes tier-upgrade pricing as "delta pricing only".

### Chosen Option
Re-check fee = **a configurable percentage of the original tier price** (`recheck_price_pct`, default
30, held in the S18 system-config store; helper `pricing.recheck_price_kobo`). Tier-upgrade charge =
**`price(to_tier) − price(from_tier)`** (`pricing.upgrade_delta_kobo`), reusing the existing per-tier
prices.

### Rationale
A percentage scales fairly across tiers (a Premium re-check reruns costlier scoped work than a Basic
one) and reconciles cleanly to the kobo. Centralised in `pricing.py` so the Phase-18 admin pricing API
is a single-call-site swap, consistent with the provisional-pricing posture.

### Revisit
Switch models once the Phase-18 admin pricing API lands; the percentage lives in system-config already.

---

## Decision: D27 — Named-recipient sharing built in S17 (full §13.2 table)

### Context
§13.2 defines four sharing modes; the named-recipient mode (full report emailed to a specific address,
time-limited, revocable, disclaimer-ack on first view) is the largest sub-surface.

### Chosen Option
**Build all four modes now**, including named-recipient: a tokenised `VerificationShare` row emails a
magic link; a public full-report-by-token view is gated on a one-time disclaimer acknowledgement;
shares are revocable (token dead immediately) with a 30-day default expiry.

### Tradeoffs
- Pros: the whole proof-sharing surface ships together; §13.3 revocation exit criterion exercised end-to-end.
- Cons: larger S17 (public full-report view + per-recipient ack + share-invite email template).

### Revisit
N/A.

---

## Decision: D28 — Build a minimal admin System-Config domain now (mirrors D14)

### Context
§14 references `dispute_window_days` (default 30), re-check pricing, and upgrade deltas as
admin-configured values. Full Mission-Control system config is Phase 18 (S22).

### Chosen Option
**Build a minimal `system_config` domain now** (user direction): a typed key-value store
(`SystemConfig(key, value_json, description)`) with `ConfigService.get_int/get_bool/set`, seeded
idempotently by `DataSeeder`, and an RBAC-gated admin CRUD. Holds `dispute_window_days`,
`recheck_price_pct`, `agent_dispute_defence_hours`. Pulls the config-store portion of Phase 18 forward,
exactly as D14 pulled the trust-weights CRUD forward.

### Tradeoffs
- Pros: §14 values are admin-configurable at MVP; S22 builds the broader ops config on this base.
- Cons: front-runs part of Phase 18; S22 re-scoped to exclude the config store delivered here.

### Revisit
S22 (Phase 18) objective updated at its run to build on this store.

---

## Decision: D29 — Report re-versioning via version_label + revision_kind (S18 / Phase 14)

### Context
§10.1/§14 want the report to display v1.0 / v1.1 (minor admin revision) / v2.0 (re-check) / v3.0 (tier
upgrade). The `Report` model carries only a monotonic integer `report_version`.

### Chosen Option
**Add a `version_label` (string) + `revision_kind` enum (INITIAL / ADMIN_REVISION / RECHECK /
TIER_UPGRADE) to `Report`.** `ReportService.release(..., revision_kind=…)` computes the label
(INITIAL→"1.0", ADMIN_REVISION→minor bump, RECHECK/TIER_UPGRADE→+1 major). The integer
`report_version` stays the monotonic counter and PK-ordering key; the label is the display convention.

### Rationale
Keeps the existing monotonic counter (and its supersede/versioning tests) intact while giving the
customer-facing semantic label the PRD specifies. Decoupled so the label scheme can evolve without
touching the counter.

### Revisit
N/A.

---

## Note: three runtime bugs the S17/S18 live drive-through surfaced (mocked tests couldn't)

Extending `backend/scripts/e2e_drive_through.py` to cover the §13 sharing + §14 revision flows
against a live backend caught three defects the mocked unit tests missed — the same class of
UUID/transaction gotchas as the S15/S16 gap-closure, all now fixed:
1. **`get_released` called with a native UUID.** The S17 `CustomerReportService` refactor
   (`_content_from_verification`) and `ShareService._build_summary` passed `verification.id`
   (a `uuid.UUID`) into `ReportRepo.get_released`, whose `verification_id` column is `String(36)`
   — asyncpg raised "expected str, got UUID". Both now coerce with `Utils.uuid_to_hex`. This had
   broken the customer report endpoint for *all* customers, not just shares.
2. **Payment reference two-string-forms.** Re-check/upgrade stored/looked-up the linking
   `payment_id` inconsistently (a fresh entity's `.id` is a `uuid.UUID`; the update path
   json-encodes it to `str(uuid)` 36-char, while lookups used `.hex` 32-char). Standardised on
   `Utils.uuid_to_hex(payment.id)` for storage, audit-detail JSON, and `get_by_payment` lookup.
3. **Get-after-create returns None.** `UpgradeService.request` re-fetched the upgrade row it had
   just created in the same uncommitted transaction (`get_model` → `None`), so the controller
   dereferenced `None.status`. It now sets `payment_id` on the attached row and returns it directly.

---

## Decision: D30 — Commission rules = per-role×tier table + admin CRUD (S19 / Phase 15)

### Context
§15.1 wants the agent commission "admin-configured per role × tier," shown on job-accept. The base
built at S10/S12 (D13) accrued a flat `AGENT_COMMISSION_SHARE (0.40) × trust-weight`.

### Chosen Option
**Build a `commission_rule` table + admin CRUD** (mirrors the D14 Trust-Score-Weights CRUD), rate in
**basis points** for exact kobo math (`commission = price_locked_minor × rate_bps / 10_000`). Defaults
seeded to reproduce the prior flat model (`weight_percent/100 × AGENT_COMMISSION_SHARE` = `weight × 40`
bps). RBAC `CONFIGURE_PRICING` (Finance). Accrual reads the rule; the rate shows on the job-accept preview.

### Tradeoffs / Constraints
- Defaults are seeded from a **static** role-weight map (not a live trust-weight DB read) so seeding is
  deterministic and never depends on trust-weight rows being visible mid-seed-transaction (the live
  drive-through caught a zero-rate seed when the read ran before the weights were flushed).
- Admin edits after seed; the Phase-18 pricing API builds on this table.

### Revisit
Fold into the broader Phase-18 pricing/finance config (S22).

---

## Decision: D31 — Earnings balance is derived-by-date; two-stage clearance; stub payouts (S19)

### Context
§15.2 defines a two-stage commission hold: the bulk clears after `commission_clearance_days`, a
`commission_reserve_pct` reserve after the chargeback window. §15.3 requires payout math to reconcile to
the kobo. No payout/withdrawal concept existed.

### Chosen Option
**Derive the agent balance by date on read** (never a stored running total): available = cleared bulk +
released reserve − paid − in-flight-locked payouts; clearing / in-reserve / on-hold / lifetime / paid are
the §15.1 line items. Accrual stamps `clearing_until` and `reserve_until`; a **claim-based clearance
sweep** flips CLEARING→AVAILABLE and releases the reserve, firing `COMMISSION_CLEARED` (the positive-
movement notification, §15.1). A new **payout domain** (agent bank account + payout, `APPROVE_PAYOUT`
finance panel) draws down available (a REQUESTED/APPROVED/HELD payout locks funds so nothing is double-
spent) with a 2-business-day SLA. Disbursement is **stub-first** (approval marks PAID + fires
`PAYOUT_APPROVED`); a real transfer gateway drops in behind this later.

### Tradeoffs
- Deriving-by-date reconciles to the kobo and can't drift; the sweep exists only to fire the notification
  and give a coarse status. Available is clamped at 0 (a late reversal after payout is the accepted,
  bounded §15.2 tail risk).
- Also closes the S18 double-accrual follow-up: `_accrue_commissions` skips a task that already carries a
  live (non-reversed) commission, so a re-checked re-release never double-accrues.

### Revisit
Swap the stub disbursement for a real transfer provider behind the payment facade.

---

## Note: three runtime bugs the S19 live drive-through surfaced (mocked tests couldn't)

Extending `backend/scripts/e2e_drive_through.py` to cover the §15 earnings→payout flow against a live
backend caught three defects the mocked unit tests missed — again the UUID/transaction-boundary class:
1. **`get_live_for_task` called with native UUIDs.** The double-accrual guard passed `verification.id` /
   `task.id` (`uuid.UUID`) into `String(36)` ref-column filters — asyncpg "expected str, got UUID", which
   500'd **every** report release. Both now coerce with `Utils.uuid_to_hex`.
2. **Zero-rate commission seed.** `CommissionRuleService.seed_defaults` read the trust weights via the DB
   mid-seed-transaction before they were visible, so every rate seeded to 0 and no commission accrued. Now
   seeded from a static role-weight map (D30) — no cross-table read ordering dependency.
3. **Payout beneficiary id-form mismatch.** `_resolve_beneficiary` keyed stored accounts by the raw
   `uuid.UUID` `a.id` but the client sends the `.hex` wire id, so a saved account never matched. Now keyed
   by `Utils.uuid_to_hex(a.id)`.

---

## Decision: D32 — Reputation metrics derived on read (S20 / Phase 16)

### Context
§16.1 wants agent metrics: completion rate, accuracy (1–5, admin-assigned), timeliness. The backend
already stores per-task `review_quality` (0–100, admin-set at approval) and task timestamps; no metrics
table exists.

### Chosen Option
**Compute metrics on read** from an agent's verification tasks (no stored metrics — can't drift).
Accuracy = the existing `review_quality` aggregated and shown on a **5-point scale** (reuses the admin
input already captured; no second scoring step). Timeliness = the fraction of submissions within a new
`task_sla_hours` system-config knob (`submitted_at − accepted_at`). A composite (completion + accuracy +
timeliness − decline penalty) drives the assignment ranking. Pure arithmetic in `reputation/metrics.py`.

### Tradeoffs
- Reuses one admin score instead of adding a distinct 1–5 rating action; a richer per-role rubric can
  layer on later without a schema change.
- Metrics recompute per request over an agent's tasks — fine at MVP volume; cache if it grows.

### Revisit
Add a stored/snapshot metrics table only if the per-read aggregation becomes a hotspot.

---

## Decision: D33 — Full coverage + interactive map; backend-owned states canon; unified dashboard (S20)

### Context
§16.1 coverage lets agents declare states + LGAs + travel distance with a "Nigeria map preview," and
specifies role-specific dashboards (Field/Registry/Lawyer). No Nigerian-locations canon existed on the
backend (only a static frontend list).

### Chosen Option
**Full coverage** (states + LGAs + travel radius) with an **interactive Nigeria SVG map** picker. The
backend owns the canonical **37-state** list (`config/nigeria_locations.py`, served at
`GET /config/nigeria-locations`) — the matching-critical field — and validates coverage against it; LGA
stays a free-text convenience. Coverage is **role-differentiated**: Field/Surveyor are location-bound
(coverage gates matching), Registry/Lawyer are remote-capable (coverage does not gate). Availability is
🟢/🟡/🔴, **forced RED at `agent_max_active_tasks`**. Assignment gains a ranked **suggested-agents**
endpoint (role eligibility + credential status + coverage + capacity → composite order; Top-Agent +
low-performance annotations) feeding the admin picker. **One unified enhanced agent dashboard** now (metrics
+ availability + tasks, with Lawyer dependency-gating already visible via the S13 progress component);
the distinct Field/Registry/Lawyer dashboard variants are a documented follow-up.

### Tradeoffs / Constraints
- The SVG map is a **schematic geo-grid** of the 37 states (approximate positions, not cartographic paths)
  — interactive and highlight-driven; an exact GeoJSON path set can drop in behind the same component API.
- "Reduced job-feed visibility" for low performers is realised in the **ranking** (excluded/sunk); the
  broadcast pool is untargeted accept-by-id today, so per-agent pool-feed reduction is a follow-up pending
  a targeted/browsable pool.

### Revisit
Build the role-specific dashboard variants + a precise map + targeted pool visibility when prioritised.

---

## Note: two runtime bugs the S20 live drive-through surfaced

Extending the drive-through to the §16 reputation/coverage/ranking flow caught two the unit tests missed:
1. **Dev seed created AGENT users but no `agent_profiles`/`agent_coverage` rows**, so the profile /
   availability / coverage endpoints 404'd and suggested-agents returned empty. The seed now creates an
   APPROVED profile + Lagos coverage per agent (D24 — the seed extends as slices land).
2. **`AgentCoverageRepo.delete` / `BankAccountRepo.delete` don't exist** — `GenericRepo`'s soft-delete is
   `soft_delete(_id)`. `set_coverage` (and the S19 bank-account remove) now call `soft_delete`. Also, a
   same-transaction re-list read stale rows after the replace, so `set_coverage` now echoes the just-written
   coverage instead of re-querying.

---

## Decision: D34 — Referral anti-farming under stub payments (S21 / Phase 17)

### Context
§17.1 requires referral discount/credit eligibility to need a **distinct verified human**: a
unique verified phone **and** a unique payment instrument (card fingerprint). Payments run in
`PAYMENT_STUB_MODE` and the `Payment` model deliberately holds no raw card data.

### Chosen Option
**Enforce unique-verified-phone anti-farming now; add a forward-compatible nullable
`card_fingerprint` on `Payment`** that stays null under the stub and is checked once the live
gateway surfaces it. `ReferralService._anti_farming_reason` voids a credit on a shared verified
phone (and on a shared card fingerprint when non-null); self-referral is rejected.

### Tradeoffs / Constraints
Consistent with the stub-first posture (KYC/payment/PDF/storage). The card half is dark until a
live gateway fills the fingerprint — phone-uniqueness is the enforced gate at MVP.

### Revisit
Wire real gateway fingerprint capture with the live payment provider.

---

## Decision: D35 — Referral credit uses the §15.2 clearance model (S21 / Phase 17)

### Context
§17.1: the referrer credit must **not** pay out until the invitee's payment clears the
chargeback-window reserve, closing the refer-then-charge-back loop.

### Chosen Option
A **`referral_credits` ledger** (child of `referral/`) mirrors the commission reserve fields: a
credit is created **PENDING** on the invitee's first payment with `clearing_until = paid_at +
chargeback_window_days`, and a swept `sweep_referral_credits()` clears PENDING→CLEARED past that
horizon, crediting the referrer's spendable `credit_balance_kobo` and firing
`REFERRAL_CREDIT_EARNED`. One credit per invitee (idempotency guard). Spent credit is debited from
the customer's balance at PAID (idempotent via `mark_paid`).

### Revisit
N/A — reuses the S19 reserve machinery.

---

## Decision: D36 — Pricing config = DB-backed tier prices + line items (S22 / Phase 18)

### Context
§18.2 exit criterion: pricing controls change customer pricing **without a deploy**. Tier prices
were a hardcoded `TIER_PRICE_NGN_KOBO` dict.

### Chosen Option
Recreate `pricing_tier_config` (tier→price) + `pricing_line_items` in `0001`, seeded from the
static defaults. `PricingConfigService.tier_price_kobo` is the **single resolver** every pricing
path reads (quote/submit/recheck/upgrade), falling back to the static default. The pure
`pricing.py` helpers now take an already-resolved base price (`recheck_price_kobo(base, pct)`,
`upgrade_delta_kobo(from, to)`) so they stay DB-agnostic. Admin CRUD at `/admin/pricing`; edits
take effect on the **next quote** — existing 24h price locks (on the verification row) are honoured.

### Revisit
N/A — the exit criterion is live-verified (an admin edit reflects in the next quote; a locked
price is untouched).

---

## Decision: D37 — Broadcasts = send-now + scheduled, event-bus fan-out (S22 / Phase 18)

### Context
§18.1 broadcasts: audience (All/Admins/Customers/Agents), compose, preview, send now **or**
schedule, manage.

### Chosen Option
A `broadcast` domain (compose→DRAFT/SCHEDULED, preview reach, send-now, cancel, paged list).
Fan-out publishes **one** `BROADCAST_ANNOUNCEMENT` event per send carrying the resolved recipient
ids — the notification subscriber creates the per-user in-app + email, reusing the §4.8 pipeline.
Scheduled sends fire from a swept `BroadcastSweepJobs` (`ALWAYS_NEW`, off under test) + an admin
dev sweep endpoint. Audience resolved from `UserRepo.list_recipient_rows` (user_type + personas).

### Revisit
Batched/queued fan-out if audiences grow large.

---

## Decision: D38 — Full analytics set, server-derived (S22 / Phase 18)

### Context
§18.1 analytics: conversion funnel, avg verification time by tier, agent performance trends
(6-month), revenue by location & tier, regional performance.

### Chosen Option
An `analytics` domain (no entity) computes all five metrics in Python over targeted repo pulls
(`analytics_snapshot`, `revenue_by_verification`, `list_approved_since`, `list_released_scores`).
Endpoints `/admin/analytics/*`, RBAC `VIEW_ANALYTICS`. Backend is the only source of truth; the
dashboard renders lightweight, theme-aware, accessible CSS-bar charts (no charting dependency).

### Tradeoffs / Constraints
Per-request aggregation over the operational tables is fine at MVP volume; materialise/cache if
the dataset grows (consistent with the reputation-metrics posture, D32).

### Revisit
Add a stored/rollup table if the per-read aggregation becomes a hotspot.

---

## Note: two runtime bugs the S21/S22 live drive-through surfaced (mocked tests couldn't)

`backend/scripts/e2e_s21_s22.py` against a live backend caught two the unit tests missed:
1. **`uuid = character varying` join.** `analytics_snapshot` joined `properties.id` (native UUID)
   to `verifications.property_id` (`String(36)`) — asyncpg refused the type mismatch and 500'd
   every time-by-tier/revenue/regional call. Fixed by `cast(Property.id, String)` in the join
   (the two-string-forms gotcha again).
2. **Seed had no Payment row.** The dev seed set `verifications.paid_at` but created no `Payment`,
   so revenue analytics / finance / mission-control all read 0. The seed now records a SUCCEEDED
   Payment (D24 extension); reset clears the growth + broadcast tables.
