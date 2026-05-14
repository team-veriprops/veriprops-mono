---
skill: prd-orchestrator
skill_version: 2.2.0
last_updated: 2026-05-12
---

# Progress Tracker

> Live state of the PRD execution loop. Updated every `run`/`resume` cycle. Source of truth alongside [requirements-matrix.md](requirements-matrix.md).

---

**status:** S0–S55 complete — ALL PHASES DONE (Phases 0–18 fully delivered)

**next_slice:** —

**current_slice:** —

**completion %:** 100% — S0–S55 shipped

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
| S11 | RBAC enforcement (R4.4, R4.5) — confirmed JWT claims already embed `admin_sub_role`; created `user/admin_team/` domain (`service.py`, `controller.py`, `models.py`) with list/deactivate/change-sub-role endpoints all guarded by `require_permission(INVITE_ADMIN)`; added `ADMIN_DEACTIVATED` to `SecurityEventType`; added `list_admins()` + `demote_to_user()` to `UserRepo`; mounted `admin_team_router` in `user/controller.py`; wrote 61 new unit tests (12 team management + 49 permission matrix); 329 backend tests passing, 0 regressions | 2026-05-07 |

| S12 | Property submission backend (R5.3, R5.4, R5.14) — audited full verification domain (models, service, validator, controller, pricing, state machine all confirmed); added `PropertyDocumentType` enum + `DocumentUploadResponseDto` to `models.py`; added `upload_document()` to `VerificationService` (injecting `DocumentStorageProviderFactory`, SSE-AES256 encrypted S3 upload); added `POST /verifications/{id}/documents` multipart route; wrote 31 service unit tests + 11 validator unit tests (42 total); 371 backend tests passing, 0 regressions | 2026-05-07 |
| S13 | Listing-URL parser (R5.2) — built `verification/parser/` module (interface, models, service, PropertyPro + NPC providers using httpx + BeautifulSoup4); added `POST /verifications/{id}/parse-listing` endpoint (jwt_required, assert_owner, assert_draft, graceful fallback); fixture HTML files for both parsers; 22 unit tests covering extraction, service routing, unknown-domain fallback, parse-error fallback | 2026-05-07 |
| S14 | Pricing validation — confirmed config.py already correct (BASIC=₦150k, STANDARD=₦350k, PREMIUM=₦750k in kobo); no code changes needed; D11 confirmed | 2026-05-07 |
| S15 | Pre-payment consent — already complete (ConsentService.record_user_consent() persists ip_address + device_fingerprint + consent_version; ConsentStep.tsx exists in wizard); no changes | 2026-05-07 |
| S16 | Payment gateway integration (R5.9, R5.15) — replaced stub initiate() with real gateway calls: CARD→Flutterwave /payments (returns checkout_url + stores provider_ref), BANK_TRANSFER→Paystack /charge virtual account (returns bank/account/expiry instructions + stores provider_ref), WIRE→settings.WIRE_* static values; added WIRE_BENEFICIARY_BANK/SWIFT/IBAN/BENEFICIARY settings; fixed Paystack webhook handle_charge_success() (was calling broken _transaction_service); fixed Flutterwave webhook verif-hash header (was verif_hash); mounted webhook_router in domain/__init__.py; 17 payment service unit tests; 410 backend tests passing, 0 regressions | 2026-05-07 |
| S17 | Post-payment portal — already complete (confirmed/page.tsx shows VID + ETA + SLA countdown + "Track" CTA; VerificationWizardContainer redirects to confirmed after onPaid()); no changes | 2026-05-07 |

