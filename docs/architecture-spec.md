# Architecture Specification

> Derived from [PRD.md](../PRD.md) §2, §4, §5 and the existing codebase. Authoritative sources:
> PRD §2 (state machines) and §4 (architecture decisions) — all prose defers to them.

## System Overview

Two deployable apps over HTTP in a monorepo:
- **backend/** — FastAPI (Python 3.12), PostgreSQL (async SQLAlchemy + asyncpg), Alembic, Kink DI.
- **frontend/** — Next.js 16 App Router, React 19, TypeScript, Tailwind v4, Zustand, React Query.

The frontend rewrites `/api/*` to the backend (reverse proxy); **no client call reaches the backend directly**.
API serialises camelCase (`to_camel`) while Python stays snake_case; frontend types are camelCase with no
transform layer. The backend is the **only source of truth** — no facts are derived on the frontend.

## Domain Model

### Entities
- **User** — `user_type` (USER/ADMIN, immutable), `user_persona` ([CUSTOMER, AGENT], additive), trusted status.
- **Agent** (profile on User) — sub-types Field / Surveyor / Registry / Lawyer; KYC result+ref; credentials
  with structured expiry; coverage (states/LGAs/travel); reputation metrics.
- **Admin** (profile on User) — sub-roles Super / Operations / Finance; RBAC permissions.
- **Property** (§4.3) — thin, first-class, separate from Verification: address, coordinates, type, submitted facts.
- **Verification** — points at a Property; tier (Basic/Standard/Premium); `status` (derived); money fields;
  `price_locked_minor` (NGN) + `charge_*`; VID `VP-YYYY-XXXXXX`.
- **Task** — role-scoped unit; per-role state machine; dependency-driven (Lawyer gated).
- **TaskEvidence** — files with server-side GPS/timestamp + SHA-256 content hash; full-res original retained.
- **Report** — versioned (v1.0→v3.0); state machine; trust-score composite.
- **Payment** — gateway-mediated; idempotency keys; chargeback flag/sub-process (not a verification state).
- **Commission / Payout** — integer minor units; clearance hold + chargeback reserve ledger states.
- **Thread / Message** — per-verification threads; message state machine + fraud holds (§4.7).
- **Notification** — projection from event bus via declarative rule table.
- **ConsentDocument / UserConsent** — versioned legal docs + acceptance records (user/version/ts/IP).
- **AuditLog** — append-only; every transition + privileged action; evidence content hashes.
- **Referral / AdminConfig / Conflict rules / Retention(Erasure)** — supporting entities.

### Value Objects
- **Money** — integer minor units + `TransactionCurrency` (NGN/USD/EUR/GBP). Never float/decimal.
- **ExactLocation / Measurement / PropertyImage** — existing frontend types; mirror server-side.
- **VID** — `VP-YYYY-XXXXXX`, high-entropy non-sequential suffix (§4.10).

### Aggregates
- **Verification** is the central aggregate: owns Tasks, Report(s), Payment linkage, consent snapshot, audit trail.
  Global `status` is **derived** from Task states + payment state + admin flags by one owner (§4.1).

## Bounded Contexts

| Context | Domains | Notes |
|---|---|---|
| Identity & Access | user (auth, oauth, otp, consent, session, signup_draft), admin_invitation, admin_team | survives (core auth); admin subdomains to rebuild |
| Agent Lifecycle | user/agent (+kyc), reputation, coverage, earnings | rebuild |
| Verification Lifecycle | property, verification, task, evidence, review, conflict, scoring, report | rebuild; central |
| Money | payment, commission, payout, referral | rebuild; integer minor units |
| Communication | thread (+fraud), message, notification | message survives; thread/notification rebuild |
| Platform Ops | admin_config, analytics, broadcast, content, retention, audit | audit survives; rest rebuild |
| Cross-cutting | appodus_utils (db, decorators, integrations, exceptions, event bus) | survives |

## Database Schema

- PostgreSQL; single squashed migration `0001_initial_schema.py` defines the full schema (**schema contract**, D6).
- `BaseEntity`: `id` (UUID), `date_created`, `date_updated`, `version` (optimistic lock), `deleted` (soft delete).
- Money columns: integer minor units + currency code. Verification: `price_locked_minor`+`currency=NGN` vs
  `charge_currency`/`charge_amount_minor`/`fx_rate_at_quote`.
- Indexes: VID (unique), verification.status, task.(verification_id, role, state), payment.gateway_event_id (idempotency),
  consent (user_id, type, version), audit (entity, ts).
- Relationships: Verification→Property (FK), Verification 1..*→Task, Verification 1..*→Report, Task 1..*→TaskEvidence,
  Verification 1→Payment, Task→Commission, Agent→Commission/Payout.

## Service Layer

- Per-domain `service.py` + `repo.py` (extends `GenericRepo`) + `controller.py`, wired via Kink DI.
- `@transactional` for atomic units (policies USE_IF_PRESENT / ALWAYS_NEW / FALLBACK_NEW).
- **State-derivation owner** `deriveVerificationState(tasks, payment_state, flags)` (§4.1): called after any task
  mutation; applies §2.5 rules in order; counts required tasks from **tier config**, not `COUNT(tasks)`; writes
  `verification.status` once; emits transition to AuditLog. Sole writer of status by convention.
- **State-machine validator**: reusable transition guard enforcing the §2 tables for Verification/Task/Report and
  the §4.7 Message machine; rejects undefined transitions at the service layer.
- **Task-dependency resolver** (§4.2): per-tier `task_dependencies` config; generic "all upstream SUBMITTED?" unlock;
  acyclicity validated at config-save; dependency-blocked tasks not instantiated until unlocked.

## API Design

- FastAPI; camelCase serialization; pagination `page`/`page_size` → `Page[T]`.
- Backend API ↔ frontend service contract kept in sync in the same PR (CLAUDE.md non-negotiable).
- Customer-facing agent fields restricted to `role`/`first_name`/`avatar_url`/`verified` — enforced server-side.
- Idempotency-key header on payment + entity-creation endpoints; idempotent gateway webhook keyed on event ID.
- Dev endpoints `POST /dev/reset` + `/dev/seed` (non-prod only, double-gated). OTP_MODE determinism contract.

## Auth Model

- **Authentication:** JWT in HttpOnly/Secure/SameSite cookie (15-min access / 30-day refresh), silent refresh;
  OAuth popup + postMessage (single-use signed state via Redis delete-on-read, PKCE S256, strict redirect-URI,
  origin-allowlisted targetOrigin). Email verified at signup; phone OTP deferred to first payment.
- **Authorization:** `user_type` gates admin/system access; `user_persona` drives portal routing
  (priority Admin→Agent→Customer); admin sub-role RBAC permission matrix enforced on every admin endpoint;
  centralised Next.js proxy route protection (cookie-presence; validity server-enforced per call).

## Eventing / Async

- **In-process synchronous event bus** (§4.8), DB-backed, not Kafka. Every domain event published once; subscribers:
  Chat projection (increments counter) and Notification projection (declarative rule table → in-app/email/SMS).
  "Routine message → Chat only; high-stakes chat event → Chat + Notification" lives in one rule table.
- **Real-time transport:** SSE for all server→client pushes + 60-sec polling fallback (shared event shape);
  HTTP POST for sends (§4.9). SSE chosen over WS deliberately (admin-mediated, fraud-scanned chat is not live).

## Observability

- Structured logging per request; `AppodusBaseException` with structured context + HTTP mapping.
- AuditLog on every transition (entity/actor/role/from→to/ts/IP/note) + evidence content hashes; retained indefinitely.
- Metrics: SLA-at-risk queue depth, fraud-scan false-positive rate (instrumented from day one), payout reconciliation.

## Security Model

### Threats
- Public-lookup enumeration/scraping; webhook replay/double-processing; OAuth state/CSRF/token leakage;
  off-platform-contact / payment solicitation in messages; evidence tampering; armchair (no-site-visit) fraud;
  referral farming; NDPA PII exposure vs indefinite audit retention.

### Mitigations
- Non-sequential VIDs + rate-limiting + indistinguishable responses (§4.10).
- Idempotency keys (payments + entity creation) + optimistic locking for updates (§4.6).
- OAuth: single-use signed state, PKCE S256, strict redirect-URI, origin-allowlisted postMessage, no silent merge.
- Message fraud scan (§4.7): synchronous, fast-lane for clean, hold flagged; instrumented.
- Evidence: server-side GPS/timestamp stamping + SHA-256 content hash over retained original (§4.5);
  proof-of-presence + property-identity confirm + conflict-of-interest attestation (§7.3a).
- NDPA: minimised third-party PII, lawful-basis recording, pseudonymisation on erasure (§4.11).
- Legal: versioned consent backbone; 1× fees liability cap (§3.5); KYC biometrics via provider facade only.

## Migration Strategy

- Treat `0001_initial_schema.py` as the schema contract (D6); align rebuilt models to it.
- Prefer **additive** migrations per slice; do not edit `0001` unless it is materially wrong vs PRD v2.4.
- Each domain-rebuild slice: model ↔ schema reconciliation check + `alembic upgrade head` clean on all envs.
- Seed first Super Admin via data migration/CLI (Phase 4).

## Testing Strategy

- **Unit:** state-machine validator (every valid/invalid transition), `deriveVerificationState` (§2.5 rules incl.
  dependency-blocked Lawyer), Money/FX arithmetic to the kobo, evidence hash, event-bus fan-out + Chat-vs-Notification rule.
- **Integration:** replayed-webhook idempotency, optimistic-lock conflict, double-tap entity creation, consent recording,
  RBAC per admin endpoint, pagination round-trip.
- **E2E:** auth flows (OAuth matrix), submission→payment→PAID, agent task submit, admin review→release→COMPLETED,
  customer live tracking via SSE, report render + PDF parity, dispute outcomes.
- TDD per CLAUDE.md: write tests first; after each change run tests, build, and lint both ends.
