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

- S11 Phase 7 — Agent task execution.
      Backend: agent execution on the S10 task domain — `list_for_agent`, `accept` (broadcast
      first-accept-wins + §6.5 capacity; manual = assigned agent only), `decline` (→pool,
      decline_count++), `start` (ACCEPTED→IN_PROGRESS), `submit` (IN_PROGRESS→SUBMITTED); every
      mutation re-derives status via the §4.1 owner (all-submitted→UNDER_REVIEW); first submit upgrades
      the AGENT to trusted. Role validator enforces the four role forms over a JSON `submission_payload`;
      submit requires ≥1 evidence. Evidence child domain: `EvidenceService.capture` computes the §4.5
      SHA-256 hash + stamps §7.3a server GPS/timestamp, uploads via the storage facade (encrypted,
      content-addressed key). `StubDocumentStorageProvider` (FileStorage.STUB) = deterministic default
      under `DOCUMENT_STORAGE_STUB_MODE`. Agent controller `/agents/tasks/*` (list/accept/decline/start/
      evidence-multipart/submit) mounted at root; ownership authz. `task_evidence` +
      `submission_payload`/`rejection_reason` folded into `0001` (round-trip clean). Frontend:
      `agent-task-service` + hooks, `/agents/tasks` dashboard (accept/decline), `/agents/tasks/[taskId]`
      workflow (accept→start→evidence upload w/ geolocation hint + content-hash display→per-role findings
      form, submit gated on required fields + evidence). Backend 515 tests; frontend 270; tsc+lint clean.
      Gaps: offline queue + image derivatives + presigned-PUT deferred (D11 fallback; see self_audit_s11).

- S12 Phase 8 — Admin review & report release.
      Backend: Trust Score Weights domain (`trust_score_weight_config`, sum-to-100 per tier,
      idempotent default seed, admin CRUD, deterministic `compute_composite = Σ weight/100 ×
      per-task quality`, D14). Report domain (versioned `report_version`, DRAFT→RELEASED→SUPERSEDED;
      release supersedes the prior version §8.6). Review service = the **release gate** (§8): admin
      `approve` records intent + quality *without* changing task state (stays SUBMITTED, so all-approved
      never auto-completes); `reject` SUBMITTED→REJECTED (derive→IN_PROGRESS rework); `release` (requires
      UNDER_REVIEW + all review-approved + no HIGH conflict) flips all SUBMITTED→APPROVED atomically
      (derive→COMPLETED exactly at release), accrues CLEARING commissions (price×weight×share, D13),
      computes the composite, creates the RELEASED report; `reopen` APPROVED→IN_PROGRESS + supersede;
      `fail` → FAILED + refund (`PaymentService.refund`, `PaymentStatus.REFUNDED`). Conflict detection
      (§8.2 rules). Endpoints `/admin/review/*` + `/admin/trust-score-weights` (RBAC). 2 tables + 2 task
      columns in `0001` (round-trip clean). Frontend: report-review at
      `/admin/verifications/[id]/report-review` (approve/reject/reopen, conflicts, trust score, release,
      fail&refund) + Trust Score Weights CRUD at `/admin/config/trust-score-weights` (live sum-to-100).
      Backend 533 tests; frontend 273; tsc+lint clean. Gaps: richer quality rubric + live gateway refund
      + report-ready email deferred (see runtime-state self_audit_s12). Final report UX + PDF is S14.

- S13 Phase 9 — Customer tracking & evidence (SSE).
      Backend: in-process realtime emitter (`app/core/realtime`, best-effort pub/sub keyed by verification;
      D15) wired at every status/task mutation (task accept/decline/start/submit + evidence, review
      approve/reject/release, payment→PAID). Customer tracking sub-package (`verification/tracking/`,
      orchestration-only): pure §9.2 label projection (`labels.py` — status/task-collapse/SLA/interim copy,
      backend source of truth); `CustomerTrackingService` builds the shared snapshot (header + SLA tracker +
      tier-adaptive progress + assigned agents + interim milestones + evidence preview) reused by the poll
      endpoint and the SSE initial frame. Endpoints on `/verifications/*`: `GET /` (my list), `/tracking`
      (poll), `/stream` (SSE `text/event-stream`, cookie-auth, ownership-gated before streaming; generator
      forwards in-memory events + 25s heartbeats, no mid-stream DB), `/evidence` (paged, **review-approved
      tasks only, D17**, presigned URLs via the storage facade), `/activity` (reuses `AuditLogService`).
      **First-name-only enforced at the API** via `AssignedAgentDto` (role/first_name/avatar_url/verified
      only). Shared SLA-health helper extracted to `core/sla.py` (admin + customer reuse). `interim_note`
      column added to `verification_tasks` (0001) + `approve_task(interim_note=…)`. Frontend: `types/tracking`,
      service (listMine/getTracking/getEvidence/streamUrl) + `useVerificationTracking` (60s poll +
      `useVerificationStream` SSE refetch, D15), shared `VerificationStatusBadge` + portable
      `VerificationProgress`, tracking dashboard `/portal/verifications/[id]`, evidence feed + full-screen
      viewer w/ tamper-evidence hash panel `/portal/verifications/[id]/evidence`, My-Verifications list
      `/portal/verifications` (fixes the sidebar 404). Backend 562 tests; frontend 277; tsc+lint clean;
      migration round-trip clean. Gaps: progressive/derivative image pipeline + messages preview (Phase 11)
      + Redis SSE fan-out (S16) deferred.