| S18 | Admin verification queue + detail — `verification/admin/` backend domain (list, detail, pause/resume/cancel/fail/delay/notes/release-to-pool); `VerificationQueue.tsx`, `VerificationDetail.tsx`, `AdminActionPanel.tsx`, `NotesList.tsx`, `VerificationStatusBadge.tsx`; admin nav + routes | 2026-05-11 |
| S19 | Task schema + competitive pool assignment — `verification/task/` + `evidence/` backend domains; `Task` ORM + OL claim (`UPDATE WHERE status=PENDING`); `TaskService` with state derivation; `admin-service.ts` + `useAdminQueries.ts` task hooks; `AssignmentModal.tsx` | 2026-05-11 |
| S20 | S20 audit — confirmed persona elevation on approve; cursor rules verified; `agent-service.test.ts` coverage | 2026-05-11 |
| S21 | Agent dashboard + accept/decline — agent task routes (available/active/completed/accept/decline); `AvailableJobsList.tsx`, `ActiveTasksList.tsx`, `CompletedTasksSummary.tsx`; agent nav updated; no-show + pool timeout APScheduler jobs | 2026-05-11 |
| S22 | Field agent submission — evidence service (GPS validation Nigeria bbox, ≥5 photo gate); `FieldAgentForm.tsx`; `EvidenceUploadSection.tsx`, `DeclarationSection.tsx`, `DraftSaveButton.tsx` | 2026-05-11 |
| S23 | Surveyor submission — `SurveyorForm.tsx`; boundary coords + survey plan validation | 2026-05-11 |
| S24 | Registry submission — `RegistryAgentForm.tsx`; registry search ref + title doc + ownership chain validation | 2026-05-11 |
| S25 | Lawyer submission + dependency gate — `LawyerForm.tsx` with locked overlay; ≥200-char legal opinion; sibling SUBMITTED/APPROVED gate server-side | 2026-05-11 |
| S26 | Offline + autosave — `sw.js` Background Sync service worker; `offlineQueue.ts` IndexedDB wrapper (drafts + upload queue); `SyncIndicator.tsx` (offline/syncing/synced banner); `SwRegistrar.tsx` client component; SW registered in agents layout | 2026-05-11 |
| S27 | Escalation + trust elevation — `verification/escalation/` backend domain (models/repo/service); `EscalationModal.tsx`; SSE publish to `admin:escalations`; trust elevation on first task submission | 2026-05-11 |
| S28 | Task Review Interface — `task/review/` backend domain (approve/reject/reopen); `TaskReviewPanel.tsx`, `EvidenceGallery.tsx`; all 4 task roles; audit log on every action | 2026-05-11 |
| S29 | Conflict Detection — 4-rule engine (occupancy mismatch, boundary divergence >5m, authenticity conflict, owner-name mismatch); `conflict/` backend domain; `ConflictPanel.tsx`, `ConflictBadge.tsx`; admin resolution (OVERRIDE / REJECT_TASK) | 2026-05-11 |
| S30 | Trust Score Computation — tier-specific weighted average; `scoring/` domain; `TrustScoreWeightConfig` ORM; admin weight editor; `TrustScoreBadge.tsx`; recomputes on every task approval | 2026-05-11 |
| S31 | Release Report + FAILED State — `release/` domain; pre-checks (all tasks APPROVED + no open conflicts); UNDER_REVIEW→COMPLETED / FAILED transitions; `ReleaseReportPanel.tsx`; SSE publish `report_released` | 2026-05-11 |
| S32 | Verification Tracking Dashboard — `portal/tracking.py`; `TrackingDto` with progress_pct, SLA, agents (first name + role only); `ProgressTracker.tsx`, `SlaTracker.tsx`, `AssignedAgentsCard.tsx`, `StateDetailBanner.tsx` | 2026-05-11 |
| S33 | SSE Live Updates — `portal/stream.py` with Redis pub/sub + 60s heartbeat; `useVerificationStream.ts` with exponential backoff + polling fallback; tracking page auto-invalidates on events | 2026-05-11 |
| S34 | Evidence Layer — `portal/evidence.py`; ownership-checked; never exposes agent identity; `EvidenceFeed.tsx` grouped by role; GPS metadata chips | 2026-05-11 |
| S35 | Report HTML View — `report/assembly.py`; tier-conditional sections (BASIC: registry; STANDARD+: physical+boundary; PREMIUM: legal opinion); `AccessGateModal.tsx` scroll-to-accept; `ReportSection.tsx` collapsible; `ReportLegalFooter.tsx`; `report_views` migration | 2026-05-11 |
| S36 | PDF Generation + Versioning — `report/pdf.py` WeasyPrint + Jinja2 + QR code; single conditional `report.html.jinja2`; version tracking with `is_superseded` watermark; `GET /api/portal/verifications/{vid}/report/pdf` blob streaming | 2026-05-11 |
| S37 | Message Threads — `thread/` backend domain (MessageThread, ThreadMessage ORM, ThreadRepo, ThreadService, REST + WS controller); Redis pub/sub fan-out; system auto-posts on status changes; agent name stripped to first name only; chat pages for portal/admin/agents; ThreadView WebSocket component; thread-service.ts | 2026-05-12 |
| S38 | Fraud Detection on Send — `thread/fraud/` subdomain (FraudFlag ORM, FraudDetectionService with compiled regexes for phone/email/URL/banking/off-platform phrases); held messages; admin fraud-flags queue; FraudFlagQueue.tsx | 2026-05-12 |
| S39 | Notification Fan-out Core — `notification/` backend domain (Notification, NotificationDispatch, NotificationPreference ORM; NotificationService.emit(); NotificationEvent enum; VerificationMessages message class); hooks wired: PAYMENT_CONFIRMED, AGENTS_ASSIGNED, REPORT_READY, REVISION_REQUEST, NEW_MESSAGE; NotificationBell + NotificationList; nav wiring for portal/admin/agents | 2026-05-12 |
| S40 | SMS + Push Enablement — SMS (Termii/Twilio) + Push (Firebase/WebPush) channels wired in VerificationMessages for high-signal events; preference opt-out read before dispatch | 2026-05-12 |
| S41 | Notification Preferences UI — `GET/PUT /api/notifications/preferences` backend; NotificationPreferencesForm.tsx; portal + agents account pages | 2026-05-12 |
| S42 | Public Lookup Page — `GET /api/public/verifications/{vid}` (no auth; 5 state branches; numeric score never exposed); `/verify/[id]/page.tsx` (noindex unless COMPLETED+PUBLIC); VerificationBadge, PublicSummaryCard, public-verification-service.ts | 2026-05-12 |
| S43 | Share Modes + Revocation — `verification/share/` backend domain (ShareLink, ShareRecipient ORM; ShareService with create/revoke/get_by_token; 30-day default expiry; NAMED_RECIPIENT email invite); ShareModal.tsx; 3 Alembic migrations: c3d4e5f6a7b8 (threads+fraud), d4e5f6a7b8c9 (notifications), e5f6a7b8c9d0 (share+recheck+dispute+commission+payout) | 2026-05-12 |
| S44 | Re-check Request — `verification/recheck/` backend domain (RecheckRequest ORM; RecheckService submit/approve/reject; scope pricing = sum of commission rates); admin recheck queue; RecheckModal.tsx; RecheckQueue.tsx; verification COMPLETED→IN_PROGRESS transition | 2026-05-12 |
| S45 | Tier Upgrade — `verification/tier_upgrade/` backend domain (TierUpgrade ORM; TierUpgradeService submit/complete; delta pricing; idempotency guard); TierUpgradeModal.tsx; upgrade-service.ts | 2026-05-12 |
| S46 | Dispute Flow — `verification/dispute/` backend domain (Dispute, DisputeResolution ORM; DisputeService submit/resolve; DisputeValidator ≥100-char gate; 3 outcomes: REJECTED/FULL_REFUND/PARTIAL_RECHECK); COMPLETED→DISPUTED state transition; DisputeModal.tsx; DisputeQueue.tsx; DisputeResolutionForm.tsx | 2026-05-12 |
| S47 | Agent Earnings + Commission — `commission/` backend domain (CommissionRule, Earning ORM; CommissionService compute_and_record/get_earnings_summary); commission_preview on task detail; admin CommissionRuleEditor; EarningsDashboard.tsx; JobBreakdownTable.tsx; earnings-service.ts | 2026-05-12 |
| S48 | Withdrawal + Payout Panel — `payout/` backend domain (BankAccount, Payout, PayoutAdjustment ORM; PayoutService submit_withdrawal/approve/hold/adjust; APPROVE_PAYOUT RBAC gate); WithdrawalModal.tsx; PayoutHistory.tsx; PayoutPanel.tsx; AdjustPayoutModal.tsx; payout-service.ts | 2026-05-12 |
| S49 | Agent Reputation + Quality Scores — `agent/quality_score/` domain; `AgentMetrics` computation (completion_rate, accuracy_score, timeliness_score + composite); agent profile page | 2026-05-12 |
| S50 | Coverage + Availability — `availability_status` + `max_travel_km`; auto-flip on task accept/release; coverage settings page | 2026-05-12 |
| S51 | Referral System — `referral/` domain; get_or_create_code; claim_referral with self-referral rejection; compute_discount with cap; referrals page | 2026-05-12 |
| S52 | Abandonment Recovery — get_abandonments/send_abandonment_emails (idempotent); refresh_price_lock; AbandonmentBanner | 2026-05-12 |
| S53 | Mission Control + Analytics — `analytics/` domain (AnalyticsRepo pure aggregation; AnalyticsService; 3 endpoints); analytics indexes migration; MissionControlPanel + RegionalPerformanceTable + AnalyticsDashboard frontend | 2026-05-14 |
| S54 | Pricing & Finance Management — `pricing/` DB models (PricingTierConfig, PricingLineItem, PricingUpgradeDelta); admin pricing CRUD; payment admin list + wire confirm; commission breakdown; PricingManager + UpgradeDeltaEditor + PaymentsTable + CommissionBreakdownTable frontend | 2026-05-14 |
| S55 | Content Layer + System-wide Broadcast — `content/` domain (ContentItem ORM; CRUD + publish + reorder + area insights; public endpoints); `broadcast/` domain (DRAFT→SCHEDULED/SENT/CANCELLED state machine; BroadcastMessages.send_broadcast); CONTENT_CREATOR + CONTENT_APPROVER sub-roles + permissions; ContentItemTable + ContentItemForm + AreaInsightPanel + BroadcastList + BroadcastComposer frontend | 2026-05-14 |

## Current Slice

ALL SLICES COMPLETE. S0–S55 (Phases 0–18) fully delivered end-to-end.

Last audit: 2026-05-14 — 19 S55 unit tests passing (content: 9, broadcast: 10); pnpm build 0 TypeScript errors.

## Pending Slices

None — full PRD delivered.

---

## Runtime State

idle — S13–S17 complete; 410 backend tests passing; no slice in-flight.

## Pending Recovery

none — S13–S17 completed cleanly.

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
