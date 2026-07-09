# Veriprops — Master Product Requirements Document

**Product:** Veriprops ("Verified Properties")
**Audience:** Nigerians in the diaspora (primary) and Nigerians in Nigeria, verifying real estate within Nigeria
**Stack:** FastAPI (Python, PostgreSQL, Alembic, SQLAlchemy, Kink DI) backend · Next.js 16 (App Router, React 19, Tailwind, Zustand, React Query) frontend
**Currencies:** NGN (contractual base), USD, EUR, GBP
**Version:** 2.4 — consolidated master (legal & liability hardening pass)
**Status:** Draft — sequenced for implementation
**Last updated:** 29 June 2026

> **Consolidates:** product brief (`README.md`), Auth & Onboarding PRD v1.1, Verification Lifecycle PRD v2.0, User-Area Top Navigation PRD v1.0, and the customer/agent/admin menu specifications. Where sources conflicted, the newest document wins (top-nav and menus supersede earlier entry-point and configuration descriptions); the state machines in §2 are authoritative over all prose.
>
> **v2.1** added the hardening set; **v2.2** simplified where it over-reached (see prior changelogs in version history). **v2.3** closes design loopholes and lifts the experience: non-sequential VIDs + lookup safety (§4.10); audit pseudonymisation on erasure (§4.11); create-side idempotency (§4.6); inaccessibility-evidence requirement (§3.5, §7.3a); job-pool starvation backstop + accept-time cap (§7.2); commission chargeback-window reserve (§15.2); referral anti-farming (§17.1); hard admin-staffing gate + graceful SLA shedding (§6.4); FX disclosure as a concrete range, NGN-prominent (§4.4, §5.2, §5.4); lighter onboarding with phone-OTP deferred to payment (§2.1, §5.4); chat fast-lane for unflagged messages (§4.7, §11.2); supportive report verdict (§10.1); interim interpreted reassurance (§9.3); cross-portal badge (§3.4); earnings hero-number UX (§15.1); low-bandwidth weight budgets (§5, §9.4).
>
> **v2.4** closes the legal & liability gaps in §3.5: explicit **limitation-of-liability cap** at 1× fees paid with fraud / willful-misconduct / non-waivable carve-outs; **agent liability** structure (independent contractor + AGENT_TERMS indemnity now, PI-insurance posture deferred to §B, lawyer-role cover gated to the Premium tier); **governing law + forum** (Nigeria courts, with cross-border enforceability flagged unconfirmed per-market); **Premium Legal Opinion ownership** (individual lawyer owns/signs, Veriprops transmits, NBA counsel gate before Phase 10). Plus two consistency fixes: dynamic copyright year (§6.2) and removal of the device-fingerprint reference from the chargeback rebuttal pack (§15), aligning it with §3.5. New §B open items 14–17 track the sign-offs these clauses require.

---

## How to read this document

This PRD uses a **phased implementation spine** (Phases 0–19) as its primary structure, because phases encode build order and dependencies — the thing a team executes against. Readers who care about a single actor or module can use the **Module Cross-Reference Index** (§0.2) to jump to the phases that touch their area.

Three companion artefacts sit alongside the phases and apply across all of them:

- **§2 — State Machines (Authoritative).** The verification, task, and report machines. All prose defers to these.
- **§4 — Architecture Decisions.** Cross-cutting structural choices (state derivation, money, property model, real-time transport, event bus, evidence integrity, idempotency, message lifecycle).
- **§A — Resolved Decisions** and **§B — Open Items.** What is settled (and whether it still needs business sign-off) versus what genuinely remains open.

---

## Table of Contents

