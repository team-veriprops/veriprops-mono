---
skill: prd-orchestrator
skill_version: 2.2.0
last_updated: 2026-05-02
---

# Execution Plan

> Slice-based plan to bring [requirements-matrix.md](requirements-matrix.md) from current state to **all green** through Phase 10 (MVP cut line) and then 11–19. Each slice is sized per the PRD orchestrator's batch rules:
>
> - **Large** — UI / docs / simple CRUD (lower risk).
> - **Medium** — service + tests.
> - **Small** — schema / auth / integration (highest care).
>
> Slices that update schema are committed with their migration in the same PR (per [CLAUDE.md](../CLAUDE.md) non-negotiable rule #2: full vertical slices).

---

## Slice S0 — Audit & reconcile current state (MUST RUN FIRST)

### Objective
Reconcile the current working tree (uncommitted Phase 0–5 work on `main`) against [requirements-matrix.md](requirements-matrix.md). Update the matrix's `Status` column to ground truth, identify gaps, and decide whether to extend or rewrite each in-progress area.

### Requirements Covered
All `done` and `in_progress` rows — verifies them.

### Dependencies
None.

### Files Impacted
- Read: every modified file in `git status` (full diff scan).
- Write: [requirements-matrix.md](requirements-matrix.md) — update statuses; [progress.md](progress.md) — log audit findings.

### Schema Changes
None.

### API Changes
None.

### Tests Required
None (this is an audit slice).

### Acceptance Criteria
- Every `done`/`in_progress` row in the matrix has been verified by reading the actual code.
- A new section in [progress.md](progress.md) lists per-row audit notes.
- Any newly-discovered ambiguity raises a CLARIFICATION entry in the next `run`.

### Risk Level
Low (read-only).

### Commit Message
`docs: audit current implementation vs PRD requirements matrix`

---

## Phase 0 closure slices

### Slice S1 — Audit log primitive

**Size:** Medium.
**Covers:** R0.10.
**Depends on:** S0.

**Files:** `backend/main/app/domain/audit/{models,repo,service}.py`, `alembic` migration, hook in `@transactional` for audit append.

**Schema:** `audit_logs` table.

**API:** None directly; hook for service-layer writers.

**Tests:** Unit on audit writer; integration on a sample state transition.

**Acceptance:** Every state-machine transition in existing code writes one row.

**Risk:** Medium (pervasive change).

### Slice S2 — Reusable state-machine validator

**Size:** Medium.
**Covers:** R0.11, R0.15 (closing remaining gaps in existing code).
**Depends on:** S1.

**Files:** `appodus_utils/state/machine.py` + Verification + Task + Report state tables.

**Schema:** None.

**Tests:** All 8 verification states × all transitions; all 6 task states × all transitions; report versioning rules.

**Acceptance:** Illegal transitions raise `IllegalStateTransition` exception.

**Risk:** High (correctness-critical).

### Slice S3 — Derived global state rules

**Size:** Small.
**Covers:** R0.16.
**Depends on:** S2.

**Files:** `verification/state_machine/derive.py`, called from any task-state mutation.

**Tests:** Each PRD §0.3 rule covered; ordering-dependence verified.

**Acceptance:** Sample fixtures: assigning the first task moves PAID → IN_PROGRESS; submitting all tasks → UNDER_REVIEW; approving all → COMPLETED-pending-release.

**Risk:** High.

---

## Phase 1 closure slices

### Slice S4 — Marketing site final polish

**Size:** Large.
**Covers:** verifies R1.* `done` against design system; reconciles uncommitted modifications in `git status`.
**Depends on:** S0.

**Files:** `frontend/src/components/website/*` and `frontend/src/app/(website)/page.tsx`.

**Tests:** Visual regression on 1440px + 375px; unit tests on currency toggle, intent-preserve.

**Acceptance:** Every Phase 1 exit criterion (PRD §1.12) passes.

**Risk:** Low.

---

## Phase 2 closure slices

### Slice S5 — Auth shell completeness audit

**Size:** Medium.
**Covers:** R2.1 – R2.15.
**Depends on:** S0–S2.

**Files:** `user/auth/*` end-to-end + frontend auth pages.

**Tests:** All E2E in PRD §2.4 exit criteria (mobile + desktop + OAuth E2E matrix).

**Acceptance:** No password/token/PII in logs; intent-preserving redirects verified; security activity log surfaces `LOGIN_FAILURE_WARNING`.

**Risk:** High (security).

### Slice S6 — OAuth security hardening

**Size:** Small.
**Covers:** R2.3, R2.6, R2.9.
**Depends on:** S5.

**Files:** `user/auth/oauth/*` (state, PKCE, JWKS, redirect allow-list).

**Tests:** Replay attack rejected; redirect injection rejected; Apple JWKS rotation handled; email-collision rejected without session.

**Acceptance:** Pen-test of OAuth surface produces zero medium-or-high findings.

**Risk:** High.

---

## Phase 3 — Agent onboarding + KYC

### Slice S7 — Agent application wizard backend

**Size:** Medium.
**Covers:** R3.1, R3.3, R3.4, R3.7.
**Depends on:** S5.

**Files:** `user/agent/{models,repo,service,validator,controller}.py` + alembic.

**Schema:** `agent_applications`, `professional_credentials`, `coverage_areas`.

**API:** `POST /api/agents/applications`, `GET /api/agents/applications/me`, draft endpoints.

**Tests:** Multi-select agent types; conditional credentials per type; draft resume; consent record on submit.

**Acceptance:** Application enters PENDING; status dashboard shows correct state.

**Risk:** Medium.

### Slice S8 — KYC: BVN + selfie integration

**Size:** Small (gated on D6 + D7 decisions).
**Covers:** R3.2, R3.6.
**Depends on:** S7, decisions D6, D7.

**Files:** `user/agent/kyc/*`, integration in `appodus_utils/integrations/kyc/`.

**Schema:** `kyc_records`.

**API:** `POST /api/agents/applications/me/kyc`, webhook receiver.

**Tests:** Vendor mock; encryption at rest; per-user IAM scope.

**Acceptance:** End-to-end BVN verification + selfie match against fixture; KYC blob encrypted in S3.

**Risk:** High (vendor + encryption + PII).

### Slice S9 — Agent onboarding frontend

**Size:** Large.
**Covers:** R3.5 (already partially done) + UI for S7 + S8.
**Depends on:** S7, S8.

**Files:** `frontend/src/app/agents/onboarding/*` + components.

**Tests:** Wizard step persistence; KYC upload; status dashboard.

**Acceptance:** Can submit application end-to-end on mobile + desktop.

**Risk:** Medium.

---

## Phase 4 — Admin onboarding + RBAC

### Slice S10 — Admin invite + acceptance

**Size:** Medium.
**Covers:** R4.1, R4.2, R4.3, R4.6.
**Depends on:** S5.

**Files:** `user/admin_invitation/*`, alembic, frontend `/auth/admin-invite/[token]`.

**Schema:** `admin_invitations`, `admin_roles`.

**API:** `POST /api/admin/invitations`, `POST /api/admin/invitations/accept`.

**Tests:** Three acceptance scenarios; expired tokens rejected; sub-role assignment audit-logged.

**Acceptance:** Seed Super Admin via migration; invited user gets correct sub-role.

**Risk:** Medium.

### Slice S11 — RBAC enforcement

**Size:** Small.
**Covers:** R4.4, R4.5.
**Depends on:** S10.

**Files:** `user/auth/utils/permissions.py`, route decorators, admin team management routes.

**Tests:** Permission matrix verified at every protected endpoint; role-change audit log.

**Acceptance:** Every admin endpoint guarded by `@requires(...)`; non-permitted users get 403.

**Risk:** High.

---

## Phase 5 — Customer submission + payment

### Slice S12 — Property submission wizard backend

**Size:** Medium.
**Covers:** R5.1, R5.3, R5.4, R5.14 (transitions only).
**Depends on:** S2, S3, S5.

**Files:** `verification/{models,repo,service,validator,controller}.py`, `verification/property/*`, alembic.

**Schema:** `verifications`, `properties`.

**API:** `POST /api/verifications` (issues VID), `PUT /api/verifications/{id}/property`, GET endpoints.

**Tests:** VID format; conditional Land vs Building; resumable drafts; transitions DRAFT → SUBMITTED.

**Acceptance:** Frontend can drive a full property-data submission.

**Risk:** Medium.

### Slice S13 — Listing-URL parser

**Size:** Small.
**Covers:** R5.2.
**Depends on:** S12, decision D13.

**Files:** `verification/parser/*` for PropertyPro + Nigeria Property Centre.

**API:** `POST /api/verifications/{id}/parse-listing`.

**Tests:** Snapshot tests on real listing fixtures; manual fallback path.

**Acceptance:** Both supported sources populate fields; failures graceful.

**Risk:** Low.

### Slice S14 — Pricing + currency + price lock

**Size:** Medium.
**Covers:** R5.5, R5.6, R5.7.
**Depends on:** S12, decisions D11, D12.

**Files:** `verification/pricing/*`, `payment/currency_rate.py`, alembic.

**Schema:** `pricing_configs`, `currency_rates`, `price_locks`, `referrals` (initial).

**API:** `POST /api/verifications/{id}/lock-price`, FX endpoints.

**Tests:** Pricing computation; lock window; FX-stale warning; recommendation banner trigger.

**Acceptance:** Continue-to-payment locks price + FX for 24 hours.

**Risk:** Medium.

### Slice S15 — Pre-payment consent

**Size:** Small.
**Covers:** R5.8.
**Depends on:** decision D19 (BLOCKING — Verification Disclaimer copy).

**Files:** `user/auth/consent/*` extension, frontend consent step.

**Schema:** `consent_snapshots`.

**Tests:** All five consent items recorded with version + IP + fingerprint.

**Acceptance:** Cannot proceed past consent step without acceptance.

**Risk:** Medium (legal).

### Slice S16 — Payment integration

**Size:** Small (gated on D4).
**Covers:** R5.9, R5.10, R5.11, R5.12.
**Depends on:** S14, S15, decision D4.

**Files:** `payment/*` extension + Paystack + Flutterwave + wire-proof flow.

**Schema:** `payments`, `wire_proofs`, `receipts`, `refunds`.

**API:** All `/api/.../payment/*` endpoints + webhooks.

**Tests:** Both gateways' webhook flows; bank-transfer 24-hr expiry; wire-proof admin queue; receipt PDF generation; retry path.

**Acceptance:** Card + bank transfer + wire proof all reach PAID state.

**Risk:** High (money + idempotency).

### Slice S17 — Customer portal post-payment

**Size:** Large.
**Covers:** R5.13, R5.15.
**Depends on:** S16.

**Files:** `frontend/src/app/portal/verifications/*`.

**Tests:** Confirmation page; trust elevation visible.

**Acceptance:** Customer sees VID + ETA + SLA after pay.

**Risk:** Low.

---

## Phase 6 — Admin verification control panel

### Slice S18 — Admin queue + verification detail

**Size:** Medium.
**Covers:** R6.1, R6.2, R6.5.
**Depends on:** S11, S12, S16.

**Files:** `frontend/src/app/admin/verifications/*` + backend list/detail endpoints.

**Tests:** Filters; admin actions all audit-logged.

**Acceptance:** Admin sees PAID verifications; can perform all listed actions.

**Risk:** Medium.

### Slice S19 — Agent assignment

**Size:** Medium.
**Covers:** R6.3, R6.4, R6.7.
**Depends on:** S18, S9.

**Files:** assignment service + ranking + tasks schema.

**Schema:** `tasks`, `task_assignments`.

**API:** `POST /api/admin/verifications/{id}/assign`.

**Tests:** Lawyer task locked until siblings SUBMITTED; reassignment audit; first assignment moves PAID → IN_PROGRESS.

**Acceptance:** Demo: PAID → IN_PROGRESS via assignment.

**Risk:** High (state-machine + dependency).

### Slice S20 — Agent application approval queue

**Size:** Medium.
**Covers:** R6.6.
**Depends on:** S9, S11.

**Files:** admin frontend + approval service.

**Tests:** Approve/reject with reason; persona elevation on approve.

**Acceptance:** Approved agents appear in assignment ranking.

**Risk:** Medium.

---

## Phase 7 — Agent task execution

### Slice S21 — Agent dashboard + accept/decline

**Size:** Medium.
**Covers:** R7.1, R7.2.
**Depends on:** S19, decision D17 (no-show timeout).

**Files:** `frontend/src/app/agent/dashboard/*`, `agent/tasks` controllers.

**Tests:** Geo-filtered jobs; accept/decline transitions; no-show timeout job.

**Acceptance:** Agent sees only role-matched, coverage-matched jobs.

**Risk:** Medium.

### Slice S22 — Field agent submission UI

**Size:** Large.
**Covers:** R7.3.
**Depends on:** S21.

**Files:** `agent/forms/field/*`, evidence schema.

**Schema:** `evidence_items`.

**Tests:** ≥5 GPS-stamped photos enforced; declaration required; submission moves IN_PROGRESS → SUBMITTED.

**Acceptance:** Field agent can complete submission end-to-end.

**Risk:** Medium.

### Slice S23 — Surveyor submission UI

**Size:** Large.
**Covers:** R7.4.
**Depends on:** S22 (shares evidence layer).

**Tests:** Coordinate validation; survey plan upload.

**Acceptance:** Surveyor can complete submission.

**Risk:** Medium.

### Slice S24 — Registry agent submission UI

**Size:** Large.
**Covers:** R7.5.
**Depends on:** S22.

**Tests:** Title doc assessment; ownership chain; multiple uploads.

**Acceptance:** Registry agent can complete submission.

**Risk:** Medium.

### Slice S25 — Lawyer submission UI

**Size:** Large.
**Covers:** R7.6, R7.10.
**Depends on:** S22, S23, S24.

**Tests:** Dependency gate enforced server-side; ≥200 char legal opinion; UNDER_REVIEW transition.

**Acceptance:** Lawyer cannot submit until siblings SUBMITTED.

**Risk:** High (dependency rule).

### Slice S26 — Offline + autosave

**Size:** Medium.
**Covers:** R7.7.
**Depends on:** S22.

**Files:** Service worker + IndexedDB queue.

**Tests:** Offline E2E with simulated network drop.

**Acceptance:** Agent can fill form offline; uploads on reconnect.

**Risk:** Medium.

### Slice S27 — Escalation + trust elevation

**Size:** Medium.
**Covers:** R7.8, R7.9.
**Depends on:** S22.

**Tests:** Issue categories; admin notified; first-submission trust flag.

**Acceptance:** Reporting an issue produces admin alert.

**Risk:** Low.

---

## Phase 8 — Admin review + report release

### Slice S28 — Task review interface

**Size:** Large.
**Covers:** R8.1, R8.2, R8.3, R8.7.
**Depends on:** S25.

**Files:** `frontend/src/app/admin/tasks/*` + backend review service.

**Tests:** Approve / reject (with min reason) / re-open; rejection moves task → REJECTED → IN_PROGRESS.

**Acceptance:** Admin can approve/reject every role's submission.

**Risk:** High (correctness).

### Slice S29 — Conflict detection

**Size:** Medium.
**Covers:** R8.4.
**Depends on:** S28, decision D15.

**Files:** `verification/conflict_rules/*`.

**Schema:** `conflict_flags`.

**Tests:** Each of the four initial rules verified.

**Acceptance:** Conflict flag blocks "Release Report".

**Risk:** Medium.

### Slice S30 — Trust score computation + report assembly

**Size:** Small (gated on D2).
**Covers:** R8.5.
**Depends on:** S28, decision D2.

**Files:** `verification/report/scoring.py`, `report/assembler.py`.

**Schema:** `reports`, `report_versions`, `trust_score_breakdowns`.

**Tests:** Weights match decision; score recomputed on every approval.

**Acceptance:** Composite score deterministic for fixture.

**Risk:** High.

### Slice S31 — Release report + FAILED state

**Size:** Medium.
**Covers:** R8.6, R8.8.
**Depends on:** S30.

**Files:** release service, FAILED admin path.

**Tests:** Release moves UNDER_REVIEW → COMPLETED; FAILED produces refund record.

**Acceptance:** End-to-end demo: PAID → IN_PROGRESS → UNDER_REVIEW → COMPLETED.

**Risk:** High.

---

## Phase 9 — Customer tracking + evidence

### Slice S32 — Verification tracking dashboard

**Size:** Large.
**Covers:** R9.1, R9.3, R9.4.
**Depends on:** S17, S31.

**Files:** `frontend/src/app/portal/verifications/[id]/*`.

**Tests:** Each state's expanded view; label mapping.

**Acceptance:** Customer sees live status with role-tagged agents.

**Risk:** Medium.

### Slice S33 — SSE live updates

**Size:** Small (gated on D10).
**Covers:** R9.2.
**Depends on:** S32, decision D10.

**Files:** `verification/stream.py`, frontend EventSource client.

**Tests:** State change propagates within 1s; polling fallback at 60s.

**Acceptance:** Live update test in staging.

**Risk:** Medium.

### Slice S34 — Evidence layer

**Size:** Medium.
**Covers:** R9.5, R9.6.
**Depends on:** S32.

**Files:** evidence feed UI + API filter on agent identity.

**Tests:** Contract test on customer-facing agent serialisation; EXIF panel; tamper-evidence (server-side timestamp/GPS overrides device).

**Acceptance:** No customer-facing endpoint leaks last_name/email/phone.

**Risk:** High.

---

## Phase 10 — Final report experience

### Slice S35 — Report HTML view

**Size:** Large.
**Covers:** R10.1, R10.2, R10.3, R10.4, R10.5.
**Depends on:** S31.

**Files:** report frontend + access-gate modal + sections.

**Tests:** Tier-conditional sections; access-gate one-time recording.

**Acceptance:** Customer sees full report; legal footer on every page.

**Risk:** Medium.

### Slice S36 — PDF generation + versioning

**Size:** Medium.
**Covers:** R10.6, R10.7.
**Depends on:** S35.

**Files:** PDF generator (server-side, e.g. WeasyPrint or Playwright), versioning service.

**Tests:** PDF parity with HTML; SUPERSEDED watermark on old versions.

**Acceptance:** Customer downloads PDF that matches HTML pixel-for-pixel for legal content.

**Risk:** Medium.

---

## **MVP CUT LINE — Slices S0 to S36**

If only one milestone is hit, it should be S36. After this, expand into Phases 11–19.

---

## Phase 11 — Communication

### Slice S37 — Customer↔Admin + Admin↔Agent threads

**Size:** Medium.
**Covers:** R11.1, R11.2, R11.3, R11.5.
**Depends on:** S31.

**Schema:** `message_threads`, `messages`.

**Tests:** System messages on status change; broadcast fan-out; agent identity filter.

**Risk:** Medium.

### Slice S38 — Fraud detection on send

**Size:** Small.
**Covers:** R11.4.
**Depends on:** S37.

**Files:** message fraud-scan service.

**Schema:** `fraud_flags`.

**Tests:** Phone, email, URL, banking, "outside the platform" all flagged; held until admin review.

**Risk:** High.

---

## Phase 12 — Notifications

### Slice S39 — Notification fan-out core

**Size:** Medium.
**Covers:** R12.1, R12.2, R12.5, R12.6, R12.7.
**Depends on:** S38.

**Schema:** `notifications`, `notification_dispatches`.

**Tests:** Each event routes to correct channels.

**Risk:** Medium.

### Slice S40 — SMS + Push enablement

**Size:** Small (gated on D5).
**Covers:** R12.3, R12.4.
**Depends on:** S39, decision D5.

**Tests:** Termii (NG) + Twilio (intl); Firebase + WebPush.

**Risk:** Medium.

### Slice S41 — Notification preferences UI

**Size:** Large.
**Covers:** R12.8.
**Depends on:** S39.

**Files:** `frontend/src/app/portal/account/notification-preferences/page.tsx`.

**Risk:** Low.

---

## Phase 13 — Public lookup + sharing

### Slice S42 — Public lookup page

**Size:** Medium.
**Covers:** R13.1, R13.2.
**Depends on:** S36.

**Files:** `frontend/src/app/verify/[id]/page.tsx`, public read endpoint.

**Tests:** Five state branches; `noindex` enforcement.

**Risk:** Medium.

### Slice S43 — Share modes + revocation

**Size:** Medium.
**Covers:** R13.3, R13.4.
**Depends on:** S42.

**Schema:** `share_links`.

**Tests:** Each share mode; revocation invalidates immediately; named recipient acknowledgement.

**Risk:** Medium.

---

## Phase 14 — Revisions / disputes

### Slice S44 — Re-check request

**Size:** Medium.
**Covers:** R14.1.
**Depends on:** S36, decision D24.

**Tests:** Cycle restart for scoped tasks; v2.0 bump.

**Risk:** Medium.

### Slice S45 — Tier upgrade

**Size:** Medium.
**Covers:** R14.2.
**Depends on:** S44.

**Tests:** Existing approved tasks preserved; v3.0 bump.

**Risk:** Medium.

### Slice S46 — Dispute flow

**Size:** Medium.
**Covers:** R14.3, R14.4, R14.5.
**Depends on:** S36.

**Tests:** Three outcomes verified; resolution note delivered verbatim.

**Risk:** High.

---

## Phase 15 — Earnings

### Slice S47 — Agent earnings dashboard + commission

**Size:** Medium.
**Covers:** R15.1, R15.2.
**Depends on:** S31.

**Schema:** `commission_rules`.

**Tests:** Commission visible pre-accept; per-job breakdown.

**Risk:** Medium.

### Slice S48 — Withdrawal + payout panel

**Size:** Medium.
**Covers:** R15.3, R15.4.
**Depends on:** S47.

**Schema:** `payouts`.

**Tests:** Payout end-to-end staging test; admin approve/hold/adjust audit-logged.

**Risk:** High (money).

---

## Phase 16 — Reputation

### Slice S49 — Performance metrics + ranking

**Size:** Medium.
**Covers:** R16.1, R16.2, R16.3.
**Depends on:** S31.

**Tests:** Metric updates post-approval; ranking deterministic.

**Risk:** Medium.

### Slice S50 — Threshold + coverage + availability + role dashboards

**Size:** Large.
**Covers:** R16.4, R16.5, R16.6, R16.7.
**Depends on:** S49, decision D17 (max capacity).

**Tests:** Auto-red at cap; visibility filter; role default views.

**Risk:** Medium.

---

## Phase 17 — Growth

### Slice S51 — Referral system

**Size:** Medium.
**Covers:** R17.1, R17.2.
**Depends on:** S16.

**Tests:** Credit applies on referrer's next paid verification.

**Risk:** Medium.

### Slice S52 — Abandonment recovery

**Size:** Medium.
**Covers:** R17.3.
**Depends on:** S51.

**Tests:** Email fires once per abandoned draft; price-lock refresh.

**Risk:** Low.

---

## Phase 18 — Admin operations + analytics

### Slice S53 — Mission Control + analytics

**Size:** Large.
**Covers:** R18.1, R18.5, R18.6.
**Depends on:** S31, S46, S48.

**Risk:** Medium.

### Slice S54 — Pricing + finance management

**Size:** Medium.
**Covers:** R18.2, R18.3.
**Depends on:** S14, S48.

**Tests:** Pricing changes propagate without deploy.

**Risk:** Medium.

### Slice S55 — Content layer + system-wide notification

**Size:** Large.
**Covers:** R18.4, R18.7.
**Depends on:** S39, decision D21.

**Risk:** Low.

---

## Phase 19 — Audit + compliance

### Slice S56 — Audit export + activity logs

**Size:** Medium.
**Covers:** R19.1, R19.2, R19.3.
**Depends on:** all prior.

**Risk:** Medium.

### Slice S57 — Consent download + fraud history + admin action logs

**Size:** Medium.
**Covers:** R19.4, R19.5, R19.6.
**Depends on:** S56.

**Risk:** Low.

### Slice S58 — Retention policy enforcement

**Size:** Medium.
**Covers:** R19.7.
**Depends on:** S57.

**Tests:** NDPR-compliant erasure path.

**Risk:** High (legal).

---

## Slice ordering summary

```
S0 (audit) → S1 → S2 → S3 (Phase 0 closure)
S4 (Phase 1)  ┐
S5 → S6       ├── parallel
S7 → S8 → S9 (Phase 3)
S10 → S11 (Phase 4)
S12 → S13 → S14 → S15 → S16 → S17 (Phase 5)
S18 → S19 → S20 (Phase 6)
S21 → S22 → S23 → S24 → S25 → S26 → S27 (Phase 7)
S28 → S29 → S30 → S31 (Phase 8)
S32 → S33 → S34 (Phase 9)
S35 → S36 (Phase 10)  ◀── MVP cut
S37 → S38 (Phase 11)
S39 → S40 → S41 (Phase 12)
S42 → S43 (Phase 13)
S44 → S45 → S46 (Phase 14)
S47 → S48 (Phase 15)
S49 → S50 (Phase 16)
S51 → S52 (Phase 17)
S53 → S54 → S55 (Phase 18)
S56 → S57 → S58 (Phase 19)
```

**Total: 58 slices.** Per-cycle the orchestrator picks the next slice whose dependencies are met and whose blocking decisions are resolved.
