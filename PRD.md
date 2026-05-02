# Veriprops — Master Product Requirements Document

**Product:** Veriprops ("Verified Properties")
**Audience:** Nigerians in the Diaspora verifying real estate in Nigeria
**Stack:** FastAPI (Python) backend · Next.js 16 (App Router, React 19) frontend
**Currencies:** NGN, USD, EUR, GBP
**Version:** 1.0 (master, consolidates product brief + auth PRD v1.1 + verification lifecycle PRD v2.0)
**Status:** Draft — ordered for implementation

> **Companion documents (authoritative for their modules):**
> - `BRAIN PICK PRDS/README.md` — full product brief
> - `BRAIN PICK PRDS/user-auth-onboarding_prd.md` — detailed auth flows
> - `BRAIN PICK PRDS/veriprops_verification_lifecycle_prd.md` — detailed verification lifecycle
>
> This document is the **master plan** across all of them, sequenced for build order. Each phase below links back to the detailed PRD where relevant.

---

## Table of Contents

### Part I — Foundations
1. [Vision & Strategy](#1-vision--strategy)
2. [Actors & Role Architecture](#2-actors--role-architecture)
3. [Legal & Liability Framework](#3-legal--liability-framework)
4. [Cross-Cutting Concerns](#4-cross-cutting-concerns)

### Part II — Implementation Phases
5. [Phase 0 — Platform Foundation](#phase-0--platform-foundation)
6. [Phase 1 — Marketing Site & Home Page](#phase-1--marketing-site--home-page)
7. [Phase 2 — Auth & Onboarding Shell](#phase-2--auth--onboarding-shell)
8. [Phase 3 — Agent Onboarding + KYC](#phase-3--agent-onboarding--kyc)
9. [Phase 4 — Admin Onboarding & Role Management](#phase-4--admin-onboarding--role-management)
10. [Phase 5 — Customer Submission & Payment](#phase-5--customer-submission--payment)
11. [Phase 6 — Admin Verification Control Panel](#phase-6--admin-verification-control-panel)
12. [Phase 7 — Agent Task Execution](#phase-7--agent-task-execution)
13. [Phase 8 — Admin Review & Report Release](#phase-8--admin-review--report-release)
14. [Phase 9 — Customer Tracking & Evidence Layer](#phase-9--customer-tracking--evidence-layer)
15. [Phase 10 — Final Report Experience](#phase-10--final-report-experience)
16. [Phase 11 — Communication Layer](#phase-11--communication-layer)
17. [Phase 12 — Notification System](#phase-12--notification-system)
18. [Phase 13 — Public Verification Lookup & Sharing](#phase-13--public-verification-lookup--sharing)
19. [Phase 14 — Revision, Re-verification & Disputes](#phase-14--revision-re-verification--disputes)
20. [Phase 15 — Agent Earnings & Commission](#phase-15--agent-earnings--commission)
21. [Phase 16 — Agent Reputation & Coverage](#phase-16--agent-reputation--coverage)
22. [Phase 17 — Growth & Conversion Mechanics](#phase-17--growth--conversion-mechanics)
23. [Phase 18 — Admin Operations & Analytics](#phase-18--admin-operations--analytics)
24. [Phase 19 — Audit & Compliance Maturity](#phase-19--audit--compliance-maturity)
25. [Post-MVP Roadmap](#post-mvp-roadmap)

### Part III — Supporting Artefacts
26. [Success Metrics](#26-success-metrics)
27. [Open Questions Consolidated](#27-open-questions-consolidated)

---

# Part I — Foundations

## 1. Vision & Strategy

### 1.1 Mission

Make **"verified property"** the default belief in the Nigerian real-estate market. End state: _"If it's not verified, nobody buys it."_

### 1.2 Strategic Pillars

| Pillar | Position |
|---|---|
| **Enemy** | Fraudsters, fake agents, forged documents, uncertainty |
| **Creed** | _"Verify everything. Trust nothing blindly."_ |
| **Language** | Trust Score (0–100), Verification ID, Verified badge |
| **Playbook** | Educate → Build ecosystem → Standardize |
| **Emotion** | Protect wealth & family legacy |
| **Symbol** | ✅ Veriprops Verified |
| **Golden line** | _"We reduce uncertainty. We do not eliminate it."_ |

### 1.3 Product Primitives

- **Verification** — a single request against one property, scoped by **tier** (Basic / Standard / Premium).
- **Verification ID** — unique public-safe identifier (`VP-YYYY-XXXXXX`), shareable, the canonical anchor for all downstream artefacts (report, certificate, public lookup).
- **Trust Score** — weighted composite (0–100) per report: 90+ Safe / 60–89 Caution / 0–59 High Risk.
- **Task** — a role-scoped unit of work (Registry / Field / Surveyor / Lawyer) belonging to a verification.
- **Report** — the versioned output (`v1.0`, `v2.0`, …) — an opinion, not a guarantee.

### 1.4 Tier → Task Matrix

| Tier | Registry | Field | Surveyor | Lawyer | Target SLA |
|---|---|---|---|---|---|
| Basic | ✅ | — | — | — | 3–5 business days |
| Standard | ✅ | ✅ | ✅ | — | 5–7 business days |
| Premium | ✅ | ✅ | ✅ | ✅ | 7–10 business days |

Lawyer task is **dependent**: it unlocks only after all non-lawyer tasks on the verification reach `SUBMITTED`.

---

## 2. Actors & Role Architecture

### 2.1 Actor Types

| Actor | Description | Created via |
|---|---|---|
| **Customer** | Submits and pays for verifications | Self-signup |
| **Agent** | Independent contributor — Field / Surveyor / Registry / Lawyer | Self-signup + KYC + admin approval |
| **Admin** | Operates platform — Super / Operations / Finance | Admin invite only |

### 2.2 User Data Model (System-Level)

Two orthogonal role fields — **must not be conflated**:

| Field | Values | Mutability |
|---|---|---|
| `user_type` | `USER` / `ADMIN` | **Immutable** after creation |
| `user_persona` | list of `CUSTOMER`, `AGENT` | **Mutable**, additive only |

A user can hold both `CUSTOMER` and `AGENT` personas. `user_type` controls admin-portal access; `user_persona` controls portal routing.

### 2.3 Trust Status

A user becomes **trusted** after meaningful engagement:

| Persona | Trust trigger |
|---|---|
| Customer | First successful payment |
| Agent | First task submission |

### 2.4 Portal Routing

| Role combination | Default portal | Notes |
|---|---|---|
| Admin only | `/admin` | |
| Agent + Customer | `/agent` | Toggle to `/portal` available in header |
| Admin + Agent + Customer | `/admin` | Highest privilege wins |
| Customer only | `/portal` | |

---

## 3. Legal & Liability Framework

**Why first:** Veriprops operates in real-estate + legal interpretation. Every product decision must be defensible. This framework predates every feature.

### 3.1 Liability Boundaries

| We ARE liable for | We are NOT liable for |
|---|---|
| Process integrity (right agents, correct steps per tier) | Property authenticity guarantee |
| Accurate presentation of agent findings | Future changes, undisclosed disputes, hidden claims |
| Platform security & data handling | Independent agent professional judgement |
| Payment handling — refund when undelivered | User's purchase decision outcomes |
| | Third-party data accuracy (registry errors) |

### 3.2 Versioned Consent (Required Across Platform)

Every legal document is versioned. Every user acceptance is recorded against the exact version shown, with timestamp, IP, and device fingerprint.

| Consent Type | Collected At |
|---|---|
| `PLATFORM_TERMS` + `PRIVACY_POLICY` | Signup |
| `AGENT_TERMS` | Agent application submission |
| `VERIFICATION_TERMS` | Before each payment |
| `REPORT_DISCLAIMER` | First report view |

Version bumps force re-acceptance on next relevant action (modal cannot be dismissed — accept or decline).

### 3.3 Refund & Liability Model

| Scenario | Fault | Action |
|---|---|---|
| Cancel before `IN_PROGRESS` | Customer | Partial refund minus surcharge |
| Cancel after `IN_PROGRESS` | Customer | No refund |
| Wrong agent assigned / step skipped | Veriprops | Full refund + free re-verification |
| Registry error / missing records | External | No refund; transparent reporting |
| Property inaccessible | External | Partial refund (field component only) |
| Fraudulent customer submission | Customer | No refund |
| Payment confirmed but verification never activated | Veriprops | Full refund |

### 3.4 Communication Boundaries

- ❌ No direct Customer ↔ Agent chat
- ✅ Customer ↔ Admin (per-verification thread)
- ✅ Admin ↔ Agent (per-task thread)
- ⚠️ Agent first name + role visible to customer; contact details never
- 🚨 All messages scanned for phone/email/payment leakage before delivery
- ✅ All communication recorded and auditable

### 3.5 Report Footer (every page, every PDF)

> _This report represents a professional opinion, not a legal guarantee. Findings are based on information available at the time of verification. Veriprops — Jurisdiction: Nigeria. "We reduce uncertainty. We do not eliminate it."_

---

## 4. Cross-Cutting Concerns

These apply to **every phase** below. Implement scaffolds in Phase 0.

| Concern | Spec |
|---|---|
| **Determinism** | Verification + task state machines fully defined (see §5). No undefined transitions. |
| **Forward-only** | Global state moves forward only. Only permitted backward move: `REJECTED → IN_PROGRESS` (task level). |
| **Derived state** | Global verification state is *derived* from task states, not set by human click. |
| **Audit** | Every transition logged: entity, actor, actor role, from→to, timestamp, IP, note. Retained indefinitely. |
| **Accessibility** | Full keyboard navigation, tab order, ARIA roles. |
| **Mobile-first** | Diaspora uses mobile heavily — design mobile first. |
| **Offline** | Agent forms auto-save locally; upload retry on reconnect; sync indicator mandatory. |
| **Embedded education** | Tooltips on technical terms everywhere (C of O, encumbrance, trust score, UNDER_REVIEW). |
| **Language** | Plain English; specific not vague ("5–7 business days", not "a few days"). |
| **Agent identity** | API enforces: customer-facing endpoints return only `role`, `first_name`, `avatar_url`, `verified`. |
| **Message fraud scan** | Phone numbers, emails, URLs, banking details, "go outside the platform" phrases — held for admin review. |

---

# Part II — Implementation Phases

Phases are sequenced. Each phase assumes the previous is live. Phases 0–10 constitute the **MVP cut line**. Phases 11–19 harden and scale. Post-MVP items are strategic adjacencies.

---

## Phase 0 — Platform Foundation

**Goal:** Stand up the scaffolding that every feature depends on. No user-visible product yet.

### 0.1 Deliverables

- **Monorepo layout** — `backend/` (FastAPI + Alembic + SQLAlchemy + Kink DI) and `web/` (Next.js 16 App Router + Tailwind + Zustand + React Query).
- **Base entity** — `BaseEntity` with `id` (UUID), `created_at`, `updated_at`, `version` (optimistic locking), `deleted` (soft delete).
- **Generic repository pattern** — `GenericRepo[Model, Create, Update, Query, Search]` with pagination, soft-delete-aware queries.
- **Transaction management** — `@transactional` decorator with three session policies (`USE_IF_PRESENT`, `ALWAYS_NEW`, `FALLBACK_NEW`).
- **Exception hierarchy** — `AppodusBaseException` with structured context, HTTP mapping.
- **Middleware** — per-request DB session, request logging, CORS.
- **Dependency injection** — Kink bootstrap in `config/bootstrap.py`.
- **Configuration & env** — `.env.{local,dev,staging,prod}` loading via `appodus_active_env`.
- **Integration shells** — stubs and credentials for AWS S3, Paystack/Flutterwave, SendGrid/Mailjet, Twilio/Termii, Firebase, Google Drive, Zoho DocSign.
- **Audit logging primitive** — `AuditLog` entity + writer hook on every state transition.
- **State-machine primitive** — reusable state-machine validator to enforce transition tables (used by Verification, Task, Report).
- **Consent store** — versioned `ConsentDocument` + `UserConsent` records.
- **Frontend design system** — Radix primitives + Tailwind tokens; form/field/input/toast/modal/wizard components.
- **Auth wiring** — JWT (httpOnly cookie, 15-min access / 30-day refresh), silent refresh, middleware guards.

### 0.2 State Machines (Authoritative)

#### Verification (Global)

| State | Meaning | Notes |
|---|---|---|
| `DRAFT` | Wizard started. VID assigned. | |
| `SUBMITTED` | Wizard complete. Awaiting payment. | |
| `PAYMENT_PENDING` | Payment initiated. | |
| `PAID` | Payment confirmed. Awaiting agent assignment. | |
| `IN_PROGRESS` | ≥1 task is `ASSIGNED`/`ACCEPTED`/`IN_PROGRESS`. | |
| `UNDER_REVIEW` | All tasks `SUBMITTED`. Admin reviewing. | |
| `COMPLETED` | Report released. | Not terminal — can go to `DISPUTED` within window. |
| `DISPUTED` | Customer filed formal dispute. | |
| `CANCELLED` | Cancelled. Refund rules applied. | Terminal |
| `REFUNDED` | Dispute upheld. | Terminal |
| `FAILED` | Critical failure. | Terminal |

#### Task (per Role)

`PENDING → ASSIGNED → ACCEPTED → IN_PROGRESS → SUBMITTED → APPROVED`
With detours: `ASSIGNED → PENDING` (decline/timeout) · `SUBMITTED → REJECTED → IN_PROGRESS` (rework).

Only **Admin** approves/rejects; only **Agent** accepts/declines/submits.

### 0.3 Derived Global State Rules (in order)

1. Payment not confirmed → `PAYMENT_PENDING`
2. Payment confirmed, no tasks assigned → `PAID`
3. ≥1 task `ASSIGNED`/`ACCEPTED`/`IN_PROGRESS` → `IN_PROGRESS`
4. All tasks `SUBMITTED` or `APPROVED`, ≥1 still `SUBMITTED` → `UNDER_REVIEW`
5. All tasks `APPROVED` → `COMPLETED` (system triggers, admin releases)
6. Any task → `REJECTED` from `UNDER_REVIEW` → `IN_PROGRESS`
7. Admin declares failure → `FAILED`
8. Customer disputes → `DISPUTED`

### 0.4 Exit Criteria

- All three state machines enforceable at the ORM/service layer.
- Audit log writes on every transition.
- `alembic upgrade head` runs clean on all environments.
- CI green; Swagger docs reachable at `/docs`.

---

## Phase 1 — Marketing Site & Home Page

**Depends on:** Phase 0.

**Goal:** Public-facing landing page that acquires and converts diaspora visitors into paying customers. This is the top-of-funnel — it must feel authoritative, trustworthy, and premium.

**Design system:** See `references/estate_assurance/DESIGN.md` — "The Sovereign Curator" aesthetic. Typography: Manrope (display/headlines) + Inter (body). Color: Midnight Navy (`#000d22`), Veridian (`#3f6653`), Gold Leaf (`#735c00`). No 1px border lines — use tonal background shifts.

### 1.1 Page Sections (in order)

| Section | Purpose | Key CTA |
|---|---|---|
| **Navigation** | Brand + links + CTAs | "Verify a Property" (gradient) + "Log in" |
| **Hero** | Big emotional promise, trust score teaser | "Start Verification" + "View Sample Report" |
| **Verification Ecosystem** | 3-feature bento: Trust Score · Verification ID · Certified Report | — |
| **Rigorous Methodology** | 5-step process stepper | — |
| **Verified Agents** | 4 agent types with role descriptions | "Become an Agent" |
| **Pricing** | Basic / Standard / Premium tier cards with currency toggle | Per-tier CTA |
| **Testimonials** | 3 diaspora customer stories | — |
| **Call to Action** | Emotional close — legacy/family wealth angle | "Secure My Property Now" |
| **Footer** | Brand statement · Socials · Resources · Company · Newsletter | — |

### 1.2 Navigation

- Sticky, glassmorphism backdrop blur on scroll
- Logo: "Veriprops" (Manrope, bold)
- Desktop links: How It Works · Pricing · Agents · Resources
- CTA buttons: "Log in" (ghost) + "Verify a Property" (signature gradient)
- Mobile: hamburger → full-screen overlay menu
- Auth intent preserved: clicking "Verify a Property" when unauthenticated → auth gate with `intent=verify`

### 1.3 Hero Section

- Left column: verified-badge pill → headline (6xl, Manrope, `-0.02em` tracking) → subheadline → two CTA buttons
- Right column: abstract property visual (CSS/SVG composition — no stock photography dependency) + floating Trust Score card (glassmorphism: `bg-white/90 backdrop-blur-xl`, circular score ring, score bar)
- Mobile: stacked, headline first

### 1.4 Verification Ecosystem (Features)

- Header: "The Verification Ecosystem" with 4px green accent underline
- 3 cards on white bg: Trust Score (`analytics` icon), Verification ID (`fingerprint` icon), Certified Report (`verified_user` icon)
- Cards: white background, hover shadow lift, no border lines

### 1.5 Rigorous Methodology (How It Works)

- Centered header: "A Rigorous Methodology"
- 5-step horizontal stepper with connecting line between steps
- Steps: 1 Submit Details → 2 Cross-Check Records → 3 Check Encumbrances → 4 Run Risk Analysis → 5 Get Certified Report
- Step 1 uses signature gradient, steps 2–4 surface-container, step 5 has Veridian border

### 1.6 Verified Agents

- 4 agent-type cards: Field Agent · Surveyor · Registry Agent · Lawyer
- Each card: icon, name, description, responsibilities list
- Section CTA: "Become an Agent" → `/auth?intent=agent`

### 1.7 Pricing

- 3 tier cards side-by-side: Basic (₦150k, 3–5 days) · Standard (₦350k, 5–7 days, "Most Popular") · Premium (₦750k, 7–10 days)
- Standard card is elevated/featured (scale up, shadow, green badge)
- Currency toggle pills: NGN · USD · GBP · EUR (conversion displayed live)
- Each card: price, SLA, feature list with `check_circle` / `add` icons
- Tier CTAs link to `/auth?intent=verify&tier={basic|standard|premium}`

### 1.8 Testimonials

- 3 cards from diaspora customers (UK, USA, Canada)
- Each: initials avatar, name, location, tier used, quote
- Quotes focus on money saved, trust built, diaspora distance solved

### 1.9 Call to Action Section

- Navy gradient background (`#000d22` → `#0a2342`)
- Headline: "Your legacy is too valuable to risk on hearsay."
- Body: diaspora wealth protection angle
- Primary CTA: "Verify a Property Now" (Veridian green button)
- Secondary CTA: "Become an Agent" (outline white)
- Trust stats: total verifications · success rate · agent count

### 1.10 Footer

- 4-column grid: Brand (logo + tagline + socials) · Resources · Company · Newsletter signup
- Brand: "The Sovereign Curator of Real Estate Verification." + social links
- Resources: Certification Standards · Verification Process · Trust Score Guide · Sample Report
- Company: Privacy Policy · Terms of Service · Contact Support · Become an Agent
- Newsletter: email input + arrow CTA
- Legal: "© 2025 Veriprops. We reduce uncertainty. We do not eliminate it."

### 1.11 SEO & Meta

- `<title>` and `<description>` already configured in root layout
- `noindex` NOT applied — all public pages are crawlable
- VID lookup pages (`/verify/[id]` — Phase 13): `noindex` unless `COMPLETED` + sharing=public

### 1.12 Exit Criteria

- All 9 sections render on desktop (1440px) and mobile (375px) without layout breaks
- "Verify a Property" CTA navigates to `/auth?intent=verify`
- "Become an Agent" CTA navigates to `/auth?intent=agent`
- Pricing currency toggle cycles NGN → USD → GBP → EUR
- All copy matches brand voice: authoritative, diaspora-specific, no generic fintech language
- Tailwind v4 `@theme inline` brand tokens resolve correctly
- Unit tests pass for all content/data modules

---

## Phase 2 — Auth & Onboarding Shell

**Depends on:** Phase 0.
**Detailed spec:** `user-auth-onboarding_prd.md` §§1–5, 8–14.

**Goal:** A user can sign up, log in, verify email & phone, and land on the right portal.

### 2.1 Features

- **Signup (email/password)** with expanded fields: first/last name, email (OTP), phone (OTP, country flag), country of residence, timezone (auto-suggested from country), preferred currency. Server enforces a recently-verified OTP marker (30-min TTL) for both email and phone before completing signup; markers are single-use and consumed on success.
- **Login (email/password)** with "forgot password" and "create account" links. Rate limiting: warning at 5 (`LOGIN_FAILURE_WARNING` event surfaced in Security Activity Log), lockout at 7 (15 min).
- **OAuth (Google, Apple, Facebook)** — popup-based flow with `postMessage` bridge and HttpOnly JWT cookie session (see §2.2 OAuth Specification).
- **OTP flow** — 6 digits, auto-advance, paste support, 10-min timer (MM:SS), resend after expiry, max 3 resends then 30-min lockout. UI surfaces remaining resends.
- **Forgot / reset password** — tokenised email link (1 hr, single-use). On reset: all sessions invalidated. Email copy must state the correct validity ("1 hour").
- **Set password** (OAuth-only users can add password login later).
- **Failed attempt tracking** — all failed logins & OTPs logged with timestamp, IP, device fingerprint; visible in Security Activity Log; fed into fraud detection.
- **Connected devices** — list active sessions (device, browser, location, last active); revoke individual; "log out all".
- **Linked OAuth accounts** — list / link / unlink with password-existence guard. Linking from an authenticated session uses the OAuth popup with `mode=link`; unlinking is rejected if the user has no password set.
- **Resume partial signup** — server-side draft (`signup_drafts` table) keyed on normalised email, 7-day TTL, soft-deleted on successful signup. Frontend wizard syncs every step and prefers the server copy on resume; `localStorage` mirror provides offline-friendly resume on the same device.
- **Versioned consent on signup** — Platform Terms + Privacy Policy checkboxes with explicit version in label; consent record captures user_id, document_type, version, accepted_at, IP, device fingerprint.
- **Auth gate** — shared interstitial for "Verify a Property" / "Become an Agent" CTAs, preserves `intent` query param through auth.
- **Centralised route protection** — Next.js Proxy (`proxy.ts`) gates `/portal/*`, `/admin/*`, `/agent[s]/*`, `/account/*` on access-token cookie presence; redirects unauthenticated users to `/auth/login?redirect=<original>`; redirects authenticated users away from guest-only routes (`/auth`, `/auth/login`, `/auth/signup`). Proxy performs cookie-presence checks only — actual session validity is enforced server-side on every API call.
- **Post-auth redirect logic** — by role priority (Admin → Agent → Customer), preserving any pending `intent`. Computed client-side from the persona list returned by `GET /users/auth/sessions/current`.
- **Customer persona default** — signup via "Verify a Property" auto-adds `CUSTOMER` persona; landing at Customer portal dashboard (or resumable verification draft if present).

### 2.2 OAuth Specification — Popup + HttpOnly Cookie

**Authoritative for the OAuth implementation. Supersedes the OAuth bullet in §2.1.**

#### 2.2.1 Flow

1. Frontend fetches `GET /api/users/auth/oauth/{provider}/start?intent=<intent>&mode=auth|link` and receives `{authorizationUrl}`.
2. Frontend opens a synchronous, click-triggered, centred popup (`window.open` invoked from the click handler before the fetch resolves, then navigated once the URL is available).
3. User completes provider consent in the popup.
4. Provider redirects (or `form_post`s, for Apple) the popup to `GET|POST {BACKEND_PUBLIC_ORIGIN}/api/users/auth/oauth/{provider}/callback`.
5. Backend validates state + PKCE, exchanges the authorization code, fetches the user profile, and:
   - **AUTH mode, existing identity** → log in.
   - **AUTH mode, new email** → auto-create user (CUSTOMER persona unless `intent=agent`); first-time profile completion modal collects phone + country + timezone + currency.
   - **AUTH mode, email collision (existing password account, provider not linked)** → REJECT with the exact message: *"Account exists. Please log in and link this provider explicitly."* No session is issued.
   - **LINK mode** → attach the provider identity to the user_id captured at `/start` (JWT-required).
6. Backend issues the JWT session as an **HttpOnly, Secure, SameSite-appropriate** cookie on the same response.
7. Backend returns a minimal HTML page that calls `window.opener.postMessage({type:"oauth_result", success, message?}, validatedTargetOrigin)` and self-closes. A visible fallback ("If this window did not close automatically…") is shown for browsers that block `window.close()`.

#### 2.2.2 `postMessage` Contract

- Success: `{ type: "oauth_result", success: true }`
- Failure: `{ type: "oauth_result", success: false, message: <string> }`
- The popup parent MUST validate `event.origin === window.location.origin` AND `event.data.type === "oauth_result"` before acting; all other messages are silently dropped.

#### 2.2.3 Security Requirements

- **Signed state** parameter (CSRF protection); single-use; deleted from Redis on first read.
- **PKCE** (S256) required for all providers.
- **Strict redirect URI validation** — registered with each provider as `${BACKEND_PUBLIC_ORIGIN}/api/users/auth/oauth/{provider}/callback`. Frontend never receives or constructs it.
- **`postMessage` targetOrigin** — selected at `/start` from a settings allowlist (`OAUTH_FRONTEND_ORIGINS`) by matching the request `Referer`/`Origin`. Never `*`.
- **Replay protection** — short-lived state TTL; one-time use enforced by Redis delete-on-read.
- **Apple specifics** — `response_mode=form_post`; `scope=name email`; `id_token` validated against Apple's published JWKS (RS256, `iss=https://appleid.apple.com`, `aud=client_id`).
- **Facebook specifics** — `email` scope required; reject if the provider does not return an email.
- **Email-ownership guard** — an OAuth flow never silently merges into an existing password account.
- **Cookie flags** — HttpOnly, Secure, SameSite appropriate for popup-cross-site origin handling. Frontend never reads or stores tokens.

#### 2.2.4 Frontend UX Rules

- **Popup blocked** → show inline fallback: *"Popups are blocked. [Continue here →]"* — clicking does a full-page redirect to the same `authorizationUrl`. The fallback landing (`/auth/oauth/{provider}/callback`) refreshes the session via `currentSession()` and routes by role priority.
- **Popup closed before completion** → silent cancellation; no toast, no error log.
- **Timeout** (default 5 min) → show retryable error toast.
- **Provider error** → toast with the message from the failure popup; default copy: *"Login failed. Please try another method."*
- **No blocking confirmations** during the OAuth flow.
- **No duplicate account creation** and **no silent linking** of existing accounts.
- On success, frontend refreshes authenticated user state and redirects to the originally requested protected route (or the role-priority default).

#### 2.2.5 Required Settings

- Backend: `BACKEND_PUBLIC_ORIGIN`, `OAUTH_FRONTEND_ORIGINS` (comma-separated allowlist), per-provider client credentials.
- Frontend: per-provider enable flag (`NEXT_PUBLIC_OAUTH_{GOOGLE|APPLE|FACEBOOK}_DISABLED`) so a provider can be hidden in production without a code change while developer-console approval is pending.

### 2.3 Deferred to later phases

- Agent KYC wizard → Phase 3
- Admin invites → Phase 4
- Trust-status elevation → Phase 5 (customer first-payment) / Phase 7 (agent first-submission)

### 2.4 Exit Criteria

- All auth flows work end-to-end on mobile + desktop.
- Security Activity Log renders correctly, including `LOGIN_FAILURE_WARNING` events.
- No password, token, or PII leak in logs or responses.
- `intent`-preserving redirects verified with Cypress/E2E tests.
- OAuth E2E covers: first-time signup with profile completion, returning user direct login, email collision rejected without session, popup-blocked fallback redirect, popup-closed cancellation, link-from-account-settings happy path, unlink password guard.

---

## Phase 3 — Agent Onboarding & KYC

**Depends on:** Phase 2.
**Detailed spec:** `user-auth-onboarding_prd.md` §6.

**Goal:** An agent can apply, complete KYC, and sit in `PENDING` status awaiting admin approval.

### 3.1 Agent Application Wizard (4 steps)

1. **Type selection** — Field / Surveyor / Registry / Lawyer (multi-select).
2. **KYC** — BVN (with live verification) **or** ID upload (NIN / Passport / Driver's Licence / Voter's Card). Selfie match against BVN photo or ID photo.
3. **Professional credentials** — conditional on type: Surveyor licence, NBA licence for Lawyer. Optional: years of experience, coverage areas (state + LGA multi-select), 300-char bio.
4. **Review & submit** — mandatory truthfulness checkbox + Agent Terms acceptance (versioned).

Application enters `PENDING` → agent sees **Approval Status Dashboard** (Pending / Approved / Rejected with reason).

### 3.2 Exit Criteria

- Can submit application with any valid combination of agent types.
- Resumable: closing tab mid-wizard returns user to the same step on re-entry.
- KYC documents stored encrypted in S3 with per-user access control.

---

## Phase 4 — Admin Onboarding & Role Management

**Depends on:** Phase 2.
**Detailed spec:** `user-auth-onboarding_prd.md` §7, §2.3.

**Goal:** Existing admins can invite new admins; RBAC enforced platform-wide.

### 4.1 Features

- **Admin invite** — Super Admin sends invite with sub-role (Super / Operations Manager / Finance Admin).
- **Invite email** — tokenised link, 72-hour validity.
- **Invite acceptance** — three scenarios: new user → signup flow pre-filled from invite; existing user → login to merge admin role onto existing account; already admin → friendly message.
- **RBAC** — permissions matrix: who can invite admins, approve agent applications, assign agents, approve payouts, configure pricing, resolve disputes, release reports.
- **Admin team management** — list, deactivate, change sub-role.

### 4.2 Exit Criteria

- Seed script creates first Super Admin (manually, via alembic data migration or CLI).
- Permission checks verified on every admin endpoint.
- Role changes audit-logged.

---

## Phase 5 — Customer Submission & Payment

**Depends on:** Phases 0, 2.
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§4–9.

**Goal:** A logged-in customer can submit a property, pay, and enter `PAID` state.

### 5.1 Property Submission Wizard (`/portal/verifications/new`)

Generates a Verification ID (`VP-YYYY-XXXXXX`) at Step 1 load. Auto-saves draft per step.

- **Step 1A — Source** — Enter manually / Paste listing URL (backend parser for PropertyPro, Nigeria Property Centre; fallback to manual on failure).
- **Step 1B — Property type** — Land / Building.
- **Step 1C — Location** — Google Maps autocomplete restricted to Nigeria (lat/lng, state, LGA); landmark description field (_"nearest junction, landmark, or local description"_ — critical diaspora escape valve).
- **Step 1D — Details** — conditional on type (Land: size, use, survey plan status, current state; Building: type, floors, age, occupancy, C of O status).
- **Step 1E — Documents** — optional upload (Survey Plan, Title Document, Purchase Agreement, Other).
- **Step 1F — Seller info** — optional (name, phone, email, relationship).
- **Step 1 Summary** — collapsible review.

### 5.2 Pricing Transparency UI

- **Tier cards** — Basic / Standard / Premium with inline inclusions and SLA.
- **Comparison modal** — full matrix.
- **Line-item breakdown** — fetched from admin-configured pricing API (Phase 18 will build the admin UI for this).
- **Currency pills** — NGN / USD / GBP / EUR with live FX conversion (5-min cache, stale-warning at 30 min).
- **Recommendation banner** — if user indicated unknown C of O / survey, nudge to Standard or Premium.
- **First-time + referral discount** auto-applied (referral link parsing; in Phase 17 we build the referral issuance side).
- **Price lock** — on "Continue to Payment", lock price + FX rate on the verification record for 24 hours.

### 5.3 Legal Consent Step

Five versioned consent items, no pre-checked boxes:
1. Verification Disclaimer
2. Findings & Opinion Acknowledgement
3. Jurisdiction & Platform-Only Transactions
4. Communication Recording
5. Refund & Cancellation Policy

On acceptance: `consent_snapshot_id` stored on verification.

### 5.4 Payment Experience

- **Methods** — Card (Paystack/Flutterwave), Bank Transfer (NGN — virtual account per transaction, 24-hr expiry), International Wire (USD/GBP/EUR with SWIFT/IBAN + proof upload, admin-confirmed).
- **Payment status UI** — Initiated / Processing / Succeeded / Failed / Pending (for transfer/wire) with plain-language messaging (never raw gateway codes).
- **Retry flow** — preserve price lock; log every failure; after 3 consecutive failures show support with VID.
- **Receipt** — instant generation, emailed, contains VID + line items + FX rate.

### 5.5 Post-Payment Confirmation

`/portal/verifications/[id]/confirmed` — shows VID, estimated completion, SLA countdown, "Track my verification" CTA.

### 5.6 Exit Criteria

- Verification transitions `DRAFT → SUBMITTED → PAYMENT_PENDING → PAID` deterministically.
- Abandoned drafts preserved with all fields; resumable on next login.
- Customer upgraded to `trusted` on first successful payment.

---

## Phase 6 — Admin Verification Control Panel

**Depends on:** Phase 5 (must have `PAID` verifications to act on) + Phase 3 (must have approved agents to assign) + Phase 4 (admin RBAC).
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§23–24.

**Goal:** Admin can see all `PAID` verifications and assign agents — moving the verification to `IN_PROGRESS`.

### 6.1 Features

- **Verifications list** (`/admin/verifications`) — filterable by status, tier, SLA (on track / at risk / overdue), state/LGA, date.
- **Verification detail** — customer, property, assigned-agents grid per role, admin actions (Assign / Reassign / Pause / Resume / Cancel / Declare Failure / Set Delay / Add Note).
- **Agent assignment modal** — suggested agents ranked by proximity, load, performance; full search fallback.
- **Load balancing view** (`/admin/agents`) — capacity view, max active tasks per agent (admin-configured).
- **Admin notes** — pinned/tagged (Operational / Quality / Risk / Handover); searchable; included in audit export.
- **Agent approval queue** — review pending agent applications (Phase 3 output): approve / reject with reason.

### 6.2 Exit Criteria

- First agent assignment moves verification `PAID → IN_PROGRESS`.
- Lawyer tasks auto-lock until non-lawyer siblings reach `SUBMITTED`.
- Reassignments, pauses, cancellations all audit-logged with reason.

---

## Phase 7 — Agent Task Execution

**Depends on:** Phase 3 (approved agents), Phase 6 (tasks assignable).
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§19–22, 25–26.

**Goal:** An approved agent can discover, accept, execute, and submit a task.

### 7.1 Agent Dashboard (`/agent/dashboard`)

- Available jobs (geo-filtered by coverage, role-matched, first-come-first-served).
- My active tasks (with status chips).
- Completed tasks summary + earnings preview.

### 7.2 Accept / Decline Flow

- Accept → `ASSIGNED → ACCEPTED`, removed from shared pool, countdown starts.
- Decline → `ASSIGNED → PENDING`, back to pool, repeated declines flagged.
- **No-show timeout** (admin-configured, e.g. 4 hrs) — auto return to `PENDING`, admin alerted.

### 7.3 Role-Specific Submission UIs (`/agent/tasks/[id]/submit`)

Structured, role-specific forms — **never generic**:

- **Field Agent** — access confirmation, condition checklist, observations narrative, neighbourhood, ≥5 photos (GPS-stamped server-side), optional video, agent trust score input, declaration.
- **Surveyor** — survey confirmation, boundary assessment, coordinates (or georeferenced file), survey plan upload, trust score, declaration.
- **Registry Agent** — registry search details, title doc assessment (type, condition, authenticity), ownership chain, document uploads, trust score, declaration.
- **Lawyer** — documents reviewed checklist, title opinion, encumbrances list, fraud/risk flags, structured legal opinion statement (≥200 chars), recommendation, NBA licence confirmation, trust score. _Gated by dependency rule._

### 7.4 Draft & Offline Support

- Local autosave every field change.
- Explicit "Save Draft" hits backend.
- Offline: upload queue retries on reconnect; clear sync indicator.

### 7.5 Escalation

"Report Issue" on task page: inaccessible / suspicious / safety / conflicting info / other. Admin alerted; admin may pause verification. **Agents cannot unilaterally cancel or pause.**

### 7.6 Exit Criteria

- All four role-specific forms validated and submission moves task `IN_PROGRESS → SUBMITTED`.
- When all tasks are `SUBMITTED`, verification auto-derives to `UNDER_REVIEW`.
- Agent upgraded to `trusted` on first submission.

---

## Phase 8 — Admin Review & Report Release

**Depends on:** Phase 7 (tasks must be submittable).
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§25–26.

**Goal:** Admin reviews each task, approves or requests revision, and releases the final report to the customer.

### 8.1 Task Review Interface

- Full submission rendered read-only, evidence gallery, admin notes, approve / reject actions.
- **Reject** requires ≥30 char reason + revision instructions → task `SUBMITTED → REJECTED → IN_PROGRESS` on agent rework; global state reverts to `IN_PROGRESS` if it was `UNDER_REVIEW`.
- **Approve** → task `SUBMITTED → APPROVED`. When all tasks are `APPROVED`, system raises "Report ready for release" alert.

### 8.2 Conflict Detection

- Automated flags on configurable rules (occupancy mismatch, boundary divergence, authenticity conflicts).
- Admin resolves: reject one/both tasks, override with reconciliation note, or flag in customer report.

### 8.3 Report Release Gate (`/admin/verifications/[id]/report-review`)

- System computes composite trust score from agent scores (weights admin-defined).
- Admin reviews assembled draft; **"Release Report"** publishes to customer and moves global state → `COMPLETED`. "Request Changes" can re-open any task.

### 8.4 FAILED State

Admin can declare `FAILED` for confirmed fraud / permanent inaccessibility / fraudulent customer submission. Reason required, irreversible, refund policy applied.

### 8.5 Exit Criteria

- End-to-end demo: PAID → IN_PROGRESS → UNDER_REVIEW → COMPLETED achievable in staging.
- No report reaches customer without admin's explicit "Release Report" click.

---

## Phase 9 — Customer Tracking & Evidence Layer

**Depends on:** Phases 5–8 (need real verifications in real states).
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§10–11.

**Goal:** The trust-building engine. Customer sees live progress and the evidence agents upload.

### 9.1 Verification Tracking Dashboard (`/portal/verifications/[id]`)

- **Header** — VID, tier, status chip, address.
- **SLA tracker** — expected date, elapsed vs total, status label (On track / Running late / Delayed + admin reason).
- **Progress tracker** — tier-adaptive step list with icons + timestamps.
- **Assigned agents** — role + first name + verified badge (never last name, never contact).
- **Evidence preview** — latest 3 thumbnails + "View all".
- **Messages preview** — latest admin message + "Open".
- **Real-time updates** — WebSocket/SSE with 60-sec polling fallback.

### 9.2 State-Specific Expanded Views

- **PAID** — "Payment confirmed — agents being assigned", 24-hr ETA for assignment, banner + admin alert if SLA breached.
- **IN_PROGRESS** — progress %, stage breakdown with plain-English labels, "Awaiting other stages" for blocked Lawyer row.
- **UNDER_REVIEW** — 100% bar, "admin quality review in progress", explanatory copy that the delay is intentional.

### 9.3 Customer State Label Mapping

| Internal | Customer Sees |
|---|---|
| `PAID` | "Payment Confirmed — Agents Being Assigned" |
| `IN_PROGRESS` | "Verification In Progress" |
| `UNDER_REVIEW` | "Under Review" |
| `COMPLETED` | "Completed ✅" |
| `FAILED` | "Could Not Be Completed" |
| `REFUNDED` | "Refunded" |

### 9.4 Evidence Layer (`/portal/verifications/[id]/evidence`)

Chronological feed of agent uploads: photos, videos, documents, maps. Each item tagged by role (not name), with server-side timestamp & GPS. Full-screen viewer with EXIF/metadata panel. Evidence immutable after submission.

### 9.5 Exit Criteria

- Customer can watch status advance in real time on a running staging verification.
- First-name-only rule enforced at API layer (not just UI).
- Evidence tamper-evidence verified (server-side metadata trumps device EXIF).

---

## Phase 10 — Final Report Experience

**Depends on:** Phase 8.
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §12.

**Goal:** Deliver the product output — a defensible, shareable, downloadable report.

### 10.1 Features

- **Access gate modal** — one-time acknowledgement before first view (records against report version).
- **Header** — Verified badge, VID, report version, date, tier, address, actions (Download PDF / Share / Request Re-check).
- **Trust Score display** — numeric + band + meaning + "What does this mean?" tooltip.
- **Report sections** (collapsible, tier-dependent):
  - Executive Summary (plain language, risk badge, key flags, recommended action)
  - Physical Findings (Standard+)
  - Registry & Title Findings (all tiers)
  - Boundary & Survey Results (Standard+)
  - Legal Opinion (Premium — with section disclaimer)
  - Risk Summary
  - **Customer-Submitted Documents Appendix** — distinguishes what customer submitted vs what agents uploaded; shows which roles referenced each document.
- **Legal footer** on every page and PDF page.
- **Downloadable PDF** — server-side generation, branded cover, TOC, all sections, evidence thumbnails, legal footer per page, QR code to public lookup, re-downloadable anytime.
- **Report versioning** — v1.0 / v1.1 (minor admin-requested revision) / v2.0 (re-check) / v3.0 (tier upgrade). Old versions watermarked SUPERSEDED.

### 10.2 Exit Criteria

- First real `COMPLETED` report rendered end-to-end.
- PDF parity with HTML — both carry legal footer on every page.

---

## Phase 11 — Communication Layer

**Depends on:** Phase 8 (real verifications with assigned agents).
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §14.

**Goal:** Structured, admin-mediated communication — audit-logged, fraud-scanned, and never direct customer↔agent.

### 11.1 Channels

- **Customer ↔ Admin** (`/portal/verifications/[id]/messages`) — per-verification thread; system auto-posts status changes as system messages; attachments allowed.
- **Admin ↔ Agent** (`/agent/tasks/[id]/messages` and mirror admin view) — per-task; admin's rejection reason auto-posted as first message; admin can broadcast to all agents on a verification simultaneously.
- **General support** (`/portal/support`) — account/billing/general; can reference a VID.

### 11.2 Message Fraud Detection

Send-time scan for phone numbers, emails, URLs, banking details, "outside the platform" phrases. Flagged messages are held; admin reviews; repeated flags trigger account review.

### 11.3 Agent Identity Display

Enforced at API: customer-facing endpoints return only `role`, `first_name`, `avatar_url`, `verified`.

### 11.4 Exit Criteria

- No customer-facing endpoint returns agent last name, phone, or email.
- Flagged message held end-to-end verified in E2E test.

---

## Phase 12 — Notification System

**Depends on:** can start from Phase 2, but becomes critical at Phase 5+ — ship a basic version early and expand.

**Goal:** Keep every actor aware in real time.

### 12.1 Channels

- **In-app** — always on, cannot be disabled.
- **Email** — per-event opt-out.
- **SMS** — per-event opt-out; reserved for high-signal events.
- **Push** (Firebase / WebPush) — Phase 2 enhancement.

### 12.2 Customer Triggers

Payment confirmed · agents assigned · status change · new evidence · new admin message · SLA breach · report ready · new report version · refund initiated · re-check decision.

### 12.3 Agent Triggers

New job alert · job accepted/reassigned · admin revision request · payment update · verification feedback.

### 12.4 Admin Triggers

SLA breach alerts · report-ready alerts · conflict flags · agent no-show · fraud-flagged messages · dispute filed · wire proof uploaded.

### 12.5 Preferences

`/portal/account/notification-preferences` — toggle email/SMS per event type.

### 12.6 Exit Criteria

- All Phase 2–11 events wired to at least the in-app channel.
- Unit tests on notification fan-out (one event → multi-channel dispatch).

---

## Phase 13 — Public Verification Lookup & Sharing

**Depends on:** Phase 10.
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§12.8, 13a.

**Goal:** The shareable proof layer + growth surface.

### 13.1 Public Lookup (`/verify/[id]`)

Unauthenticated. Shows **summary only**: VID, ✅ Verified badge, trust band (not number), tier, report date, property type, state & LGA, version. Never: full address, agent names, owner names, documents, numeric score.

States: shared → summary; private → "not enabled"; in-progress → "still in progress"; disputed → "under dispute review"; not-found → error.

Includes "Start a verification →" CTA (growth). `noindex` unless status=`COMPLETED` AND sharing=public.

### 13.2 Report Sharing

| Mode | Who sees | Content |
|---|---|---|
| Private (default) | Customer only | Full report |
| Link-only | Anyone with link | Summary |
| Public | Anyone with VID | Summary |
| Named recipient | Specific email | Full report, time-limited, revocable |

30-day default expiry; revocable any time; recipients must acknowledge disclaimer first view.

### 13.3 Exit Criteria

- Public lookup renders for a real `COMPLETED` verification.
- Share-link revocation invalidates tokens immediately.

---

## Phase 14 — Revision, Re-verification & Disputes

**Depends on:** Phase 10.
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§13, 13b, 23.3.

**Goal:** Handle real-world imperfection — customers can ask for re-checks, upgrades, or raise disputes.

### 14.1 Re-check Request

Customer on completed report: free-text reason + optional docs. Admin approves → new cycle for scoped tasks; report version bumps to v2.0. Pricing admin-configured.

### 14.2 Tier Upgrade

Available on `COMPLETED` or `IN_PROGRESS`. Delta pricing only. New tasks created for added scope. SLA extended. Report version bumps to v3.0 with new sections.

### 14.3 Dispute Flow

- Available within configurable window (e.g. 30 days) after `COMPLETED`.
- Form: dispute type + ≥100-char description + optional evidence.
- On submit → `COMPLETED → DISPUTED`; admin reviews within 5 business days.
- Outcomes: reject (back to `COMPLETED`) / uphold full refund (`REFUNDED`) / uphold partial + free re-check (`IN_PROGRESS` new cycle).
- Admin resolution note is mandatory and delivered verbatim to customer.

### 14.4 Exit Criteria

- All three dispute outcomes produce correct state transitions and audit entries.
- Tier upgrade preserves existing approved tasks (idempotency on resubmit).

---

## Phase 15 — Agent Earnings & Commission

**Depends on:** Phases 7–8 (need approved tasks to pay for) + Phase 4 (Finance Admin role).
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §23.

**Goal:** Keep agents engaged through transparent, actionable earnings.

### 15.1 Features

- **Agent earnings dashboard** (`/agent/earnings`) — monthly / lifetime / available balance / pending; per-job breakdown with status (Paid / Pending / On Hold).
- **Commission matrix** — admin-configured per role × tier; visible to agent on job detail before accept.
- **Withdrawal flow** — stored bank account (or one-time entry), confirmation, 2-business-day SLA.
- **Finance admin payout panel** — approve / hold / adjust. Approvals audit-logged.

### 15.2 Exit Criteria

- Sample agent can request and receive a payout end-to-end in staging.
- Commission rules configurable without code change.

---

## Phase 16 — Agent Reputation & Coverage

**Depends on:** Phase 8 (admin approvals drive ratings).
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §§24–26.

**Goal:** Quality control + smart assignment via performance data.

### 16.1 Features

- **Performance metrics** — completion rate, accuracy score (1–5 stars admin-assigned), timeliness.
- **Agent profile** — own view: aggregated metrics, total jobs, active since, coverage.
- **Assignment ranking** — admin's suggested list ranks by composite score.
- **Threshold behaviours** — low performers get reduced job visibility; "Top Agent" badge for high performers (admin-visible only).
- **Coverage settings** (`/agent/settings/coverage`) — states + LGAs multi-select + max travel distance.
- **Availability status** — 🟢/🟡/🔴; auto-red when at max capacity.
- **Role-specific dashboards** — Field/Surveyor default to map+nearby; Registry to document-based list; Lawyer to "waiting for other agents" queue + legal opinion queue.

### 16.2 Exit Criteria

- Suggested agent list orders correctly for a test dataset.
- Lawyer dashboard visibly gates on dependency.

---

## Phase 17 — Growth & Conversion Mechanics

**Depends on:** Phases 5, 10.
**Detailed spec:** `veriprops_verification_lifecycle_prd.md` §16.

**Goal:** Compound customer acquisition and reduce abandonment.

### 17.1 Features

- **Referral system** — unique referral links per customer; invitee gets first-time discount; referrer gets credit (admin-configured).
- **First-time discount** — auto-applied, never a code, visible in pricing breakdown.
- **Abandoned verification recovery** — 24-hour banner + one email; draft preserved; price lock refreshed if > 24 hrs.

### 17.2 Exit Criteria

- Credit balance displays and applies correctly at checkout.
- Abandonment email fires exactly once per abandoned draft.

---

## Phase 18 — Admin Operations & Analytics

**Depends on:** Phases 5–16 (need data to analyse and levers to pull).

**Goal:** Give admins the strategic controls to run and evolve the business.

### 18.1 Mission Control

- Active verifications / pending assignments / stuck jobs / revenue / agent availability / SLA-at-risk counts.

### 18.2 Pricing & Tier Configuration

- Admin UI for tier creation, line-item pricing, service fee, upgrade-delta pricing, cancellation surcharge %, discount caps.

### 18.3 Financial Management

- Customer payments · agent payouts · commission breakdown · wire proof review queue.

### 18.4 Content & Trust Layer

- "How it works" content · FAQs · testimonials · verified-agent spotlight · Area Insights content per LGA.

### 18.5 Geographic View

- Map of active verifications · regional performance (Lagos vs Abuja vs others) — informs expansion.

### 18.6 Analytics Dashboard

- Signup → payment conversion · average verification time by tier · agent performance trends · revenue by location/tier · dispute rate.

### 18.7 System-wide Notification Control

- Broadcast to all agents / all customers; compose + preview + schedule.

### 18.8 Exit Criteria

- All pricing controls change downstream customer pricing without deploy.

---

## Phase 19 — Audit & Compliance Maturity

**Depends on:** All prior phases.

**Goal:** Harden the audit layer into a legal evidence system.

### 19.1 Features

- Full audit export per verification (PDF or CSV) — admin only.
- Customer-facing simplified activity log.
- Agent-facing task transition history.
- Versioned consent records downloadable per user.
- Fraud-flag review history.
- Admin action logs (permission changes, role changes, payout approvals).

### 19.2 Retention

Indefinite for audit logs and consent records; PII subject to data-retention policy.

### 19.3 Exit Criteria

- Admin can export a legally defensible pack for any VID: verification record + all state transitions + consent snapshots + message history + dispute record + refund record.

---

## Post-MVP Roadmap

Strategic adjacencies — plan, do not build pre-MVP.

| Initiative | Description |
|---|---|
| **Property Identity Layer** | Canonical property entity distinct from verification; a property can have multiple verifications over time. Foundation for market-wide price & history. |
| **Escrow / Transaction Layer** | Facilitate the actual purchase transaction post-verification — holding funds, releasing on title transfer. |
| **Deep Trust & Anti-Fraud Mechanisms** | Cross-verification pattern detection, document hash registry, fraudulent seller database. |
| **Verification Academy / Content Hub** | Educational content surface — "How land scams work", "How to read a survey plan", embedded tooltips expanded into long-form courses. |
| **Auto-assignment AI** | Replace manual admin assignment with ranked auto-assignment subject to admin override. |
| **WhatsApp OTP delivery** | Supplement SMS for Nigerian mobile preference. |
| **Mobile apps (iOS/Android)** | Native parity for customers and field agents. |

---

# Part III — Supporting Artefacts

## 26. Success Metrics

Platform-level health measurements.

| Metric | Definition | Target |
|---|---|---|
| Avg completion time | `PAID` → `COMPLETED`, by tier | Basic ≤5d · Standard ≤7d · Premium ≤10d |
| % completed without task revision | No task ever hit `REJECTED` | > 80% |
| Median task acceptance time | `ASSIGNED` → `ACCEPTED` | < 2 hours |
| Agent no-show rate | Tasks timed out unaccepted | < 5% |
| SLA breach rate | Exceeded tier SLA | < 10% |
| Customer trust rating | Post-report satisfaction (1–5) | ≥ 4.5 |
| Admin report release time | All tasks `APPROVED` → released | < 4 hours |
| Signup → payment conversion | First-verification activation | Target TBD |
| Abandoned-draft recovery rate | Drafts paid within 7 days of abandonment | Target TBD |

---

## 27. Open Questions Consolidated

Merged from both detailed PRDs. Resolve before or during the owning phase.

### Business

| # | Question | Phase |
|---|---|---|
| 1 | Cancellation surcharge percentage (allow admin to set it, defaults to 5%) | 5 |
| 2 | Exact pricing per tier + per line-item | 5 / 18 |
| 3 | Service fee percentage (allow admin to set it, defaults to 10%) | 5 |
| 4 | First-time discount percentage (allow admin to set it, defaults to 5%) | 17 |
| 5 | Referral credit + invitee discount amounts (allow admin to set it, defaults to 5%) | 17 |
| 6 | Max combined discount cap | 17 |
| 7 | Re-check pricing model (flat / per-agent / %) | 14 |
| 8 | Trust score weighting formula per role | 8 |
| 9 | Should trust score be visible to agents before submit? | 7 |
| 10 | Price lock validity window (24 hr suggested) | 5 |
| 11 | FX rate source (live API vs admin-set) | 5 |
| 12 | Dispute window length (30 days suggested) | 14 |

### Engineering

| # | Question | Phase |
|---|---|---|
| 13 | Payment gateway(s): Paystack (NGN), Flutterwave (multi) | 5 |
| 14 | SMS provider(s): Termii vs Twilio | 2 / 12 |
| 15 | BVN verification provider (Mono / Dojah / Okra) | 3 |
| 16 | Selfie matching technology (vendor vs in-house) | 3 |
| 17 | Listing sites supported by URL parser | 5 |
| 18 | OAuth providers Phase 2: Google confirmed; Apple / Facebook? | 2 |
| 19 | Country/timezone source dataset | 2 |
| 20 | Automated conflict detection rules (initial set) | 8 |
| 21 | Wire proof: manual review vs auto-match by reference | 5 |
| 22 | WebSocket vs SSE for live dashboard | 9 |

### Operations / Legal

| # | Question | Phase |
|---|---|---|
| 23 | Admin SLA for agent application review (2–5 days stated) | 3 |
| 24 | Agent no-show timeout window (4 hrs suggested) | 7 |
| 25 | Max active task capacity per agent (5 suggested) | 16 |
| 26 | Nigerian public holidays excluded from SLA | 0 / 5 |
| 27 | Manual vs automated KYC doc review | 3 |
| 28 | Verification Disclaimer final copy | Legal sign-off — precedes Phase 5 |
| 29 | Who publishes consent doc versions / triggers re-consent prompts | 0 / 2 |
| 30 | Trust-status visibility to other users | 16 |
| 31 | Area Insights content source + maintainer | 10 / 18 |
| 32 | Admin-configurable trust score weights: initial values + owner | 8 |
| 33 | Admin report release SLA (<4 hrs suggested) | 8 |
| 34 | Share link default expiry (30 days) — customer-configurable? | 13 |
| 35 | What OAuth profile data is stored (NDPR compliance) | 2 |

---

*Master PRD prepared from `BRAIN PICK PRDS/README.md` (product brief), `user-auth-onboarding_prd.md` v1.1, and `veriprops_verification_lifecycle_prd.md` v2.0.*
*Implementation order is advisory — phases 0–10 constitute the MVP cut line.*
*Last updated: 2026-04-25.*