- S14 Phase 10 — Final report experience *(built; Legal Opinion go-live gated on NBA sign-off §B, D18)*.
      Backend: `report_pdf` facade (`appodus_utils/integrations/report_pdf/` — decoupled primitive
      `ReportPdfContext`; **fpdf2** pure-Python renderer as the default (D16, per-page §3.5 legal footer via
      `footer()` + embedded QR to the public lookup + SUPERSEDED watermark) + deterministic stub, selected by
      `REPORT_PDF_STUB_MODE`). Pure content builder (`report/content.py` — `trust_band` 90/60 bands, opinion-framed
      verdict, tier-gated sections; Legal Opinion section built but content withheld unless `LEGAL_OPINION_ENABLED`,
      D18). `CustomerReportService` (ownership gate → released report → content → ack state → PDF). Access-gate
      acknowledgement child domain (`report/acknowledgement/`, recorded against the report version;
      `report_acknowledgements` in 0001). Customer endpoints `/verifications/{id}/report`, `/report/acknowledge`,
      `/report/pdf` (StreamingResponse application/pdf). Wired `send_report_ready` into the release path (closes
      the S12 email follow-up). `LEGAL_OPINION_ENABLED` surfaced via `/config/public`. Frontend: `types/report`,
      report-service + hooks, report page `/portal/verifications/[id]/report` (one-time access-gate modal →
      acknowledge, verified-badge header + Download PDF / Request Re-check, plain-language verdict lead,
      trust-score band + tooltip, collapsible tier-dependent sections with the Legal Opinion section hidden until
      the flag is on, per-page legal footer, superseded banner) + a "View report" CTA on the tracking page when
      COMPLETED. Backend 582 tests; frontend 280; migration round-trip clean; tsc+lint clean. Real fpdf2 render
      verified: %PDF valid, legal footer on every page (7/7), QR embedded, tier-gated sections. Gaps: pixel-perfect
      HTML-CSS PDF + customer-vs-agent document appendix attribution deferred; Legal Opinion **build-only** until §B.

- S15 Phase 11 — Communication layer *(full, incl. structured clarifications, D19)*.
      Backend: new `app/domain/communication/` parent with one-entity-per-domain children — `conversation/`
      (thread: CUSTOMER_ADMIN / ADMIN_AGENT / GENERAL_SUPPORT), `conversation_participant/` (per-user read
      state → the §N.3 Chat unread counter), `chat_message/` (ChatMessage + §4.7 fraud-hold state). Pure
      deterministic `fraud_scan.py` (phone/email/URL/banking/social/off-platform → categories; clean = fast
      lane DELIVERED, any flag = HELD). `ChatMessageState` in `core/state/status.py` + transition table in
      `machine.py` (PENDING_SCAN→{DELIVERED,HELD}; HELD→{DELIVERED,BLOCKED}; DELIVERED/BLOCKED terminal).
      `CommunicationService` façade (ownership + thread resolution + send). Admin hold review
      (`/admin/messages/held` + approve/reject, audit-logged). Structured clarifications (CLARIFICATION_
      REQUEST/RESPONSE + clarification_status). Rejection reason auto-posts tagged to the task (§11.1,
      best-effort hook in ReviewService). Per-user SSE (`UserEventEmitter` + `/chat/stream`). §11.3 identity
      guard: customer-facing sender = first_name/avatar only. Read-only-when-approved for agents. Attachments
      column kept, no upload (D22). 3 tables in 0001 (round-trip clean; `created_by` inherited from BaseEntity).
      Frontend: `types/chat`, `chat-service` + `useChatQueries` (+`useChatRealtime`), `useUserStream`;
      `ChatButton` in the top nav (Support→Chat→Notifications→Account, 9+ cap, hidden at 0); shared `ChatThread`;
      thread pages (portal/agent/admin verification messages, `/portal/chat` list, `/portal/support` FAQ +
      general support, `/admin/messages` hold queue); contextual Messages CTAs + nav items. Backend 627 tests
      (+36); frontend 296 (+7); migration round-trip clean; tsc+lint clean. Gaps: attachments + customer
      status-change auto-posts (land via the S16 event bus) + admin chat counter deferred.

