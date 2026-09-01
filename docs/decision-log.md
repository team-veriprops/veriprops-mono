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

---

## Decision: D39 — S23 completes Phase 19; reconcile the S56/S57/S58 pre-build (S23 / Phase 19)

### Context
Resuming to implement S23 (Phase 19 audit & compliance maturity), exploration found Phase 19 was
already ~40% built and committed under a finer, **undocumented** "S56/S57/S58" code numbering that the
orchestrator docs (which marked S23 fully pending) did not reflect: the customer activity endpoint
(`/verifications/{id}/activity`), consent history + CSV download (`/users/auth/consents/history[/download]`),
the admin action log (`/admin/audit/actions`), and the four `DATA_ERASURE_*` audit action types.

### Chosen Option
S23 **completes** Phase 19 rather than rebuilding it: wire the missing audit-pack export, add the agent
task-history endpoint + the two compliance config keys, build the data-erasure workflow + pseudonymisation,
and build every Phase-19 frontend surface (all routes were pre-declared in `routes.ts`). The S56/S57/S58
work is folded into the S23 record.

### Tradeoffs / Constraints
The pre-built `list_for_verification_pack` was **latently broken** (filtered `resource_type` on uppercase
`"VERIFICATION"`/`"TASK"` while the codebase stores lowercase `"verification"`/`"verification_task"`, so the
§19.3 pack would have been empty) and too narrow. Replaced with an id-based `list_by_resource_ids` and a
`VerificationAuditPackService` that gathers the whole verification object graph (every related repo exposes
`list_for_verification`) into one flat legal-pack CSV (transitions + evidence hashes + consent snapshots).

### Revisit
If the audit dataset grows, the id-set pack query can be indexed/materialised (consistent with D32/D38).

---

## Decision: D40 — MANAGE_COMPLIANCE (SUPER-only) + self-service erasure (S23 / Phase 19)

### Context
Data erasure irreversibly pseudonymises PII. It needs an RBAC gate, and an initiation model.

### Chosen Option
New `Permission.MANAGE_COMPLIANCE`, granted to **SUPER only** (SUPER already holds `set(Permission)`, so no
matrix change was needed — OPERATIONS/FINANCE explicitly do not receive it), gates the admin erasure
approve/reject/execute + the admin erasure page. The audit-log read/export stays on `VIEW_ADMIN_PANEL`
(consistent with the existing action-log). Erasure requests are **self-service** — the data subject opens a
request from Account → Data & privacy (§N.5); an admin reviews → approve → execute, or reject.

### Tradeoffs / Constraints
Concentrating the irreversible action on SUPER limits blast radius. A confirm dialog guards `execute` on the
frontend; one open request per subject is enforced server-side.

### Revisit
Grant MANAGE_COMPLIANCE to OPERATIONS if day-to-day NDPA volume warrants delegated processing.

---

## Decision: D41 — Erasure = pseudonymisation, not deletion; execute is built, legal sign-off is a launch gate (S23)

### Context
§4.11 resolves the audit-retention-vs-NDPA-erasure tension via **pseudonymisation, not deletion**: replace
the subject's identifying PII with a stable opaque token while retaining the events. §B item 12 flags the
post-erasure legal basis + re-identification risk as needing legal sign-off.

### Chosen Option
`PiiPseudonymiser` derives a deterministic per-subject token (`erased-{sha256(user_id + AUTHJWT_SECRET_KEY)[:16]}`)
and scrubs eight surfaces in one transaction — `users` (name/email/phone/avatar/password → login impossible),
`audit_logs` (**actor_id → token, ip → null**, events retained, §4.11), `device_sessions` (+revoked),
`security_events`, `user_consents`, `oauth_identities`, `kyc_records`, `agent_bank_accounts`. Execute works in
all non-prod envs (the live e2e proves it end-to-end); the §B legal-basis sign-off is a documented **launch
gate**, consistent with D18 (Legal Opinion build-behind-flag) and the S9/S14 legal gates.

### Tradeoffs / Constraints
Runs via `get_db_session_from_context()` bulk `update()`s (sanctioned for transactional service code) — avoids
scattering near-identical scrub methods across eight repos. Secondary PII (payment card fingerprints,
third-party share-recipient emails, property addresses) is a documented follow-up — each needs its own
retention basis. True anonymisation (§4.11 caveat: context can re-identify) is out of scope by design.

