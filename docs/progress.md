# Progress Tracker

status: running (S1–S4 foundation)

## Completed Slices
- S1  Foundation reconciliation & doc fixes — cleaned 0001 orphaned seeds (pricing + trust-weights),
      moved `app/state` → `app/core/state`, root CLAUDE.md MySQL→PostgreSQL, removed 9 orphaned
      deleted-domain tests → suite green (267 passed).
- S2  State derivation owner + task-dependency config — `app/core/state/{status,derive,dependencies}.py`;
      pure `derive_status` (§2.5) + tier composition / Lawyer-dependency / acyclicity (§4.2). 49 tests, 316 total.
- S3  Idempotency + VID + evidence-hash — `app/core/vid.py`, `app/core/evidence.py`,
      `app/core/idempotency/{models,repo,service}.py`; `idempotency_keys` table folded into 0001;
      Money kobo-reconciliation tests. 344 total. (Live `alembic upgrade head` deferred — no DB here.)
- S4  SLA business-day calculator + Nigerian holiday calendar — `app/core/sla.py` (fixed + Easter-computus
      + maintained movable-Islamic holidays; per-tier due dates 5/7/10). 363 total.
- S5  Phase 1 — Marketing completion + Legal documents + footer pages.
      Backend: `consent_documents` gains `body` + `signoff_status` (0001); legal content registry
      (`consent/content/`, 10 drafted docs from PRD §3.5); idempotent `ConsentService.seed_documents()` wired
      into `DataSeeder`; public read API (`GET /consents/documents`, `/documents/{slug}`). Frontend: reusable
      SEO pattern (`lib/seo.ts buildMetadata` + `JsonLd`) applied to all public pages, `app/sitemap.ts` +
      `app/robots.ts`; dynamic `/legal/[slug]` pages (react-markdown) with DRAFT banner; conversion FAQ after
      Client Stories (FAQPage JSON-LD); `/sample-report`; footer dynamic year + socials disable-when-unset.
      Backend 373 tests; frontend +seo/home.data tests (58). Live-verified: API returns 10 docs, DRAFT/FINAL
      correct, legal pages + sitemap/robots render. Incidental baseline build repairs (not mine): added
      `NotificationBell` stub (AppShell orphan import), removed dead `lib/mockUrlExtractor.ts`.

- S6  Phase 2 — Auth hardening.
      Backend: `PHONE_VERIFICATION_ENABLED` setting + public `GET /config/public`; revoked-session enforcement on
      token refresh (`POST /sessions/current` rejects revoked/absent device sessions); paginated Security
      Activity Log (`GET /sessions/security/events` → `Page[SecurityEventDto]`); cross-portal summary aggregator
      (`GET /cross-portal/summary`, forward-compatible source registry → 0 until S11/S16). Frontend: `/account`
      shell (AppShell + account nav) with Security/Devices/Linked/Password pages; `PortalSwitcher` + badge wired
      into AppShell top nav (multi-persona only); `usePublicConfigQuery` exposes the phone flag for the S9 gate.
      Backend 384 tests; frontend 241 tests (incl. auth-service contract test); build green; endpoints + route
      protection live-verified.

- S7  Phase 3 — Agent onboarding & KYC.
      Backend: KYC provider facade (`appodus_utils/integrations/kyc/` — deterministic Stub default + gated
      Dojah scaffold + factory, registered like payments); agent domain (`app/domain/user/agent/`: models,
      repo, service, validator, controller, kyc_service) + pure `credentials.py` role-level expiry suspension
      (§3.3a); resumable application drafts. Endpoints `/users/agents/*` — applicant draft/submit/status; admin
      list/detail/approve/reject gated by `require_permission(APPROVE_AGENT)`. Submit runs KYC, creates PENDING
      profile, persists credentials/coverage, records AGENT_TERMS consent, adds AGENT persona, audits. Agent/KYC
      tables folded into `0001` (greenfield single-migration); validated downgrade base→upgrade head (61 tables).
      Frontend: reusable full-screen `WizardOverlay` (route-backed `/agents/apply`, resumable), 4-step wizard
      (Roles/KYC/Credentials/Review), approval-status card on `/agents/dashboard`, admin review at
      `/admin/agents/applications` (DataTable→DetailDrawer approve/reject). Backend 418 tests; frontend 246;
      tsc + lint clean. Known gap: KYC/credential S3 upload UI deferred (refs stored; facade supports encrypted).

- S8  Phase 4 — Admin onboarding & RBAC.
      Backend: RBAC matrix + `require_permission` already existed (permissions.py, 19 tests). New
      `admin_invitation` domain (tokenised 72h single-use invite, email-match guard, accept elevates to
      `user_type=ADMIN`+sub_role per decision-log D10, unauthenticated 3-scenario preview) + `admin_team`
      domain (list/change-sub-role/deactivate over `users`, self-deactivate guard, all audited). Endpoints
      gated by `require_permission` (INVITE_ADMIN / VIEW_ADMIN_PANEL / MANAGE_USERS). `admin_invitations`
      folded into `0001`. Frontend: `/admin/team` (DataTable→DetailDrawer change-role/deactivate + invite
      form returning a copyable link + pending-invitations revoke); invite acceptance at
      `/auth/admin-invite/[token]` (preview-driven signup/login/already-admin routing). Backend 431 tests;
      frontend 251; tsc+lint clean. Known gap: templated invite email deferred (link returned instead).

