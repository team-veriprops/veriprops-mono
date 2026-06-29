# Execution Plan

> Slice-based, **MVP-first** (D2). Each slice is a vertical cut where possible (backend domain + Alembic +
> tests + frontend), per CLAUDE.md non-negotiables. Status seeded from the brownfield audit (D1); rebuilt
> models align to the `0001` schema (D6). Run order is top-to-bottom; later slices assume earlier are green.

## Sequencing overview

```
S1  Reconcile foundation + doc fixes        (closes survivors, fixes CLAUDE.md DB)
S2  State-machine core (validator + derive owner + dependency config)   ← unblocks everything
S3  Money + idempotency + VID + evidence-hash primitives
S4  SLA business-day/holiday calendar
── MVP feature spine ──
S5  Phase 1 marketing completion
S6  Phase 2 auth hardening (account-security gaps)
S7  Phase 3 agent onboarding & KYC
S8  Phase 4 admin onboarding & RBAC
S9  Phase 5 customer submission + payment      (legal-cap copy gate)
S10 Phase 6 admin control panel + 6a chargeback
S11 Phase 7 agent task execution
S12 Phase 8 admin review & report release
S13 Phase 9 customer tracking & evidence layer (SSE)
S14 Phase 10 final report experience           (NBA gate on Legal Opinion go-live)
── Harden & scale ──
S15 Phase 11 communication layer
S16 Phase 12 notifications & event bus
S17 Phase 13 public lookup & sharing
S18 Phase 14 revision/re-verification/disputes
S19 Phase 15 agent earnings & commission
S20 Phase 16 reputation & coverage
S21 Phase 17 growth & conversion
S22 Phase 18 admin ops & analytics
S23 Phase 19 audit & compliance maturity
```

---

## Slice S1 — Foundation reconciliation & doc fixes
### Objective
Confirm surviving foundation works against `0001`; fix the CLAUDE.md DB mismatch (D4) and `web/`→`frontend/` (D5).
### Requirements Covered
R0.1–R0.7, R0.17, R0.19, R0.22 (verify); doc corrections.
### Dependencies
none.
### Files Impacted
`CLAUDE.md` (MySQL→PostgreSQL), `appodus_utils/*` (verify), `backend/main/alembic/versions/0001_initial_schema.py` (read-only check).
### Schema Changes
none (reconciliation only).
### Tests Required
`alembic upgrade head` clean on local/test; existing foundation unit tests green.
### Acceptance Criteria
Foundation imports/tests pass; CLAUDE.md states PostgreSQL; no `web/` references in new docs.
### Risk Level
Low.
### Commit Message
`chore(foundation): reconcile survivors with 0001 schema; fix DB/dir docs`

## Slice S2 — State-machine core (§2, §4.1, §4.2)
### Objective
Build the reusable transition validator, `deriveVerificationState(...)` owner, and per-tier task-dependency config.
### Requirements Covered
R0.9, R0.10, R0.11.
### Dependencies
S1.
### Files Impacted
new `app/domain/verification/state_machine.py`, `.../derivation.py`, `.../dependencies.py`; align to `0001`.
### Schema Changes
confirm `task_dependencies`/tier-config tables in `0001`; additive only if missing.
### API Changes
none (internal primitives).
### Tests Required
every valid/invalid transition for all four machines; §2.5 rules in order incl. dependency-blocked Lawyer counted from tier config; acyclicity rejection.
### Acceptance Criteria
Invalid transitions rejected; status derived, never set inline; Lawyer not instantiated until siblings SUBMITTED.
### Risk Level
High (correctness-critical; everything depends on it).
### Commit Message
`feat(core): state-machine validator, derivation owner, task-dependency config`

## Slice S3 — Money, idempotency, VID, evidence-hash primitives
### Objective
Close the remaining Phase-0 money/safety primitives.
### Requirements Covered
R0.5 (confirm), R0.13, R0.14, R0.15.
### Dependencies
S1.
### Files Impacted
`appodus_utils/db/types/money.py` (confirm), new idempotency-key middleware + dedup store, VID generator, evidence content-hash helper.
### Schema Changes
idempotency/dedup table keyed on gateway event ID + client key (additive).
### Tests Required
replayed-webhook → one PAID/receipt; double-tap create → one row; VID non-sequential/high-entropy; SHA-256 mismatch detectable.
### Acceptance Criteria
Phase-0 idempotency + VID + evidence-hash exit criteria pass.
### Risk Level
High.
### Commit Message
`feat(core): idempotency keys, non-sequential VID generator, evidence content-hash`

## Slice S4 — SLA business-day & Nigerian holiday calendar
### Objective
Wire the SLA calculator used from PAID onward.
### Requirements Covered
R0.21.
### Dependencies
S1.
### Files Impacted
new `app/domain/verification/sla.py` + holiday data.
### Tests Required
SLA excludes weekends + NG public holidays; countdown correctness.
### Acceptance Criteria
Phase-0 SLA exit criterion met.
### Risk Level
Medium.
### Commit Message
`feat(core): SLA business-day calculator with Nigerian holiday calendar`