### Revisit
Extend the scrub set + revisit the token/retention basis once §B item 12 legal sign-off lands.

---

# Cycle 2 — WhatsApp Channel (PRD.md §7)

> Cycle 1 (core platform, D1–D41) closed with [final-audit.md](final-audit.md); its as-built state
> is consolidated in [MASTER-PRD.md](../MASTER-PRD.md). Cycle 2 implements the locked §7 WhatsApp
> Channel spec. The PRD's own Decision Record A–P is imported as **locked upstream input** — those
> letters are cited directly and are not re-decided here. D-numbering continues below with the
> decisions taken at the cycle-2 `initialize` clarification gate (2026-08-31, user-answered).

## Decision: D42 — Fresh cycle-2 docs; cycle-1 archive carried forward

### Context
Cycle-1 orchestrator docs were moved to `docs.back/`. MASTER-PRD.md links to
`docs/decision-log.md` and `docs/final-audit.md`; recovery-first resume needs a clean cycle-2
runtime state, but decision history should stay continuous.

### Options Considered
1. Fresh docs/ + copy decision-log & final-audit back; append to the same log (continuous D-numbering).
2. Fully fresh docs/, archive untouched, MASTER-PRD links dead or retargeted.
3. Restore everything and extend the completed cycle's files in place.

### Chosen Option
**Option 1** (user-selected; also the recommendation).

### Rationale
MASTER-PRD links stay valid; one continuous decision history; progress/requirements/runtime state
start clean so resume semantics are unambiguous.

### Tradeoffs / Constraints
The log grows large; `docs.back/` remains the authoritative archive for cycle-1 analysis,
matrix, execution plan, progress, and runtime state. `docs/final-audit.md` currently holds the
**cycle-1** audit and will be superseded by the cycle-2 final audit at completion.

### Revisit
Not expected.

## Decision: D43 — Live Meta Cloud API from day one, deterministic stub sibling mandatory

### Context
PRD Decision C locks transport = Meta Cloud API direct (no BSP). Launch gates (Meta Business
verification, green tick, template approvals, number custody) are external. The repo's §4.13
facade pattern normally ships stub-first. A live-send provider already exists
(`appodus_utils/integrations/messaging/providers/whatsapp/whatsapp_business.py`) with Cloud API
settings and secret keys registered in `Settings.SECRET_ENV_KEYS`.

### Options Considered
1. Stub-first facade; live wiring deferred as TODO(gap).
2. **Live Meta Cloud API wired from day one alongside the deterministic stub** — live path
   config-selected (Doppler secrets), stub is what CI/e2e run.
3. Concierge phase only (widget, no bot).

### Chosen Option
**Option 2** (user-selected, overriding the stub-first recommendation).

### Rationale
Surfaces real-transport behaviour (24-hour window, template review quirks, media semantics) early
instead of at the end; the existing live provider means much of the send path is already written.

### Tradeoffs / Constraints
- Pros: no late-integration surprises; live smoke tests possible as soon as Meta assets exist.
- Cons: development can be blocked on external Meta assets for the live path; mitigated by the
  stub being the default in every non-prod environment.
- Constraint (non-negotiable): **CI/e2e never touch Meta.** The stub transport must satisfy the
  full e2e suite, mirroring the `OTP_MODE`/`KYC_PROVIDER=STUB` determinism contracts. Provider
  selection is a config knob; live requires real secrets via Doppler.
- Constraint: webhook receiver must be built against Meta's real signature scheme
  (`X-Hub-Signature-256` over the raw body) from the start, with recorded-fixture tests.

### Revisit
If Meta assets stall the schedule, slices proceed on the stub and live smoke moves to S11.

## Decision: D44 — LLM-assisted intent classification (Claude), deterministic flows and guardrails

### Context
§7.6 requires "structured conversation flows, intent matching, guardrail enforcement". Options
were deterministic keyword/menu matching vs LLM-assisted classification of free text into the
fixed intent set.

### Options Considered
1. Deterministic menus + keyword matching only.
2. **Claude classifies free text into the fixed §7.6 intent set; flows stay deterministic
   state machines.**