- S16 Phase 12 — Notification system & event bus *(full refactor, D20)*.
      Backend: `app/core/events/` = the §4.8 in-process synchronous `EventBus` (`DomainEvent` + `EventType`
      full §12.2 set; publish once, best-effort per subscriber). Three subscribers registered at bootstrap:
      `realtime_subscriber` (re-emits the **exact S13 verification SSE event name** — frontend hooks
      untouched), `notification_subscriber` (declarative rule-table fan-out), `chat_counter_subscriber`
      (per-user Chat counter for `MESSAGE_SENT`, §12.3). `notification/` domain (feed + counter + mark-read;
      `rules.py` = the single Chat-vs-Notification table; `content.py` = backend-owned copy + links;
      `dispatcher.py` sends the template on a computed channel set). `notification_preference/` domain
      (per-event email/SMS opt-out; in-app always on). **Refactor:** every `publish_verification_event(...)`
      (review/task/verification) now publishes a `DomainEvent` once; notification-worthy events carry the
      customer recipient + type (`PAYMENT_CONFIRMED` at PAID, `STATUS_CHANGED` on derive, `REPORT_READY` at
      release — the direct `send_report_ready` call removed); chat delivery publishes `MESSAGE_SENT`.
      SLA-breach sweep (`SlaMonitorService`, D23) publishes `SlaBreached` once per overdue verification
      (idempotent), wired into the S10 scheduler (30-min, ALWAYS_NEW, off under test) + admin dev endpoint.
      2 tables in 0001 (round-trip clean). Frontend: `types/notification`, `notification-service` +
      `useNotificationQueries` (+`useNotificationRealtime`); real `NotificationBell` (counter 9+/hidden-at-0
      + dropdown + "View all") replacing the stub; `/portal/notifications` history; notification-preferences
      page (portal + agent, per-event email/SMS toggles). Backend 644 tests (+17); frontend 299 (+3);
      migration round-trip clean; tsc+lint clean. Gaps: customer status-change chat auto-post + admin
      SLA-breach notification + dispute/payout/re-check sources (S18/S19) are documented follow-ups; full
      live UI drive-through deferred (test-substitute gate, per S13/S14).

## Current Slice
- none — S15 (Phase 11) + S16 (Phase 12) delivered & committed. Communication + notifications ship end-to-end.

## Post-MVP hardening (S1–S14 review pass)
- **Persona dashboards completed.** `/portal/dashboard` and `/admin/dashboard` did not exist (both
  landing redirects 404'd); the agent dashboard was a thin status card. Added backend-owned summary
  endpoints — `GET /verifications/summary` (`CustomerDashboardDto`), `GET /admin/verifications/summary`
  (`AdminDashboardDto`, RBAC `VIEW_ADMIN_PANEL`), `GET /agents/tasks/summary` (`AgentDashboardDto`) —
  each deriving all counts server-side (status rollups, overdue via `core/sla.ACTIVE_SLA_STATES`,
  open pool tasks, pending applications, open chargebacks). Frontend: shared `ui/StatCard`, dashboard
  pages for all three personas, services/hooks + contract tests. Nav sidebars trimmed to built routes
  (S15+ items restored as their slices land) so nothing 404s.
- **Full build verified both ends** (closes final-audit follow-up #6): backend `pytest` 587 passed;
  frontend `pnpm lint` clean, `tsc --noEmit` clean, `vitest` 286 passed, and a real `pnpm build`
  succeeds (both dashboard routes prerender).

## Pending Slices
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
- ~70% (16 of 23 slices; Phase-0 foundation + Phases 1–12 complete — the MVP cut line plus the communication
  layer (admin-mediated fraud-scanned chat) and the notification/event-bus surface ship end-to-end:
  submission → payment → assignment → agent execution → admin review/release → live tracking → final report +
  PDF → mediated chat → in-app/email/SMS notifications). Remaining: S17–S23 (harden & scale, Phases 13–19).

---

### ⚠️ Strict-mode reminder
`config.yaml` is `mode: strict` (D3). Worktree committed at each slice boundary; clean between slices.

<!-- legacy note retained for history -->
`config.yaml` is `mode: strict` (D3). The worktree was previously **dirty** (large staged domain deletions +
edits). `prd-orchestrator run` will refuse to start until the worktree is committed/clean. Commit the in-flight
refactor before invoking `run`.
