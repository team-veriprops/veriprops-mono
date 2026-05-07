---
skill: prd-orchestrator
skill_version: 2.2.0
last_updated: 2026-05-07
---

# Progress Tracker

> Live state of the PRD execution loop. Updated every `run`/`resume` cycle. Source of truth alongside [requirements-matrix.md](requirements-matrix.md).

---

**status:** S10 complete — ready for S11

**next_slice:** S11 (RBAC enforcement — R4.4, R4.5)

**current_slice:** —

**completion %:** 51% (71 done / 140 total — R4.1–R4.3/R4.6 were already done; S10 delivered tests + bugfix)

---

## Completed Slices

| Slice | Description | Completed |
|---|---|---|
| S0 | Audit & reconcile current state against requirements matrix | 2026-05-02 |
| S1 | Audit log primitive — `AuditLog` model, repo, service, ContextVar queue, `@transactional` drain, Alembic migration, tests | 2026-05-02 |
| S2 | Reusable state-machine validator — `appodus_utils/state/machine.py`, `IllegalStateTransitionException`, Verification + Task + Report machines, 101 unit tests | 2026-05-02 |
| S3 | Derived global state rules — `derive_status()` pure function (PRD §0.3 rules 1–8), `VerificationService.derive_global_state()`, 31 unit tests | 2026-05-05 |
| S4 | Marketing site final polish — CTA URL fix (6 locations `/auth/login?intent=` → `/auth?intent=`); `formatPrice` extracted to `home.data.ts`; 14 new unit tests (43 total, all passing); PRD §1.12 exit criteria all met | 2026-05-05 |
| S5 | Auth shell completeness audit — R2.5–R2.15 all verified; 59 backend unit tests + 24 frontend tests passing; `make_oauth_state`/`normalise_provider` helpers added to oauth package; `_phone_e164` added to otp_service; `models.ts` frontend enum file verified; `resolvePostAuthRedirect` route corrected to `/agents/*` | 2026-05-07 |
| S6 | OAuth security hardening — Google ID token JWKS-based signature verification (replaced `get_unverified_claims`); Apple + Google JWKS cached in Redis with 5-min TTL + key-rotation fallback; OAuth state stored with explicit 10-min TTL; `resolve_frontend_origin` rejects unlisted origins (ForbiddenException) instead of silently falling back; 11 new unit tests; 70 auth tests passing | 2026-05-07 |
| S7 | Agent application wizard tests — verified full backend implementation in `user/agent/` (models, repo, service, validator, controller, KYC subdomain, migration); wrote 16 unit tests in `test/unit/app/domain/agent/` covering R3.1 (multi-select types), R3.3 (conditional credentials), R3.4 (AGENT_TERMS consent recording, PENDING transition, truthfulness gate), R3.7 (idempotent get_or_create, wizard state preservation), plus approve/reject paths; 86 backend unit tests total passing | 2026-05-07 |
| S8 | KYC BVN + selfie integration (Dojah) — `DojahKycProvider` (sync BVN via `/kyc/bvn/advance`, async selfie via `/kyc/selfie`); `KycRecord` ORM + repo + Alembic migration `d3e4f5a6b7c8`; `kyc/webhook.py` HMAC-SHA256 validation + `parse_dojah_selfie_webhook`; D18: selfie score < `KYC_SELFIE_REVIEW_THRESHOLD` (80) routes to UNDER_REVIEW admin queue; S3 `upload(encrypted=True)` adds SSE-AES256; service updated with `process_kyc_webhook` + `admin_review_kyc`; controller adds `POST /agents/kyc/webhook` + admin review endpoints; 3 new audit action types; 22 new unit tests (108 total passing) | 2026-05-07 |
| S9 | Agent onboarding frontend — confirmed all 6 wizard components (`TypeSelectionStep`, `KycStep`, `CredentialsStep`, `ReviewStep`, `ApprovalStatusCard`, `AgentOnboardingContainer`) + service layer + TanStack Query hooks; added stable `data-testid` selectors (`agent-wizard-*`, `agent-status-*`) to all interactive elements; extracted `deriveResumeStep` + `validateCredentialsStep` pure functions into `wizardUtils.ts`; wrote 25 Vitest tests (18 wizard logic + 7 service HTTP); route protection confirmed in `proxy.ts`; 193 frontend tests total passing | 2026-05-07 |
| S10 | Admin invite + acceptance — verified complete backend (`admin_invitation/` service, repo, controller, migration in `b1f2c3d4e5f6`), frontend (`admin-service.ts`, `useAdminQueries.ts`, `/auth/admin-invite/[token]/page.tsx`), and Super Admin seed migration; wrote 17 backend unit tests (all 4 acceptance branches, expired-token gate, revoke, `attach_admin_role_to_new_user`) + 8 frontend service HTTP tests; fixed `UpdateUserDto` missing `user_type` field (silent Pydantic drop bug — user was never promoted to ADMIN); 268 backend + 201 frontend tests passing | 2026-05-07 |