### Chosen Option
**Option 2** (user-selected, overriding the deterministic-only recommendation).

### Rationale
Better free-text handling from day one; escalation-rate metric (§7.10) still measures coverage.

### Tradeoffs / Constraints
- The classifier lives behind its own facade (`INTENT_PROVIDER=STUB|CLAUDE` pattern): STUB is a
  deterministic keyword table used by CI/e2e; CLAUDE is the live provider.
- **Guardrails remain deterministic and sit outside the classifier**: guardrail topics, menu
  selections, and the two-unmatched-intents escalation rule are enforced by the bot engine
  regardless of classifier output. Classifier error/timeout/low-confidence routes to a human,
  never a guess (§7.6.4).
- The classifier only ever returns a member of the closed intent enum (structured output;
  free literals prohibited per repo enum rule).
- Default model assumption: **Haiku-class** (`claude-haiku-4-5`) for cost/latency; a Settings
  knob, revisable without redesign. `ANTHROPIC_API_KEY` joins `SECRET_ENV_KEYS` via Doppler.
- Consult the `claude-api` skill at implementation time for current model ids/limits.

### Revisit
Model choice and prompt once real conversation data accrues (concierge corpus, §7.11).
**Amended by D48 (2026-08-31):** the classifier facade is provider-agnostic — no lock-in to
Anthropic/Claude; the Claude-specific knob and key named above are superseded.

## Decision: D45 — §7.3.2 channel states are a projection, not a new case state machine

### Context
§7.3.2 lists `enquiry → intake_in_progress → intake_complete → payment_pending → paid → verifying
→ field_inspection → report_ready → delivered → closed`. The backend already has the authoritative
`VerificationStatus` machine (MASTER-PRD §3.1) plus draft/payment states, and §7.3.1 mandates the
bot read the same state through the same API as the dashboard.

### Chosen Option
Map §7.3.2 names onto existing state: pre-case stages (`enquiry`, `intake_in_progress`,
`intake_complete`) live in bot-session + existing submission-draft state; from payment onward the
projection derives from `VerificationStatus` + payment records, exactly as the customer tracking
labels (§14.2) already do. No schema change to the case machine; a single projection function
owns the mapping (single state-derivation owner, §4.1).

### Rationale
Two state machines for one case is the "two surfaces show different statuses" failure §7.3.1
exists to prevent.

### Tradeoffs / Constraints
Milestone template triggers (§7.7) bind to existing domain events, not to projected names.

### Revisit
Only if intake resumability turns out to need persisted states the draft model cannot express.

## Decision: D46 — SMS-OTP fallback deferred; WhatsApp auth template is the v1 linking transport

### Context
PRD Decision C notes "SMS-OTP fallback provider pending (§B)". Twilio/Termii providers exist in
the messaging layer but no provider decision has been made upstream.

### Chosen Option
Defer SMS fallback entirely at v1 (default assumption, minor — not user-blocking): E1 linking OTPs
go via the WhatsApp `otp_auth` template (deterministic under `OTP_MODE`); a `TODO(gap):` marks the
fallback site and a Known-Gaps row tracks the pending provider decision.

### Rationale
The linking flow's primary transport is WhatsApp itself; blocking v1 on an unmade upstream
provider decision would violate scope discipline.

### Revisit
When §B resolves the SMS provider, wire it through the existing router fallback pattern
(same shape as the email Resend→Mailjet→SES chain).

## Decision: D47 — Pre-initialize commit hygiene executed

### Context
Skill config: commit mode `advisory`, `require_clean_worktree_before_run: true`. The worktree
carried unrelated in-flight work (Resend email provider, UAT Playwright suite, PRD/docs
restructure).

### Chosen Option
User approved committing before initialize. Landed as three logical commits: Resend provider +
email fallback chain; UAT Playwright suite + enablement fixes (incl. seeded-consent fix and two
ruff autofixes in the OAuth controller); MASTER-PRD/PRD/docs restructure. Worktree clean before
artifact generation.

### Revisit
n/a.

## Decision: D48 — Intent LLM is provider-agnostic (amends D44)