## Slice S5 — Phase 1 Marketing completion
### Objective
Finish landing sections, currency toggle, SEO/noindex, dynamic year.
### Requirements Covered
R1.1–R1.6.
### Dependencies
S1.
### Files Impacted
`frontend/src/components/website/*`.
### Tests Required
content/data module unit tests; renders 1440px + 375px.
### Acceptance Criteria
All sections render; CTAs route with intent; currency cycles NGN→USD→GBP→EUR.
### Risk Level
Low.
### Commit Message
`feat(marketing): complete Phase 1 landing sections + currency toggle + SEO`

## Slice S6 — Phase 2 Auth hardening
### Objective
Close account-security gaps on top of the working auth core.
### Requirements Covered
R2.2, R2.5–R2.9, R2.14 (partials → done).
### Dependencies
S1.
### Files Impacted
`app/domain/user/auth/*`, `frontend/src/components/website/auth/*`.
### Tests Required
lockout (warn@5/lockout@7); reset invalidates sessions; device revoke; link/unlink password guard; cross-portal badge.
### Acceptance Criteria
Phase-2 exit criteria fully met; no PII leak.
### Risk Level
Medium.
### Commit Message
`feat(auth): rate-limit, password reset, devices, linked accounts, cross-portal badge`

## Slice S7 — Phase 3 Agent Onboarding & KYC
### Objective
Rebuild agent application wizard + KYC facade + credentials/expiry + approval queue.
### Requirements Covered
R3.1–R3.7.
### Dependencies
S2, S6.
### Files Impacted
`app/domain/user/agent/**` (+kyc providers), `frontend/src/app/agents/**`.
### Schema Changes
align agent/KYC/credential tables to `0001` (additive if needed).
### Tests Required
resumable wizard; provider result persisted (no raw biometrics); role-level suspension on expiry.
### Acceptance Criteria
Phase-3 exit criteria; KYC docs encrypted + access-controlled.
### Risk Level
High (KYC, encryption).
### Commit Message
`feat(agent): onboarding wizard, KYC provider facade, credential expiry, approval queue`

## Slice S8 — Phase 4 Admin Onboarding & RBAC
### Objective
Rebuild admin invite/acceptance, RBAC matrix, team management, seed Super Admin.
### Requirements Covered
R4.1–R4.5.
### Dependencies
S6.
### Files Impacted
`app/domain/user/admin_invitation/**`, `app/domain/user/admin_team/**`, migration seed, `frontend/src/app/admin/**`.
### Tests Required
permission checks per admin endpoint; role changes audit-logged; invite scenarios.
### Acceptance Criteria
Phase-4 exit criteria; first Super Admin seeded.
### Risk Level
High (authz).
### Commit Message
`feat(admin): invitations, RBAC matrix, team management, super-admin seed`

## Slice S9 — Phase 5 Customer Submission & Payment
### Objective
Rebuild submission wizard, pricing/price-lock, consent, gateway payment, phone gate, receipts.
### Requirements Covered
R5.1–R5.11.
### Dependencies
S2, S3, S4, S6.
### Gate
**Liability-cap consent copy (§3.5/§B) must be finalised before go-live.**
### Files Impacted
`app/domain/property/**`, `app/domain/verification/**`, `app/domain/payment/**`, `frontend/src/app/portal/verifications/new/**` + pay.
### Schema Changes
align property/verification/payment to `0001`; price-lock + charge fields.
### Tests Required
DRAFT→SUBMITTED→PAYMENT_PENDING→PAID via derivation owner; dup-webhook idempotency; double-tap create idempotent; phone gate; trusted upgrade.
### Acceptance Criteria
Phase-5 exit criteria all pass.
### Risk Level
High (money, legal gate).
### Commit Message
`feat(verification): submission wizard, pricing/price-lock, consent, gateway payment`

## Slice S10 — Phase 6 + 6a Admin Control Panel & Chargeback
### Objective
Verifications list/detail, assignment (manual + broadcast), work queue/SLA shedding, chargeback sub-process.
### Requirements Covered
R6.1–R6.9, R6a.1–R6a.2.
### Dependencies
S7, S8, S9.
### Files Impacted
`app/domain/verification/admin/**`, `app/domain/payment/**`, `frontend/src/app/admin/verifications/**`.
### Tests Required
first assign → PAID→IN_PROGRESS; Lawyer auto-lock; chargeback flags payment + freezes commission without touching state machine; rebuttal pack assembles.
### Acceptance Criteria
Phase-6 + 6a exit criteria.
### Risk Level
High.
### Commit Message
`feat(admin): verification control panel, assignment, work queue, chargeback handling`