## Current Slice

S10 complete. Next: S11 — RBAC enforcement (R4.4, R4.5).

## Pending Slices

S10 → … → S58 (full sequence in [execution-plan.md](execution-plan.md)).

---

## Runtime State

idle — S9 checkpointed, no slice in-flight. Awaiting `run` to begin S10.

## Pending Recovery

none — S2 completed cleanly; no interrupted work detected.

---

## Blockers

The following decisions in [decision-log.md](decision-log.md) are **REQUIRES USER INPUT** and gate one or more slices:

| Decision | Description | Gates slices |
|---|---|---|
| D2 | Trust score weighting formula | S30 (Phase 8 trust score), S35 (Phase 10 report) |
| D3 | Trust score visibility to agents pre-submit | S22–S25 (Phase 7 forms) |
| D4 | Payment gateway primary selection | S16 (Phase 5 payment) |
| D5 | SMS provider selection | S40 (Phase 12 SMS) |
| ~~D6~~ | ~~BVN verification provider~~ | ~~S8~~ — **confirmed: Dojah** |
| ~~D7~~ | ~~Selfie match technology~~ | ~~S8~~ — **confirmed: vendor-bundled with Dojah** |
| D9 | OAuth profile data persistence (NDPR) | S5 (Phase 2 audit) |
| ~~D10~~ | ~~Real-time channel~~ | ~~S33~~ — **confirmed: SSE (push) + WS (two-way)** |
| D11 | Pricing defaults (knobs) | S14 (Phase 5 pricing) |
| ~~D12~~ | ~~FX rate source~~ | ~~S14~~ — **confirmed: Flutterwave FX rates, 5-min cache** |
| D13 | Listing-URL parser sources | S13 (Phase 5 parser) |
| D14 | Country/timezone source dataset | S5 (Phase 2) |
| D15 | Conflict-detection initial rule set | S29 (Phase 8 conflicts) |
| D16 | Wire-proof reconciliation | S16 (Phase 5 payment) |
| D17 | Admin SLAs | S21 (Phase 7), S50 (Phase 16) |
| ~~D18~~ | ~~KYC document review path~~ | ~~S8~~ — **confirmed: admin reviews low-confidence only (score < KYC_SELFIE_REVIEW_THRESHOLD=80)** |
| ~~D19~~ | ~~Verification Disclaimer copy~~ | ~~S15~~ — **confirmed-placeholder: proceed, swap before launch** |
| D20 | Trust-status visibility | S49 (Phase 16) |
| D21 | Area Insights content owner | S55 (Phase 18) |
| D23 | Nigerian public holidays source | S14 (Phase 5 pricing — SLA) |
| D24 | Re-check pricing model | S44 (Phase 14 re-check) |

**Previously blocking decisions now confirmed:** D6 (Dojah), D7 (Dojah bundled), D19 (placeholder copy). Critical-path is now unblocked through Phase 5.

The orchestrator can proceed on Phases 0–2 + 4 (audit + closure) immediately. Phase 3 (S8) blocks until D6/D7. Phase 5 (S15) blocks until D19. Other phases have provisional defaults that the orchestrator will adopt unless the user overrides.

---

## Open Questions