### Context
User refinement after initialize (2026-08-31): the LLM used for intent classification must not be
locked to one platform (OpenAI, Anthropic, DeepSeek, …). D44's original wording committed to
Claude specifically (`INTENT_PROVIDER=STUB|CLAUDE`, `ANTHROPIC_API_KEY`).

### Options Considered
1. **In-house facade + adapters** — `IntentClassifier` interface in
   `appodus_utils/integrations/intent/` with named providers, mirroring the messaging provider
   registry: `STUB` (deterministic keyword table, CI/e2e), `ANTHROPIC` (native adapter), and
   `OPENAI_COMPATIBLE` (generic adapter with configurable base URL + model + API key — one adapter
   covers OpenAI, DeepSeek, Groq, Ollama, and most other providers).
2. LiteLLM dependency as the multi-provider layer.
3. Defer the abstraction shape to slice S5.

### Chosen Option
**Option 1** (user-selected; also the recommendation).

### Rationale
Matches existing repo conventions (messaging registry, `KYC_PROVIDER=STUB` facade shape), adds
zero dependencies for what is a single structured `classify()` call, and the OpenAI-compatible
adapter makes provider switching a config change, not a code change.

### Tradeoffs / Constraints
- Pros: no vendor lock-in; provider/model swappable via settings (`INTENT_PROVIDER`,
  `INTENT_MODEL`, base URL + key) with secrets in Doppler; STUB path unchanged so the
  determinism contract holds.
- Cons: two small adapters to maintain in-house; no built-in cross-provider retry/fallback at v1
  (can be added later in the router shape the email chain uses, if ever needed).
- Everything else in D44 stands unchanged: flows and guardrails deterministic and outside the
  classifier; closed intent enum only; classifier failure/low-confidence ⇒ human routing.
- Default provider/model chosen at S5 (Haiku-class-or-equivalent latency/cost target); the
  provider's API key joins `SECRET_ENV_KEYS`.

### Revisit
Add a fallback chain across providers only if live error rates warrant it.

## Decision: D49 — `0001` frozen; additive migrations from `0002` onward

### Context
D9 made `0001_initial_schema.py` the single editable migration while the schema was
greenfield, and scoped that posture itself: "once a non-throwaway database exists
(staging/prod), stop editing `0001`". Cycle 2 adds **columns to existing tables**
(`conversations`, `chat_messages`), and `0001` builds a table only when it is absent — so
a column added there is silently skipped on every already-migrated database.

### Options Considered
1. **Additive `0002`+ from here; `0001` frozen.**
2. Keep editing `0001`, requiring every existing database to be dropped and rebuilt.

### Chosen Option
**Option 1** (user-selected; also the recommendation).

### Rationale
Column additions actually apply. The local dev database, the dev-branch deploy, and the
UAT suite's seeded data all survive. It is D9's own revisit condition, reached.

### Tradeoffs / Constraints
- Migration history grows again, which D9 had deliberately collapsed.
- Additive revisions carry **no** `table_exists` guard: alembic's version table already
  runs each once, and the guard breaks offline (`--sql`) generation.
- `test_migration_schema_parity.py` now reads builders from every migration in
  `versions/`, not only `0001`.

### Revisit
Not expected — this is the normal posture from here.

## Decision: D50 — Landing depth is per-intent, not uniform

### Context
§7.4.2 says the three `/wa/*` landings are "pre-authenticated for that action"; §7.5 says
the token is not a session; and locked Decision B says report delivery is an
**authenticated** portal link. Those cannot all be satisfied by one uniform depth.

### Options Considered
1. **`pay` token-scoped; `upload` and `report` hand off to the authenticated portal.**
2. All three fully token-scoped.
3. All three validate then hand off to login.

### Chosen Option
**Option 1** (user-selected after asking for the risk in option 2).

### Rationale
The intents carry very different downside. A leaked `pay` link costs a stranger paying
someone else's bill — no disclosure, no card data, and payment friction is what §7.10
calls the channel's most important metric. A leaked `report` link would let whoever taps
first in a forwarded family group open the full report, deciding access by tap order and
bypassing the §13.2/§13.3 sharing model whose exit criterion is that revocation works. A
leaked `upload` link would let anyone inject evidence into the canonical verification file
(§7.1.6/M1) — the conversation-hijack class §7.4.3 exists to defeat.