- S9  Phase 5 — Customer submission & payment.
      Backend: property (thin first-class §4.3), verification (central aggregate — VID/DRAFT on step-1,
      resumable draft on the row, 24h price-lock, VERIFICATION_TERMS consent snapshot, DRAFT→SUBMITTED→
      PAYMENT_PENDING→PAID guarded by the state machine; post-PAID projected by the derive owner), payment
      (idempotent init + idempotent webhook on the gateway event id). Provisional per-tier pricing in NGN kobo
      (Money minor units; FX indicative via `TransactionCurrency.fx_rate`). Geocoding facade (Stub default +
      gated Google Places + factory) with NG autocomplete/geocode endpoints. Deterministic payment
      (`PAYMENT_STUB_MODE` + non-prod `/payments/stub/confirm` → idempotent webhook → PAID); phone gate before
      payment; first payment upgrades the customer to `trusted`. property/verifications/payments folded into
      `0001`. Frontend: submission WizardOverlay at `/portal/verifications/new` (Property/Tier/Consent,
      idempotent VID/DRAFT on load, autosave per step) → pay overlay `/portal/verifications/[id]/pay`
      (phone-verify gate + initiate + deterministic confirm) → `/confirmed` (VID + SLA + track CTA);
      backend-sourced pricing/FX (never recomputed on the client). Backend 453 tests; frontend 260; tsc+lint
      clean. Gaps: live-gateway call + emailed receipt + full draft-resume UI + conditional property details
      deferred (see runtime-state self_audit_s9). §B liability-cap copy gates go-live only.

- S10 Phase 6 + 6a — Admin control panel & chargeback.
      Backend: task domain (per-role `VerificationTask` + state machine; `instantiate_unlocked` at PAID
      respecting §4.2 locks — Premium Lawyer skipped until siblings SUBMITTED; manual assign/reassign with
      §6.5 capacity; broadcast pool + §7.2 no-show/starvation sweeps; every mutation re-derives
      `verification.status` via the §4.1 derive owner). Admin control panel (paged list with SLA health,
      composed detail, pause/resume flag, state-guarded cancel, SLA delay, notes; RBAC MANAGE_VERIFICATIONS /
      ASSIGN_AGENT). `admin_note`, `commission` (freeze/unfreeze/reverse, D13), `chargeback` (§6a — idempotent
      webhook flags payment + freezes commissions without touching the state machine; auto-assembled rebuttal
      pack; won→unfreeze / lost→reverse+payment FAILED; non-prod stub-flag endpoint). Scheduler sweeps wired
      (D12, ALWAYS_NEW wrappers, disabled under test) + admin dev sweep endpoints; `payment.handle_webhook`
      calls `task_service.prepare_for_paid` at PAID. Four tables folded into `0001` (+`paused`,
      `chargeback_status`, `refunded_amount_minor`); downgrade base→upgrade head clean. **Fixed a real bug**:
      `_sla_health` OVERDUE branch was dead code (`business_days_remaining` clamps at 0) — now detects overdue
      from the due-date. Frontend: `types/adminVerification`, `admin-verification-service` +
      `useAdminVerificationQueries`, list at `/admin/verifications` (DataTable + status/tier/overdue filters +
      SLA badge) → detail `/admin/verifications/[id]` (task grid + inline (re)assign, progress, property/
      payments/commissions/chargebacks, notes, pause/resume/delay/cancel, chargeback rebuttal/resolve).
      Backend 494 tests; frontend 266; tsc+lint clean. Gaps: agent-side accept UX + live gateway chargeback
      webhook + agent-picker deferred (see runtime-state self_audit_s10).

## Current Slice
- S11 (Phase 7 agent task execution) — next.

## Pending Slices
- S11 Phase 7 — Agent task execution
- S12 Phase 8 — Admin review & report release
- S13 Phase 9 — Customer tracking & evidence (SSE)
- S14 Phase 10 — Final report experience  *(gated: NBA sign-off for Legal Opinion go-live §B)*
- S15–S23 Phases 11–19 — harden & scale

## Runtime State
- idle (S1–S4 committed; checkpoint clean)

## Pending Recovery
- none

## Blockers
- none. Migration validated live on the test DB (`downgrade base` + `upgrade head` clean; `idempotency_keys`
  created with correct columns/indexes). Pre-squash orphan tables (`pricing_tier_configs`,
  `trust_score_weight_config`) remain in the test DB — no current migration creates them; recreated in S9/S12.

## Open Questions
- D6 (relaxed by D9): foundation built greenfield; `0001` is the single editable initial migration.
- D4: applied in S1 — root CLAUDE.md now says PostgreSQL.
- §B legal sign-offs are launch gates, not build blockers: liability-cap copy gates Phase 5 go-live;
  NBA counsel gates Phase 10 Legal Opinion go-live; Premium-lawyer insurance posture gates that tier.
- §6.4 admin staffing gate is a business commitment (not buildable) — record before launch.

## Risks
- State-derivation correctness (single owner, tier-config counts) — highest-leverage correctness risk.
- Money/FX reconciliation to the kobo across pay→refund→commission→payout.
- Webhook double-processing (mitigated by idempotency keys, proven in S3).
- Brownfield drift between rebuilt models and `0001` schema.
- Strict commit mode + dirty worktree: `run` is blocked until committed (see below).

## Last Commit
- S1 `bec85e1`, S2 `0465a5a`, S3 `a138219`, S4 (this commit) — foundation slices.

## Completion %
- ~43% (10 of 23 slices; Phase-0 foundation + Phases 1–6/6a complete)

---

### ⚠️ Strict-mode reminder
`config.yaml` is `mode: strict` (D3). Worktree committed at each slice boundary; clean between slices.

<!-- legacy note retained for history -->
`config.yaml` is `mode: strict` (D3). The worktree was previously **dirty** (large staged domain deletions +
edits). `prd-orchestrator run` will refuse to start until the worktree is committed/clean. Commit the in-flight
refactor before invoking `run`.