**Part I — Foundations**
- 0. [Orientation: Phase Map & Cross-Reference Index](#0-orientation)
- 1. [Vision & Strategy](#1-vision--strategy)
- 2. [State Machines (Authoritative)](#2-state-machines-authoritative)
- 3. [Actors, Roles & Legal Framework](#3-actors-roles--legal-framework)
- 4. [Architecture Decisions](#4-architecture-decisions)
- 5. [Cross-Cutting Concerns](#5-cross-cutting-concerns)

**Part II — Implementation Phases**
- [Phase 0 — Platform Foundation](#phase-0)
- [Phase 1 — Marketing Site & Home Page](#phase-1)
- [Phase 2 — Auth & Onboarding Shell](#phase-2)
- [Phase 3 — Agent Onboarding & KYC](#phase-3)
- [Phase 4 — Admin Onboarding & Role Management](#phase-4)
- [Phase 5 — Customer Submission & Payment](#phase-5)
- [Phase 6 — Admin Verification Control Panel](#phase-6)
- [Phase 6a — Chargeback Handling](#phase-6a)
- [Phase 7 — Agent Task Execution](#phase-7)
- [Phase 8 — Admin Review & Report Release](#phase-8)
- [Phase 9 — Customer Tracking & Evidence Layer](#phase-9)
- [Phase 10 — Final Report Experience](#phase-10)
- [Phase 11 — Communication Layer](#phase-11)
- [Phase 12 — Notification System & Event Bus](#phase-12)
- [Phase 13 — Public Lookup & Sharing](#phase-13)
- [Phase 14 — Revision, Re-verification & Disputes](#phase-14)
- [Phase 15 — Agent Earnings & Commission](#phase-15)
- [Phase 16 — Agent Reputation & Coverage](#phase-16)
- [Phase 17 — Growth & Conversion](#phase-17)
- [Phase 18 — Admin Operations & Analytics](#phase-18)
- [Phase 19 — Audit & Compliance Maturity](#phase-19)
- [Post-MVP Roadmap](#post-mvp)

**Part III — Navigation, Menus & Supporting Artefacts**
- [N. User-Area Top Navigation](#n-top-navigation)
- [M. Portal / Agent / Admin Menu Maps](#m-menu-maps)
- [§A. Resolved Decisions](#a-resolved-decisions)
- [§B. Open Items](#b-open-items)
- [§C. Success Metrics](#c-success-metrics)
- [§D. Hardening Backlog](#d-hardening-backlog)

---

<a id="0-orientation"></a>
# Part I — Foundations

## 0. Orientation: Phase Map & Cross-Reference Index

### 0.1 The MVP cut line

Phases 0–10 constitute the **MVP**. Phases 11–19 harden and scale. Each phase assumes the previous phases are live unless its **Depends on** line says otherwise.

| Phase | Title | MVP |
|---|---|---|
| 0 | Platform Foundation | ✅ |
| 1 | Marketing Site & Home Page | ✅ |
| 2 | Auth & Onboarding Shell | ✅ |
| 3 | Agent Onboarding & KYC | ✅ |
| 4 | Admin Onboarding & Role Management | ✅ |
| 5 | Customer Submission & Payment | ✅ |
| 6 | Admin Verification Control Panel | ✅ |
| 6a | Chargeback Handling | ✅ |
| 7 | Agent Task Execution | ✅ |
| 8 | Admin Review & Report Release | ✅ |
| 9 | Customer Tracking & Evidence Layer | ✅ |
| 10 | Final Report Experience | ✅ |
| 11 | Communication Layer | — |
| 12 | Notification System & Event Bus | — |
| 13 | Public Lookup & Sharing | — |
| 14 | Revision, Re-verification & Disputes | — |
| 15 | Agent Earnings & Commission | — |
| 16 | Agent Reputation & Coverage | — |
| 17 | Growth & Conversion | — |
| 18 | Admin Operations & Analytics | — |
| 19 | Audit & Compliance Maturity | — |

### 0.2 Module Cross-Reference Index

| Module | Primary phases | Supporting |
|---|---|---|
| **Authentication & Onboarding** | 2, 3, 4 | 0 (auth wiring), 19 (consent records) |
| **Verification Lifecycle (customer)** | 5, 9, 10 | 13, 14, 17 |
| **Agent Lifecycle** | 7, 15, 16 | 3 (onboarding), 11 (admin↔agent) |
| **Admin Operations** | 6, 6a, 8, 18 | 4 (RBAC), 14 (disputes), 19 (audit) |
| **Communication & Notifications** | 11, 12 | N (top-nav entry points) |
| **Payments & Money** | 5, 6a, 15 | 4.4 (collection model), 18 (finance) |
| **Reports & Sharing** | 10, 13 | 14 (versioning on re-check) |
| **Top Navigation & Menus** | N, M | 11, 12 (counters) |
| **Trust, Reputation & Scoring** | 7, 8, 16 | 18 (weights config), D (hardening) |

### 0.3 Source reconciliation rules

1. **State machines (§2) are authoritative.** Any prose describing transitions defers to them.
2. **Newest document wins on conflicts.** The Top-Navigation PRD (23 Jun 2026) and the menu specs supersede earlier entry-point, notification, and configuration descriptions.
3. **OAuth is popup-only** (§Phase 2). The earlier redirect/token model is dropped; a full-page redirect remains only as the popup-blocked fallback.
4. **Collection is gateway-mediated** (§4.4). All collection runs through Paystack/Flutterwave behind the provider facade; NGN is contractual and NGN-settled by default; customers may pay in USD/GBP/EUR via international card (gateway-converted). No direct SWIFT/IBAN wire at MVP.
5. **KYC defers liveness and face-match to the provider** (Dojah default, behind a facade); BVN is primary, government-ID upload is the fallback.

---

## 1. Vision & Strategy

### 1.1 Mission

Make **"verified property"** the default belief in the Nigerian real-estate market. End state: *"If it's not verified, nobody buys it."*

### 1.2 Strategic pillars

| Pillar | Position |
|---|---|
| **Enemy** | Fraudsters, fake agents, forged documents, uncertainty |
| **Creed** | *"Verify everything. Trust nothing blindly."* |
| **Language** | Trust Score (0–100), Verification ID, Verified badge |
| **Playbook** | Educate → Build ecosystem → Standardize |
| **Emotion** | Protect wealth & family legacy |
| **Symbol** | ✅ Veriprops Verified |
| **Golden line** | *"We reduce uncertainty. We do not eliminate it."* |

### 1.3 Product primitives

- **Verification** — a single request against one property, scoped by **tier** (Basic / Standard / Premium).
- **Verification ID** — unique public-safe identifier (`VP-YYYY-XXXXXX`), shareable, the canonical anchor for all downstream artefacts.
- **Trust Score** — weighted composite (0–100) per report: 90+ Safe / 60–89 Caution / 0–59 High Risk.
- **Task** — a role-scoped unit of work (Registry / Field / Surveyor / Lawyer) belonging to a verification.
- **Report** — the versioned output (`v1.0`, `v2.0`, …) — a professional opinion, not a guarantee.
- **Property** — a first-class entity distinct from the verification (see §4.3); a property may be verified more than once over time.

### 1.4 Tier → Task matrix

| Tier | Registry | Field | Surveyor | Lawyer | Target SLA |
|---|---|---|---|---|---|
| Basic | ✅ | — | — | — | 3–5 business days |
| Standard | ✅ | ✅ | ✅ | — | 5–7 business days |
| Premium | ✅ | ✅ | ✅ | ✅ | 7–10 business days |

The Lawyer task is **dependent**: it unlocks only after all non-lawyer tasks on the verification reach `SUBMITTED`. Dependencies are modelled as data, not hard-coded logic (see §4.2).

---

## 2. State Machines (Authoritative)

These three machines are the single source of truth. All prose elsewhere defers to them. Global verification state is **derived** from task states by one owner function (§4.1) — never set by a human clicking a button.

### 2.1 Verification state machine (global)

| State | Meaning |
|---|---|
| `DRAFT` | Wizard started. Verification ID assigned. Not yet submitted. |
| `SUBMITTED` | Wizard complete. Awaiting payment initiation. |
| `PAYMENT_PENDING` | Payment initiated. Awaiting gateway confirmation. |
| `PAID` | Payment confirmed. Awaiting agent assignment. |
| `IN_PROGRESS` | ≥1 task assigned/accepted/in progress. Work underway. |
| `UNDER_REVIEW` | All tasks submitted. Admin reviewing. |
| `COMPLETED` | All tasks approved; report released. Not terminal. |
| `DISPUTED` | Customer filed a formal post-completion dispute. |
| `CANCELLED` | Cancelled. Refund rules applied. **Terminal.** |
| `REFUNDED` | Dispute upheld; refund issued. **Terminal.** |
| `FAILED` | Critical failure (fraud / permanent inaccessibility). **Terminal.** |

**Permitted transitions:**

```
DRAFT            → SUBMITTED, CANCELLED
SUBMITTED        → PAYMENT_PENDING, CANCELLED
PAYMENT_PENDING  → PAID, CANCELLED, FAILED
PAID             → IN_PROGRESS, CANCELLED, REFUNDED, FAILED
IN_PROGRESS      → UNDER_REVIEW, FAILED, CANCELLED
UNDER_REVIEW     → COMPLETED, IN_PROGRESS, FAILED
COMPLETED        → DISPUTED, IN_PROGRESS
DISPUTED         → COMPLETED, REFUNDED, IN_PROGRESS
Terminal         : CANCELLED, REFUNDED, FAILED
```

### 2.2 Task state machine (per role)

| State | Meaning |
|---|---|
| `PENDING` | Task exists for this role. No agent committed. |
| `ASSIGNED` | Admin assigned an agent (manual path). Awaiting accept. |
| `ACCEPTED` | Agent committed. Clock starts. |
| `IN_PROGRESS` | Agent actively working. |
| `SUBMITTED` | Findings submitted. Awaiting admin review. |
| `REJECTED` | Admin requested rework. |
| `APPROVED` | Admin approved the submission. |

**Permitted transitions:**

```
PENDING      → ASSIGNED, ACCEPTED
ASSIGNED     → ACCEPTED, PENDING
ACCEPTED     → IN_PROGRESS, PENDING
IN_PROGRESS  → SUBMITTED
SUBMITTED    → APPROVED, REJECTED
REJECTED     → IN_PROGRESS
APPROVED     → IN_PROGRESS
Terminal     : none
```

**Two paths into a task:**
- **Manual:** `PENDING → ASSIGNED → ACCEPTED` (admin picks an agent).
- **Auto-assignment** (`auto_assignment_enabled = true`): the task is broadcast to qualifying agents at `PAID`; the first to accept goes `PENDING → ACCEPTED`, skipping `ASSIGNED`. Broadcast is **first-accept-wins**; once one agent accepts, the task leaves the pool and others see "no longer available."

**Backward transitions (both admin-initiated, both intentional):**
- `REJECTED → IN_PROGRESS` — agent reworks after a revision request.
- `APPROVED → IN_PROGRESS` — admin **reopens** an already-approved task (release-gate "Request Changes", conflict resolution, tier upgrade rescope).

### 2.3 Report state machine

| State | Meaning |
|---|---|
| `DRAFT` | Report assembled from approved task data; not yet released. |
| `RELEASED` | Admin released the report to the customer. |
| `SUPERSEDED` | A newer report version has replaced this one. **Terminal.** |

```
DRAFT      → RELEASED
RELEASED   → SUPERSEDED
Terminal   : SUPERSEDED
```

> `RELEASED` corresponds exactly to the admin "Release Report" action. Versioning (`v1.0 → v1.1 → v2.0 → v3.0`) is a real state change: the prior version moves to `SUPERSEDED` and is shown watermarked.

### 2.4 Invariants

- **No skipped states.** Only the transitions listed above are valid; the derivation owner rejects anything else.
- **Forward-only at the global level, except admin-initiated revision loops:** `UNDER_REVIEW → IN_PROGRESS`, `COMPLETED → IN_PROGRESS`, `DISPUTED → IN_PROGRESS`.
- **Task-level backward transitions are admin-initiated only:** `REJECTED → IN_PROGRESS` and `APPROVED → IN_PROGRESS`.
- **Derived global state.** The verification's status is a projection of its task states plus payment state plus admin flags — written by exactly one function (§4.1). No endpoint sets `verification.status` directly.
- **`COMPLETED` requires ALL tasks `APPROVED`** — not merely `SUBMITTED`.
- **Terminal means terminal.** `CANCELLED`, `REFUNDED`, `FAILED`, and report `SUPERSEDED` admit no further transitions.
- **Every transition is logged** to `AuditLog` with actor, role, from→to, timestamp, IP, and optional note (§19).

### 2.5 Derived global-state rules (evaluated in order)

| # | Condition | Global state |
|---|---|---|
| 1 | Payment not confirmed | `PAYMENT_PENDING` |
| 2 | Payment confirmed, no tasks assigned | `PAID` |
| 3 | ≥1 task is `ASSIGNED` / `ACCEPTED` / `IN_PROGRESS` | `IN_PROGRESS` |
| 4 | ALL *instantiated* tasks `SUBMITTED` or `APPROVED`, ≥1 still `SUBMITTED` | `UNDER_REVIEW` |
| 5 | ALL required tasks `APPROVED` | `COMPLETED` (system stages; admin releases) |
| 6 | ANY task → `REJECTED` from an `UNDER_REVIEW` verification | `IN_PROGRESS` |
| 7 | Admin declares critical failure | `FAILED` |
| 8 | Customer files dispute post-completion | `DISPUTED` |
| 9 | Admin rejects dispute | `COMPLETED` |
| 10 | Admin upholds dispute | `REFUNDED` |

**Dependency-blocked tasks (lawyer-dependency fix).** A dependency-blocked task (e.g., Lawyer before its upstream siblings reach `SUBMITTED`) is **not instantiated as a `PENDING` row** until its dependency unlocks (§4.2). It therefore does not fall through rules 3–4. The progress formula (§2.6) and the "all required tasks" test in rule 5 count it from **tier configuration**, not from a `COUNT(tasks)` query — so a Premium verification with three submitted siblings and a not-yet-created Lawyer task correctly derives to `UNDER_REVIEW` only once the Lawyer task is created, unlocked, worked, and submitted. Implementations must read required-task counts from tier config, never from existing task rows.

### 2.6 Progress formula

```
Progress % = (Approved tasks ÷ Total required tasks for tier) × 100
```

Task counts are tier-specific (Basic 1, Standard 3, Premium 4). Displayed on the customer dashboard and admin panel. Example: Standard, 1 of 3 approved → 33%.

---

## 3. Actors, Roles & Legal Framework

### 3.1 Actor types

| Actor | Description | Created via |
|---|---|---|
| **Customer** | Submits and pays for verifications | Self-signup |
| **Agent** | Independent contributor — Field / Surveyor / Registry / Lawyer | Self-signup + KYC + admin approval |
| **Admin** | Operates the platform — Super / Operations / Finance | Admin invite only |

### 3.2 User data model — two orthogonal role fields

These must **not** be conflated.

| Field | Values | Mutability |
|---|---|---|
| `user_type` | `USER` / `ADMIN` | **Immutable** after creation. Controls admin-portal & system access. |
| `user_persona` | list of `CUSTOMER`, `AGENT` | **Mutable, additive only.** Controls portal routing. Default `[]`. |

A user may hold both `CUSTOMER` and `AGENT`. Self-signup users get `user_type = USER`; admin-invited users get `ADMIN`.

#### Agent sub-types

| Type | Responsibility |
|---|---|
| Field Agent | Physical site inspection |
| Surveyor | Boundary & location confirmation |
| Registry Agent | Registry search |
| Lawyer | Title verification, ownership, legal opinion, encumbrances & risk |

#### Admin sub-roles

| Sub-role | Capabilities |
|---|---|
| Super Admin | Full access; invite admins; configure all settings |
| Operations Manager | Assign agents, manage verifications, view reports |
| Finance Admin | Approve payouts, view payments, manage commissions |

### 3.3 Trust status

A user becomes **trusted** after meaningful engagement:

| Persona | Trust trigger |
|---|---|
| Customer | First successful payment |
| Agent | First task submission |

Trust status reduces friction on later flows, gates certain features, and feeds fraud-detection thresholds.

### 3.3a Credential expiry & re-verification

Agent credentials are time-bound and tracked, not captured once and forgotten.

- **Structured expiry dates** are stored for any credential that has one (Surveyor licence, NBA licence). Credentials without a natural expiry are re-attested on the periodic cadence below.
- **Auto-flagging:** the system flags credentials approaching expiry (admin-configurable lead time) and expired credentials.
- **Role-level suspension, not account-level:** on expiry of a role's required credential, **only that role** is suspended (the agent stops receiving and can no longer submit that role's tasks, and the "Verified Agent" badge is withdrawn for that role). Other roles the agent holds are unaffected. A disbarred lawyer keeps a clean Field-Agent role.
- **Periodic re-attestation:** identity (BVN/ID) is re-attested on a light, configurable cadence (default annual) to keep KYC current without churning good agents.
- A suspended role is restored when a valid renewed credential is uploaded and admin-approved.

### 3.4 Portal routing & switching

| Role combination | Default portal | Notes |
|---|---|---|
| Admin only | `/admin` | |
| Agent + Customer | `/agent` | Toggle to `/portal` in header (client-side, shared session) |
| Admin + Agent + Customer | `/admin` | Highest privilege wins |
| Customer only | `/portal` | |

Post-auth redirect: any pending `intent` wins; otherwise role priority **Admin → Agent → Customer**, computed client-side from the persona list returned by the current-session endpoint.

The portal-switch control shows a **count badge for unread/actionable items in the other portal** (§2.1), so a multi-role user does not miss items meant for their other hat. Feeds remain scoped per portal; the badge only signals across them.

### 3.5 Legal & liability framework

Veriprops operates in real estate + legal interpretation. Every product decision must be defensible. This framework predates every feature.

#### Liability boundaries

| We ARE liable for | We are NOT liable for |
|---|---|
| Process integrity (right agents, correct steps per tier) | Property authenticity guarantee |
| Accurate presentation of agent findings | Future changes, undisclosed disputes, hidden claims |
| Platform security & data handling | Independent agent professional judgement |
| Payment handling — refund when undelivered | The user's purchase decision and its outcomes |
| | Third-party data accuracy (registry errors) |

> **Payment processor, not merchant of record.** Paystack/Flutterwave are payment *processors*; Veriprops remains the legal seller of the verification service and is responsible for tax remittance, chargeback handling, and compliance. Collection is gateway-mediated (§4.4), but the merchant-of-record obligations sit with Veriprops.

#### Limitation of liability

The boundary table above defines *what* Veriprops is liable for; this clause caps *how much*. The refund matrix (below) is a business policy, not a contractual ceiling — without an explicit cap, the "opinion, not guarantee" disclaimer limits the *nature* of a claim but not the *quantum*. A diaspora buyer who relied on a clean report and lost a large sum to a fraud the process did not catch is not, absent this clause, bounded by the verification fee.

- **Aggregate cap: 1× fees paid.** Veriprops' total aggregate liability to a customer for any and all claims arising from a verification is capped at **the total fees that customer paid for that verification** (the contractual NGN figure, §4.4). This is the most conservative defensible position; a cap of zero invites a court to strike the clause as unconscionable, so the cap is set at fees-paid, not lower.
- **Carve-outs (cap does not apply).** The cap does **not** limit liability for fraud, willful misconduct, or anything a court will not permit to be capped (e.g. death or personal injury, or non-waivable statutory consumer rights). These are stated explicitly because courts read them in regardless; stating them improves the clause's survivability rather than weakening it.
- **Relationship to the disclaimer.** The disclaimer and the cap are complementary, not redundant: the disclaimer limits the *nature* of the claim ("opinion, not guarantee"), the cap limits the *amount*. Both depend on the versioned-consent record below to be enforceable.

> **Carried in:** `PLATFORM_TERMS` and `VERIFICATION_TERMS`. The exact cap language and carve-out list are on the §B legal sign-off list and **block Phase 5**.

#### Agent liability & professional indemnity

The boundary table disclaims liability for "independent agent professional judgement," but the customer's contract is with **Veriprops**, not the agent. If an agent is negligent and the agent is judgment-proof, "not our liability" is a weak shield. This clause closes the chain.

- **Independent-contractor status.** Agents (including the Premium lawyer role) act as **independent contractors**, not employees or agents-in-law of Veriprops. Stated in `AGENT_TERMS`.
- **Indemnity to Veriprops.** `AGENT_TERMS` carries an **indemnity running back to Veriprops** for losses caused by the agent's negligence, misconduct, or breach. Captured as a versioned attestation, the same machinery as the conflict-of-interest declaration (§7.3).
- **Professional-indemnity insurance — deferred to §B.** Whether agents must carry their own PI cover, or Veriprops carries platform-level cover, is a **costed business decision deferred to §B**. An indemnity against a judgment-proof individual provides contractual recourse but not necessarily recovery; real recovery requires insurance, which has cost and onboarding-friction tradeoffs.
- **Premium-lawyer carve-out (hard gate).** The lawyer role is the highest-negligence-risk surface (it renders opinions). The **Premium "Legal Opinion" tier must not go live until the insurance posture for the lawyer role specifically is resolved** (§B). A narrow PI mandate on that one role is realistic, since licensed lawyers are the agents most likely to already carry cover.

#### Governing law, forum & cross-border enforceability

The report footer asserts "Jurisdiction: Nigeria," but the terms themselves were previously silent on governing law and forum — the gap most specific to a diaspora model where the *entire* customer base is offshore (UK, US, Canada).

- **Governing law & forum.** The terms are governed by the **laws of Nigeria**, and the **courts of Nigeria** are the agreed forum for disputes (a forum-selection clause, carried in `PLATFORM_TERMS` / `VERIFICATION_TERMS`). Courts, not arbitration, are the MVP default — consumer arbitration is increasingly unenforceable in several target markets and can read as hostile to consumers; arbitration is left as a future reconsideration (§B) if claim volume concentrates enough to justify it.
- **Cross-border enforceability — flagged unconfirmed.** A Nigeria forum clause does **not** fully bind foreign consumers: UK / EU / Canadian buyers may retain **non-waivable home-jurisdiction rights** to sue locally regardless of this clause. Cross-border enforceability is therefore an **unresolved structural risk, confirmed per-market only as volume warrants** — not a formality the clause disposes of. Revisited in §B; per-market counsel is deliberately *not* purchased pre-revenue.

#### Versioned consent (platform-wide)

Versioned consent is the evidentiary backbone of the liability framework: the disclaimer ("opinion, not guarantee") holds only if Veriprops can prove a specific user accepted specific language at a specific time. Every legal document is versioned, and every acceptance is recorded against the exact version shown, with **user ID, consent type, version, timestamp, and IP**. (Device fingerprinting is deliberately not collected — it adds little evidentiary value, is increasingly unreliable, and is itself an NDPA exposure.)

| Consent type | Collected at |
|---|---|
| `PLATFORM_TERMS` + `PRIVACY_POLICY` | Signup |
| `AGENT_TERMS` | Agent application submission |
| `VERIFICATION_TERMS` | Before each payment (a single bundled acceptance — see §5.3) |
| `REPORT_DISCLAIMER` | First report view |

When a document version changes, the user re-accepts on their next relevant action. **Material** changes force immediate re-acceptance via a modal (accept or decline); declining blocks the affected feature but preserves any in-progress draft and offers an email follow-up rather than a dead end. **Cosmetic** version bumps are acknowledged passively without blocking.

#### Refund & liability model

| Scenario | Fault | Action |
|---|---|---|
| Cancel before `IN_PROGRESS` | Customer | Partial refund minus `cancellation_surcharge_pct` |
| Cancel after `IN_PROGRESS` | Customer | No refund |
| Wrong agent assigned / step skipped | Veriprops | Full refund + free re-verification |
| Registry error / missing records | External | No refund; transparent reporting |
| Property inaccessible | External | Partial refund (field component only) — **requires** geotagged proof of the access attempt + the contact-person who denied access (§7.3a); **admin**, not the agent, classifies the cause |
| Fraudulent customer submission | Customer | No refund |
| Payment confirmed but verification never activated | Veriprops | Full refund |
| **Ambiguous location input** — customer's address/landmark was genuinely ambiguous and the agent verified a defensible interpretation | Customer | No refund; re-verification at re-check pricing |
| **Wrong property despite clear input** — agent ignored an unambiguous submitted address/coordinates and verified the wrong plot | Veriprops | Full refund + free re-verification |

All refund amounts compute from the **contractual NGN figure** (§4.4), in integer minor units, and are **issued in NGN through the gateway**. Because international card payments were gateway-converted at charge time, a refund is re-converted by the customer's card network at its prevailing rate on the way back, which may differ from the original charge. The Refund consent item (§5.3) discloses this: *"Refunds are issued in Naira at the amount paid; your bank converts back at its prevailing rate, which may differ from your original charge."* For **Veriprops-at-fault** refunds only, admin may apply a goodwill top-up to offset an adverse reverse-FX gap.

#### Communication boundaries

- ❌ No direct Customer ↔ Agent chat.
- ✅ Customer ↔ Admin — one thread per verification.
- ✅ Admin ↔ Agent — one thread per verification, with task tags (not a separate thread per task).
- ✅ Routine customer↔agent coordination uses **structured, fraud-scanned clarification requests** routed through the verification thread — not free-text, and not requiring an admin keystroke for every exchange. Admin reviews exceptions.
- ⚠️ Agent first name + role visible to customer; contact details never.
- 🚨 All messages scanned for phone/email/payment leakage before delivery (§4.7, §11).
- ✅ All communication recorded and auditable.

#### Premium Legal Opinion — ownership & regulated-activity posture

Rendering legal opinions in Nigeria is a regulated activity. The Premium tier therefore must be clear about *whose* opinion the report carries, both for liability and for unauthorized-practice exposure. This is a **structural** question, not a copy question — no amount of careful wording fixes a wrong structure.

- **The opinion is the individual licensed lawyer's.** The Premium Legal Opinion is **owned and signed by the individual NBA-licensed lawyer** who renders it (the role already confirms its NBA licence per §7.3). Veriprops **transmits** the opinion and is liable only for **transmission integrity** — that the opinion shown to the customer is the one the lawyer produced, unaltered (underpinned by the §4.5 evidence hash). Veriprops does **not** author, own, or warrant the opinion's substance.
- **Why this framing.** It is the posture least likely to constitute unauthorized practice or to place the opinion's substantive liability on the platform. A customer relying on "an opinion *from Veriprops*" vs. "from licensed lawyer X, *via* Veriprops" are very different regulatory and liability pictures; this clause fixes it as the latter.
- **NBA counsel gate (before Phase 10).** This framing is the sensible default but is **unconfirmed against NBA / Nigerian regulatory rules until counsel signs off**. Confirmation is a **hard gate before the Phase 10 Legal Opinion section goes live** (§B) — it does not block MVP design/build, only go-live. Holding the entire tier is over-cautious; building against the safe framing with a go-live gate is sufficient.

#### Report footer (every page, every PDF)

> *This report represents a professional opinion, not a legal guarantee. Findings are based on information available at the time of verification. Veriprops — Jurisdiction: Nigeria. "We reduce uncertainty. We do not eliminate it."*

---

## 4. Architecture Decisions

Cross-cutting structural choices that are expensive to change later. Each notes **when** to build it. Scaffolds for the "do-now" items land in Phase 0.

### 4.0 Build-timing summary

| Decision | Build when | Rationale |
|---|---|---|
| 4.1 Single state-derivation owner | Phase 0 | Keeps state logic in one place |
| 4.2 Data-driven task dependencies | Phase 0 | Generalizes the Lawyer gate; config not code |
| 4.3 Property separated from Verification | Phase 0 | Cheap now; painful migration later |
| 4.4 Gateway-mediated collection, integer minor units | Phase 0 (money) / Phase 5 (flows) | Reconciliation correctness; no-FX-liability posture |
| 4.5 Per-item evidence hash | Phase 9 | Makes alteration detectable, cheaply |
| 4.6 Idempotency (payment paths) + optimistic locking | Phase 0 | Webhook double-processing protection |
| 4.7 Message state machine + single-tier fraud hold | Phase 11 | Holds off-platform-contact attempts |
| 4.8 In-process event bus | Phase 12 | One routing rule for Chat vs Notifications + fan-out |
| 4.9 SSE real-time transport | Phase 9 | One transport; honest about a mediated chat |
| 4.10 Non-sequential VID + lookup safety | Phase 0 (IDs) / Phase 13 (lookup) | Closes enumeration/scraping of the public lookup |
| 4.11 Audit pseudonymisation on erasure | Phase 19 | Resolves NDPA erasure vs. indefinite audit |

> **Not adopted:** full event sourcing. The system keeps `verification.status` as a real column written by the §4.1 owner, with `AuditLog` written on every transition. The per-item evidence hash (§4.5) and payment idempotency (§4.6) carry the audit-integrity weight at far lower cost.

### 4.1 Single state-derivation owner

One backend function — `deriveVerificationState(tasks, payment_state, flags)` — owns the computation of `verification.status`. It runs after any task mutation, applies the §2.5 rules, writes the result once, and emits the transition to `AuditLog`. All task-mutating handlers call it rather than setting status inline; frontends never derive global state, they render what the API returns. The customer-facing label mapping (§9.2) is a thin presentation layer over this one value. This keeps state logic in one place and prevents "dashboard says X, admin says Y" bugs. (A repository-layer write-guard that physically rejects direct status writes is deferred; the single-function convention is sufficient for the current team size.)

### 4.2 Data-driven task dependencies

Task dependencies are **data**, not hard-coded checks. A per-tier `task_dependencies` structure declares, e.g., `LAWYER depends-on [REGISTRY, FIELD, SURVEYOR]`. The unlock check is generic: "are all upstream tasks `SUBMITTED`?" The Lawyer "Awaiting other agents" UI renders the *actual* blocking tasks from this structure.

- Adding/changing a dependency is configuration, consistent with pricing/timeouts/weights being admin-configurable.
- Acyclicity is validated at config-save time (trivial at four roles).

### 4.3 Property as a first-class entity

Property is a thin entity separate from Verification from day one: address, coordinates, type, and the customer-submitted facts. Verifications point at a property; re-checks and tier upgrades reuse the same property row.

- **MVP does not auto-deduplicate** — one property row per submission is acceptable. Structural separation is the point; dedup intelligence is the Post-MVP Property Identity Layer.
- Makes the Post-MVP market-wide property layer *additive*, not a migration.

### 4.4 Money & currency — gateway-mediated collection

**All money collection is gateway-mediated** through Paystack/Flutterwave, behind the provider facade (§0.1). Veriprops **never** handles raw card data, bank-account numbers, or banking credentials — the gateway hosts the payment surface. Gateway **webhooks** (idempotent, §4.6) drive `PAYMENT_PENDING → PAID`. This is feasible on both providers today: international Visa/Mastercard (and Amex for Nigeria-based accounts) collection in USD/GBP/EUR is supported, and NGN bank transfer is handled via gateway-issued virtual accounts.

**Storage.** All monetary values are **integer minor units** (kobo, cents) with an explicit currency code — never float/decimal. This keeps pricing → payment → refund → commission → payout reconciling to the kobo.

**Contractual vs. charge.** Two separate concerns on the verification record:

| Field group | Meaning | Used by |
|---|---|---|
| `price_locked_minor` + `currency = NGN` | The **contractual amount owed**, always NGN | Refunds, commissions, disputes, audit |
| `charge_currency`, `charge_amount_minor`, `fx_rate_at_quote` | How the customer **actually paid** through the gateway | Settlement, receipts |

**Contractual posture: NGN-contractual, NGN-settled by default.** The price is owed in NGN. A diaspora customer may **pay in USD/GBP/EUR via international card**; the **gateway** converts at the network rate at charge time and settles Veriprops in **NGN**. Veriprops carries **no FX risk**. (For Nigerian merchants, Naira-card transactions settle in NGN regardless of display currency, per the CBN dollarisation policy.) The pre-payment foreign figure shown to the customer is **indicative only**, presented with a concrete expected range and with the NGN amount as the prominent, certain figure (§5.2); disclosure required: *"You'll be charged in Naira; your bank converts at its rate, typically within ±3%."*

**Collection methods (all gateway-mediated):**

| Currency | Methods |
|---|---|
| NGN | Card; gateway-issued virtual-account bank transfer |
| USD / GBP / EUR | International card (gateway-converted; settled NGN) |

There is **no direct SWIFT/IBAN wire** to a Veriprops bank account at MVP, and therefore no manual wire reconciliation flow.

**Multi-currency routing.** A single gateway account does not uniformly handle every currency (e.g., USD can be configured alongside NGN on a Nigerian Paystack account, but some combinations require separate gateway accounts/providers). The **provider facade routes per currency** to the correct account/provider, so application code is currency-agnostic.

**Optional, post-MVP (treasury decision, not collection architecture):** to *retain* foreign currency rather than settle to NGN, enable Flutterwave USD settlement / payout-balance or the Paystack Zenith USD-domiciliary pilot. This changes settlement only; the collection model is unchanged.

**Price lock.** On "Continue to Payment", the NGN price and the indicative FX rate are locked on the verification record for **24 hours**, then re-lock at the current rate.

### 4.5 Evidence integrity — per-item content hash

On evidence upload, compute and store a SHA-256 content hash of the file in the audit event. Combined with S3 immutability and the audit log, this makes any post-submission alteration **detectable** — the stored hash no longer matches the file.

- Strengthens the §3.5 "accurate presentation of findings" boundary and the Phase 19 evidence pack.
- Proves integrity **after receipt**; authenticity **at capture** is a separate control (server-side GPS/timestamp stamping, §7.3a).
- A per-item hash is deliberately chosen over a chained hash: chaining only defends against rewriting the audit log itself — a threat that, if real, defeats more than the chain — and it fights concurrent multi-agent uploads. Revisit only if a specific legal demand requires it.

### 4.6 Idempotency & double-submit protection

**Payment paths and entity creation use idempotency keys.** The gateway webhook handler is keyed on the gateway event ID and is safe to replay; payment initiation takes a client idempotency key. A duplicate "payment succeeded" webhook therefore cannot create two `PAID` transitions or two receipts. The same client-key mechanism guards **entity-creation** endpoints — new verification draft, re-check request, dispute, payout request — because creation is the one place optimistic locking cannot help: there is no prior row to collide with, so a double-tap or retry-on-timeout (common on flaky mobile networks) would otherwise create duplicates.

**Updates rely on optimistic locking.** Task submit, tier upgrade, and other mutations of existing rows are guarded by the `version` column on `BaseEntity` (§Phase 0) — a double-tapped "Submit" loses the stale write.

Stated as one rule: **idempotency keys for payments and entity creation; optimistic locking for updates.**

### 4.7 Message lifecycle & fraud holds

Messages have their **own state machine**, parallel to the others:

```
PENDING_SCAN → HELD → {APPROVED → DELIVERED | REJECTED → BLOCKED}
PENDING_SCAN → DELIVERED        (passed scan)
```

At send time, messages are scanned for off-platform-contact and payment-solicitation patterns (phone, email, URLs, banking details, "go outside the platform"). **Messages with no flaggable content deliver immediately** (a fast lane — the scan is synchronous and most messages contain nothing to flag); only genuinely flagged messages are **held** pending admin approve (deliver) or reject (block). So the hold is the rare exception, not the default experience. MVP ships a **single hold behaviour** — every flagged message is held the same way. The false-positive rate is instrumented from day one; **severity tiers** (hard-block vs. soft-flag) are a fast-follow added once that data shows where the line sits, not built blind. The held-message notice to the sender is worded so it never reads as suspicion of the customer (e.g. *"Just a moment while we check this through"*). Held-message journeys are audit-logged. Full detail in Phase 11.

### 4.8 In-process event bus

Every domain event (`MessageSent`, `DisputeOpened`, `TaskRejected`, `SLABreached`, …) is published **once**. Subscribers decide surfacing:
- The **Chat** projection increments its counter (person-to-person).
- The **Notification** projection consults a **declarative rule table** to decide whether the event also warrants a system notification and on which channels (in-app / email / SMS).

This puts the "routine message → Chat only; high-stakes event about a chat → Chat + Notification" rule (top-nav FR-6/FR-7) in **one** table. Implemented as an **in-process synchronous dispatcher** backed by the existing DB — not Kafka. Introduced at Phase 12 when notifications get real; a new channel (e.g., WhatsApp, Post-MVP) is a new subscriber, not a rewrite.

### 4.9 Real-time transport — SSE throughout

One transport for the whole app: **SSE** delivers server→client pushes (new messages, notifications, status changes, evidence, SLA alerts); message **sends** are ordinary HTTP POST. A 60-second polling fallback shares the same event shape, so it is not a separate code path that rots.

SSE is chosen over WebSocket deliberately. The chat is **admin-mediated and fraud-scanned** — a message may be held for minutes before delivery (§4.7) — so live-presence affordances (typing indicators, presence, read receipts) would misrepresent a channel that is not, by design, live. There is no duplex richness to justify the operational cost of WebSockets; SSE also survives flaky mobile networks and proxies with built-in browser reconnection. All pushes are driven by the §4.8 event bus.

### 4.10 Verification ID generation & public-lookup safety

The Verification ID keeps its human-readable shape `VP-YYYY-XXXXXX`, but `XXXXXX` is **high-entropy and non-sequential** — never a guessable counter. The public lookup (`/verify/[id]`, §13.1) is unauthenticated and therefore an enumeration/scraping surface; three controls close it:

- **Non-sequential IDs** so an attacker cannot walk the ID space. (A separate internal counter serves any at-a-glance volume metric.)
- **Rate-limiting** on the public lookup endpoint, tuned so a legitimately viral shared link is not blocked.
- **Indistinguishable responses** — "not found", "not public", and "in progress" return shapes that do not let a prober confirm which IDs exist.

### 4.11 Audit retention vs. NDPA erasure — pseudonymisation

Audit logs and consent records are retained indefinitely for legal defensibility (§19), yet they contain PII (actor identity, IP, sometimes message content), which collides with an NDPA erasure request. The resolution is **pseudonymisation, not deletion**: on erasure, the actor's PII in audit events is replaced with a stable opaque token while the event, transition, timestamp, and legally necessary content are retained; the erasure itself is recorded as an event.

- This satisfies erasure (identifying PII removed) while preserving a defensible trail (events intact).
- **Caveat:** pseudonymised records can sometimes be re-identified from context (a property + dates may fingerprint a person); true anonymisation is harder, and the retention basis after erasure needs legal sign-off (§B).

---

## 5. Cross-Cutting Concerns

Apply to every phase. Scaffolds land in Phase 0.

| Concern | Spec |
|---|---|
| **Determinism** | Verification, task, report, and message state machines fully defined (§2, §4.7). No undefined transitions. |
| **Derived state** | Global verification state is derived from task states by one owner (§4.1). |
| **Audit** | Every transition logged: entity, actor, actor role, from→to, timestamp, IP, note. Evidence events carry a per-item content hash (§4.5). Retained indefinitely. |
| **Idempotency** | Payment paths use idempotency keys; other mutations use optimistic locking (§4.6). |
| **Money** | Integer minor units; NGN contractual; gateway-mediated collection (§4.4). |
| **Accessibility** | Full keyboard navigation, tab order, ARIA roles. |
| **Mobile-first** | Diaspora uses mobile heavily; design mobile-first. |
| **Offline & low-bandwidth** | Agent forms auto-save locally; upload retry on reconnect; sync indicator mandatory. The two heaviest paths — agent evidence upload and customer evidence viewing — have explicit weight budgets: images compressed/resized on upload (full-res original retained server-side, compressed derivatives served), progressive low-res-first viewing, static-map fallback over live embeds, queued server-side PDF generation. |
| **Embedded education** | Tooltips on technical terms everywhere (C of O, encumbrance, trust score, `UNDER_REVIEW`). 50–100 words, plain English. |
| **Language** | Plain English; specific not vague ("5–7 business days", not "a few days"). |
| **Agent identity** | API enforces that customer-facing endpoints return only `role`, `first_name`, `avatar_url`, `verified`. |
| **Message fraud scan** | Phone, email, URLs, banking details, "go outside the platform" phrases — held for admin review (§4.7). |
| **Real-time** | SSE for all server→client pushes (chat receive, status, notifications) + polling fallback; HTTP POST for sends (§4.9). |
| **Compliance** | Data & privacy handling per **NDPA**; PII retention per `pii_retention_days`; erasure workflow (§18, §19). |

---

# Part II — Implementation Phases

Phases 0–10 are the MVP cut line. Each phase assumes the previous are live unless noted.

<a id="phase-0"></a>
## Phase 0 — Platform Foundation

**Goal:** Stand up the scaffolding every feature depends on. No user-visible product yet.

### 0.1 Deliverables

- **Monorepo:** `backend/` (FastAPI + Alembic + SQLAlchemy + Kink DI) and `web/` (Next.js 16 App Router + Tailwind + Zustand + React Query).
- **Base entity:** `BaseEntity` with `id` (UUID), `date_created`, `date_updated`, `version` (optimistic locking), `deleted` (soft delete).
- **Generic repository:** `GenericRepo[Model, Create, Update, Query, Search]` with pagination and soft-delete-aware queries.
- **Transaction management:** `@transactional` decorator with session policies (`USE_IF_PRESENT`, `ALWAYS_NEW`, `FALLBACK_NEW`).
- **Idempotency (§4.6):** idempotency-key handling for payment endpoints + a dedup store keyed on gateway event ID; optimistic locking (the `BaseEntity.version` column) for other mutations.
- **Exception hierarchy:** `AppodusBaseException` with structured context and HTTP mapping.
- **Middleware:** per-request DB session, request logging, CORS.
- **Dependency injection:** Kink bootstrap in `config/bootstrap.py`.
- **Configuration & env:** `.env.{local,dev,staging,prod}` via `appodus_active_env`.
- **Integration shells:** stubs/credentials for AWS S3, Paystack/Flutterwave, SendGrid/Mailjet, Twilio/Termii, Firebase, Google Drive, Zoho DocSign, and the **KYC provider facade** (Dojah default).
- **Audit primitive (§4.5):** `AuditLog` entity + writer hook on every transition; per-item evidence content-hash helper.
- **State-machine primitive (§2):** reusable validator enforcing the transition tables for Verification, Task, Report, and Message.
- **State-derivation owner (§4.1):** `deriveVerificationState(...)` called by all task-mutating handlers; sole writer of `verification.status` by convention.
- **Task-dependency structure (§4.2):** per-tier dependency config + acyclicity validation.
- **Property entity (§4.3):** thin Property table separate from Verification.
- **Verification ID generator (§4.10):** `VP-YYYY-XXXXXX` with a high-entropy, non-sequential suffix; a separate internal counter serves volume metrics.
- **Money primitives (§4.4):** integer-minor-unit value type; `price_locked_minor` (NGN) vs `charge_*` separation.
- **Consent store:** versioned `ConsentDocument` + `UserConsent`.
- **Frontend design system:** Radix primitives + Tailwind tokens; form/field/input/toast/modal/wizard components.
- **Auth wiring:** JWT (httpOnly cookie, 15-min access / 30-day refresh), silent refresh, middleware guards.

### 0.2 Exit criteria

- All four state machines enforceable at the ORM/service layer; the derivation owner is the sole writer of global status.
- Audit log writes on every transition; per-item evidence-hash helper unit-tested.
- Payment idempotency proven with a replayed-webhook test; optimistic-lock conflict proven with a concurrent-write test.
- `alembic upgrade head` runs clean on all environments; CI green; Swagger reachable at `/docs`.
- Nigerian public-holiday calendar wired into the SLA business-day calculator.

---

<a id="phase-1"></a>
## Phase 1 — Marketing Site & Home Page

**Depends on:** Phase 0.
**Goal:** Public landing page that acquires and converts diaspora visitors. Authoritative, trustworthy, premium.

**Design system:** "The Sovereign Curator" aesthetic. Type: Manrope (display) + Inter (body). Color: Midnight Navy `#000d22`, Veridian `#3f6653`, Gold Leaf `#735c00`. No 1px border lines — use tonal background shifts.

### 1.1 Sections (in order)

| Section | Purpose | Key CTA |
|---|---|---|
| Navigation | Brand + links + CTAs | "Verify a Property" (gradient) + "Log in" |
| Hero | Emotional promise, trust-score teaser | "Start Verification" + "View Sample Report" |
| Verification Ecosystem | 3-feature bento: Trust Score · Verification ID · Certified Report | — |
| Rigorous Methodology | 5-step process stepper | — |
| Verified Agents | 4 agent types with role descriptions | "Become an Agent" |
| Pricing | Basic / Standard / Premium cards + currency toggle | Per-tier CTA |
| Testimonials | 3 diaspora customer stories | — |
| Call to Action | Emotional close — legacy/family-wealth angle | "Secure My Property Now" |
| Footer | Brand · Socials · Resources · Company · Newsletter | — |

### 1.2 Key behaviours

- Sticky nav, glassmorphism backdrop blur on scroll. Desktop links: How It Works · Pricing · Agents · Resources. Mobile: hamburger → full-screen overlay.
- Auth intent preserved: "Verify a Property" when unauthenticated → auth gate with `intent=verify`; "Become an Agent" → `intent=agent`.
- Methodology steps: 1 Submit Details → 2 Cross-Check Records → 3 Check Encumbrances → 4 Run Risk Analysis → 5 Get Certified Report.
- Pricing: Basic / Standard ("Most Popular", elevated) / Premium. Currency toggle pills **NGN · USD · GBP · EUR** with live indicative conversion.
- Footer legal: *"© {current_year} Veriprops. We reduce uncertainty. We do not eliminate it."* (year rendered dynamically — never hard-coded, to avoid staleness across calendar years.)
- SEO: public pages crawlable; VID lookup pages `noindex` unless `COMPLETED` + public sharing (Phase 13).

### 1.3 Exit criteria

- All sections render on desktop (1440px) and mobile (375px) without breaks.
- CTAs route to `/auth?intent=verify` and `/auth?intent=agent`.
- Currency toggle cycles NGN → USD → GBP → EUR.
- Copy matches brand voice; brand tokens resolve; content/data module unit tests pass.

---

<a id="phase-2"></a>
## Phase 2 — Auth & Onboarding Shell

**Depends on:** Phase 0.
**Goal:** A user can sign up, log in, verify email & phone, and land on the right portal.

### 2.1 Features

- **Signup (email/password):** first/last name, email (verified), phone (country flag). To shorten the runway to value (§ onboarding rationale), **only email is verified at signup; phone OTP is deferred to first payment**, and country/timezone/currency are collected **progressively inside the portal**, not on the signup form. A user can reach a real price before any phone OTP. Server enforces a recently-verified email marker (30-min TTL, single-use) before completing signup; the phone-verified marker is enforced at the payment step instead.
- **Note on fraud controls:** deferring phone verification weakens the referral anti-farming gate (§17.1) until payment — acceptable because the payment itself (unique card fingerprint) is the binding fraud gate, and junk drafts cost little.
- **Login:** "forgot password" + "create account". Rate limiting: warning at 5 (`LOGIN_FAILURE_WARNING` in Security Activity Log), lockout at 7 (15 min).
- **OAuth (Google Phase 1; Apple/Facebook Phase 2):** popup-based flow with `postMessage` bridge + HttpOnly cookie session (§2.2 below). **Popup-only model; redirect is the fallback for blocked popups.**
- **OTP:** 6 digits, auto-advance, paste support, 10-min timer, resend after expiry, max 3 resends then 30-min lockout.
- **Forgot/reset password:** tokenised email link (1 hour, single-use). On reset, all sessions invalidated. Email copy states the correct validity ("1 hour").
- **Set password** for OAuth-only users (add email/password login later).
- **Failed-attempt tracking:** all failed logins & OTPs logged (timestamp, IP, device fingerprint); visible in Security Activity Log; fed into fraud detection.
- **Connected devices:** list sessions; revoke individual; "log out all".
- **Linked OAuth accounts:** list / link / unlink with password-existence guard. Link uses the OAuth popup with `mode=link`; unlink rejected if no password set.
- **Resume partial signup:** server-side draft (`signup_drafts`), normalised-email key, 7-day TTL, soft-deleted on success; `localStorage` mirror for same-device offline resume; server copy preferred on resume.
- **Versioned consent on signup:** Platform Terms + Privacy Policy, explicit version in label.
- **Auth gate:** shared interstitial for "Verify a Property" / "Become an Agent"; preserves `intent`.
- **Centralised route protection:** Next.js proxy gates `/portal/*`, `/admin/*`, `/agent[s]/*`, `/account/*` on cookie presence; redirects unauthenticated users to `/auth/login?redirect=<original>`; redirects authenticated users away from guest-only routes. Cookie-presence only — session validity is enforced server-side on every API call.
- **Customer persona default:** signup via "Verify a Property" auto-adds `CUSTOMER`; lands at the verification wizard (or resumable draft). Country/timezone/currency are filled progressively as needed, not up front.
- **Cross-portal awareness (multi-role users):** for a user holding both Agent and Customer personas, the portal-switch control carries a **count badge of unread/actionable items in the *other* hat**, so a customer-side message is never lost while in agent view. Notifications carry a role tag; the per-portal feeds stay separated (the badge signals across them without merging them).

### 2.2 OAuth specification — popup + HttpOnly cookie (authoritative)

**Flow:**
1. Frontend fetches `GET /api/users/auth/oauth/{provider}/start?intent=<intent>&mode=auth|link` → `{authorizationUrl}`.
2. Frontend opens a synchronous, click-triggered, centred popup, then navigates it to the URL once resolved.
3. User completes provider consent.
4. Provider redirects (or `form_post`s, for Apple) the popup to the backend callback.
5. Backend validates state + PKCE, exchanges the code, fetches profile, and:
   - **AUTH, existing identity** → log in.
   - **AUTH, new email** → auto-create user (CUSTOMER unless `intent=agent`); profile-completion modal collects phone (number only — OTP deferred to first payment, §2.1) while country/timezone/currency are gathered progressively in-portal.
   - **AUTH, email collision** (existing password account, provider not linked) → **REJECT** with exactly: *"Account exists. Please log in and link this provider explicitly."* No session issued.
   - **LINK** → attach provider identity to the JWT-authenticated user.
6. Backend issues the JWT session as an **HttpOnly, Secure, SameSite-appropriate** cookie.
7. Backend returns a minimal HTML page that calls `window.opener.postMessage({type:"oauth_result", success, message?}, validatedTargetOrigin)` and self-closes, with a visible fallback if `window.close()` is blocked.

**`postMessage` contract:** success `{type:"oauth_result", success:true}`; failure adds `message`. Parent MUST validate `event.origin === window.location.origin` AND `event.data.type === "oauth_result"`; all else dropped.

**Security:** signed single-use `state` (Redis delete-on-read); PKCE S256 all providers; strict redirect-URI validation (registered as `${BACKEND_PUBLIC_ORIGIN}/api/users/auth/oauth/{provider}/callback`, frontend never constructs it); `postMessage` targetOrigin from an `OAUTH_FRONTEND_ORIGINS` allowlist (never `*`); short-lived state TTL; Apple `form_post` + JWKS validation; Facebook requires email; OAuth never silently merges into a password account; frontend never reads or stores tokens.

**Frontend UX:** popup blocked → inline fallback full-page redirect; popup closed → silent cancel; timeout (5 min) → retryable toast; provider error → toast with failure message; no blocking confirmations; on success refresh user state and route by intent/role priority.

### 2.3 Exit criteria

- All auth flows work end-to-end on mobile + desktop; Security Activity Log renders `LOGIN_FAILURE_WARNING`.
- No password/token/PII leak in logs or responses.
- `intent`-preserving redirects verified by E2E.
- OAuth E2E covers: first-time signup with profile completion, returning login, email-collision rejection, popup-blocked fallback, popup-closed cancel, link-from-settings, unlink password guard.

---

<a id="phase-3"></a>
## Phase 3 — Agent Onboarding & KYC

**Depends on:** Phase 2.
**Goal:** An agent can apply, complete KYC, and sit in `PENDING` awaiting admin approval.

### 3.1 Application wizard (4 steps)

1. **Roles** — Field / Surveyor / Registry / Lawyer (multi-select; "Pick all that apply. You will be reviewed for each role you select."). At least one required.
2. **KYC** — **BVN (primary)** with the provider performing liveness + face-match; **government-ID upload (fallback)**: NIN / Passport / Driver's Licence / Voter's Card. **Liveness and face recognition are deferred entirely to the third-party provider** (Dojah default, behind the §0.1 facade). The platform stores the provider's verification result and reference, not raw biometric processing.
3. **Credentials** — conditional: Surveyor licence; NBA licence for Lawyer. Optional: years of experience, coverage areas (state + LGA / Google Place), 300-char bio.
4. **Review & submit** — truthfulness checkbox + versioned Agent Terms acceptance.

Application enters `PENDING` → **Approval Status Dashboard** (Pending / Approved / Rejected with reason). Pending applications block the agent from receiving jobs.

### 3.2 Exit criteria

- Can submit any valid combination of roles.
- Resumable: closing mid-wizard returns to the same step.
- KYC documents stored encrypted in S3 with per-user access control; provider reference persisted behind the facade.

---

<a id="phase-4"></a>
## Phase 4 — Admin Onboarding & Role Management

**Depends on:** Phase 2.
**Goal:** Existing admins invite new admins; RBAC enforced platform-wide.

### 4.1 Features

- **Admin invite** — Super Admin sends invite with sub-role (Super / Operations Manager / Finance Admin). Tokenised link, 72-hour validity.
- **Invite acceptance** — three scenarios: new user → pre-filled signup; existing user → log in to merge admin role; already admin → friendly message.
- **RBAC** — permissions matrix: invite admins, approve agent applications, assign agents, approve payouts, configure pricing, resolve disputes, release reports.
- **Admin team management** — list, deactivate, change sub-role.

### 4.2 Exit criteria

- Seed script creates the first Super Admin (alembic data migration or CLI).
- Permission checks verified on every admin endpoint; role changes audit-logged.

---

<a id="phase-5"></a>
## Phase 5 — Customer Submission & Payment

**Depends on:** Phases 0, 2.
**Goal:** A logged-in customer can submit a property, pay, and enter `PAID`.

### 5.1 Property submission wizard (`/portal/verifications/new`)

A 4-step guided flow with a persistent step indicator. A Verification ID (`VP-YYYY-XXXXXX`, `DRAFT`) is generated on Step 1 load. Progress auto-saves to backend per step (sessionStorage fallback per keystroke). The Property entity (§4.3) is created/linked here.

```
[1. Property Details] → [2. Tier & Pricing] → [3. Consent] → [4. Payment]
```

**Step 1 sub-steps:**
- **1A Source** — manual entry. (Listing-URL import is **removed from MVP** — see §17.x note; it was brittle third-party scraping of low value. Manual entry is the sole MVP path.)
- **1B Type** — Land / Building.
- **1C Location** — **Google Places autocomplete is the primary input** (restricted to Nigeria; returns lat/lng, state, LGA) behind a **geocoding facade** so the provider is swappable. Because Google Places has weak coverage of informal and peri-urban Nigerian addresses — exactly the plots this product exists to verify — the **landmark / free-text field is a mandatory escape valve** whenever Places cannot resolve the property, labelled *"Help the agent find it: nearest junction, landmark, or local description."* The map pin is **draggable** to correct geocoding. Places-only is never a hard gate.
- **1D Details** — conditional (Land: size, use, survey-plan status, current state; Building: type, floors, age, occupancy, C of O status).
- **1E Documents** — optional upload (Survey Plan, Title Document, Purchase Agreement, Other).
- **1F Seller info** — optional (name, phone, email, relationship, notes).
- **1 Summary** — collapsible review, expand-to-edit.

### 5.2 Pricing transparency UI (Step 2)

- Tier cards with inline inclusions + SLA; "Compare tiers" modal with full matrix.
- Line-item breakdown fetched from the admin-configured pricing API (admin UI built in Phase 18).
- Currency pills **NGN / USD / GBP / EUR**, default to the user's stored preferred currency (reused everywhere so they never re-pick; the same currency shows consistently on every surface). The **NGN amount is the prominent, certain figure** (it is the contractual amount, §4.4); any foreign figure is explicitly secondary and **indicative**, shown with a concrete expected range rather than a vague caveat — e.g. *"You'll be charged ₦X; your bank converts this, typically within ±3%."* FX rate refreshed at page load, cached 5 min, stale warning at 30 min.
- Recommendation banner: if C of O / survey unknown, nudge Standard or Premium.
- First-time + referral discount auto-applied (referral parsing; issuance in Phase 17), capped at `max_discount_percent`.
- **Price lock** on "Continue to Payment": locks NGN price + FX rate for 24 hours (§4.4).

### 5.3 Legal consent (Step 3)

A single versioned **`VERIFICATION_TERMS`** acceptance, not pre-checked, covering five clauses each with expandable full text:
1. Verification Disclaimer
2. Findings & Opinion Acknowledgement
3. Jurisdiction & Platform-Only Transactions
4. Communication Recording
5. Refund & Cancellation Policy (states `cancellation_surcharge_pct` and the reverse-FX refund note, §3.5)

The five clauses are accepted together as one record — the legal coverage is identical to five separate records, with a fifth of the storage. On acceptance, a `consent_snapshot_id` is stored on the verification (user, type, version, timestamp, IP — no device fingerprint, per §3.5).

### 5.4 Payment experience (Step 4)

**Gateway-mediated collection (§4.4).** NGN is the contractual amount; all collection runs through Paystack/Flutterwave behind the provider facade. Veriprops never handles raw card or bank credentials.

**Phone verification gate.** Because phone OTP is deferred from signup (§2.1), the customer's phone is **verified here, before payment completes** (a recently-verified phone marker is required to proceed). This keeps the signup runway short while still ensuring a reachable, verified phone before money changes hands.

| Currency | Methods |
|---|---|
| NGN | Card; gateway-issued virtual-account bank transfer (24-hr expiry) |
| USD / GBP / EUR | International card (gateway-converted; Veriprops settled in NGN) |

- **Card:** the gateway/network converts at charge time; Veriprops bears no FX risk; the customer is charged the certain NGN amount, with the foreign debit disclosed as indicative within a stated range (§5.2).
- **Bank transfer (NGN):** gateway-issued dedicated virtual account per transaction; "I've made the transfer" triggers polling; gateway webhook auto-activates within ~15 min.
- **No direct SWIFT/IBAN wire** at MVP — international customers pay by international card through the gateway. (Retaining foreign currency is a post-MVP treasury option, §4.4.)
- **Status UI:** Initiated / Processing / Succeeded / Failed / Pending (transfer) with plain-language messaging, never raw gateway codes.
- **Retry:** preserves price lock; logs every failure; after 3 consecutive failures, show support with VID. All payment endpoints and the webhook handler are idempotent (§4.6).
- **Receipt:** instant, emailed; contains VID, line items, contractual NGN, charge currency/amount, indicative FX rate.

### 5.5 Post-payment confirmation

`/portal/verifications/[id]/confirmed` — VID, estimated completion, SLA countdown, "Track my verification" CTA, receipt download. SLA clock starts at `PAID` (business days = Mon–Fri minus Nigerian public holidays).

### 5.6 Exit criteria

- Verification transitions `DRAFT → SUBMITTED → PAYMENT_PENDING → PAID` deterministically via the derivation owner.
- Abandoned drafts preserved with all fields; resumable on next login.
- Customer upgraded to `trusted` on first successful payment.
- Duplicate payment webhook proven not to create a second `PAID` transition or receipt.
- Duplicate verification-create / re-check requests (double-tap, retry) proven idempotent via client key (§4.6).
- Phone verified at the payment gate before `PAID` (§5.4), with signup itself requiring only email verification.

---

<a id="phase-6"></a>
## Phase 6 — Admin Verification Control Panel

**Depends on:** Phase 5 (PAID verifications) + Phase 3 (approved agents) + Phase 4 (RBAC).
**Goal:** Admin sees all `PAID` verifications and assigns agents — moving the verification to `IN_PROGRESS`.

### 6.1 Features

- **Verifications list** (`/admin/verifications`) — filter by status, tier, SLA (on track / at risk / overdue), state/LGA, date.
- **Verification detail** — customer, property, per-role agent grid, actions (Assign / Reassign / Pause / Resume / Cancel / Declare Failure / Set Delay / Add Note).
- **Agent assignment modal** — suggested agents ranked by proximity, load, performance; full-search fallback.
- **Load-balancing view** (`/admin/agents`) — capacity view; `agent_max_active_tasks` enforced.
- **Admin notes** — pinned/tagged (Operational / Quality / Risk / Handover); searchable; in audit export; never visible to customers/agents.
- **Agent approval queue** — review pending applications (Phase 3): approve / reject with reason.

### 6.2 Auto-assignment

When `auto_assignment_enabled` is true, tasks are auto-created and broadcast to qualifying agents at `PAID`; first-accept-wins (§2.2). Manual assignment is always available and overrides geo rules.

### 6.3 Exit criteria

- First agent assignment (manual or auto) moves the verification `PAID → IN_PROGRESS` via the derivation owner.
- Lawyer tasks auto-lock until non-lawyer siblings reach `SUBMITTED` (§4.2 dependency data).
- Reassignments, pauses, cancellations audit-logged with reason.

### 6.4 Admin work queue & responsiveness SLAs

Every quality gate routes through a human admin (task approvals, report releases, held messages, disputes, conflicts, chargeback rebuttals). The platform makes this load **visible and prioritised** rather than assuming infinite capacity.

- **Unified work queue** — one prioritised queue across all admin action types, with item **age** and **priority weighting** (SLA-at-risk first, then higher-value tiers). Surfaced in Mission Control (§18).
- **Customer first-response SLA** — Customer↔Admin threads carry a first-response target; breaches surface in the queue. A fraud-held message (§4.7) older than a short threshold auto-escalates so the hold never silently strands a customer.
- **Staffing gate (hard pre-launch requirement):** the queue's SLAs are fiction without staff. Before launch the business must record and sign off "N admins sustain M verifications/day at these SLAs" — this is a launch gate, not an aspiration, and is revisited as volume grows. (Tracked in §B and §D as a business commitment, not a buildable feature.)
- **Graceful SLA shedding:** when queue depth exceeds a threshold, customer-facing SLAs **auto-extend with proactive notification** ("we're running a day behind — your new date is X") rather than breaching silently. Honest, managed lateness beats invisible lateness; the threshold and extension are configurable and the shedding is itself surfaced to admin so it cannot quietly mask chronic under-staffing.
- **Trust-gated auto-approval (early fast-follow, not MVP):** routine submissions from agents above an accuracy threshold may skip manual review, removing the highest-volume human action from the critical path. It needs reputation data not available at launch, so it ships as the **first post-launch priority**, not day one.

**Exit criteria (additive):** work queue prioritises SLA-at-risk items and exposes item age; customer first-response SLA breach is visible; held messages auto-escalate past the threshold; SLA shedding triggers a proactive customer notification and an admin signal.

---

<a id="phase-6a"></a>
## Phase 6a — Chargeback Handling

**Depends on:** Phase 5 (gateway-mediated payments).
**Goal:** Treat card chargebacks as a first-class revenue-integrity process. High-value intangible cross-border services carry elevated chargeback risk; the platform's audit trail is the asset that wins them.

### 6a.1 Model

A chargeback is a **gateway/bank-side financial dispute**, distinct from the customer `DISPUTED` verification flow (§14). It is modelled as a **flag + sub-process on the payment**, **not** a verification state — bank-side states Veriprops does not control never enter the verification state machine.

### 6a.2 Flow

1. Gateway chargeback webhook arrives (idempotent, §4.6) → payment flagged `CHARGEBACK`; admin alerted.
2. **Commission freeze:** any related agent commissions in *clearing* (§15.2) are frozen immediately.
3. **Auto-assembled rebuttal pack:** the system compiles consent records (versioned, with user ID, version, timestamp, and IP — no device fingerprint, per §3.5), the released report, the full audit trail, evidence hashes (§4.5), and payment/receipt records, formatted for submission back through the gateway.
4. Admin reviews and submits the rebuttal within the gateway's window.
5. Outcome (controlled by the card network, on its timeline):
   - **Won** → payment restored; frozen commissions resume clearing.
   - **Lost** → payment reversed; related commissions reversed (clawed back from clearing/available balance); verification annotated; repeat-offender customer flagged.

### 6a.3 Exit criteria

- Chargeback webhook flags the payment and freezes related commissions without touching the verification state machine.
- Rebuttal pack auto-assembles from existing audit artefacts for a test verification.

---

<a id="phase-7"></a>
## Phase 7 — Agent Task Execution

**Depends on:** Phase 3 (approved agents), Phase 6 (assignable tasks).
**Goal:** An approved agent can discover, accept, execute, and submit a task.

### 7.1 Agent dashboard (`/agent/dashboard`)

- **"Active to receive tasks" toggle** in the top menu (availability 🟢/🟡/🔴; auto-🔴 at `agent_max_active_tasks`).
- Available jobs (geo-filtered by coverage, role-matched, first-come-first-served).
- My active tasks with status chips; completed summary + earnings preview.

### 7.2 Accept / decline

- Accept → `ASSIGNED → ACCEPTED` (or `PENDING → ACCEPTED` for broadcast), removed from pool, countdown starts, admin notified.
- **Accept-time capacity check:** a broadcast accept is rejected if it would exceed the agent's `agent_max_active_tasks`, so the cap is enforced on the broadcast path, not only on admin assignment — preventing one fast agent from hoarding jobs.
- Decline → back to `PENDING`/pool; repeated declines flagged.
- **No-show / pool timeouts** (`no_show_timeout_hours`, `pool_timeout_hours`) → auto-return to `PENDING`, admin alerted, non-response logged against performance.
- **Starvation backstop:** a broadcast task unclaimed past `pool_timeout_hours` does not simply loop in the pool — it **auto-escalates to targeted assignment** (a ranked offer to the best-matched available agent, or admin if none), so hard/remote/low-commission jobs cannot rot while popular areas clear instantly. An optional flat **remote-job bonus** (config toggle) can be attached to aging or hard-to-reach tasks; dynamic per-job commission uplift is deferred (it complicates the commission promise and is a pricing-policy decision).

### 7.3 Role-specific submission UIs (`/agent/tasks/[id]/submit`)

Structured, never generic. Each ends with an agent **trust-score input** (0–100 slider; rationale required if <60 or >90) feeding the weighted composite, and a **declaration**.

- **Field Agent** — access confirmation; condition checklist; observations narrative (≥100 chars); neighbourhood; ≥5 photos (GPS+timestamp stamped server-side; hashed §4.5); optional video; ≤50 files; visit-date + GPS-at-submission.
- **Surveyor** — survey confirmation; boundary assessment vs submitted plan; coordinates (≥2) or georeferenced file (incl. KMZ); survey-plan upload; plan-quality comments.
- **Registry Agent** — registry search details; title-doc assessment (type, condition, authenticity — explanation mandatory if questionable/forged); ownership chain; document uploads (redact where required).
- **Lawyer** — documents-reviewed checklist; title opinion + ownership (explanation ≥150 chars); encumbrances list; fraud/risk flags; structured legal-opinion statement (≥200 chars, plain English); recommendation; NBA licence confirmation. **Gated by the §4.2 dependency rule.**

### 7.3a Proof-of-work, identity confirmation & conflict-of-interest

Evidence serves two distinct purposes — *informing the report* and *proving the agent did the work*. The second is treated as its own class, with the principle: **evidence the system stamps is strong; evidence the agent can fabricate is corroborating only.**

- **Proof-of-presence (required, on-site roles — Field/Surveyor):** server-side GPS + timestamp at point of capture (machine-checkable), a location check at submission, and a same-day capture constraint. This is the primary control against armchair fraud (§ insider-fraud, Hardening Backlog). GPS is spoofable by a determined actor — it raises cost, it does not prove honesty.
- **Property-identity confirmation (required, on-site roles):** the agent confirms "the property I inspected matches the submitted address / landmark / coordinates" and records which markers matched; ambiguity is noted. This catches honest wrong-property errors before the report ships and underpins the §3.5 wrong-property liability line.
- **Contact-person / source (optional, admin-only, NDPA-governed):** the agent may record who granted site access (caretaker, neighbour, seller's rep) with name and phone, as a corroboration *lead* for admin — never proof on its own. This is **third-party personal data**: it is **optional** (never a required field — required third-party PII invites junk and NDPA exposure), **admin-only** (never customer-facing; it would also breach the no-direct-contact rule), minimised, lawful-basis recorded, and included in the retention/erasure policy (§19).
- **Conflict-of-interest declaration (required, all roles, per task):** a versioned attestation — *"I have no personal or financial interest in this property or seller"* — captured like consent. It deters and creates contractual liability if false; it does not detect collusion (detection is the post-MVP Deep Trust layer).
- **Inaccessibility evidence (required to claim "inaccessible"):** an agent reporting a property as inaccessible must submit geotagged, timestamped proof of the access *attempt* (captured at the gate/boundary) plus the contact-person who denied access. The agent cannot self-classify the outcome as "inaccessible" for refund purposes — **admin** classifies the cause (§3.5). This deters both a lazy agent shedding travel and a customer/seller colluding to deny access while keeping the desk-based findings.

### 7.4 Draft & offline

Local autosave per field change; explicit "Save Draft" hits backend; offline upload queue retries on reconnect; sync indicator ("Saving…" / "Saved ✅" / "Offline — will sync ⚠️").

**Scoping note (real engineering, not a checkbox).** Offline-with-retry is prioritised for **Field Agent and Surveyor** (on-site, poor connectivity); Registry and Lawyer are desk roles and need only ordinary autosave. **Conflict-resolution rule:** last-write-wins on the agent's own local draft; the server is authoritative on submission. Size this realistically — offline upload queues with conflict handling are genuinely hard and easy to under-estimate.

### 7.5 Escalation

"Report Issue": inaccessible / suspicious / safety / conflicting info / other (description ≥50 chars + optional evidence). Admin alerted; admin may pause. **Agents cannot unilaterally cancel or pause.**

### 7.6 Exit criteria

- All four forms validate; submission moves task `IN_PROGRESS → SUBMITTED`.
- When all tasks `SUBMITTED`, the verification auto-derives to `UNDER_REVIEW`.
- Agent upgraded to `trusted` on first submission.
- Evidence hashes recorded and chain-verified.

---

<a id="phase-8"></a>
## Phase 8 — Admin Review & Report Release

**Depends on:** Phase 7.
**Goal:** Admin reviews each task, approves or requests revision, and releases the final report.

### 8.1 Task review

Full submission read-only + evidence gallery + admin notes + approve/reject.
- **Reject** requires ≥30-char reason + revision instructions → task `SUBMITTED → REJECTED → IN_PROGRESS` on rework; global state reverts `UNDER_REVIEW → IN_PROGRESS` if applicable. Rejection reason auto-posts to the admin↔agent thread (Phase 11).
- **Approve** → `SUBMITTED → APPROVED`. When all tasks `APPROVED`, system raises "Report ready for release".

### 8.2 Conflict detection

Automated flags on configurable rules (occupancy mismatch, boundary divergence, authenticity conflicts). Admin resolves: reject one/both tasks, override with reconciliation note, or flag in the customer report's risk summary. All resolutions logged.

### 8.3 Report release gate (`/admin/verifications/[id]/report-review`)

System computes the composite trust score from agent scores using admin-defined **Trust Score Weights** (per tier, per role, summing to 100%). Report assembled as `DRAFT`. Admin reviews:
- **"Release Report"** → report `DRAFT → RELEASED`; global state → `COMPLETED`; customer notified.
- **"Request Changes"** → reopen any task (`APPROVED → IN_PROGRESS`), restarting its loop.

No report reaches the customer without the deliberate release action.

### 8.4 FAILED state

Admin may declare `FAILED` for confirmed fraud / permanent inaccessibility / fraudulent customer submission. Reason + supporting evidence required; irreversible; refund policy applied; agents' completed work still logged.

### 8.5 Exit criteria

- End-to-end in staging: `PAID → IN_PROGRESS → UNDER_REVIEW → COMPLETED`.
- No report reaches a customer without explicit "Release Report".
- Reopen path (`APPROVED → IN_PROGRESS`) works from the release gate.

### 8.6 Reopened reports & trust-score recomputation

When a `COMPLETED` verification is reopened (`COMPLETED → IN_PROGRESS` via re-check, tier upgrade, or partially-upheld dispute), the already-released report and its trust score need defined behaviour.

**What the customer sees.** Two states only: the **current** report and **superseded** prior versions. During a reopen, the current report stays visible with a **"Revision in progress"** banner, computed from state (report is `RELEASED` while the verification is back in `IN_PROGRESS`) rather than stored as a separate mode; "final" language is suspended while the banner shows.

**Superseding.** When the new version is released, the prior version flips to `SUPERSEDED` — not before. The customer is notified on each release.

**Trust-score recomputation.** The composite trust score recomputes **only at release**, from the then-current agent scores and current admin-defined weights — one deterministic recomputation, no mid-flight changes.

**Versioning on reopen.** Any reopen that completes **bumps the version** (e.g., `v1.0 → v1.1`) and records a reason — including when content is unchanged (reason: "dispute reviewed, no change"). A monotonic version with a reason is simpler and more auditable than computing whether content "meaningfully" changed.

---

<a id="phase-9"></a>
## Phase 9 — Customer Tracking & Evidence Layer

**Depends on:** Phases 5–8.
**Goal:** The trust-building engine. Live progress + agent evidence. SSE transport (§4.9).

### 9.1 Tracking dashboard (`/portal/verifications/[id]`)

Header (VID, tier, status chip, address) · SLA tracker (expected date, elapsed/total, On track / Running late / Delayed+reason) · progress tracker (tier-adaptive steps + timestamps) · assigned agents (role + first name + verified badge only) · evidence preview (latest 3 + "View all") · messages preview · real-time via SSE with 60-sec polling fallback.

### 9.2 Customer-facing state labels

| Internal | Customer sees |
|---|---|
| `PAID` | "Payment Confirmed — Agents Being Assigned" |
| `IN_PROGRESS` | "Verification In Progress" |
| `UNDER_REVIEW` | "Under Review" |
| `COMPLETED` | "Completed ✅" |
| `DISPUTED` | "Dispute Under Review" |
| `FAILED` | "Could Not Be Completed" |
| `REFUNDED` | "Refunded" |

Task-level states collapse for customers: `PENDING/ASSIGNED/ACCEPTED` → "Pending"; `IN_PROGRESS/SUBMITTED/REJECTED` → "In Progress"; `APPROVED` → "Completed". The Lawyer row shows "Awaiting other stages" when its dependency is unmet.

### 9.3 State-specific expanded views

- **PAID** — "Payment confirmed — agents being assigned"; estimated start = payment + 24 hr; banner + admin alert if assignment SLA breached.
- **IN_PROGRESS** — progress %, stage breakdown (plain English), "Awaiting other stages" for blocked Lawyer; portable component reused on the list, detail page, and notification detail.
- **Interim interpreted reassurance.** As each task is approved, its completion is translated into customer-meaningful language rather than a bare status chip (e.g. *"✓ Registry check complete — the title document matches the seller's claim"*). This fills the anxiety gap between "I paid" and "I know" with *meaning*, not just motion. Two guardrails: clearly-positive milestones surface automatically; any **risk-bearing interim finding is withheld until admin review** so a negative is delivered only with context and never prejudices the final opinion, and an interim positive is framed as provisional ("so far, no issues found at this stage") so a later adverse finding does not read as a bait-and-switch. Admin may attach an optional one-line interim note per milestone.
- **UNDER_REVIEW** — 100% bar; "admin quality review in progress"; estimated report within the admin release SLA; copy frames the delay as intentional/quality-driven.

### 9.4 Evidence layer (`/portal/verifications/[id]/evidence`)

Chronological feed of agent uploads (photos, videos, documents, maps), tagged by **role not name**, with server-side timestamp + GPS and a **content hash (§4.5)**. Full-screen viewer with EXIF/metadata panel, **progressive low-res-first loading** for low-bandwidth viewers. On upload, images are compressed/resized for serving while the **full-resolution original is retained server-side** (so fine detail — document fine print, boundary markers — is never lost); the content hash (§4.5) is computed over the retained original. Evidence immutable after submission; server-side metadata trumps device EXIF; any alteration makes the stored content hash mismatch and is detectable.

### 9.5 Exit criteria

- Customer watches status advance in real time on a running staging verification.
- First-name-only rule enforced at the API layer, not just UI.
- Evidence tamper-evidence verified (content hash + server metadata).

---

<a id="phase-10"></a>
## Phase 10 — Final Report Experience

**Depends on:** Phase 8.
**Goal:** Deliver the product output — a defensible, shareable, downloadable report.

### 10.1 Features

- **Access gate modal** — one-time acknowledgement before first view, recorded against report version.
- **Header** — Verified badge, VID, report version, date, tier, address; actions (Download PDF / Share / Request Re-check).
- **Plain-language verdict (leads the report).** Above the collapsible detail, a human-voiced summary states, in plain terms, what the findings mean and what Veriprops would do — framed as professional opinion consistent with the disclaimer, never as instruction. This serves the anxious remote buyer: the report opens as counsel, not as an audit document. (Recommendation wording is on the §B legal sign-off list, since a strong steer — e.g. a low score that reads "we'd walk away" — must be carefully worded as opinion.)
- **Trust Score display** — numeric + band + meaning + "What does this mean?" tooltip (90+ Safe / 60–89 Caution / 0–59 High Risk).
- **Sections** (collapsible, tier-dependent): Executive Summary · Physical Findings (Standard+) · Registry & Title (all) · Boundary & Survey (Standard+) · Legal Opinion (Premium, with section disclaimer) · Risk Summary · **Customer-Submitted Documents Appendix** (distinguishes customer vs agent uploads; shows which roles referenced each; "did they look at what I sent?").
- **Legal footer** on every page and PDF page.
- **Downloadable PDF** — server-side, branded cover, TOC, all sections, evidence thumbnails, legal footer per page, QR to public lookup, re-downloadable anytime.
- **Report versioning** — `v1.0` / `v1.1` (minor admin revision) / `v2.0` (re-check) / `v3.0` (tier upgrade). Prior versions move to `SUPERSEDED` and render watermarked.

### 10.2 Exit criteria

- First real `COMPLETED` report rendered end-to-end.
- PDF parity with HTML — both carry the legal footer on every page.
- Superseding a report transitions the prior version's state correctly.

---

<a id="phase-11"></a>
## Phase 11 — Communication Layer

**Depends on:** Phase 8.
**Goal:** Structured, admin-mediated communication — audit-logged, fraud-scanned, never direct customer↔agent. SSE delivery, HTTP-POST sends (§4.9). Surfaced through the **Chat** top-nav icon (§N).

### 11.1 Channels

- **Customer ↔ Admin** (`/portal/verifications/[id]/messages`) — one thread per verification; system auto-posts status changes; attachments allowed; 2,000-char limit.
- **Admin ↔ Agent** (`/agent/verifications/[id]/messages` + admin mirror) — one thread per verification, **task-tagged** so messages about a specific role are filterable; a task rejection reason auto-posts (tagged to that task); admin can broadcast to all agents on a verification; a task's messages become read-only to the agent once that task is `APPROVED`.
- **Structured clarifications** — routine customer↔agent coordination (e.g., site-access details) flows as a **structured, fraud-scanned clarification request/response** within the relevant thread, without requiring an admin keystroke per exchange. The no-direct-contact and no-contact-leakage rules still apply; admin reviews only flagged exceptions.
- **General support** (`/portal/support`) — account/billing/general; can reference a VID (§N.2).

### 11.2 Message lifecycle & fraud detection (§4.7)

Messages follow `PENDING_SCAN → HELD → {APPROVED→DELIVERED | REJECTED→BLOCKED}` (or straight to `DELIVERED`). Send-time scan for phone, email, URLs, banking details, social handles, and "outside the platform" phrases. **Unflagged messages deliver immediately (fast lane)** — the scan is synchronous and most messages carry nothing to flag — so latency hits only the rare flagged message. A flagged message is **held** (single behaviour for MVP — severity tiers are a fast-follow once false-positive data exists, §4.7): the sender sees a non-accusatory notice (*"Just a moment while we check this through"*), the admin gets an alert with a snippet and Approves (deliver) or Rejects (block, warn). Repeated flags trigger account review. The false-positive rate is instrumented from day one; admin decisions are logged.

### 11.3 Agent identity display

Enforced at API: customer-facing endpoints return only `role`, `first_name`, `avatar_url`, `verified`.

### 11.4 Exit criteria

- No customer-facing endpoint returns agent last name, phone, or email.
- Held → approved/rejected message journey verified end-to-end (with the message state machine).
- Routine messages increment the Chat counter only; do not appear in Notifications (§N).

---

<a id="phase-12"></a>
## Phase 12 — Notification System & Event Bus

**Depends on:** can start at Phase 2 (basic), becomes critical at Phase 5+.
**Goal:** Keep every actor aware in real time, via one event bus (§4.8). Surfaced through the **Notifications** top-nav icon (§N).

### 12.1 Event bus & channels

Every domain event is published once (§4.8). The Notification projection consults a declarative rule table to fan out across:
- **In-app** — always on, cannot be disabled (SSE delivery).
- **Email** — per-event opt-out.
- **SMS** — per-event opt-out; high-signal events only.
- **Push** (Firebase/WebPush) — later enhancement.

### 12.2 Triggers

- **Customer:** payment confirmed · agents assigned · status change · new evidence · new admin message · SLA breach · report ready · new report version · refund initiated · re-check decision.
- **Agent:** new job · accepted/reassigned · admin revision request · payment update · verification feedback.
- **Admin:** SLA breach · report-ready · conflict flags · agent no-show · fraud-flagged messages · dispute filed · payment settled.

### 12.3 Chat-vs-Notification routing (top-nav FR-6/FR-7)

Routine chat messages increment the **Chat** counter only. **High-stakes events about a chat** (e.g., a dispute opened on a verification) fire a **system notification** *and* keep the underlying messages in Chat. This rule lives in the single §4.8 rule table.

### 12.4 Preferences

`/account/notification-preferences` (drawer) — toggle email/SMS per event type. In-app cannot be disabled.

### 12.5 Exit criteria

- All Phase 2–11 events flow through the bus to at least the in-app channel.
- Unit tests on fan-out (one event → multi-channel dispatch) and on the Chat-vs-Notification rule table.

---

<a id="phase-13"></a>
## Phase 13 — Public Lookup & Sharing

**Depends on:** Phase 10.
**Goal:** The shareable proof layer + growth surface.

### 13.1 Public lookup (`/verify/[id]`)

Unauthenticated. **Summary only:** VID, ✅ Verified badge, trust **band** (not number), tier, report date, property type, state & LGA, version. Never: full address, agent names, owner names, documents, numeric score.

States: shared → summary; private → "not enabled"; in-progress → "still in progress"; disputed → "under dispute review"; not-found → error. CTA "Start a verification →". `noindex` unless `COMPLETED` + public.

### 13.2 Sharing

| Mode | Who sees | Content |
|---|---|---|
| Private (default) | Customer only | Full report |
| Link-only | Anyone with link | Summary |
| Public | Anyone with VID | Summary |
| Named recipient | Specific email | Full report, time-limited, revocable |

30-day default expiry; revocable any time; recipients acknowledge the disclaimer on first view.

### 13.3 Exit criteria

- Public lookup renders for a real `COMPLETED` verification.
- Share-link revocation invalidates tokens immediately.

---

<a id="phase-14"></a>
## Phase 14 — Revision, Re-verification & Disputes

**Depends on:** Phase 10.
**Goal:** Handle real-world imperfection — re-checks, upgrades, disputes.

### 14.1 Re-check

Customer on a completed report: free-text reason + optional docs. Admin approves → new cycle for scoped tasks (reopening via `APPROVED → IN_PROGRESS` where needed); report bumps to `v2.0` (prior → `SUPERSEDED`). Pricing admin-configured.

### 14.2 Tier upgrade

Available on `COMPLETED` or `IN_PROGRESS`. Delta pricing only (`Upgrade Deltas` config). New tasks for added scope; existing approved tasks preserved; SLA extended; report bumps to `v3.0` with new sections. Idempotent on resubmit.

### 14.3 Dispute flow

- Window: `dispute_window_days` (default 30) after `COMPLETED`.
- Form: dispute type + description (≥100 chars) + optional evidence.
- Submit → `COMPLETED → DISPUTED`; admin reviews within 5 business days; **a system notification fires** (high-stakes chat event, §12.3).
- **Agent dispute-defence (when a dispute targets an agent's task):** the affected agent is notified and given a bounded-window response that the admin sees **before** resolving. The admin still decides. The channel is admin-mediated — the agent never learns the customer's identity or contact details. The agent's context often helps the admin resolve correctly and protects Veriprops if a commission clawback (§15.2) is later challenged.
- Outcomes: reject → `DISPUTED → COMPLETED`; uphold full refund → `REFUNDED`; uphold partial + free re-check → `DISPUTED → IN_PROGRESS` (new cycle).
- Admin resolution note mandatory, delivered verbatim to the customer.

### 14.4 Exit criteria

- All three dispute outcomes produce correct transitions and audit entries.
- Tier upgrade preserves existing approved tasks (idempotency on resubmit).

---

<a id="phase-15"></a>
## Phase 15 — Agent Earnings & Commission

**Depends on:** Phases 7–8 + Phase 4 (Finance Admin).
**Goal:** Transparent, actionable earnings. All money in integer minor units (§4.4).

### 15.1 Features

- **Earnings dashboard** (`/agent/earnings`) — **"Available to withdraw now" is the single hero figure**; "Clearing", "In reserve" (§15.2), "Lifetime", and "Total paid" are secondary, explained line items, so the agent anchors on the certain number rather than a fluctuating total. Per-job breakdown (Paid / Clearing / In reserve / On hold). The agent is **notified when money moves *to* available** (positive movement), not only when it is held or reversed. Payout timing (clearing + reserve) is explained at agent onboarding so it is an expectation, not a surprise.
- **Commission rules** — admin-configured per role × tier (`Commission rules`); visible to the agent on job detail before accept.
- **Payouts** (`/agent/payouts`) — "Request Withdrawal"; stored bank account or one-time entry; confirmation; 2-business-day SLA; withdrawal history with right-to-left detail drawer.
- **Finance payout panel** — approve / hold / adjust; approvals audit-logged.

### 15.2 Commission clearance hold (two-stage; not escrow)

Commission timing must not let money leave before the dispute/chargeback risk closes, while still keeping agents motivated.

- **Earned on `APPROVED`:** the moment a task is approved, its commission is shown to the agent as **"earned (clearing)"** — visible and motivating, and the commission amount is shown on the job-accept screen beforehand.
- **Withdrawable after a clearance period:** the commission becomes part of the **available** (withdrawable) balance only after a per-task **clearance window** (`commission_clearance_days`, configurable; shorter than the full `dispute_window_days`, e.g. tied to task SLA + a buffer). The "clearing" label is honest and visible — never presented as immediately withdrawable.
- **Chargeback-window reserve:** because the card chargeback window (network-dependent, ~90–120 days) far outlasts `dispute_window_days`, the bulk of the commission becomes withdrawable after `commission_clearance_days`, but a small percentage (`commission_reserve_pct`) is **retained in reserve** until the chargeback window closes, to absorb a late reversal. The reserve is disclosed at job-accept and shown as its own earnings line.
- **Freeze on dispute/chargeback:** a dispute (§14) or a chargeback (§6a) on the verification **freezes** related clearing commissions until resolution; an upheld dispute or lost chargeback **reverses** them (clawed back from clearing, available, or reserve as needed).
- **This is a ledger state, not escrow.** It is a delayed-payout rule on funds Veriprops already holds — it does not hold third-party funds in trust and carries no trust-account or escrow-licensing implications. (The Post-MVP "Escrow / Transaction Layer" is a separate, regulated product concerning the *property purchase* between buyer and seller, not commissions.)
- **Residual risk accepted:** a clearance window shorter than the dispute window leaves bounded tail risk (a late dispute after payout). This is a deliberate trade of small, bounded loss against agent-retention — the product's stated priority.

### 15.3 Exit criteria

- Sample agent requests and receives a payout end-to-end in staging.
- Commission rules configurable without code change; payout math reconciles to the kobo.

---

<a id="phase-16"></a>
## Phase 16 — Agent Reputation & Coverage

**Depends on:** Phase 8.
**Goal:** Quality control + smart assignment via performance data.

### 16.1 Features

- **Metrics** — completion rate, accuracy score (1–5 admin-assigned), timeliness (`task_sla_hours`).
- **Profile** — aggregated metrics, total jobs, active since, coverage.
- **Assignment ranking** — admin's suggested list ranks by composite score.
- **Thresholds** — `agent_low_performance_threshold` reduces job-feed visibility; `agent_top_agent_accuracy_threshold` earns a "Top Agent" badge (admin-visible only).
- **Coverage settings (declared, with guardrails — not a residence cap)** — agents declare states + LGAs + max travel distance; immediate effect on new matching; Nigeria map preview. A new agent's coverage **defaults to their residence state** (a sensible default, *not* a hard limit). Agents may **add** states; unusually wide coverage is **flagged for admin review** rather than forbidden. Coverage is **role-differentiated:** Field/Surveyor are genuinely location-bound (tighter defaults; GPS-proximity matters), while Registry and Lawyer are far less so (looser; registry work can be effectively remote). The real control against "agent wasn't actually there" is **proof-of-presence evidence** (§7.3a), which checks *what happened*, not *where the agent lives* — a residence cap would throttle the scarce, multi-state supply (licensed Surveyors/Lawyers) the marketplace depends on.
- **Availability** — 🟢/🟡/🔴; auto-🔴 at `agent_max_active_tasks`.
- **Role-specific dashboards** — Field/Surveyor → map+nearby; Registry → document list; Lawyer → "waiting for other agents" queue + legal-opinion queue with dependency status bar.

### 16.2 Exit criteria

- Suggested-agent list orders correctly on a test dataset.
- Lawyer dashboard visibly gates on dependency (§4.2).

---

<a id="phase-17"></a>
## Phase 17 — Growth & Conversion

**Depends on:** Phases 5, 10.
**Goal:** Compound acquisition; reduce abandonment.

### 17.1 Features

- **Referral** — unique links; invitee gets first-time discount; referrer gets `referral_credit_ngn`; credit shown on dashboard, auto-applied at checkout, capped at `max_discount_percent`. **Anti-farming:** discount/credit eligibility requires a **distinct verified human** — unique verified phone *and* unique payment instrument (card fingerprint); self-referral via duplicate phone/card is rejected. **Referrer credit does not pay out until the invitee's payment clears the chargeback-window reserve** (§15.2), closing the refer-then-charge-back loop. Determined multi-SIM/multi-card rings are reduced, not eliminated; deeper device-graph detection is post-MVP if abuse appears.
- **First-time discount** — `first_time_discount_percent`, auto-applied, never a code, visible in the breakdown.
- **Abandoned-verification recovery** — 24-hour banner + one email; draft preserved; price lock refreshed if >24 hr. **Re-lock guard:** if the refreshed price differs from the previously shown price, an explicit **"price updated"** interstitial is shown before payment — the customer is never silently charged a new amount. This protects the "no payment surprises" promise the price lock exists to deliver.

### 17.x Removed from MVP — Listing-URL import

The listing-URL import (paste a PropertyPro / Nigeria Property Centre link to pre-fill the wizard) is **removed from MVP**: it is brittle third-party scraping that breaks on layout changes and is liable to be blocked, for near-zero user benefit (customers can type the address). It may return post-MVP as an explicitly best-effort convenience, never a relied-upon path. Manual entry is the sole MVP source (§5.1).

### 17.2 Exit criteria

- Credit balance displays and applies correctly at checkout.
- Abandonment email fires exactly once per abandoned draft.
- Re-lock price change triggers the "price updated" interstitial before payment.

---

<a id="phase-18"></a>
## Phase 18 — Admin Operations & Analytics

**Depends on:** Phases 5–16.
**Goal:** Strategic controls to run and evolve the business. (Full menu in §M.)

### 18.1 Surfaces

- **Mission Control** — active verifications, pending assignments, stuck jobs, SLA-at-risk, revenue, available agents; action items (pending agent applications, pending team invitations).
- **Analytics** — conversion funnel, avg verification time by tier, agent performance trends (6 mo), revenue by location & tier, regional performance (active/completed, avg trust score, revenue by state).
- **Pricing & Tier Config** — tier pricing + line items (next-quote effect), upgrade deltas.
- **Finance** — payments (filter status/method), commissions (by status/period), payouts (approve/hold/adjust).
- **Commission rules** — % per tier × role.
- **Broadcasts** — audience (All/Admins/Customers/Agents), compose, preview, send now or schedule; manage.
- **System configuration** — Trust Score Weights (per tier/role, sum 100%) + the General configuration keys (§A).
- **Data Erasure Requests** — Pending / Approved / Executed / Rejected / All (NDPA).

### 18.2 Exit criteria

- All pricing controls change downstream customer pricing without a deploy.

---

<a id="phase-19"></a>
## Phase 19 — Audit & Compliance Maturity

**Depends on:** all prior phases.
**Goal:** Harden the audit layer into a legal evidence system.

### 19.1 Features

- Full audit export per verification (PDF/CSV) — admin only — incl. evidence content hashes.
- Customer-facing simplified activity log; agent-facing task transition history.
- Versioned consent records downloadable per user.
- Fraud-flag review history; admin action logs (permission/role changes, payout approvals).
- **Data erasure** workflow per NDPA: `pii_retention_days`, `erasure_request_review_sla_days`.

### 19.2 Retention

Indefinite for audit logs and consent records; PII subject to the retention policy.

### 19.3 Exit criteria

- Admin can export a legally defensible pack for any VID: verification record + all transitions + consent snapshots + message history + dispute record + refund record + evidence content hashes.

---

<a id="post-mvp"></a>
## Post-MVP Roadmap

| Initiative | Description |
|---|---|
| **Property Identity Layer** | Build the market-wide layer on the already-separate Property entity (§4.3): price & ownership history, multiple verifications per property, dedup intelligence. |
| **Escrow / Transaction Layer** | Facilitate the purchase itself — hold funds, release on title transfer. |
| **Deep Trust & Anti-Fraud** | Cross-verification pattern detection, document-hash registry, fraudulent-seller database. |
| **Verification Academy / Content Hub** | "How land scams work", "How to read a survey plan"; tooltips expanded into courses. |
| **Auto-assignment AI** | Ranked auto-assignment subject to admin override (beyond the Phase 6 broadcast model). |
| **WhatsApp delivery** | OTP and notifications via a new event-bus subscriber. |
| **Mobile apps (iOS/Android)** | Native parity for customers and field agents. |

---

# Part III — Navigation, Menus & Supporting Artefacts

<a id="n-top-navigation"></a>
## N. User-Area Top Navigation

Persistent global access in the top-right, fixed order **Support → Chat → Notifications → Account**. Replaces an earlier bell+envelope layout: the envelope is removed; Support (headset) and a dedicated Chat entry are introduced; conversations are separated from the notifications feed. This model supersedes earlier entry-point descriptions wherever they conflict.

| Element | Icon | Counter | Behaviour |
|---|---|---|---|
| **Support** | Headset | None | Navigates to the Support page |
| **Chat** | Chat bubble | Yes | Opens the conversation list |
| **Notifications** | Bell | Yes | Opens a dropdown of new notifications |
| **Account** | Avatar + first name | None | Opens dropdown (Account settings, Logout) |

### N.1 Counter rules (Chat & Notifications)

- Numeric badge of unread/new items; caps at **"9+"**; hidden entirely at zero (no "0").
- Support and Account never show a counter.

### N.2 Support

Headset icon → Support page presenting an **FAQ** section plus routing into the appropriate chat: **verification-specific** support routes through that verification's own chat/dispute thread; **general** enquiries route through the general chat. Direct navigation, no dropdown.

### N.3 Chat

Counter = number of conversations with unread messages (9+ max, hidden at zero). Opening a conversation marks it read and decrements. Chat carries **all person-to-person conversations** (verification/dispute threads + general chat). Chat messages **do not** appear in Notifications. New inbound message increments the Chat counter only (exception: high-stakes events, §N.4). Delivered over SSE (§4.9).

### N.4 Notifications

Bell → dropdown of new (unread) system updates, with "View all" / "All notifications" → full history page. Counter = number of new notifications. The feed contains **in-app system updates only**; routine chat messages are never listed. **High-stakes events about a chat** (e.g., a dispute opened on the user's verification) generate a system notification while the underlying messages stay in Chat. SSE-backed (§4.9), driven by the §4.8 rule table.

### N.5 Account

Avatar (photo or placeholder) + first name → dropdown with **Account settings** and **Logout**. Account settings sections each open as a **right-to-left drawer**:

| Section | Contents |
|---|---|
| Personal info | Personal details and contact |
| Login & security | Password, linked social accounts, connected devices, security activity |
| Data & privacy | Manage personal data per **NDPA** |
| Wallet & payments | Add withdrawal bank account |
| Agent settings | Roles, KYC, credentials |
| Notification preferences | Per-event email/SMS toggles |
| Global preferences | Default language, currency, timezone |

### N.6 Functional requirements

| ID | Requirement |
|---|---|
| FR-1 | Top nav displays, left→right: Support, Chat, Notifications, Account. |
| FR-2 | Support uses a headset icon, no counter, navigates to the Support page. |
| FR-3 | Support page presents FAQ and routes verification-specific support to the relevant verification chat/dispute, general enquiries to the general chat. |
| FR-4 | Chat shows a counter of conversations with unread messages and opens the conversation list. |
| FR-5 | Notifications shows a counter of new notifications and opens a dropdown with "View all" / "All notifications". |
| FR-6 | The Notifications feed contains system updates only; not routine chat messages. |
| FR-7 | High-stakes events about a chat (e.g., dispute opened) generate a system notification. |
| FR-8 | Counters are numeric, cap at "9+", hidden at zero. |
| FR-9 | Account shows avatar + first name and opens a dropdown with Account settings and Logout. |
| FR-10 | Account settings sections each open in a right-to-left drawer. |

---

<a id="m-menu-maps"></a>
## M. Portal / Agent / Admin Menu Maps

### M.1 Customer Portal (`/portal`)

1. **Dashboard** — welcome; if no verification, nudge ("Your first verification is one step away…") with **[Verify a Property]**; if verifications exist, show stats + active list.
2. **My Verifications** — list filtered ALL / Active / Completed / Cancelled; **[New Verification]**; row click → right-to-left detail drawer (progress, disputes, chat thread with admin).
3. **Payment History** — list; row click → right-to-left drawer (state transitions).

### M.2 Agent (`/agent`)

- **Top menu:** "active to receive tasks" toggle.
1. **Dashboard** — stats (Total Jobs, Accuracy x/5, Timeliness %, Completion %, Available Earnings, Completed[Approved/Under Review/Total]); My Active Tasks; Available Jobs.
2. **My Tasks** — filtered Active / Under review / Completed / All; row click → drawer (state transitions, disputes, chat thread with admin).
3. **Earnings** — stats (Available, Lifetime, Pending, Total paid); Job Breakdown.
4. **Payouts** — **[Request Withdrawal]**; Withdrawal History; row click → drawer (progress).
5. **Onboarding** — Roles (Field/Registry/Surveyor/Lawyer-NBA); KYC (BVN + provider liveness/face-match); Credentials (licence, experience, bio, coverage via Google Place); Review (accept accuracy + agent terms, submit).

### M.3 Admin (`/admin`)

1. **Dashboard** — Mission Control (active verifications, pending assignments, stuck jobs, SLA at risk, total revenue, available agents); Action items (pending agent applications, pending team invitations).
2. **Analytics** — conversion funnel; avg verification time by tier; agent performance trends (6 mo); revenue by location & tier; regional performance.
3. **User management** — Team (admins, [Invite Admin]); Agents (approve/reject; pending blocks jobs); Customers; Users.
4. **Verifications** — manage/review all; filter status & tier.
5. **Disputes** — manage disputes.
6. **Re-check requests** — manage.
7. **Commission rules** — % per tier × role.
8. **Pricing** — Pricing Management (tier pricing + line items, next-quote effect); Upgrade Deltas.
9. **Finance** — Payments; Commissions; Payouts.
10. **Broadcasts** — New (audience, compose, preview, send now/schedule); manage.
11. **Admin Audit Log** — filter by date range & action types.
12. **Data Erasure Requests** — Pending / Approved / Executed / Rejected / All.
13. **System configuration** — Trust Score Weights (per tier/role, sum 100%); General configuration (§A.2).

---

<a id="a-resolved-decisions"></a>
## A. Resolved Decisions

**Status legend:** **Decided** = policy locked. **Default set** = a working default exists in config but the *number/policy* still needs business sign-off (a default is not an approval).

### A.1 Product & architecture decisions (Decided)

| # | Decision |
|---|---|
| 1 | Product name **Veriprops**. |
| 2 | Structure: phased spine (0–19) + module cross-reference index. |
| 3 | State machines per §2 are authoritative, incl. admin-reopen `APPROVED → IN_PROGRESS` and auto-assign `PENDING → ACCEPTED`. |
| 4 | Report states `DRAFT / RELEASED / SUPERSEDED`. |
| 5 | OAuth popup-only; redirect is the popup-blocked fallback. |
| 6 | Top-nav model (Support/Chat/Notifications/Account) wins; envelope removed. |
| 7 | Menu docs (indexes 6 & 7) are identical; treated as one. |
| 8 | KYC: BVN primary, government-ID fallback; **liveness + face-match deferred to provider** (Dojah default, behind a facade). |
| 9 | No event sourcing; single state-derivation owner (§4.1); per-item evidence hash (§4.5); payment idempotency + optimistic locking (§4.6); integer minor units (§4.4). |
| 10 | Property separated from Verification (§4.3); MVP does not auto-dedup. |
| 11 | In-process event bus from Phase 12 (§4.8). |
| 12 | SSE for all server→client pushes (chat receive, notifications, status); HTTP-POST sends; no live-presence affordances in a mediated chat (§4.9). |
| 13 | Message lifecycle with a single-tier fraud hold for MVP; severity tiers deferred until false-positive data exists (§4.7). |
| 14 | **Gateway-mediated collection** (Paystack/Flutterwave behind the provider facade): Veriprops never handles raw card/bank credentials; NGN contractual and **NGN-settled by default**; customers may pay in USD/GBP/EUR via international card (gateway-converted); webhooks drive `PAYMENT_PENDING → PAID`; no direct SWIFT/IBAN wire at MVP; contractual NGN stored separately from charge/settlement fields. |
| 15 | Compliance references **NDPA** for data & privacy. |
| 16 | Area Insights authored by **admin only** (D21 resolved). |
| 17 | Notification semantics: routine messages → Chat counter only; high-stakes chat events → system notification (FR-6/FR-7). |
| 18 | **Chargebacks** modelled as a payment-side flag + sub-process (§6a), never a verification state; rebuttal pack auto-assembled from audit artefacts. |
| 19 | **Commission clearance hold** (§15.2): earned on `APPROVED`, withdrawable after `commission_clearance_days`, frozen on dispute/chargeback. **Explicitly not escrow** — a ledger rule on funds already held. |
| 20 | **Reopened-report behaviour & trust-score recomputation** defined (§8.6): report stays visible with a revising banner; supersede at next release; score recomputes once at release; no-change outcomes annotate rather than version-bump. |
| 21 | **Proof-of-work evidence class** (§7.3a): system-stamped proof-of-presence (required, on-site roles), property-identity confirmation (required, on-site roles), optional admin-only NDPA-governed contact-person, per-task conflict-of-interest declaration (all roles). |
| 22 | **Agent dispute-defence** (§14.3): affected agent notified and given a bounded response before resolution, admin-mediated, admin still decides. |
| 23 | **Credential expiry & re-attestation** (§3.3a): tracked expiry, role-level (not account-level) suspension, periodic identity re-attestation. |
| 24 | **Admin work queue + responsiveness SLAs** (§6.4): unified prioritised queue, customer first-response SLA, held-message auto-escalation, explicit staffing assumption. |
| 25 | **Address input** (§5.1): Google Places primary behind a geocoding facade + **mandatory landmark escape valve**; Places-only never a hard gate. **Agent coverage** (§16): declared coverage with residence-state **default** and role-differentiated guardrails — **not** a residence cap. Listing-URL import **removed from MVP** (§17.x). |
| 26 | **Non-sequential high-entropy VIDs + public-lookup rate-limiting + indistinguishable responses** (§4.10) close the enumeration/scraping surface. |
| 27 | **Idempotency keys cover payments *and* entity creation** (draft, re-check, dispute, payout); optimistic locking covers updates (§4.6). |
| 28 | **Audit pseudonymisation on NDPA erasure** (§4.11): sever identity, retain the event; erasure recorded as an event. |
| 29 | **Commission chargeback-window reserve** (§15.2): a small `commission_reserve_pct` held until the ~90–120-day chargeback window closes, beyond the dispute-window clearance. Referral credit waits on the same reserve (§17.1). |
| 30 | **Referral anti-farming** (§17.1): eligibility requires a distinct verified human (unique phone + unique card fingerprint). |
| 31 | **Onboarding lightened** (§2.1): email verified at signup; **phone OTP deferred to first payment** (§5.4); country/timezone/currency collected progressively. **Job-pool starvation backstop + accept-time cap** (§7.2). **Chat fast-lane** for unflagged messages (§4.7). **Cross-portal count badge** for multi-role users (§3.4). **Supportive report verdict** (§10.1) and **interim interpreted reassurance** (§9.3). **Low-bandwidth weight budgets** with full-res originals retained (§5 cross-cutting, §9.4). |

### A.2 Configuration defaults (Default set — needs business sign-off where noted)

These exist as admin-configurable keys with defaults; the **mechanism is built**, but the starting values are placeholders pending sign-off.

| Key | Meaning | Status |
|---|---|---|
| `cancellation_surcharge_pct` | Surcharge on cancellation after assignment | Default set; sign-off |
| `first_time_discount_percent` | Auto first-verification discount | Default set; sign-off |
| `referral_credit_ngn` | Referrer credit on invitee's first payment | Default set; sign-off |
| `max_discount_percent` | Combined discount cap (referral + first-time) | Default set; sign-off |
| `no_show_timeout_hours` | Hours post-acceptance, no evidence, before no-show alert | Default set |
| `pool_timeout_hours` | Hours a PENDING task stays unclaimed before alert | Default set |
| `auto_assignment_enabled` | Auto-create + broadcast tasks at PAID | Decided (mechanism) |
| `agent_max_active_tasks` | Max concurrent active tasks before auto-UNAVAILABLE | Default set |
| `agent_low_performance_threshold` | Completion % below which job visibility is reduced | Default set |
| `agent_top_agent_accuracy_threshold` | Accuracy (1–5) at/above which the Top Agent badge is earned | Default set |
| `task_sla_hours` | Hours from acceptance counted as on-time | Default set |
| `dispute_window_days` | Dispute window after COMPLETED (default 30) | Default set |
| `pii_retention_days` | PII retention before NDPA erasure window (≈7 years) | Default set; legal |
| `erasure_request_review_sla_days` | SLA to review an erasure request | Default set |
| `commission_clearance_days` | Per-task clearance window before commission becomes withdrawable (< `dispute_window_days`) | Default set; sign-off |
| `credential_expiry_lead_days` | Lead time before credential expiry triggers an agent flag | Default set |
| `reattestation_cadence_days` | Cadence for agent identity (BVN/ID) re-attestation (default annual) | Default set |
| `customer_first_response_sla_hours` | First-response target on Customer↔Admin threads | Default set; sign-off |
| `held_message_escalation_hours` | Age at which a fraud-held message auto-escalates | Default set |
| `same_day_capture_required` | Whether on-site evidence must be captured the day of submission | Decided (on-site roles) |
| Trust Score Weights | Per tier × role, must sum to 100% | Default set; sign-off |
| `area_insights_owner` | 'admin' only | Decided |
| `commission_reserve_pct` | % of commission held until the chargeback window closes | Default set; sign-off |
| `chargeback_window_days` | Reserve-release horizon (network-dependent, ~90–120) | Default set |
| `lookup_rate_limit_per_min` | Public-lookup requests per IP per minute | Default set |
| `sla_shed_queue_depth` | Admin-queue depth above which customer SLAs auto-extend | Default set; sign-off |
| `remote_job_bonus_ngn` | Optional flat bonus on aging/hard-to-reach broadcast tasks | Default set (off by default) |

---

<a id="b-open-items"></a>
## B. Open Items

Genuinely unresolved — needs **business or legal**, not engineering.

| # | Item | Needs | Blocks |
|---|---|---|---|
| 1 | **Exact tier pricing** (Basic/Standard/Premium) + per-line-item figures | Business sign-off | Phase 5 go-live pricing |
| 2 | **Default settlement currency** — NGN-only at MVP, vs. enabling USD retention (Flutterwave USD settlement / Paystack Zenith dom-account pilot) | Business / treasury | Settlement config (post-MVP optional) |
| 3 | **Verification Disclaimer final copy** (Step 3 item ①) | Legal sign-off | Precedes Phase 5 |
| 4 | Re-check pricing model (flat / per-agent / % of original) | Business | Phase 14 |
| 5 | FX rate source for indicative display (live API vs admin-set) | Business / Eng | Phase 5 display |
| 6 | Initial automated conflict-detection rule set | Ops / Eng | Phase 8 |
| 7 | Confirm SMS provider (Termii vs Twilio) | Eng | Phases 2 / 12 |
| 8 | **Multi-currency account/provider routing** — which gateway account/provider handles each currency behind the facade (single account where supported vs separate accounts) | Eng / Ops | Phase 5 international card |
| 9 | International card fee (~3.8–3.9%) absorbed vs. surfaced — fold into pricing | Business | Phase 5 pricing |
| 10 | **Admin staffing commitment** — N admins per M verifications/day; a **hard pre-launch gate** for the §6.4 SLAs, not an aspiration | Business / Ops | Launch |
| 11 | **Report verdict wording** — the plain-language recommendation lead (§10.1) must be worded as opinion, not advice | Legal sign-off | Phase 10 |
| 12 | **Audit pseudonymisation retention basis** — confirm the post-erasure legal basis and re-identification risk (§4.11) | Legal sign-off | Phase 19 |
| 13 | **Commission reserve %** and **chargeback-window length** — set `commission_reserve_pct` / `chargeback_window_days` | Business / Finance | Phase 15 |
| 14 | **Limitation-of-liability cap** — final clause copy: 1× fees paid + fraud / willful-misconduct / non-waivable carve-outs (§3.5) | Legal sign-off | Phase 5 |
| 15 | **Agent PI-insurance posture** — IC + AGENT_TERMS indemnity locked (§3.5); decide agent-carried vs. platform-carried cover. Lawyer-role cover is a **hard gate** before the Premium Legal Opinion tier (§3.5) | Legal / Business | Phase 5 (structure built); **Premium tier** (lawyer insurance) |
| 16 | **Governing law + forum clause** — Nigeria courts locked (§3.5); confirm cross-border enforceability **per target market** (UK / US / CA); revisit arbitration only if claim volume warrants | Legal sign-off (per-market) | Phase 5 (clause); per-market as volume warrants |
| 17 | **Premium Legal Opinion ownership** — individual-lawyer-owns / Veriprops-transmits framing locked (§3.5); confirm against NBA / Nigerian regulatory rules | NBA-aware counsel | Phase 10 |

> Note: previously-open KYC-provider, currency-model, wire-buffer, dispute-window, discount, and listing-parser questions are now **resolved or removed** (§A, §17.x) and are no longer listed.

---

<a id="c-success-metrics"></a>
## C. Success Metrics

| Metric | Definition | Target |
|---|---|---|
| Avg completion time | `PAID` → `COMPLETED`, by tier | Basic ≤5d · Standard ≤7d · Premium ≤10d |
| % completed without task revision | No task ever hit `REJECTED` | > 80% |
| Median task acceptance time | `ASSIGNED`/broadcast → `ACCEPTED` | < 2 hours |
| Agent no-show rate | Tasks timed out unaccepted | < 5% |
| SLA breach rate | Exceeded tier SLA | < 10% |
| Customer trust rating | Post-report satisfaction (1–5) | ≥ 4.5 |
| Admin report release time | All tasks `APPROVED` → released | < 4 hours |
| Message false-positive rate | Held messages later admin-approved | Track & minimise (§4.7) |
| Chargeback rate | Card chargebacks ÷ paid verifications | Track & minimise (§6a) |
| Chargeback win rate | Chargebacks won with the auto-assembled rebuttal pack | Maximise (§6a) |
| Customer first-response time | Median admin first response on Customer↔Admin threads | Within `customer_first_response_sla_hours` |
| Pool-starvation rate | Broadcast tasks hitting the §7.2 starvation backstop | Low; track underserved areas |
| SLA-shed frequency | How often the §6.4 graceful-shedding fires | A staffing signal, not a target |
| Signup → payment conversion | First-verification activation | TBD |
| Abandoned-draft recovery rate | Drafts paid within 7 days of abandonment | TBD |

---

<a id="d-hardening-backlog"></a>
## D. Hardening Backlog

Operational disciplines that cannot be fully solved on paper — they need real data and tuning. The PRD's job is to give each a home and an owner, not to pretend the spec eliminates the risk.

| Item | MVP coverage | Post-MVP target | Owner |
|---|---|---|---|
| **Insider agent fraud** | Deterred via per-task conflict-of-interest declaration (§7.3a) + system-stamped proof-of-presence + sibling conflict detection (§8.2) | Pattern detection (reused EXIF, implausible GPS clusters, statistically too-clean scores) in the Deep Trust layer | Ops / Eng |
| **Admin capacity** | Prioritised work queue + staffing assumption (§6.4) | Trust-gated auto-approval for high-accuracy agents | Ops |
| **Chargeback win rate** | Auto-assembled rebuttal pack (§6a) | Tuned evidence templates per chargeback reason code | Finance / Ops |
| **Offline field capture** | Field/Surveyor priority, last-write-wins draft + server-authoritative submit (§7.4) | Robust conflict UX, partial-upload resumption | Eng |
| **Refund reverse-FX goodwill** | Goodwill top-up on Veriprops-at-fault refunds (§3.5) | Policy refinement once refund volume is observed | Finance |
| **Job-pool fairness** | Starvation backstop + accept-time cap + optional remote bonus (§7.2) | Dynamic per-job commission uplift if starvation persists | Ops |
| **Referral abuse** | Distinct-human gate: unique phone + card fingerprint (§17.1) | Device-graph detection if rings appear | Ops / Eng |
| **FX-surprise support load** | NGN-prominent + concrete ±range disclosure (§5.2) | Migrate cards to real per-currency prices (Model C) if tickets climb | Business |
| **Admin staffing** | Hard pre-launch gate + graceful SLA shedding (§6.4) | Trust-gated auto-approval (first post-launch priority) | Business / Ops |

---

*Master PRD consolidated from the product brief, Auth & Onboarding PRD v1.1, Verification Lifecycle PRD v2.0, Top-Navigation PRD v1.0, and the menu specifications. State machines in §2 and architecture decisions in §4 are authoritative over all prose. Phases 0–10 (plus 6a) constitute the MVP cut line.*