### Tradeoffs / Constraints
- Two of three landings still require a login; both pre-fill the redirect so a signed-in
  customer is one tap away.
- Option 2 would have required a new decision overriding locked Decision B.

### Revisit
If seam-conversion data shows the report login is costing materially, revisit `report`
alone — with a fresh decision, not silently.

## Decision: D51 — Redeem once, then hold a short-lived scoped grant

### Context
§7.5 records the `jti` on redemption and rejects replays. Read literally, the link burns
on the first page load — a refresh, a back-navigation, or WhatsApp's own link-preview
fetch is enough.

### Options Considered
1. **Redeem once, issue a grant scoped to that intent + case, valid until the token's own
   expiry.**
2. Strict: every page load redeems.

### Chosen Option
**Option 1** (user-selected; also the recommendation).

### Rationale
Preserves replay rejection where it matters (a forwarded copy is dead) without making a
refresh on a phone destroy the customer's link.

### Tradeoffs / Constraints
- The grant is explicitly **not a session**: HttpOnly, path-scoped to
  `/api/public/wa/handoff`, `SameSite=Lax` (the customer arrives cross-site from
  WhatsApp), expiring with its token, carrying no role or persona.
- `redeem` accepts the caller's existing grant nonce so the original holder resumes;
  anyone else presenting the same token is refused. **Writing the e2e scenario for this is
  what caught that the landing re-redeemed on every mount** — the grant existed but was
  never consulted.
- One more concept to pen-check; tracked in `docs/handoff-token-pen-check.md`.

### Revisit
Not expected.

## Decision: D52 — Widget config split by ownership

### Context
WA-02 requires the official number to render "from a single config source", and repo rule
5 makes the backend the only source of truth — but page-code attribution describes
frontend routes the backend does not model.

### Chosen Option
The number and a `whatsappWidgetEnabled` flag join `/config/public`; page codes derive
from the frontend route registry, with a first-segment fallback so a new page stays
attributable without a table edit.

### Rationale
The number is published on the site, on certified reports, and in bot copy — one backend
value keeps them from drifting, and the widget renders nothing rather than falling back to
a hardcoded number. Route naming is genuinely frontend knowledge.

### Revisit
If the backend ever needs to reason about page codes (e.g. server-side attribution
reporting), move the table server-side then.

## Decision: D53 — Intent facade: in-house, three providers, Anthropic default

### Context
D48 settled that intent classification is provider-agnostic and left the default provider
and model "chosen at S5". S5 needs the answer before the facade is written.

### Options Considered
1. **Both adapters, Anthropic default** — `STUB` (keyword table, CI/e2e), `ANTHROPIC`
   (native, structured tool-use), `OPENAI_COMPATIBLE` (base URL + model + key).
2. Generic OpenAI-compatible adapter only, pointed at Anthropic's compat endpoint.
3. STUB only now; live adapter deferred to S11.

### Chosen Option
**Option 1** (user-selected; also the recommendation). Prod default `INTENT_PROVIDER=ANTHROPIC`,
`INTENT_MODEL=claude-haiku-4-5`.

### Rationale
Native structured output is the most reliable way to force an answer from the closed
intent enum — the guarantee §7.6.4 rests on. The generic adapter keeps provider switching
a config change, so there is no lock-in despite a named default.

### Tradeoffs / Constraints
- Two live adapters to maintain instead of one.
- `ENVIRONMENT=test ⇒ INTENT_PROVIDER=STUB`, enforced at startup like the
  `WHATSAPP_PROVIDER`/`OTP_MODE` contracts. CI and e2e never call a model.
- The provider's API key joins `SECRET_ENV_KEYS`.

### Revisit
If live error rates warrant it, add a cross-provider fallback chain in the shape the
email router already uses.

## Decision: D54 — FAQ content is code-owned; pricing answers come from the live config

### Context
WA-30 requires FAQ/Learn/Pricing answers from "a maintained content set", and the
requirements matrix marked it `Schema: yes`. Pricing is already admin-tunable through
`PricingConfigService`.

