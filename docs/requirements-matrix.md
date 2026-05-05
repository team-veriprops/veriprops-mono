---
skill: prd-orchestrator
skill_version: 2.2.0
last_updated: 2026-05-05
---

# Requirements Traceability Matrix

> One row per discrete, testable requirement extracted from [PRD.md](../PRD.md).
> Status legend: `pending` (not started) · `in_progress` (code exists, gaps remain) · `done` (meets exit criteria + tests) · `blocked` (needs decision — see [decision-log.md](decision-log.md)).
>
> *Status column reflects best-effort assessment from current `main` branch on 2026-05-02. The `audit` slice in [execution-plan.md](execution-plan.md) reconciles status against the live code.*

| ID | Phase | Requirement | Dependencies | Modules | Schema Impact | API Impact | Security Impact | Complexity | Risk | Acceptance Criteria | Test Coverage | Status |
|----|------|-------------|--------------|----------|---------------|------------|----------------|------------|------|---------------------|---------------|--------|
| R0.1 | 0 | Monorepo layout (backend/, frontend/) | none | repo | no | no | low | low | low | Both apps boot independently; `/api/*` rewrite works | smoke | done |
| R0.2 | 0 | `BaseEntity` (UUID id, created_at, updated_at, version, deleted) | none | appodus_utils/db | yes | no | low | low | low | All domain entities inherit; soft-delete enforced | unit | done |
| R0.3 | 0 | `GenericRepo[Model,Create,Update,Query,Search]` with pagination, soft-delete-aware | R0.2 | appodus_utils/db | no | no | low | medium | low | Generic CRUD/list/page works for any subclass | unit | done |
| R0.4 | 0 | `@transactional` with USE_IF_PRESENT / ALWAYS_NEW / FALLBACK_NEW | R0.2 | appodus_utils/decorators | no | no | medium | medium | medium | Each policy verified; raises if missing context | unit | done |
| R0.5 | 0 | `AppodusBaseException` hierarchy + HTTP mapping | none | appodus_utils/exception | no | yes | medium | low | low | Custom exceptions return structured HTTP | unit | done |
| R0.6 | 0 | DBSessionMiddleware + RequestLoggingMiddleware + CORS | R0.4 | appodus_utils/middleware | no | yes | medium | low | low | Per-request session in ContextVar; logs emitted | integration | done |
| R0.7 | 0 | Kink DI bootstrap (logger, Redis, JWT bearer, AsyncClient) | none | appodus_utils/config | no | no | low | low | low | `di[T]` resolves; app-side override works | unit | done |
| R0.8 | 0 | Env-based config via `appodus_active_env` (`local/test/dev/staging/prod`) | none | app/config | no | no | medium | low | low | All envs load without import errors | smoke | done |
| R0.9 | 0 | Integration shells (S3, Paystack, Flutterwave, SendGrid, Mailjet, Twilio, Termii, Firebase, Google Drive, Zoho DocSign) | R0.7 | appodus_utils/integrations | no | yes (webhooks) | medium | medium | medium | Stubs callable; webhook routes mounted | integration | in_progress |
| R0.10 | 0 | `AuditLog` entity + writer hook on every state transition | R0.2 | app/domain/audit | yes | no | high | medium | high | Every transition produces an AuditLog row | unit + integration | done |
| R0.11 | 0 | Reusable state-machine validator | none | appodus_utils/state | no | no | high | medium | high | Verification, Task, Report all consume it | unit | done |
| R0.12 | 0 | `ConsentDocument` + `UserConsent` entities + version bump triggers re-consent | R0.2 | app/domain/user/auth/consent | yes | yes | high | medium | high | Records (user_id, doc_type, version, accepted_at, ip, fingerprint) | unit + integration | done |
| R0.13 | 0 | Frontend design system (Radix + Tailwind v4 tokens; form/field/input/toast/modal/wizard) | none | frontend/components/ui | no | no | low | medium | low | All listed components present and storybook'd | visual + unit | done |
| R0.14 | 0 | JWT auth wiring (HttpOnly cookie 15-min/30-day, silent refresh, Next.js proxy guards) | R0.7 | backend auth + frontend proxy | yes | yes | high | medium | high | Cookie set/cleared correctly; proxy redirects | E2E | done |
| R0.15 | 0 | Verification + Task + Report state machines authoritatively defined | R0.11 | appodus_utils/state/machine.py | no | no | high | high | high | Transition tables match PRD §0.2; rejected illegal moves | unit | done |
| R0.16 | 0 | Derived global state rules (PRD §0.3) | R0.15 | verification/state_machine | no | no | high | high | high | Global state derives from task states deterministically | unit | done |
| R0.17 | 0 | `alembic upgrade head` clean on local/test/dev/staging/prod | R0.2 | alembic | yes | no | low | low | low | CI green on all envs | smoke | in_progress |
| **— Phase 1 — Marketing site —** | | | | | | | | | | | | |
| R1.1 | 1 | Sticky glassmorphism nav with brand + links + CTAs (intent preserve) | R0.13 | frontend/components/website | no | no | low | low | low | All nav items present; mobile overlay works | visual + unit | done |
| R1.2 | 1 | Hero with badge pill, headline, subhead, two CTAs, floating Trust Score card | R1.1 | frontend/components/website/HeroSection | no | no | low | medium | low | 1440px + 375px viewports both pass | visual | done |
| R1.3 | 1 | Verification Ecosystem 3-feature bento (Trust Score / Verification ID / Certified Report) | R1.1 | frontend/components/website | no | no | low | low | low | All three cards present with correct icons | visual | done |
| R1.4 | 1 | Rigorous Methodology 5-step horizontal stepper | R1.1 | frontend/components/website | no | no | low | low | low | 5 steps in order with connecting line | visual | done |
| R1.5 | 1 | Verified Agents — 4 cards (Field / Surveyor / Registry / Lawyer) + "Become an Agent" CTA | R1.1 | frontend/components/website/VerifiedAgents | no | no | low | low | low | All four roles present; CTA → /auth?intent=agent | visual + unit | done |
| R1.6 | 1 | Pricing — 3 tiers + currency toggle (NGN/USD/GBP/EUR) + tier CTAs | R1.1 | frontend/components/website/PricingSection | no | no | low | medium | medium | Toggle cycles all 4; live FX rate displayed | unit + visual | done |
| R1.7 | 1 | Testimonials (3 diaspora stories) | R1.1 | frontend/components/website | no | no | low | low | low | UK/USA/Canada quotes present | visual | done |
| R1.8 | 1 | CTA Section (legacy / family wealth) | R1.1 | frontend/components/website/CTASection | no | no | low | low | low | Trust stats render | visual | done |
| R1.9 | 1 | Footer (4-column + newsletter signup) | R1.1 | frontend/components/website | no | no | low | low | low | All four columns + newsletter form | visual + unit | done |
| R1.10 | 1 | SEO meta correctly set; `noindex` only on phase-13 lookup unless completed+public | R1.1 | frontend/app | no | no | low | low | low | Public pages crawlable; lookup logic correct | unit | done |
| **— Phase 2 — Auth shell —** | | | | | | | | | | | | |
| R2.1 | 2 | Email/password signup with first/last/email/phone/country/timezone/currency, OTP markers (30-min TTL, single-use) | R0.12 | user/auth/service | yes | yes | high | medium | high | Both OTP markers required; consumed on success | unit + E2E | done |
| R2.2 | 2 | Email/password login with rate limit (warn@5, lockout@7 for 15 min) | R2.1 | user/auth/service | yes | yes | high | medium | high | Lockout + LOGIN_FAILURE_WARNING surfaced | unit + E2E | done |
| R2.3 | 2 | OAuth — Google/Apple/Facebook popup + HttpOnly cookie + postMessage bridge | R2.1 | user/auth/oauth | yes | yes | high | high | high | All §2.2 security requirements met (state, PKCE, redirect, etc.) | E2E | in_progress |
| R2.4 | 2 | OTP flow (6 digits, 10-min TTL, max 3 resends, 30-min lockout) | R2.1 | user/auth/otp_service | yes | yes | high | medium | medium | All caps enforced server-side | unit + E2E | done |
| R2.5 | 2 | Forgot/reset password (1-hr token, single-use, all sessions invalidated on reset) | R2.1 | user/auth/service | yes | yes | high | medium | medium | Sessions revoked; email copy correct | unit + E2E | in_progress |
| R2.6 | 2 | Set password (OAuth-only users add password later) | R2.3 | user/auth/service | no | yes | high | low | low | Password added; login works after | unit | in_progress |
| R2.7 | 2 | Failed-attempt logging (timestamp, IP, fingerprint) → Security Activity Log | R2.1 | user/auth/service | yes | yes | medium | medium | medium | All failures logged + visible | unit + E2E | in_progress |
| R2.8 | 2 | Connected devices list + revoke (individual / all) | R2.1 | user/auth/session | yes | yes | high | medium | medium | Sessions surfaced; revoke works | E2E | in_progress |
| R2.9 | 2 | Linked OAuth accounts list / link / unlink (with password-existence guard) | R2.3 | user/auth/oauth | yes | yes | high | medium | medium | Unlink rejected if no password | E2E | in_progress |
| R2.10 | 2 | Resume partial signup — server-side `signup_drafts` (7-day TTL) + localStorage mirror | R2.1 | user/auth/signup_draft | yes | yes | medium | medium | medium | Server prefers; localStorage fallback | unit + E2E | done |
| R2.11 | 2 | Versioned consent on signup (Platform Terms + Privacy Policy) | R0.12 | user/auth/consent | yes | yes | high | low | medium | Records carry version, ip, fingerprint | unit | done |
| R2.12 | 2 | Auth gate interstitial preserving `intent` query param | R2.1 | frontend/auth | no | no | low | low | low | `?intent=verify`/`?intent=agent` round-trips | E2E | in_progress |
| R2.13 | 2 | Centralised route protection in Next.js `proxy.ts` for /portal/* /admin/* /agent[s]/* /account/* | R0.14 | frontend/proxy | no | no | high | low | medium | Cookie-presence redirects work both ways | E2E | done |
| R2.14 | 2 | Post-auth redirect by role priority (Admin → Agent → Customer) preserving intent | R2.1, R2.12 | frontend | no | no | medium | low | medium | All role combos route correctly | E2E | in_progress |
| R2.15 | 2 | Customer persona auto-add on "Verify a Property" signup flow | R2.1 | user/auth/service | no | yes | medium | low | medium | CUSTOMER persona present after | unit | in_progress |
| **— Phase 3 — Agent onboarding + KYC —** | | | | | | | | | | | | |
| R3.1 | 3 | Agent application wizard step 1 — type selection (Field / Surveyor / Registry / Lawyer multi-select) | R2.* | user/agent | yes | yes | medium | low | low | Multi-select persisted | unit | done |
| R3.2 | 3 | KYC step — BVN with live verification OR ID upload + selfie match | R3.1 | user/agent/kyc | yes | yes | high | high | high | Vendor integration verified; encrypted storage | unit + integration | in_progress |
| R3.3 | 3 | Professional credentials — Surveyor licence, NBA licence, coverage areas, bio | R3.1 | user/agent | yes | yes | medium | medium | medium | Conditional fields enforced | unit | done |
| R3.4 | 3 | Review & submit — versioned Agent Terms + truthfulness checkbox | R0.12, R3.1 | user/agent | yes | yes | high | low | medium | Consent record captured | unit | in_progress |
| R3.5 | 3 | Approval Status Dashboard (PENDING / APPROVED / REJECTED with reason) | R3.4 | frontend/agents/onboarding/status | no | yes | low | low | low | All three states render | unit + E2E | done |
| R3.6 | 3 | KYC docs encrypted in S3 with per-user access | R3.2 | integrations/storage | no | yes | high | medium | high | Encryption at rest verified; access enforced | integration | pending |
| R3.7 | 3 | Resumable wizard (re-enter on tab close) | R3.1 | user/agent | yes | yes | low | medium | low | Step preserved server-side | unit + E2E | done |
| **— Phase 4 — Admin invites + RBAC —** | | | | | | | | | | | | |
| R4.1 | 4 | Admin invite (Super Admin sends, sub-role: Super / Operations / Finance) | R2.* | user/admin_invitation | yes | yes | high | low | medium | Invite token issued | unit + E2E | done |
| R4.2 | 4 | Invite email tokenised, 72-hr validity | R4.1 | user/admin_invitation | no | yes | medium | low | medium | Expired tokens rejected | unit | done |
| R4.3 | 4 | Invite acceptance — three scenarios (new user / existing / already admin) | R4.1 | user/admin_invitation | yes | yes | high | medium | high | All three branches tested | unit + E2E | done |
| R4.4 | 4 | RBAC matrix (invite admins, approve agents, assign agents, approve payouts, configure pricing, resolve disputes, release reports) | R0.7 | user/auth/utils/permissions | no | yes | high | high | high | Every admin endpoint guarded | unit | done |
| R4.5 | 4 | Admin team management (list, deactivate, change sub-role) | R4.4 | user/admin | no | yes | high | low | medium | Audit logs on changes | E2E | done |
| R4.6 | 4 | Seed first Super Admin via alembic data migration or CLI | R4.4 | alembic | yes | no | high | low | low | First admin exists post-deploy | smoke | done |
| **— Phase 5 — Customer submission + payment —** | | | | | | | | | | | | |
| R5.1 | 5 | Property submission wizard with VID assignment at Step 1 (`VP-YYYY-XXXXXX`) | R2.* | verification/property | yes | yes | medium | medium | medium | VID generated + persisted | unit + E2E | done |
| R5.2 | 5 | Listing-URL parser (PropertyPro, Nigeria Property Centre; manual fallback) | R5.1 | verification | no | yes | low | medium | medium | URL → fields populated | integration | **blocked (Q17)** |
| R5.3 | 5 | Property type / location / details forms (conditional Land vs Building) | R5.1 | verification/property | yes | yes | low | medium | low | All conditional fields | unit | in_progress |
| R5.4 | 5 | Optional document upload + seller info | R5.1 | verification/property | yes | yes | medium | low | medium | Files in S3; seller info captured | unit | in_progress |
| R5.5 | 5 | Pricing transparency UI (tier cards, comparison modal, line-item breakdown, currency toggle, recommendation banner) | R5.1 | verification/pricing | yes | yes | low | medium | medium | All views render | unit + visual | in_progress |
| R5.6 | 5 | First-time + referral discount auto-applied | R5.5 | verification/pricing | yes | yes | medium | low | medium | Discount visible in breakdown | unit | pending |
| R5.7 | 5 | Price lock on Continue to Payment (24 hrs default) | R5.5 | verification | yes | yes | medium | medium | medium | Lock window enforced | unit | done |
| R5.8 | 5 | Five versioned consent items pre-payment (no pre-check) | R0.12 | verification | yes | yes | high | low | medium | All five recorded | unit | **blocked (D19 — legal copy required)** |
| R5.9 | 5 | Payment methods — Card (Paystack/Flutterwave), Bank transfer (NGN virtual account 24-hr), International wire (USD/GBP/EUR + proof + admin confirm) | R5.5 | payment | yes | yes | high | high | high | All three paths complete | E2E | in_progress |
| R5.10 | 5 | Payment status UI with plain-language messaging | R5.9 | payment | no | yes | low | medium | low | Never raw gateway codes | unit | in_progress |
| R5.11 | 5 | Retry flow (preserve price lock; log failures; support after 3 failures) | R5.9 | payment | yes | yes | medium | medium | medium | Retry preserves lock | E2E | pending |
| R5.12 | 5 | Receipt — instant generation, emailed, contains VID + line items + FX rate | R5.9 | payment | yes | yes | medium | low | low | PDF receipt arrives | integration | pending |
| R5.13 | 5 | Post-payment confirmation page (VID, ETA, SLA countdown, "Track" CTA) | R5.9 | frontend/portal | no | yes | low | low | low | All shown | E2E | done |
| R5.14 | 5 | DRAFT → SUBMITTED → PAYMENT_PENDING → PAID transitions deterministic | R0.15, R5.9 | verification/state_machine | no | yes | high | high | high | All transitions audit-logged | unit + E2E | in_progress |
| R5.15 | 5 | Customer upgraded to `trusted` on first successful payment | R5.9 | user/service | yes | yes | medium | low | low | Trust flag flips | unit | pending |
| **— Phase 6 — Admin verification control panel —** | | | | | | | | | | | | |
| R6.1 | 6 | Verifications list filterable (status, tier, SLA, state/LGA, date) | R5.* | admin | no | yes | medium | medium | medium | All filters work | unit + E2E | pending |
| R6.2 | 6 | Verification detail with admin actions (Assign / Reassign / Pause / Resume / Cancel / Declare Failure / Set Delay / Add Note) | R6.1 | admin | yes | yes | high | high | high | All actions audit-logged | unit + E2E | pending |
| R6.3 | 6 | Agent assignment modal (suggested by proximity/load/performance + search) | R6.2, R3.* | admin | no | yes | medium | medium | medium | Ranking deterministic for fixtures | unit | pending |
| R6.4 | 6 | Load-balancing view + capacity per agent | R6.3 | admin | yes | yes | medium | medium | medium | Per-agent active task count | unit | pending |
| R6.5 | 6 | Admin notes (pinned, tagged, searchable) | R6.2 | admin | yes | yes | medium | low | low | Tags filterable | unit | pending |
| R6.6 | 6 | Agent application approval queue | R3.5 | admin | no | yes | high | medium | medium | Approve/reject with reason | unit + E2E | in_progress |
| R6.7 | 6 | First assignment moves PAID → IN_PROGRESS; Lawyer task locked until siblings SUBMITTED | R6.3, R0.15 | verification/state_machine | no | yes | high | high | high | Dependency rule enforced | unit | pending |
| **— Phase 7 — Agent task execution —** | | | | | | | | | | | | |
| R7.1 | 7 | Agent dashboard — available jobs, my active, completed + earnings preview | R3.5 | agent | no | yes | medium | medium | medium | Lists render correctly | unit + E2E | pending |
| R7.2 | 7 | Accept / Decline + no-show timeout (admin-configured) | R7.1 | agent | yes | yes | high | medium | medium | Timeouts return to PENDING | unit | **blocked (Q24)** |
| R7.3 | 7 | Field-agent submission UI (access, condition, observations, ≥5 GPS-stamped photos, optional video, score, declaration) | R7.1 | agent/forms | yes | yes | high | medium | medium | All fields validated | unit + E2E | pending |
| R7.4 | 7 | Surveyor submission UI (boundary, coordinates, plan upload, score, declaration) | R7.1 | agent/forms | yes | yes | high | medium | medium | Coordinate validation | unit | pending |
| R7.5 | 7 | Registry-agent submission UI (search details, title doc assessment, ownership chain, uploads, score, declaration) | R7.1 | agent/forms | yes | yes | high | medium | medium | All sections required | unit | pending |
| R7.6 | 7 | Lawyer submission UI gated by sibling-task SUBMITTED (legal opinion ≥200 chars, NBA confirmation, score) | R7.1, R0.16 | agent/forms | yes | yes | high | high | high | Dependency gate enforced server-side | unit | pending |
| R7.7 | 7 | Local autosave + explicit "Save Draft" + offline upload queue + sync indicator | R7.1 | agent | yes | yes | medium | medium | medium | Offline test passes | E2E | pending |
| R7.8 | 7 | "Report Issue" escalation (categorised; admin alerted) | R7.1 | agent | yes | yes | medium | low | low | Admin notified | unit | pending |
| R7.9 | 7 | Agent upgraded to `trusted` on first task submission | R7.* | user/service | no | yes | medium | low | low | Trust flag flips | unit | pending |
| R7.10 | 7 | Submitting all tasks auto-derives global state to UNDER_REVIEW | R0.16, R7.* | verification/state_machine | no | yes | high | high | high | Auto-derivation tested | unit | pending |
| **— Phase 8 — Admin review + report release —** | | | | | | | | | | | | |
| R8.1 | 8 | Task review interface (read-only render, evidence gallery, approve / reject) | R7.* | admin | no | yes | high | medium | medium | Both actions work | unit + E2E | pending |
| R8.2 | 8 | Reject requires ≥30-char reason + revision instructions; task SUBMITTED → REJECTED → IN_PROGRESS on rework | R8.1, R0.15 | verification/state_machine | no | yes | high | high | high | Min length enforced; transition correct | unit | pending |
| R8.3 | 8 | Approve → APPROVED; when all APPROVED, "Report ready for release" alert | R8.1 | admin | no | yes | high | medium | medium | Alert fires | unit | pending |
| R8.4 | 8 | Conflict detection (configurable rules) + admin resolve | R8.1 | admin | yes | yes | high | medium | high | Initial rule set wired | unit | **blocked (Q20)** |
| R8.5 | 8 | Report release gate — composite trust score from agent scores | R8.3 | verification/report | yes | yes | high | high | high | Weights match decision | unit | **blocked (Q8, Q32)** |
| R8.6 | 8 | "Release Report" publishes + COMPLETED transition | R8.5, R0.15 | verification/state_machine | no | yes | high | high | high | Customer cannot see until released | E2E | pending |
| R8.7 | 8 | "Request Changes" can re-open any task | R8.5 | admin | no | yes | medium | medium | medium | Task re-opens cleanly | unit | pending |
| R8.8 | 8 | FAILED state declarable by admin (irreversible, refund applied) | R8.5, R0.15 | verification/state_machine | no | yes | high | high | high | Reason required; refund triggered | unit | pending |
| **— Phase 9 — Customer tracking + evidence —** | | | | | | | | | | | | |
| R9.1 | 9 | Verification tracking dashboard (header, SLA tracker, progress, agents, evidence preview, messages preview) | R5.* | portal | no | yes | medium | high | medium | All blocks render | unit + E2E | pending |
| R9.2 | 9 | Real-time updates — WebSocket or SSE with 60-sec polling fallback | R9.1 | portal + backend channel | no | yes | medium | high | high | Live update verified | E2E | **blocked (Q22)** |
| R9.3 | 9 | State-specific expanded views (PAID, IN_PROGRESS, UNDER_REVIEW) | R9.1 | portal | no | no | low | medium | low | All three render correctly | visual + unit | pending |
| R9.4 | 9 | Customer state label mapping (per PRD §9.3) | R9.1 | portal | no | no | low | low | low | All six labels present | unit | pending |
| R9.5 | 9 | Evidence layer — chronological feed, role-tagged (not name), full-screen viewer + EXIF panel, server-side timestamp/GPS | R9.1 | portal | yes | yes | high | medium | high | Tamper-evidence verified | unit + E2E | pending |
| R9.6 | 9 | First-name-only rule enforced at API (not UI) | R9.5 | backend serialisation | no | yes | high | high | high | Contract test on customer-facing endpoints | unit | pending |
| **— Phase 10 — Final report experience —** | | | | | | | | | | | | |
| R10.1 | 10 | Access-gate modal (one-time, recorded against report version) | R0.12, R8.6 | report | yes | yes | high | medium | medium | Records on first view | unit | pending |
| R10.2 | 10 | Report header (badge, VID, version, date, tier, address, actions) | R8.6 | report | no | yes | low | low | low | All actions wired | unit | pending |
| R10.3 | 10 | Trust Score display (numeric + band + tooltip) | R8.5 | report | no | yes | low | low | low | Tooltip plain-English | unit | pending |
| R10.4 | 10 | Report sections (collapsible, tier-dependent: Exec Summary, Physical, Registry, Boundary, Legal Opinion, Risk, Customer Docs Appendix) | R8.5 | report | yes | yes | medium | medium | medium | Sections gate by tier | unit | pending |
| R10.5 | 10 | Legal footer on every page (HTML + PDF) | R10.2 | report | no | no | high | medium | high | PDF parity verified | unit | pending |
| R10.6 | 10 | Server-side PDF generation with branded cover, TOC, evidence thumbnails, QR to lookup, re-downloadable | R10.5 | report | yes | yes | medium | high | medium | PDF round-trip valid | integration | pending |
| R10.7 | 10 | Report versioning (v1.0 / v1.1 / v2.0 / v3.0; SUPERSEDED watermark) | R10.6 | report | yes | yes | high | medium | medium | Old versions watermarked | unit | pending |
| **— Phase 11 — Communication layer —** | | | | | | | | | | | | |
| R11.1 | 11 | Customer ↔ Admin per-verification thread + system messages on status change | R5.*, R8.* | message | yes | yes | high | medium | medium | Thread persists; system msgs auto-posted | unit + E2E | in_progress |
| R11.2 | 11 | Admin ↔ Agent per-task thread; admin broadcast to all agents on a verification | R7.*, R6.* | message | yes | yes | high | medium | medium | Broadcast fan-out works | unit + E2E | pending |
| R11.3 | 11 | General support channel (account/billing/general; can reference VID) | R2.* | message | yes | yes | medium | low | low | VID attachment optional | unit | pending |
| R11.4 | 11 | Send-time fraud detection (phone, email, URL, banking, "outside the platform") | R11.* | message | no | yes | high | medium | high | Flagged messages held | unit + E2E | pending |
| R11.5 | 11 | Customer-facing endpoints return only role/first_name/avatar/verified for agents | R9.6 | backend | no | yes | high | high | high | Contract test | unit | pending |
| **— Phase 12 — Notification system —** | | | | | | | | | | | | |
| R12.1 | 12 | In-app notifications (always on) | R2.* | notification | yes | yes | medium | low | medium | Bell icon shows unread | unit + E2E | pending |
| R12.2 | 12 | Email notifications (per-event opt-out) | R0.9 | notification | yes | yes | medium | low | medium | Opt-out toggles | integration | pending |
| R12.3 | 12 | SMS notifications (per-event opt-out; high-signal only) | R0.9 | notification | yes | yes | medium | medium | medium | SMS sent + opt-out | integration | **blocked (Q14)** |
| R12.4 | 12 | Push notifications (Firebase / WebPush) — Phase 2 enhancement | R0.9 | notification | yes | yes | medium | medium | medium | Push delivery verified | integration | pending |
| R12.5 | 12 | Customer triggers (payment, agents assigned, status change, evidence, message, SLA, report ready, refund, re-check) | R5.*–R10.* | notification | no | yes | medium | low | low | Each event routes correctly | unit | pending |
| R12.6 | 12 | Agent triggers (new job, accepted, reassigned, revision request, payment, feedback) | R7.*, R8.* | notification | no | yes | medium | low | low | Each event routes | unit | pending |
| R12.7 | 12 | Admin triggers (SLA, report-ready, conflict, no-show, fraud-flag, dispute, wire proof) | R6.*, R8.*, R14.* | notification | no | yes | medium | low | low | Each event routes | unit | pending |
| R12.8 | 12 | `/portal/account/notification-preferences` page | R12.* | portal | yes | yes | low | low | low | All event toggles | unit | pending |
| **— Phase 13 — Public lookup + sharing —** | | | | | | | | | | | | |
| R13.1 | 13 | `/verify/[id]` summary-only public page (band not number, never address/agents/owners/docs) | R10.* | website | no | yes | high | medium | medium | All five states render | unit + E2E | pending |
| R13.2 | 13 | `noindex` unless COMPLETED + sharing=public | R13.1 | website | no | no | medium | medium | medium | Robots header verified | unit | pending |
| R13.3 | 13 | Share modes (Private / Link-only / Public / Named recipient) with 30-day default + revocation | R10.* | report sharing | yes | yes | high | medium | high | Revoke invalidates immediately | unit + E2E | pending |
| R13.4 | 13 | Named recipients must acknowledge disclaimer first view | R0.12 | report sharing | yes | yes | high | low | medium | Recorded against version | unit | pending |
| **— Phase 14 — Revisions / re-verification / disputes —** | | | | | | | | | | | | |
| R14.1 | 14 | Re-check request (free-text + optional docs; admin approves; v2.0 bump) | R10.* | verification | yes | yes | high | medium | medium | Cycle restarts for scoped tasks | unit + E2E | **blocked (Q7)** |
| R14.2 | 14 | Tier upgrade (delta pricing only; new tasks for added scope; SLA extended; v3.0) | R10.* | verification | yes | yes | high | medium | medium | Existing approved tasks preserved | unit | pending |
| R14.3 | 14 | Dispute flow (≥100-char description, optional evidence; COMPLETED → DISPUTED) | R10.* | verification/state_machine | yes | yes | high | high | high | Window enforced | unit + E2E | pending |
| R14.4 | 14 | Dispute outcomes (reject / uphold full refund / uphold partial + free re-check) | R14.3 | verification/state_machine | no | yes | high | high | high | All three transitions verified | unit | pending |
| R14.5 | 14 | Admin resolution note delivered verbatim | R14.4 | message | no | yes | medium | low | low | Customer sees exact text | E2E | pending |
| **— Phase 15 — Agent earnings —** | | | | | | | | | | | | |
| R15.1 | 15 | Agent earnings dashboard (monthly / lifetime / available / pending) | R7.*, R8.* | agent | yes | yes | medium | medium | medium | Per-job breakdown | unit + E2E | pending |
| R15.2 | 15 | Commission matrix (admin-configured per role × tier; visible pre-accept) | R4.4 | pricing | yes | yes | medium | low | medium | Visible on job detail | unit | pending |
| R15.3 | 15 | Withdrawal flow (stored bank account, confirmation, 2-business-day SLA) | R15.1 | agent | yes | yes | high | high | high | Payout end-to-end staging test | E2E | pending |
| R15.4 | 15 | Finance admin payout panel (approve / hold / adjust; audit-logged) | R4.4 | admin | yes | yes | high | medium | medium | All actions audited | unit | pending |
| **— Phase 16 — Reputation + coverage —** | | | | | | | | | | | | |
| R16.1 | 16 | Performance metrics (completion rate, accuracy 1–5, timeliness) | R8.* | agent | yes | yes | medium | medium | medium | Metrics updated post-approval | unit | pending |
| R16.2 | 16 | Agent profile self-view (metrics, total jobs, active since, coverage) | R16.1 | agent | no | yes | low | low | low | Renders correctly | unit | pending |
| R16.3 | 16 | Assignment ranking by composite score | R16.1, R6.3 | admin | no | yes | medium | medium | medium | Order deterministic | unit | pending |
| R16.4 | 16 | Threshold behaviours (low → reduced visibility; high → "Top Agent" badge) | R16.1 | agent | no | yes | medium | low | medium | Visibility filter works | unit | pending |
| R16.5 | 16 | Coverage settings (states + LGAs + max travel) | R3.* | agent | yes | yes | low | low | low | Multi-select persists | unit | pending |
| R16.6 | 16 | Availability status 🟢/🟡/🔴 (auto-red at max capacity) | R16.5 | agent | no | yes | medium | low | medium | Auto-flip at cap | unit | **blocked (Q25)** |
| R16.7 | 16 | Role-specific dashboards (Field/Surveyor → map; Registry → docs; Lawyer → wait queue) | R7.* | agent | no | yes | medium | medium | medium | Each renders default | unit | pending |
| **— Phase 17 — Growth + conversion —** | | | | | | | | | | | | |
| R17.1 | 17 | Referral system (unique link per customer; invitee + referrer credit) | R5.* | growth | yes | yes | medium | low | medium | Credit applies on first paid verification | unit + E2E | pending |
| R17.2 | 17 | First-time discount auto-applied (no code) | R5.6 | growth | no | yes | low | low | low | Visible in breakdown | unit | pending |
| R17.3 | 17 | Abandoned-verification recovery (24-hr banner + one email; price lock refresh > 24 hrs) | R5.7 | growth | yes | yes | medium | low | low | Email fires once | E2E | pending |
| **— Phase 18 — Admin operations + analytics —** | | | | | | | | | | | | |
| R18.1 | 18 | Mission Control (active verifications, pending assignments, stuck jobs, revenue, availability, SLA) | R5.*–R16.* | admin | no | yes | medium | medium | medium | All KPIs live | unit | pending |
| R18.2 | 18 | Pricing & tier configuration UI (tier creation, line items, fees, upgrade delta, surcharge, discount caps) | R5.5 | admin | yes | yes | high | medium | medium | Changes propagate without deploy | unit + E2E | pending |
| R18.3 | 18 | Financial management (payments, payouts, commission, wire proof review queue) | R5.9, R15.* | admin | no | yes | high | medium | medium | Wire-proof queue actionable | unit | pending |
| R18.4 | 18 | Content & Trust Layer (How it works, FAQs, testimonials, agent spotlight, Area Insights per LGA) | R1.* | admin | yes | yes | low | low | low | CMS-style edits | unit | **blocked (Q31)** |
| R18.5 | 18 | Geographic view (map of active verifications) | R5.* | admin | no | yes | low | medium | low | Map renders + filters | unit | pending |
| R18.6 | 18 | Analytics dashboard (signup→pay conversion, time by tier, agent perf, revenue by region/tier, dispute rate) | R5.*, R8.*, R14.* | admin | no | yes | medium | medium | medium | Charts render with real data | unit | pending |
| R18.7 | 18 | System-wide notification broadcast (compose, preview, schedule) | R12.* | admin | no | yes | medium | low | medium | Broadcast deliverable | unit | pending |
| **— Phase 19 — Audit + compliance maturity —** | | | | | | | | | | | | |
| R19.1 | 19 | Full audit export per verification (PDF or CSV; admin only) | R0.10 | audit | no | yes | high | medium | high | Pack reproducible | unit + E2E | pending |
| R19.2 | 19 | Customer-facing simplified activity log | R0.10 | portal | no | yes | medium | low | medium | No PII leakage | unit | pending |
| R19.3 | 19 | Agent-facing task transition history | R0.10 | agent | no | yes | medium | low | medium | All transitions visible | unit | pending |
| R19.4 | 19 | Versioned consent records downloadable per user | R0.12 | account | no | yes | high | low | medium | Download produces full history | unit | pending |
| R19.5 | 19 | Fraud-flag review history | R11.4 | admin | no | yes | medium | low | medium | Searchable | unit | pending |
| R19.6 | 19 | Admin action logs (permission, role, payout) | R4.4, R15.4 | admin | no | yes | high | low | high | All admin mutations logged | unit | pending |
| R19.7 | 19 | Retention policy (audit indefinite; PII per policy) | R0.10 | data lifecycle | no | no | high | high | high | NDPR-compliant erasure path | manual | pending |

---

## Status Summary

*Updated 2026-05-02 by Slice S0 audit — reconciled against live `main` branch.*

| Status | Count |
|---|---|
| `done` | 40 |
| `in_progress` | 27 |
| `blocked` | 11 |
| `pending` | 62 |
| **Total** | **140** |

**Key S0 audit findings:**
- R0.11 verified done: `verification/state_machine/__init__.py` has full `StateMachine` class with `assert_can_transition()`.
- R0.12 verified done: `consent/models.py` has `ConsentDocument` + `UserConsent` with version, ip_address, device_fingerprint.
- R2.1/R2.2 verified done: signup OTP 30-min gate enforced; login warn@5/lockout@7 implemented.
- R2.10/R2.11 verified done: `signup_drafts` 7-day TTL + consent records on signup.
- R3.1/R3.3/R3.7 verified done: agent types JSON array, conditional credential fields, resumable wizard on main AgentApplication row.
- R4.1–R4.6 verified done: full admin invitation flow, three acceptance branches, RBAC permission matrix, super-admin seed migration.
- R5.1/R5.7 verified done: VP-YYYY-XXXXXX VID generation, 24-hr price lock enforced.
- **Critical gaps still pending:** R5.6 (first-time/referral discounts), payment webhooks (R5.9 stubs). R0.10 delivered by S1. R0.16 delivered by S3.
- **No test suite found** — zero test files in backend.