## Slice S11 — Phase 7 Agent Task Execution
### Objective
Agent dashboard, accept/decline + capacity, role submission UIs, proof-of-work/COI, offline.
### Requirements Covered
R7.1–R7.7.
### Dependencies
S2, S3, S10.
### Files Impacted
`app/domain/verification/task/**` (+evidence), `frontend/src/app/agents/tasks/**`.
### Tests Required
four forms validate; IN_PROGRESS→SUBMITTED; all-submitted→UNDER_REVIEW; capacity on broadcast; evidence hashes; trusted on first submit.
### Acceptance Criteria
Phase-7 exit criteria.
### Risk Level
High (offline queue, evidence integrity).
### Commit Message
`feat(agent): task execution, role submission forms, proof-of-presence, offline queue`

## Slice S12 — Phase 8 Admin Review & Report Release
### Objective
Task review, conflict detection, release gate + composite trust score, reopen, FAILED, versioning.
### Requirements Covered
R8.1–R8.6.
### Dependencies
S11.
### Files Impacted
`app/domain/verification/review/**`, `.../conflict/**`, `.../scoring/**`, `frontend/src/app/admin/verifications/[id]/report-review/**`.
### Tests Required
reject→IN_PROGRESS; all-approved→release-ready; release→COMPLETED; reopen APPROVED→IN_PROGRESS; version bump+reason; recompute at release only.
### Acceptance Criteria
Phase-8 exit criteria; no report without explicit release.
### Risk Level
High.
### Commit Message
`feat(admin): task review, conflict detection, trust-score release gate, versioning`

## Slice S13 — Phase 9 Customer Tracking & Evidence (SSE)
### Objective
Live tracking dashboard, state labels, interim reassurance, evidence layer with content hash.
### Requirements Covered
R9.1–R9.5.
### Dependencies
S9–S12; SSE transport (§4.9).
### Files Impacted
`app/domain/verification/**` (SSE endpoints), `frontend/src/app/portal/verifications/[id]/**`.
### Tests Required
status advances live; first-name-only at API; evidence tamper-evidence; risk-bearing interim withheld until review.
### Acceptance Criteria
Phase-9 exit criteria.
### Risk Level
Medium-High.
### Commit Message
`feat(portal): live tracking dashboard + evidence layer over SSE`

## Slice S14 — Phase 10 Final Report Experience
### Objective
Report view, access gate, PDF parity, versioning/supersede, Premium Legal Opinion framing.
### Requirements Covered
R10.1–R10.6.
### Dependencies
S12.
### Gate
**NBA counsel sign-off gates Legal Opinion go-live (§3.5/§B)** — build, do not go live, until cleared.
### Files Impacted
`app/domain/verification/report/**` (+PDF), `frontend/src/app/portal/verifications/[id]/report/**`.
### Tests Required
COMPLETED report renders; PDF/HTML footer parity; supersede transition.
### Acceptance Criteria
Phase-10 exit criteria.
### Risk Level
Medium-High (legal gate).
### Commit Message
`feat(report): final report experience, branded PDF, versioning, legal-opinion framing`

## Slices S15–S23 — Harden & Scale (Phases 11–19)

| Slice | Phase | Scope (reqs) | Deps | Risk |
|---|---|---|---|---|
| S15 | 11 | Communication layer + message fraud holds (R11.1–11.3) | S12 | H |
| S16 | 12 | Event bus + notification fan-out + Chat-vs-Notification rule (R12.1–12.4) | S6+ | M |
| S17 | 13 | Public lookup + sharing + lookup safety (R13.1–13.2) | S14 | H |
| S18 | 14 | Re-check / tier upgrade / disputes (R14.1–14.3) | S14 | H |
| S19 | 15 | Earnings, commission clearance/reserve, payouts (R15.1–15.3) | S11,S12,S8 | H |
| S20 | 16 | Reputation metrics + coverage + role dashboards (R16.1–16.3) | S12 | M |
| S21 | 17 | Referral anti-farming, first-time discount, abandonment recovery (R17.1–17.3) | S9,S14 | H |
| S22 | 18 | Mission Control, analytics, pricing/finance/broadcasts, system config (R18.1–18.5) | S9–S20 | M |
| S23 | 19 | Audit export, activity logs, NDPA erasure + pseudonymisation (R19.1–19.3) | all | H |

> Each S15–S23 slice expands into objective/files/schema/tests/acceptance/commit at the start of its `run`,
> following the same template as S1–S14.

## Cross-slice non-negotiables (every slice)
- Write tests first (TDD); after changes run tests, build, and lint **both** ends.
- Backend API and frontend service contract changed together in the same slice.
- No frontend/backend duplicate implementations; reuse existing abstractions (`GenericRepo`, `DataTable`, `Page<T>`).
- Backend is the only source of truth; no derived facts on the frontend.
- Self-audit after each slice (correctness, PRD/architecture compliance, security, migration safety, API consistency, tests).