### Options Considered
1. **Code-owned content module + pricing rendered from `PricingConfigService`.**
2. `whatsapp_content_entries` table with an admin CRUD editor in S5.
3. Table seeded from code, read-only in S5, editing deferred to S8.

### Chosen Option
**Option 1** (user-selected; also the recommendation). Amends WA-30's `Schema: yes` — no
content table is created.

### Rationale
A second source of pricing truth is the failure the "backend is the only source of truth"
rule exists to prevent: a stale table would have the bot quoting a price the website does
not charge. Prose changes are copy, and copy benefits from review.

### Tradeoffs / Constraints
A wording fix needs a deploy. Accepted: the alternative was an admin CRUD surface inside
an already-large S5, for content that changes rarely.

### Revisit
If ops needs same-day copy edits at volume, promote the module to a table plus the admin
editor S8's template registry will already have the shape for.

## Decision: D55 — `HandoffIntent.LINK`: one signer, two exclusive claim shapes

### Context
WA-24 (WhatsApp→web linking) needs a signed link carrying a phone number. §7.5's claim
list is `sub · case · intent · exp · jti` — an action token's shape. A linking token has
no case, and no customer either: it is minted for a number with no account yet.

### Options Considered
1. **Extend `HandoffIntent` with `LINK`; make `case`/`sub` optional and add a `phone`
   claim, with a validator holding the two shapes apart.**
2. A separate link-token module with its own signer and redemption table.
3. No token — an unsigned deep link, with the OTP carrying all the weight.

### Chosen Option
**Option 1** (user-selected; also the recommendation).

### Rationale
One RS256 signer, one `jti` ledger, one pen-check surface. A second implementation would
double what §7.11's token pen-check has to cover, for a token that is strictly weaker than
the ones already there.

### Tradeoffs / Constraints
- Deviates from §7.5's literal claim list — hence this entry.
- The shapes are **mutually exclusive by construction**: a model validator rejects a
  `link` token naming a case and an action token missing one, and `_encode` emits only the
  keys a shape uses, so neither carries the other's claims even on the wire.
- The public `/public/wa/handoff/{intent}/…` landings refuse `link` outright — those
  routes hand out case context, and a link token names no case.
- `handoff_token_redemptions.case_id` becomes nullable (migration `0004`), with a
  `phone_e164` column so a link redemption is still traceable.
- Starting a linking attempt **reads** the token; only confirmation spends it. Burning it
  at page load would strand a customer whose first code never arrived.

### Revisit
If a fourth intent shape appears, promote the shape rules to a per-intent schema rather
than growing the validator.

## Decision: D56 — Chat intake collects the full field set; consent and payment stay on web

### Context
§7.6.2 requires chat intake to collect "the same fields as web intake", while §7.4.6 puts
the two consent controls at payment confirmation and the §7.3.4 capability matrix makes
payment web-only.

### Options Considered
1. **Full field set + tier in chat; consent and payment on the `pay` landing.**
2. Core fields in chat, finish on web.
3. Full parity including consent captured as chat confirmations.

### Chosen Option
**Option 1** (user-selected; also the recommendation).

### Rationale
Honours "same fields" without moving consent off the screen §7.4.6 names. Option 2 leaves
the WhatsApp-only customer unable to finish; option 3 downgrades the evidentiary quality
of a consent record that has to stand up as a legal artefact.

### Tradeoffs / Constraints
The longest bot flow in the cycle. Both surfaces write the same `verifications` draft row
(`draft_step`/`draft_payload`), which is what makes resumption real rather than claimed.

### Revisit
If chat intake completion rates are poor, revisit the step granularity — not the seam.

## Decision: D57 — Sticky human mode with explicit hand-back

### Context
Every inbound WhatsApp message already lands in the admin console. Once an agent is in the
thread, the bot must stop answering — §7.6.2's escalation says "routed to console", which
only means something if the bot then goes quiet.

### Options Considered
1. **Sticky `HUMAN` mode; an admin hands control back from the console.**
2. Time-window suppression after any admin message.
3. Bot always replies.

### Chosen Option
**Option 1** (user-selected; also the recommendation).

### Rationale
A bot talking over an agent mid-conversation is the failure customers notice most, and a
time window is a guess that will be wrong for slow threads. It also makes §7.10's
escalation-rate metric exactly countable rather than inferred.

