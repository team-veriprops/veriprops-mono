# Architecture Specification

> Authoritative architecture for Veriprops MVP through Phase 19. Cross-references [PRD.md](../PRD.md), [decision-log.md](decision-log.md), and per-app guidance in [backend/CLAUDE.md](../backend/CLAUDE.md) and [frontend/CLAUDE.md](../frontend/CLAUDE.md).

---

## System Overview

Two deployable apps over HTTP:

```
[Diaspora user] ── HTTPS ──> [Next.js 16 frontend] ── /api/* rewrite ──> [FastAPI backend] ──> [MySQL]
                                       │                                          │
                                       │                                          ├── Redis (sessions, rate limit, OAuth state)
                                       │                                          ├── S3 (KYC + evidence + receipts + reports)
                                       │                                          ├── Paystack / Flutterwave (payments)
                                       │                                          ├── SendGrid / Mailjet (email)
                                       │                                          ├── Twilio / Termii (SMS)
                                       │                                          ├── Firebase / WebPush (push)
                                       │                                          ├── Dojah (BVN + selfie — D6/D7)
                                       │                                          ├── Google Drive (file collab)
                                       │                                          └── Zoho DocSign (signing)
                                       │
                                       └── SSE channel for live verification updates (D10)
```

- Backend at `:8000` in dev, mounted under `/api` in prod via the Next.js rewrite.
- Webhooks at `/webhooks/...` (separate router so a CSRF-strict edge can't accidentally block them).
- Real-time channel: SSE one-way (provisional D10), polling fallback at 60s.
- Storage: MySQL primary; Redis for ephemeral/rate-limit/OAuth-state; S3 for binary blobs.

---

## Domain Model

### Aggregates (highest-level boundaries)

1. **User** — identity, personas, sessions, OAuth identities, consent records.
2. **AgentApplication** — KYC, professional credentials, approval state.
3. **AdminInvitation** — invite tokens, sub-roles.
4. **Verification** — the central aggregate. Owns property, tasks, payments, evidence, report versions, share links, disputes.
5. **Task** — child of Verification, role-scoped (Field / Surveyor / Registry / Lawyer).
6. **Report** — child of Verification; versioned; carries trust-score snapshot.
7. **Payment** — child of Verification; payment + wire proof + receipt.
8. **Message** — channel between actors (customer↔admin, admin↔agent, support); fraud-scanned.
9. **Notification** — fan-out events.
10. **AuditLog** — append-only ledger of every state transition.
11. **PricingConfig + CommissionRule** — admin-configured economic knobs.

### Entities (per aggregate)

| Aggregate | Entities |
|---|---|
| User | `User`, `UserPersona`, `Session`, `OAuthIdentity`, `OtpAttempt`, `LoginAttempt`, `SignupDraft`, `UserConsent`, `Device`, `NotificationPreference` |
| AgentApplication | `AgentApplication`, `KycRecord`, `ProfessionalCredential`, `CoverageArea` |
| AdminInvitation | `AdminInvitation`, `AdminRole` |
| Verification | `Verification`, `Property`, `ConsentSnapshot`, `Referral`, `ShareLink` |
| Task | `Task`, `TaskAssignment`, `EvidenceItem`, `ConflictFlag` |
| Report | `Report`, `ReportVersion`, `TrustScoreBreakdown` |
| Payment | `Payment`, `WireProof`, `Receipt`, `Refund`, `Payout`, `PriceLock` |
| Message | `MessageThread`, `Message`, `FraudFlag` |
| Notification | `Notification`, `NotificationDispatch` |
| AuditLog | `AuditLog` |
| PricingConfig | `PricingConfig`, `CurrencyRate`, `CommissionRule`, `BusinessCalendar` |

### Value Objects (no independent identity)

- `VerificationId` (`VP-YYYY-XXXXXX` format)
- `TrustScore` (0–100 with band)
- `Currency` (NGN/USD/GBP/EUR)
- `Money` (amount + currency)
- `Coordinates` (lat/lng)
- `BusinessHours` (with holiday-aware arithmetic)
- `ConsentVersionRef` (doc_type + version)

---

## Bounded Contexts

| Context | Owns | Talks to |
|---|---|---|
| **Identity & Access** | User, sessions, OAuth, RBAC, consent | Everyone (read-only auth check) |
| **Onboarding** | AgentApplication, AdminInvitation, KYC | Identity (writes persona on approval) |
| **Verification Core** | Verification, Property, Task, ReportVersion, state machines | Identity (assigns), Payment (gates), Communication (system msgs), Notification (fan-out) |
| **Payment & Finance** | Payment, WireProof, Receipt, Refund, Payout, PricingConfig, CommissionRule | Verification (lifecycle), Identity (trust-elevation) |
| **Communication** | MessageThread, Message, FraudFlag | Identity (actor lookup), Verification (system msgs), Notification |
| **Notification** | NotificationDispatch, channel preferences | Email/SMS/Push integrations; Identity (recipient profile) |
| **Audit & Compliance** | AuditLog, ConsentSnapshot, retention policies | Everywhere (subscribed to all transitions) |
| **Growth** | Referral, ShareLink, abandoned-draft recovery | Verification, Payment, Notification |
| **Admin Operations** | Mission Control, analytics, content layer | Reads from all contexts |

---

## Database Schema

### Conventions

- All tables extend `BaseEntity` columns: `id` (UUID, PK), `created_at`, `updated_at`, `version` (optimistic lock), `deleted` (soft-delete flag).
- **No DB foreign keys, no cascade, no ON DELETE/UPDATE.** Reference IDs are indexed `CHAR(36)` columns; integrity is application-enforced.
- **No duplicate indexes;** prefer `UniqueConstraint` over `create_index(unique=True)`.
- Per [backend/CLAUDE.md](../backend/CLAUDE.md): MySQL via async driver.

### Table Inventory (post-Phase 19 target)

#### Identity & Access
- `users` — base identity. `user_type` (`USER`/`ADMIN`, immutable). Trust flag.
- `user_personas` — many-to-many; persona ∈ {`CUSTOMER`, `AGENT`}.
- `sessions` — JWT refresh sessions; device + IP + last-active.
- `oauth_identities` — provider + subject + linked_user_id.
- `otp_attempts` — issued + delivered + consumed flags; TTL.
- `login_attempts` — for rate limit + Security Activity Log.
- `signup_drafts` — server-side resume (7-day TTL, soft-deleted on signup).
- `consent_documents` — versioned legal docs (D1).
- `user_consents` — acceptance records (user_id, doc_type, version, accepted_at, ip, fingerprint).
- `devices` — connected device metadata.
- `notification_preferences` — per-event opt-out.

#### Onboarding
- `agent_applications` — application_state, sub-types selected.
- `kyc_records` — encrypted-blob refs, BVN reference, vendor request_id.
- `professional_credentials` — Surveyor / NBA licence numbers + verification status.
- `coverage_areas` — state + LGA + max travel distance per agent.
- `admin_invitations` — token hash, sub-role, expires_at.
- `admin_roles` — current admin sub-role per user.

#### Verification Core
- `verifications` — VID, customer_id, tier, global_state, sla snapshot, price-lock.
- `properties` — verification_id, type, location, details, seller info.
- `tasks` — verification_id, role, agent_id, state, assigned_at, accepted_at, submitted_at.
- `task_assignments` — historical assignments (reassignment audit).
- `evidence_items` — task_id, type (photo/video/doc/map), s3_key, server-stamped GPS+ts, EXIF.
- `conflict_flags` — verification_id, rule_id, status (open/resolved), resolution note.
- `reports` — verification_id, current_version_id.
- `report_versions` — verification_id, version_str, trust_score, body, pdf_s3_key.
- `trust_score_breakdowns` — per-role contribution + weights snapshot.
- `consent_snapshots` — verification_id, snapshot of accepted consent versions at payment.
- `share_links` — token_hash, share_mode, expires_at, revoked_at.

#### Payment & Finance
- `payments` — verification_id, gateway, status, amount + currency, fx_rate, gateway_ref.
- `wire_proofs` — payment_id, s3_key, admin reviewer.
- `receipts` — payment_id, pdf_s3_key, line items snapshot.
- `refunds` — payment_id, reason, status.
- `payouts` — agent_id, amount + currency, status, finance_admin_id.
- `price_locks` — verification_id, price_breakdown_json, fx_rate, expires_at.
- `pricing_configs` — current pricing snapshot (admin-versioned).
- `currency_rates` — base, target, rate, source (live API or admin override), as_of.
- `commission_rules` — role × tier → percentage or flat.
- `business_calendar` — Nigerian public holidays (D23).
- `referrals` — referrer_id, code, redemptions.

#### Communication
- `message_threads` — context_type (verification/task/support), context_id.
- `messages` — thread_id, sender_id, body, attachments, fraud_status.
- `fraud_flags` — message_id, rule_id, admin reviewer.

#### Notifications
- `notifications` — recipient_id, event_type, body, read_at.
- `notification_dispatches` — notification_id, channel (in-app/email/sms/push), status.

#### Audit & Compliance
- `audit_logs` — entity_type, entity_id, actor_id, actor_role, from_state, to_state, ts, ip, note.

### Indexes (illustrative, not exhaustive)

- `verifications(customer_id, global_state, created_at desc)` — customer dashboard list
- `verifications(global_state, created_at desc)` — admin queue
- `tasks(agent_id, state)` — agent dashboard
- `tasks(verification_id, role)` — verification detail
- `evidence_items(task_id, created_at desc)` — evidence feed
- `messages(thread_id, created_at)` — chronological reads
- `audit_logs(entity_type, entity_id, ts)` — per-entity history
- `share_links(token_hash unique)` — public lookup
- `oauth_identities(provider, subject)` unique — OAuth re-auth
- `user_consents(user_id, doc_type, version)` unique — one record per acceptance
- `notifications(recipient_id, read_at, created_at desc)` — bell counter

---

## Service Layer

### Service responsibilities (per domain)

Each domain has `service.py` with `@transactional` methods. Shape per [backend/CLAUDE.md](../backend/CLAUDE.md):

```python
class VerificationService:
    @transactional()
    async def create_draft(self, customer_id: UUID, dto: CreateVerificationDto) -> Verification: ...

    @transactional()
    async def submit_for_payment(self, verification_id: UUID, locked_price: PriceLock) -> Verification: ...

    @transactional()
    async def derive_global_state(self, verification_id: UUID) -> VerificationState: ...
    # called from any task-state-mutation path
```

### Cross-domain choreography (domain events)

Implemented as in-process notifier calls within the same transaction; **no external event bus in MVP**. Sequence on payment confirmation:

```
PaymentService.confirm_payment(payment_id)
  ├── update payments.status = SUCCEEDED
  ├── VerificationService.derive_global_state(verification_id)  → PAID
  ├── UserService.elevate_trust(customer_id, persona=CUSTOMER)
  ├── NotificationService.fan_out(event=PAYMENT_CONFIRMED, recipient=customer_id)
  └── AuditLogService.write(...)
```

All within one `@transactional` outer call. If any inner call fails, the outer transaction rolls back.

### Decision: in-process events vs event bus

We use **in-process notifier calls within a transaction** for MVP. Phase 19 may introduce an outbox pattern if eventual-consistency requirements grow.

---

## API Design

### Conventions

- Mount under `/api`. Frontend rewrites `/api/*` → backend host.
- camelCase JSON via `to_camel` Pydantic alias generator.
- All endpoints auth-protected by default; explicit `@public` decorator for the few that aren't (public lookup, OAuth callback, marketing fetches).
- Pagination via `?page=`, `?size=`, returns `{items, total, page, size}`.

### Endpoint surface (representative)

| Endpoint | Phase | Purpose |
|---|---|---|
| `POST /api/users/auth/signup` | 2 | Email/password signup with OTP markers |
| `POST /api/users/auth/login` | 2 | Email/password login |
| `POST /api/users/auth/logout` | 2 | Invalidate session |
| `GET /api/users/auth/sessions/current` | 2 | Current session + persona list |
| `GET /api/users/auth/oauth/{provider}/start` | 2 | OAuth start (returns `authorizationUrl`) |
| `GET\|POST /api/users/auth/oauth/{provider}/callback` | 2 | OAuth callback (sets cookie + postMessage) |
| `POST /api/users/auth/otp/send` | 2 | Issue OTP (email or phone) |
| `POST /api/users/auth/otp/verify` | 2 | Verify OTP, set marker |
| `POST /api/users/auth/password/forgot` | 2 | Forgot password (1-hr token) |
| `POST /api/users/auth/password/reset` | 2 | Reset password + invalidate sessions |
| `GET /api/users/auth/sessions` | 2 | Connected devices list |
| `DELETE /api/users/auth/sessions/{id}` | 2 | Revoke session |
| `GET /api/users/auth/oauth/identities` | 2 | Linked OAuth list |
| `POST /api/users/auth/oauth/{provider}/link` | 2 | Link from authenticated session |
| `DELETE /api/users/auth/oauth/identities/{id}` | 2 | Unlink (password-existence guard) |
| `GET /api/users/auth/signup-drafts/me` | 2 | Resume partial signup |
| `PUT /api/users/auth/signup-drafts/me` | 2 | Save partial signup |
| `POST /api/agents/applications` | 3 | Submit agent application |
| `GET /api/agents/applications/me` | 3 | Approval status |
| `POST /api/agents/applications/me/kyc` | 3 | Upload KYC docs / start BVN |
| `POST /api/admin/invitations` | 4 | Send admin invite |
| `POST /api/admin/invitations/accept` | 4 | Accept invite (3 scenarios) |
| `GET /api/admin/team` | 4 | List admins |
| `POST /api/verifications` | 5 | Create draft (issues VID) |
| `PUT /api/verifications/{id}/property` | 5 | Save property data |
| `POST /api/verifications/{id}/parse-listing` | 5 | URL parser |
| `POST /api/verifications/{id}/lock-price` | 5 | Lock price + FX |
| `POST /api/verifications/{id}/payment/initiate` | 5 | Start payment |
| `POST /api/verifications/{id}/payment/confirm` | 5 | (system, via webhook) confirm |
| `POST /api/verifications/{id}/wire-proof` | 5 | Upload wire proof |
| `GET /api/verifications` | 5 | List user's verifications |
| `GET /api/verifications/{id}` | 5–9 | Verification detail (role-scoped serialisation) |
| `GET /api/verifications/{id}/evidence` | 9 | Evidence feed |
| `GET /api/verifications/{id}/messages` | 11 | Customer↔Admin thread |
| `POST /api/verifications/{id}/messages` | 11 | Customer→Admin message |
| `GET /api/admin/verifications` | 6 | Admin queue |
| `POST /api/admin/verifications/{id}/assign` | 6 | Assign agents to tasks |
| `POST /api/admin/verifications/{id}/pause` | 6 | Pause |
| `POST /api/admin/verifications/{id}/cancel` | 6 | Cancel |
| `GET /api/agent/jobs` | 7 | Available + active jobs |
| `POST /api/agent/tasks/{id}/accept` | 7 | Accept |
| `POST /api/agent/tasks/{id}/decline` | 7 | Decline |
| `PUT /api/agent/tasks/{id}/draft` | 7 | Save draft |
| `POST /api/agent/tasks/{id}/submit` | 7 | Submit |
| `POST /api/agent/tasks/{id}/escalate` | 7 | Report Issue |
| `POST /api/admin/tasks/{id}/approve` | 8 | Approve |
| `POST /api/admin/tasks/{id}/reject` | 8 | Reject (≥30 char reason) |
| `POST /api/admin/verifications/{id}/release-report` | 8 | Release report |
| `POST /api/admin/verifications/{id}/declare-failed` | 8 | Declare FAILED |
| `GET /api/reports/{verification_id}` | 10 | Get report |
| `GET /api/reports/{verification_id}/pdf` | 10 | Generate/download PDF |
| `POST /api/reports/{verification_id}/share` | 13 | Create share link |
| `DELETE /api/share-links/{id}` | 13 | Revoke |
| `GET /api/public/verifications/{vid}` | 13 | Public lookup (summary only) |
| `POST /api/verifications/{id}/recheck` | 14 | Request re-check |
| `POST /api/verifications/{id}/upgrade-tier` | 14 | Tier upgrade |
| `POST /api/verifications/{id}/dispute` | 14 | File dispute |
| `GET /api/agent/earnings` | 15 | Earnings dashboard |
| `POST /api/agent/withdrawals` | 15 | Request payout |
| `POST /api/admin/payouts/{id}/approve` | 15 | Approve payout |
| `GET /api/admin/dashboard` | 18 | Mission Control |
| `PUT /api/admin/pricing-configs` | 18 | Update pricing |
| `GET /api/admin/audit-export/{vid}` | 19 | Audit export |
| `GET /api/me/audit-log` | 19 | Customer activity log |
| `GET /api/agent/audit-log` | 19 | Agent transition history |

### Customer-facing agent identity contract

API serialiser (FastAPI dependency / response model) **enforces filtering** on all customer-facing endpoints:

```
agent → { role, first_name, avatar_url, verified }
```

Verified by **contract test** that asserts no customer-facing response payload contains `last_name`, `email`, `phone`, or `bvn`.

### SSE channel

`GET /api/verifications/{id}/stream` — server-sent events emitting `state_change`, `evidence_added`, `message_received`. Clients open per verification page; backend subscribes to in-process pub/sub.

---

## Auth Model

### Authentication
- JWT access token (15-min) in HttpOnly cookie `access_token`.
- JWT refresh token (30-day) in HttpOnly cookie `refresh_token`.
- Silent refresh: frontend requests `/api/users/auth/sessions/refresh` on 401.
- OAuth: see PRD §2.2 spec — popup + postMessage + cookie. Backend issues cookie on successful callback; frontend never reads tokens.

### Authorization (RBAC)

`@requires(permission="...")` decorator on routes. Permissions evaluated against:

- `user_type` (USER/ADMIN)
- `user_persona` set (CUSTOMER, AGENT)
- `admin_role` (Super / Operations / Finance) when applicable

Permission matrix (Phase 4):

| Action | Super | Operations | Finance | Agent | Customer |
|---|---|---|---|---|---|
| Invite admins | ✅ | — | — | — | — |
| Approve agent applications | ✅ | ✅ | — | — | — |
| Assign agents to tasks | ✅ | ✅ | — | — | — |
| Configure pricing | ✅ | — | ✅ | — | — |
| Approve payouts | ✅ | — | ✅ | — | — |
| Resolve disputes | ✅ | ✅ | — | — | — |
| Release reports | ✅ | ✅ | — | — | — |
| Declare verification FAILED | ✅ | ✅ | — | — | — |
| Submit task | — | — | — | ✅ (own task) | — |
| Submit verification | — | — | — | — | ✅ (own) |

### Centralised route protection

Next.js `proxy.ts` (cookie-presence only):
- Protected: `/portal/*`, `/admin/*`, `/agent[s]/*`, `/account/*`.
- Guest-only: `/auth`, `/auth/login`, `/auth/signup`.

Backend re-validates session validity on every API call.

---

## Eventing / Async

### MVP: in-process notifier

No external queue. State transitions trigger same-transaction calls to:

- `AuditLogService.write` — every transition.
- `NotificationService.fan_out` — recipient + event lookup → in-app + email/SMS/push.
- `MessageService.post_system_message` — for status changes that surface in customer/agent threads.

### Webhooks (inbound)

| Source | Path | Purpose |
|---|---|---|
| Paystack | `/webhooks/paystack` | Payment confirmation |
| Flutterwave | `/webhooks/flutterwave` | Payment confirmation |
| Dojah | `/webhooks/dojah` | BVN verification result + selfie match |
| Zoho DocSign | `/webhooks/zoho-docsign` | Document signing completion |
| SendGrid / Mailjet | `/webhooks/email` | Bounce + complaint feedback |

Webhooks are idempotent (request_id de-dupe in Redis).

### Background jobs

Implemented as `@transactional(session_policy=ALWAYS_NEW)` functions invoked by:

- Scheduled task runner (Celery beat / APScheduler — Phase 12 enhancement; for MVP, periodic FastAPI background tasks):
  - SLA breach detector — every 15 min.
  - Agent no-show timeout — every 5 min.
  - Abandoned-draft email — daily.
  - Wire-proof admin reminder — daily.
  - Currency rate refresh — every 5 min.
  - Share-link expiry sweep — hourly.

---

## Observability

### Logs
- Structured JSON via `RequestLoggingMiddleware`. Per request: method, path, status, duration, user_id, request_id.
- Domain logs via `di[Logger]` resolved from Kink.
- Sensitive: redact passwords, OTPs, tokens, raw BVN, payment refs.

### Metrics (Phase 18+)
- Counter: signups, verifications created, verifications paid, reports released, disputes filed.
- Histogram: `time(PAID → COMPLETED)` per tier, `time(ASSIGNED → ACCEPTED)`.
- Gauge: active verifications, SLA at-risk count, agents available.

### Tracing
- Optional in MVP. OpenTelemetry hooks in `RequestLoggingMiddleware` if `OTEL_EXPORTER_*` envs present.

### Audit (mandatory, separate from logs)
- `audit_logs` table — append-only, indefinite retention.
- Every state transition writes one audit row.
- Phase 19 export packages all audit rows for a VID into a PDF/CSV bundle.

---

## Security Model

### Threats

| Threat | Mitigation |
|---|---|
| Account takeover via OAuth silent merge | PRD §2.2.3 — explicit reject on email-collision |
| Stolen refresh token | HttpOnly + Secure cookies; per-session revocation |
| Brute-force login | 5-warn / 7-lockout for 15 min; CAPTCHA on retry |
| OTP spam | Max 3 resends → 30-min lockout |
| CSRF on state-changing routes | SameSite cookie + per-form anti-CSRF token |
| OAuth state replay | Signed state, single-use Redis delete-on-read |
| OAuth redirect injection | Strict allow-list on `OAUTH_FRONTEND_ORIGINS` |
| Apple / Facebook id-token forgery | JWKS validation against published keys |
| KYC blob leak | Encrypted at rest in S3; per-user IAM scope; pre-signed URLs ≤5 min |
| Payment-flow replay | Idempotency keys on payment-initiation endpoint |
| Wire proof fraud | Manual finance-admin review (D16) |
| Customer↔agent direct contact | API filter on agent identity (R9.6); fraud scan on messages (R11.4) |
| PDF report tampering | Server-side generation only; checksums in DB |
| Public lookup SEO leak (disputed/in-progress) | `noindex` enforced (R13.2) |
| Audit log tampering | Append-only constraint at the service layer; no UPDATE/DELETE on `audit_logs` |
| PII in logs | Redaction filter in `RequestLoggingMiddleware` |
| Cookie theft via XSS | HttpOnly + Tailwind/Next.js auto-escape; CSP header |

### Cryptographic posture

- TLS everywhere; HSTS preload.
- JWT signing: asymmetric (RS256) with key rotation per environment.
- Password hashing: bcrypt, 12 rounds.
- KYC blob encryption: AES-256-GCM with per-user data key (Phase 3).
- Audit hash chain (Phase 19): each `audit_logs` row carries hash of previous → tamper-evident.

---

## Migration Strategy

### Per-phase Alembic plan

- **Phase 0** — `BaseEntity` + audit/consent/state-machine primitives. Single migration.
- **Phase 2** — users, sessions, OAuth identities, OTP attempts, signup drafts, consent docs/records, login attempts, devices.
- **Phase 3** — agent applications, KYC records, professional credentials, coverage areas.
- **Phase 4** — admin invitations, admin roles.
- **Phase 5** — verifications, properties, payments, wire proofs, receipts, refunds, price locks, currency rates, pricing configs, consent snapshots, business calendar, referrals.
- **Phase 6** — tasks, task assignments.
- **Phase 7** — evidence items.
- **Phase 8** — conflict flags, reports, report versions, trust score breakdowns.
- **Phase 11** — message threads, messages, fraud flags.
- **Phase 12** — notifications, notification dispatches, notification preferences.
- **Phase 13** — share links.
- **Phase 14** — disputes (extension to verifications schema).
- **Phase 15** — payouts, commission rules.
- **Phase 18** — analytics views (read-only views).
- **Phase 19** — audit export materialised tables.

Existing migration `b1f2c3d4e5f6_phases_3_4_5.py` covers parts of Phases 3/4/5 — Slice S0 reconciles its actual content against this plan.

### Seed data

- Phase 0: initial `consent_documents` rows for `PLATFORM_TERMS`, `PRIVACY_POLICY`, `AGENT_TERMS`, `VERIFICATION_TERMS`, `REPORT_DISCLAIMER` v1.0.
- Phase 0: `business_calendar` 2026 + 2027 Nigerian public holidays.
- Phase 4: First Super Admin (manual — credentials supplied at deploy).
- Phase 5: initial `pricing_configs` row matching D11 defaults; initial `commission_rules`.
- Phase 18: blank `area_insights` content, populated via admin UI.

### Backwards compatibility

- camelCase JSON contract is locked; renaming fields requires versioning the endpoint.
- VID format is part of the public contract; never changes.
- Report version numbers (`v1.0`, `v2.0`, …) are public; cannot be renumbered.

---

## Testing Strategy

### Unit
- Per [backend/CLAUDE.md](../backend/CLAUDE.md): `test/unit/` mirrors `main/app/`. `pytest.ini` has `asyncio_mode=auto`.
- Per service: positive-path + at least one validation failure.
- State machines: every legal transition + at least three illegal transitions per machine.
- Contract tests: agent-identity filter on all customer-facing endpoints.

### Integration
- `test/e2e/` for cross-service flows that need real external creds.
- Payment webhooks: simulated Paystack + Flutterwave events.
- BVN webhook: simulated Dojah callback.

### Frontend
- React Testing Library for components.
- Cypress / Playwright for end-to-end auth, signup, verification creation, payment, agent submit, admin review/release. Required E2E flows per phase exit criteria.

### Coverage targets (MVP)
- Service layer: ≥85% line.
- Routes: ≥80% line + 100% of state-mutating endpoints.
- State machines: 100% transition coverage.

### Self-audit checklist (run after every slice)

1. PRD requirement IDs covered by tests are marked `done` in [requirements-matrix.md](requirements-matrix.md).
2. New state transitions write `audit_logs`.
3. New customer-facing endpoints pass agent-identity contract test.
4. New UI components have keyboard navigation.
5. Migration runs clean on local + test DBs.
6. No new domain in `main/app/domain/__init__.py` that's missing import wiring.
7. CLAUDE.md updated when a new pattern emerges.
