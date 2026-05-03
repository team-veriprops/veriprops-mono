---
skill: prd-orchestrator
skill_version: 2.2.0
last_updated: 2026-05-02
---

# Progress Tracker

> Live state of the PRD execution loop. Updated every `run`/`resume` cycle. Source of truth alongside [requirements-matrix.md](requirements-matrix.md).

---

**status:** S2 complete — ready for S3

**next_slice:** S3 (Derived global state rules — R0.16)

**current_slice:** —

**completion %:** 31% (43 done / 140 total — R0.11 + R0.15 delivered by S2)

---

## Completed Slices

| Slice | Description | Completed |
|---|---|---|
| S0 | Audit & reconcile current state against requirements matrix | 2026-05-02 |
| S1 | Audit log primitive — `AuditLog` model, repo, service, ContextVar queue, `@transactional` drain, Alembic migration, tests | 2026-05-02 |
| S2 | Reusable state-machine validator — `appodus_utils/state/machine.py`, `IllegalStateTransitionException`, Verification + Task + Report machines, 101 unit tests | 2026-05-02 |

## Current Slice

S2 complete. Next: S3 — Derived global state rules (see [execution-plan.md](execution-plan.md)).

## Pending Slices

S1 → S2 → S3 → S4 → S5 → … → S58 (full sequence in [execution-plan.md](execution-plan.md)).

---

## Runtime State

idle — S2 checkpointed, no slice in-flight. Awaiting `run` to begin S3.

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
| D18 | KYC document review path | S8 (Phase 3 KYC) |
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

Branch: `main`. Most recent commit: `c5e9796 implement auth`.

Working tree has uncommitted modifications across backend (auth, consent, oauth, session, payment), frontend (admin/portal/agents pages, auth components), and untracked Phase 3/4/5 code. See `git status` for full list.

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