### Tradeoffs / Constraints
An agent who forgets to hand back leaves the thread bot-less, so the console shows the
mode; a 30-day idle also resets to the welcome flow.

### Revisit
If hand-back is routinely forgotten, add an inactivity auto-return with a visible notice —
not a silent one.

## Decision: D58 — WA-21's opaque short code is the existing VID

### Context
§7.4.3 requires "Continue on WhatsApp" affordances to carry an opaque case code, never an
address or customer name, because WhatsApp renders message previews.

### Chosen Option
Reuse the existing `vid` (`VP-YYYY-XXXXXX`, `app/core/vid.py`). No new column.

### Rationale
It is already opaque, already CSPRNG-suffixed, already the code the customer sees on the
dashboard and on their report, and already what the handoff landings acknowledge. A second
code would be a second thing to keep in sync for no gain.

### Revisit
Not expected.

## Decision: D59 — Meta template registry: definitions in code, status from Meta

### Context
S4 shipped the `otp_auth` linking OTP, but `render_whatsapp_payload` could only produce
free text. Meta accepts free text only inside the 24-hour service window, and an OTP to a
number that has never messaged us is definitionally outside it — so the path worked on the
stub and would have failed live. Closing it means building §7.7, which also unblocks the
launch gate: "all §7.7 templates approved" is on the critical path because approval lags,
and nothing in the app could say which templates existed or what Meta thought of them.

### Options Considered
1. **Code-owned definitions + a Meta-synced status table + a read-only admin page.**
2. Code-owned definitions only; approval tracked in the launch-gate checklist.
3. A full CRUD registry — names, categories and parameters editable by an admin.

### Chosen Option
**Option 1** (user-selected; also the recommendation), in three parts:

**D59a — definitions in code, status from Meta.** The Meta template name, category,
language, ordered parameter list and button kind live in
`appodus_utils/integrations/messaging/templating/whatsapp_templates.py`. Approval status
lives in `whatsapp_templates`, populated from `GET /{waba_id}/message_templates` through a
`WHATSAPP_PROVIDER`-selected directory facade. Closes WA-15/WA-41.

**D59b — template-by-registration, not window-by-send.** A declared §7.7 template always
sends as a template; free text is reserved for in-conversation bot replies. All seven §7.7
templates are business-initiated and therefore outside the window by construction, and a
bot reply is inside it by construction — so the rule is a property of the message, not a
runtime guess about timing.

**D59c — approval is advisory at send time.** An unapproved template shows in the registry
and on the §7.11 checklist; it never fails a send. A stale sync must not be able to take
the channel down.

### Rationale
The code is what fills a template's parameters, so a DB-editable parameter list nothing
reads would describe something the app does not do — and the failure would surface as a
rejected send in production. Status is the opposite: it is genuinely Meta's, changes
without a deploy, and is what the launch gate asks about. Splitting them on that line
gives each half an owner that can actually be right.

### Tradeoffs / Constraints
- The declaration's parameter **order** is the wire contract: Meta's body parameters are
  positional and unnamed, so a reordered list delivers the right values in the wrong
  sentence. `_build_template` now orders numerically — string ordering put "10" before
  "2", harmless at today's counts and silently wrong past nine parameters.
- `StubTemplateDirectory` reports the declared set as `APPROVED` so the channel stays
  fully demoable without Meta; the live directory is the same interface behind the other
  transport, and CI/e2e never reach Meta.
- An unreadable or absent status becomes `NOT_FOUND`, never `APPROVED`: optimism here
  would let the §7.11 gate pass on a template that cannot be delivered.
- All seven templates are declared with bodies although only `otp_auth` has a sender —
  §7.7 exists to get them submitted early. Their consumer until S6–S9 is the registry page
  and the Meta submission.
- **TODO(gap):** the authentication-template *button* component shape (copy-code /
  one-tap) could not be confirmed from Meta's public send-side documentation, so it is
  declared per template and `otp_auth` ships body-only. Confirm against the real approved
  template during the S11 live smoke.

### Revisit
If ops needs same-day copy edits at volume, promote the bodies to a table plus an editor —
the registry page already has the shape for it.