See full list in [prd-analysis.md § Ambiguities](prd-analysis.md#ambiguities-from-prd-27--open-questions). Highest-priority gate questions are tracked above as Decision IDs.

The next message to the user surfaces these as a CLARIFICATION REQUIRED block.

---

## Risks

- **Working tree has uncommitted Phase 0–5 work.** Slice S0 must reconcile before slicing forward — otherwise we duplicate work or overwrite in-flight code.
- **Three blocking decisions** (D6, D7, D19) gate the critical path. If the user can confirm provisional defaults, the orchestrator can proceed; if not, work parallelises around them on Phase 1, 2, 4.
- ~~**Audit log primitive (R0.10) is `pending`**~~ — **delivered by S1** (2026-05-02). `AuditLog` table live, drain atomically committed with each state-machine transition.
- **No DB foreign keys / cascades** is a hard repo convention; slices that touch schema must follow it.
- Adopting all provisional decisions verbatim risks misalignment with stakeholder intent — the user should **at minimum confirm D11 pricing values** before any payment-touching slice ships.

---

## Last Commit

Branch: `main`. Most recent commit: `41b0caf implement S3: derived global state rules (R0.16)`.

Working tree: S4 changes uncommitted (6 component files + home.data.ts + home.data.test.ts).

---

## Audit Notes (Slice S0) — 2026-05-02

All `done`/`in_progress` rows reconciled against live `main` branch (commit `0f2217d finalize phases 1-5`).

### Promoted to `done`
- **R0.11** — `verification/state_machine/__init__.py` has `StateMachine` class with `VERIFICATION_TRANSITIONS` dict + `assert_can_transition()` raising `InvalidResourceStateException`.
- **R0.12** — `consent/models.py` has `ConsentDocument` (type, consent_version, effective_at) + `UserConsent` (user_id, doc_type, consent_version, accepted_at, ip_address, device_fingerprint).
- **R2.1** — Signup OTP gate enforced: `OTP_VERIFIED_TTL=30min`, both email + phone markers single-use and consumed on signup. All profile fields captured.
- **R2.2** — Login rate limiting: warn at 5 attempts (`LOGIN_FAILURE_WARNING` event), lockout at 7 for 15 minutes (`ACCOUNT_LOCKED` event). Configurable via settings.
- **R2.10** — `SignupDraft` model with 7-day TTL, upsert/discard. Soft-deleted on signup completion.
- **R2.11** — Versioned consent on signup captures `PLATFORM_TERMS` + `PRIVACY_POLICY` with version, ip, fingerprint.
- **R3.1** — `AgentApplication.types` as MutableList JSON, multi-select AgentType enum (FIELD, SURVEYOR, REGISTRY, LAWYER).
- **R3.3** — Conditional credential fields: `surveyor_licence_no/url`, `nba_licence_no/url`; service validates per agent type.
- **R3.7** — Resumable wizard: draft state on main `AgentApplication` row (status=DRAFT until PENDING), no separate draft table.
- **R4.1–R4.3** — Full admin invitation: token hash, 72-hr TTL, all three acceptance branches (SIGNUP_REQUIRED / LOGIN_REQUIRED / ALREADY_ADMIN / ACCEPTED).
- **R4.4–R4.5** — Full RBAC: `Permission` enum, role matrix (SUPER/OPERATIONS/FINANCE), `require_permission()` FastAPI dependency, guarded endpoints.
- **R4.6** — Super Admin seed in `fdd959a2cfda_auto_generated.py` via `SUPER_ADMIN_PASSWORD` env.
- **R5.1** — VID `VP-{year}-{6-char-hex}` generated in `verification/service.py::_generate_vid()`.
- **R5.7** — Price lock: `locked_at` + `locked_until` in pricing snapshot, TTL from `PRICE_LOCK_TTL_HOURS` (default 24h).

### Confirmed `in_progress` (code exists, gaps remain)
- **R2.3 (OAuth)** — State param, PKCE, Apple JWKS, email-collision rejection all present. **Missing:** redirect allow-list for callback `redirect_uri`.
- **R0.9** — Paystack/Flutterwave gateway clients real; **missing:** webhook receiver routes (payment/controller.py stubs them).
- **R5.5** — Pricing tier matrix + quote logic done. **Missing:** first-time + referral discount auto-application (R5.6 stays `pending`).
- **R5.9** — Paystack `initialize_payment()/verify_payment()` + Flutterwave both real. Wire proof flow done. **Missing:** webhook handlers (idempotency, provider_ref deduplication).
- **R5.14** — State machine transitions enforced. **Missing:** dedicated `AuditLog` writer (R0.10) — depends on S1.

### Confirmed `pending` (no code)
- ~~**R0.10**~~ — **Delivered by S1** (2026-05-02): `app/domain/audit/` created; `AuditLog` ORM + `AuditLogRepo` + `AuditLogService.schedule()` + `audit_ctx.py` ContextVar queue + `@transactional` drain + Alembic migration `c2d3e4f5a6b7`. Wired into `VerificationService` + `AgentApplicationService`. 11 unit tests + 3 e2e tests pass.
- **R0.16** — No derivation layer mapping task states → global verification state. **S3 delivers this.**
- **R5.6** — No first-time discount or referral credit logic anywhere. S14 delivers this.
- **R3.2** — KYC stubs raise `NotImplementedError`. Gated on D6/D7 decisions (BVN + selfie provider).

### Test harness established (S1)
`test/unit/app/domain/audit/` — 11 unit tests (no DB; `AsyncMock`-based).
`test/e2e/app/domain/verification/` — 3 e2e tests (real DB; `ALWAYS_NEW` helper pattern).
Pattern: `@transactional(ALWAYS_NEW)` helper functions own independent sessions. No `@decorate_all_methods(transactional)` on the test class is needed when each DB step should commit independently. All subsequent slices add tests following this pattern.

### R2.3 gap — OAuth redirect allow-list
`S6` will add this. Flag raised for security review if any slice touches OAuth before S6 lands.
