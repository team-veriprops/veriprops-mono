# Veriprops — Product Requirements Document

**Product:** Veriprops ("Verified Properties")
**Audience:** Nigerians in the diaspora (primary) and Nigerians in Nigeria, verifying real estate within Nigeria
**Stack:** FastAPI (Python 3.12, PostgreSQL, async SQLAlchemy, Alembic, Kink DI) backend · Next.js 16 (App Router, React 19, Tailwind v4, Zustand, TanStack Query) frontend
**Currencies:** NGN (contractual base), USD, EUR, GBP
**Version:** 3.0 — as-built consolidation (supersedes the v2.4 phased draft)
**Status:** Living document — describes the shipped product
**Last updated:** 12 July 2026

> **v3.0 rewrites this document around the product that exists.** v2.4 was a forward-looking plan organized
> as implementation phases (0–19); all of those phases have since been implemented and live-verified by
> scripted end-to-end drive-throughs ([docs/final-audit.md](docs/final-audit.md)). This version describes
> current behaviour as fact, sourced from the code. Where implementation decisions diverged from the v2.4
> plan, the as-built behaviour is written here and the full decision rationale lives in
> [docs/decision-log.md](docs/decision-log.md) (D1–D41). Deliberately deferred work is consolidated in
> [Known Gaps & Roadmap](#g-known-gaps) and marked `TODO(gap):` at its code location.

---

## How to read this document

- **Part I — Foundations**: vision, actors & legal framework, the authoritative state machines, and the
  cross-cutting architecture. §3 (state machines) and §4 (architecture) are authoritative over all prose.
- **Part II — Product Modules** (§6–§25): the product organized by module, matching how the codebase is
  organized by domain. Each module states what exists, its key flows, its configuration knobs, and any
  current limitation as plain fact.
- **Part III — Reference**: navigation & menus (§N), the configuration reference (§R), Known Gaps & Roadmap
  (§G), the v2.4 phase → module map (§X), and success metrics (§C).
- Code comments and older docs that cite "§14", "Phase 7" etc. refer to **v2.4 phase numbering** — translate
  via the [phase map](#x-phase-map).

## Table of Contents

**Part I — Foundations**
- [1. Vision & Strategy](#1-vision)
- [2. Actors, Roles & Legal Framework](#2-actors)
- [3. State Machines (Authoritative)](#3-state-machines)
- [4. Platform Architecture](#4-architecture)
- [5. Cross-Cutting Concerns](#5-cross-cutting)

**Part II — Product Modules**
- [6. Marketing Site & Public Web](#6-marketing)
- [7. Auth, Accounts & Sessions](#7-auth)
- [8. Agent Onboarding & KYC](#8-agent-onboarding)
- [9. Admin Onboarding & RBAC](#9-admin-rbac)
- [10. Customer Submission & Payment](#10-submission-payment)
- [11. Verification Operations (Admin)](#11-verification-ops)
- [12. Agent Task Execution](#12-task-execution)
- [13. Review, Trust Score & Report Release](#13-review-release)
- [14. Customer Tracking & Evidence](#14-tracking)
- [15. Report Experience](#15-report)
- [16. Communication](#16-communication)
- [17. Notifications & Event Bus](#17-notifications)
- [18. Public Lookup & Sharing](#18-lookup-sharing)
- [19. Re-check, Tier Upgrade & Disputes](#19-aftermarket)
- [20. Agent Earnings, Commissions & Payouts](#20-earnings)
- [21. Agent Reputation & Coverage](#21-reputation)
- [22. Growth & Conversion](#22-growth)
- [23. Admin Operations & Analytics](#23-admin-ops)
- [24. Audit & Compliance](#24-audit-compliance)
- [25. Dev, Automation & QA](#25-dev-qa)

**Part III — Reference**
- [N. Top Navigation & Portal Menus](#n-navigation)
- [R. Configuration Reference](#r-configuration)
- [G. Known Gaps & Roadmap](#g-known-gaps)
- [X. Appendix: v2.4 Phase → Module Map](#x-phase-map)
- [C. Success Metrics](#c-success-metrics)

---

<a id="1-vision"></a>
# Part I — Foundations

## 1. Vision & Strategy

### 1.1 Mission

Make **"verified property"** the default belief in the Nigerian real-estate market. End state: *"If it's
not verified, nobody buys it."*

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
- **Verification ID (VID)** — unique public-safe identifier (`VP-YYYY-XXXXXX`, high-entropy suffix, §4.10),
  shareable, the canonical anchor for all downstream artefacts.
- **Trust Score** — weighted composite (0–100) per report: 90+ Safe / 60–89 Caution / 0–59 High Risk.
- **Task** — a role-scoped unit of work (Registry / Field / Surveyor / Lawyer) belonging to a verification.
- **Report** — the versioned output (`v1.0`, `v1.1`, `v2.0`, …) — a professional opinion, not a guarantee.
- **Property** — a first-class entity distinct from the verification (§4.3); a property may be verified more
  than once over time.

### 1.4 Tier → task matrix

Defined as data in `backend/main/app/core/state/dependencies.py` (`TIER_ROLES`) and
`backend/main/app/core/sla.py`:

| Tier | Registry | Field | Surveyor | Lawyer | Required tasks | SLA (business days from `PAID`) |
|---|---|---|---|---|---|---|
| `BASIC` | ✅ | — | — | — | 1 | 5 |
| `STANDARD` | ✅ | ✅ | ✅ | — | 3 | 7 |
| `PREMIUM` | ✅ | ✅ | ✅ | ✅ | 4 | 10 |

The Lawyer task is **dependent**: it unlocks only after all non-lawyer tasks reach `SUBMITTED`, and is not
even instantiated as a row until then (§4.2). Business days use the Nigerian holiday calendar (§4.11).

---

<a id="2-actors"></a>
## 2. Actors, Roles & Legal Framework

### 2.1 Actor types

| Actor | Description | Created via |
|---|---|---|
| **Customer** | Submits and pays for verifications | Self-signup |
| **Agent** | Independent contributor — Field / Surveyor / Registry / Lawyer | Self-signup + KYC + admin approval |
| **Admin** | Operates the platform | Admin invite only (plus the seeded first Super Admin) |

### 2.2 User data model — two orthogonal role fields

Implemented on `User` (`backend/main/app/domain/user/models.py`). These must **not** be conflated.

| Field | Values | Mutability |
|---|---|---|
| `user_type` | `USER` / `ADMIN` | Immutable after creation, with **one sanctioned exception**: accepting a valid admin invitation elevates a `USER` to `ADMIN` (§9.2). Controls admin-portal access — every admin endpoint gates on `user_type == ADMIN`. |
| `personas` | list of `CUSTOMER`, `AGENT` | Mutable, additive. Controls portal routing. |

A user may hold both `CUSTOMER` and `AGENT`. Signup intent (`AuthIntent`: `default` / `verify` / `agent` /
`invited-admin`) sets the initial persona.

#### Agent sub-types (`AgentRole`)

| Role | Responsibility | Required credential (`ROLE_REQUIRED_CREDENTIAL`) |
|---|---|---|
| `FIELD` | Physical site inspection | — |
| `SURVEYOR` | Boundary & location confirmation | `SURVEYOR_LICENCE` |
| `REGISTRY` | Registry search | — |
| `LAWYER` | Title verification, ownership, legal opinion, encumbrances & risk | `NBA_LICENCE` |

#### Admin sub-roles (`AdminSubRole`)

| Sub-role | Capabilities |
|---|---|
| `SUPER` | Full access (holds every `Permission`, including the SUPER-only `MANAGE_COMPLIANCE`); invites admins; configures all settings |
| `OPERATIONS` | Assign agents, manage verifications, review tasks, release reports |
| `FINANCE` | Approve payouts, view payments, manage commissions & pricing |
| `CONTENT_CREATOR` | Draft marketing/content material (admin content pages are not yet built — §G) |
| `CONTENT_APPROVER` | Approve content (same caveat) |

### 2.3 Trust status

`TrustStatus`: `UNTRUSTED` → `TRUSTED`. A customer becomes trusted on first successful payment; an agent on
first task submission. Trust status reduces friction on later flows and feeds fraud thresholds.

### 2.4 Credential expiry & role-level suspension

Agent credentials are time-bound (`AgentCredential`, `CredentialStatus`: `PENDING / VERIFIED / EXPIRED /
SUSPENDED`). On expiry of a role's required credential, **only that role** is suspended — the agent stops
receiving and can no longer submit that role's tasks; other roles are unaffected. A suspended role is
restored when a renewed credential is uploaded and admin-verified. Expiring credentials are flagged ahead of
time (lead-time configurable).

### 2.5 Portal routing & switching

| Role combination | Default portal |
|---|---|
| Admin only | `/admin` |
| Agent + Customer | `/agents` (toggle to `/portal` via the header `PortalSwitcher`) |
| Admin + Agent + Customer | `/admin` (highest privilege wins) |
| Customer only | `/portal` |

Post-auth redirect: any pending `intent` wins; otherwise role priority **Admin → Agent → Customer**,
computed client-side from the persona list. Redirect targets are validated same-origin
(`isSafeRedirectPath` / `resolvePostAuthRedirect`, `frontend/src/components/website/auth/libs/auth/redirect.ts`).
The portal switcher carries a **cross-portal count badge** of unread/actionable items in the user's other
portal (`user/auth/cross_portal/`), so a multi-role user never misses items meant for their other hat.

<a id="2-6-legal"></a>
### 2.6 Legal & liability framework

Veriprops operates in real estate + legal interpretation; every product decision must be defensible.
This framework governs the product; the clause copy items still awaiting counsel sign-off are launch gates
tracked in §G.

#### Liability boundaries

| We ARE liable for | We are NOT liable for |
|---|---|
| Process integrity (right agents, correct steps per tier) | Property authenticity guarantee |
| Accurate presentation of agent findings | Future changes, undisclosed disputes, hidden claims |
| Platform security & data handling | Independent agent professional judgement |
| Payment handling — refund when undelivered | The user's purchase decision and its outcomes |
| | Third-party data accuracy (registry errors) |

> **Payment processor, not merchant of record.** Paystack/Flutterwave are payment *processors*; Veriprops
> remains the legal seller of the verification service and owns tax remittance, chargeback handling, and
> compliance.

#### Limitation of liability

- **Aggregate cap: 1× fees paid** per verification (the contractual NGN figure). Why not zero: a zero cap
  invites a court to strike the clause as unconscionable.
- **Carve-outs:** the cap does not limit liability for fraud, willful misconduct, or anything a court will
  not permit to be capped (death/personal injury, non-waivable statutory consumer rights).
- The disclaimer limits the *nature* of a claim ("opinion, not guarantee"); the cap limits the *amount*.
  Both depend on the versioned-consent record below. Final clause copy: legal sign-off gate (§G).

#### Agent liability & professional indemnity

- Agents (including the Premium lawyer) act as **independent contractors**; `AGENT_TERMS` carries an
  **indemnity back to Veriprops** for losses caused by agent negligence/misconduct, captured as a versioned
  attestation.
- PI-insurance posture (agent-carried vs platform-carried) is an open business decision; **lawyer-role cover
  is a hard gate** before the Premium Legal Opinion goes live (§G, `LEGAL_OPINION_ENABLED`).

#### Governing law & forum

Nigerian law, Nigerian courts (forum-selection clause in `PLATFORM_TERMS` / `VERIFICATION_TERMS`). Foreign
consumers (UK/EU/Canada) may retain non-waivable home-jurisdiction rights; cross-border enforceability is
confirmed per-market only as volume warrants (§G).

#### Versioned consent (platform-wide)

The evidentiary backbone: every legal document is versioned (`ConsentDocument`, seeded idempotently), and
every acceptance is recorded against the exact version shown with user ID, type, version, timestamp, and IP
(`UserConsent`). `ConsentSignoffStatus` marks whether a document's wording is counsel-final (`DRAFT` /
`FINAL`). The ten `ConsentDocumentType` values and where they are collected:

| Consent type | Collected at |
|---|---|
| `PLATFORM_TERMS`, `PRIVACY_POLICY` | Signup (step 4 of the wizard) |
| `AGENT_TERMS` | Agent application submission |
| `VERIFICATION_TERMS` | Submission wizard Consent step, before payment |
| `VERIFICATION_DISCLAIMER`, `FINDINGS_OPINION_ACK`, `JURISDICTION_PLATFORM_ONLY`, `COMMUNICATION_RECORDING`, `REFUND_POLICY` | The five expandable clauses inside the same Consent step |
| `REPORT_DISCLAIMER` | First report view (acknowledgement gate, §15.1) |

A `consent_snapshot_id` is stored on the verification at acceptance. Users can view and download their full
consent history (§24.3).

#### Refund & liability model

All refunds compute from the contractual NGN figure in kobo and are issued in NGN through the gateway
(reverse-FX disclosure carried in `REFUND_POLICY`).

| Scenario | Fault | Action |
|---|---|---|
| Cancel before `IN_PROGRESS` | Customer | Partial refund minus `cancellation_surcharge_pct` (default 20%) |
| Cancel after `IN_PROGRESS` | Customer | No refund |
| Wrong agent assigned / step skipped | Veriprops | Full refund + free re-verification |
| Registry error / missing records | External | No refund; transparent reporting |
| Property inaccessible | External | Partial refund (field component); requires geotagged proof of the access attempt; **admin** classifies the cause |
| Fraudulent customer submission | Customer | No refund |
| Payment confirmed but never activated | Veriprops | Full refund |
| Ambiguous location input, defensible interpretation verified | Customer | No refund; re-verification at re-check pricing |
| Wrong property despite clear input | Veriprops | Full refund + free re-verification |

#### Communication boundaries

- ❌ No direct Customer ↔ Agent chat. Routine coordination flows as **structured, fraud-scanned
  clarification requests** through the verification thread (§16.3).
- ✅ Customer ↔ Admin and Admin ↔ Agent — one thread each per verification.
- ⚠️ Agent first name + role + verified badge visible to customers; contact details never (§5, enforced at
  the API layer).
- 🚨 All messages scanned for phone/email/payment leakage before delivery (§16.2); all communication
  recorded and auditable.

#### Premium Legal Opinion — ownership posture

The Premium Legal Opinion is **owned and signed by the individual NBA-licensed lawyer** who renders it;
Veriprops **transmits** it and is liable only for transmission integrity (underpinned by the §4.5 evidence
hash). The report section is fully built but its customer display is gated behind
`LEGAL_OPINION_ENABLED = False` until NBA counsel sign-off + lawyer PI cover land (§G).

#### Report footer (every page, every PDF page)

> *This report represents a professional opinion, not a legal guarantee. Findings are based on information
> available at the time of verification. Veriprops — Jurisdiction: Nigeria. "We reduce uncertainty. We do
> not eliminate it."*

---

<a id="3-state-machines"></a>
## 3. State Machines (Authoritative)

Canonical enums: `backend/main/app/core/state/status.py`. Transition tables + validator:
`backend/main/app/core/state/machine.py` (self-loops are idempotent no-ops; terminal states reject all
exits). Global verification state is **derived** from task states by one owner function (§4.1) — never set
by a human clicking a button. Frontend mirrors these enums in `frontend/src/types/*` — enum references,
never free string literals.

### 3.1 Verification state machine (`VerificationStatus`)

| State | Meaning |
|---|---|
| `DRAFT` | Wizard started. VID assigned. Not yet submitted. |
| `SUBMITTED` | Wizard complete. Awaiting payment initiation. |
| `PAYMENT_PENDING` | Payment initiated. Awaiting gateway confirmation. |
| `PAID` | Payment confirmed. Awaiting agent assignment. |
| `IN_PROGRESS` | ≥1 task assigned/accepted/in progress/rejected. Work underway. |
| `UNDER_REVIEW` | All instantiated tasks submitted. Admin reviewing. |
| `COMPLETED` | All tasks approved; report released. Not terminal. |
| `DISPUTED` | Customer filed a formal post-completion dispute. |
| `CANCELLED` | Cancelled. Refund rules applied. **Terminal.** |
| `REFUNDED` | Dispute upheld / failure refunded. **Terminal.** |
| `FAILED` | Critical failure (fraud / permanent inaccessibility). **Terminal.** |

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

### 3.2 Task state machine (`TaskState`)

| State | Meaning |
|---|---|
| `PENDING` | Task exists for this role. No agent committed. |
| `ASSIGNED` | Admin assigned an agent (manual path). Awaiting accept. |
| `ACCEPTED` | Agent committed. Clock starts. |
| `IN_PROGRESS` | Agent actively working. |
| `SUBMITTED` | Findings submitted. Awaiting admin review. |
| `REJECTED` | Admin requested rework. |
| `APPROVED` | Admin approved the submission. |

```
PENDING      → ASSIGNED, ACCEPTED
ASSIGNED     → ACCEPTED, PENDING
ACCEPTED     → IN_PROGRESS, PENDING
IN_PROGRESS  → SUBMITTED
SUBMITTED    → APPROVED, REJECTED
REJECTED     → IN_PROGRESS
APPROVED     → IN_PROGRESS      (admin reopen)
Terminal     : none
```

**Two paths into a task:** manual (`PENDING → ASSIGNED → ACCEPTED`, admin picks an agent) and broadcast
(`PENDING → ACCEPTED`, first-accept-wins pool, §11.3). **Backward transitions are admin-initiated only:**
`REJECTED → IN_PROGRESS` (rework after a revision request) and `APPROVED → IN_PROGRESS` (reopen — release
gate "Request Changes", re-check scope, tier-upgrade rescope, partially-upheld dispute).

**`ReviewDecision` is separate from `TaskState`.** The admin's per-task verdict (approve/reject with a
quality score) is recorded as review intent; the actual `SUBMITTED → APPROVED` flip happens **atomically at
release** (§13.3), so an all-approved verification cannot auto-complete without the deliberate release
action.

### 3.3 Report state machine (`ReportState` + `ReportRevisionKind`)

```
DRAFT      → RELEASED
RELEASED   → SUPERSEDED
Terminal   : SUPERSEDED
```

Reports are never auto-created; `ReviewService.release` is the explicit gate. Each release increments the
monotonic integer `report_version` and computes a semantic `version_label` from `ReportRevisionKind`:

| `revision_kind` | Label effect | Trigger |
|---|---|---|
| `INITIAL` | `v1.0` | First release |
| `ADMIN_REVISION` | minor bump (`v1.1`) | Admin reopen + re-release |
| `RECHECK` | major bump (`v2.0`) | Paid re-check cycle (§19.1) |
| `TIER_UPGRADE` | major bump (`v3.0`) | Paid tier upgrade (§19.2) |

On each release the prior `RELEASED` report flips to `SUPERSEDED` (rendered watermarked).

### 3.4 Chat message state machine (`ChatMessageState`)

Every chat message is fraud-scanned synchronously at send time (§16.2):

```
PENDING_SCAN → DELIVERED          (fast lane — nothing flaggable; the common case)
PENDING_SCAN → HELD               (flagged; queued for admin review)
HELD         → DELIVERED          (admin approves)
HELD         → BLOCKED            (admin rejects)
Terminal     : DELIVERED, BLOCKED
```

### 3.5 Erasure request state machine (`ErasureRequestState`)

```
PENDING → APPROVED, REJECTED
APPROVED → EXECUTED               (irreversible pseudonymisation, §24.4)
Terminal : EXECUTED, REJECTED
```

### 3.6 Subsidiary status enums

Not part of the shared `StateMachine`; transitions are guarded in their services.

| Enum | Members | Home |
|---|---|---|
| `PaymentStatus` | `INITIATED / PROCESSING / SUCCEEDED / FAILED / PENDING_TRANSFER / REFUNDED` | `payment/models.py` |
| `PaymentPurpose` | `INITIAL / RECHECK / UPGRADE` (webhook routes confirmations by purpose) | `payment/models.py` |
| `PaymentMethodKind` | `CARD / BANK_TRANSFER` | `payment/models.py` |
| `ChargebackStatus` | `FLAGGED / REBUTTAL_SUBMITTED / WON / LOST` | `payment/chargeback/models.py` |
| `CommissionStatus` | `CLEARING / AVAILABLE / FROZEN / REVERSED` | `commission/models.py` |
| `PayoutStatus` | `REQUESTED / APPROVED / HELD / PAID / REJECTED / CANCELLED` | `payout/models.py` |
| `ReferralCreditStatus` | `PENDING / CLEARED / VOID` | `referral/credit/models.py` |
| `RecheckStatus` | `PENDING / APPROVED / REJECTED / STARTED` | `verification/recheck/models.py` |
| `DisputeStatus` / `DisputeOutcome` | `OPEN / RESOLVED` · `REJECTED / FULL_REFUND / PARTIAL_RECHECK` | `verification/dispute/models.py` |
| `DisputeType` | `INACCURATE_FINDING / MISSING_CHECK / AGENT_CONDUCT / OTHER` | `verification/dispute/models.py` |
| `AgentApplicationStatus` | `PENDING / APPROVED / REJECTED` | `user/agent/profile/models.py` |
| `AvailabilityStatus` | `GREEN / AMBER / RED` (forced `RED` at capacity) | `user/agent/profile/models.py` |
| `CredentialStatus` | `PENDING / VERIFIED / EXPIRED / SUSPENDED` | `user/agent/credential/models.py` |
| `ClarificationStatus` | `OPEN / ANSWERED` | `communication/chat_message/models.py` |
| `PublicLookupState` | `SHARED / PRIVATE / IN_PROGRESS / DISPUTED / NOT_FOUND` | `verification/share/models.py` |
| `ShareType` | `LINK_SUMMARY / NAMED_FULL` | `core/state/status.py` |

### 3.7 Derived global-state rules

One pure function owns the projection: `derive_status(current_status, task_states)` in
`backend/main/app/core/state/derive.py`. Evaluated in order:

| # | Condition | Result |
|---|---|---|
| 1 | Current status is **preserved** (`CANCELLED`, `REFUNDED`, `FAILED`, `DISPUTED`) | returned as-is (admin/dispute flows own these) |
| 2 | Current status is **pre-payment** (`DRAFT`, `SUBMITTED`, `PAYMENT_PENDING`) | returned as-is (payment flow owns these) |
| 3 | Any task **active** (`ASSIGNED` / `ACCEPTED` / `IN_PROGRESS` / `REJECTED`) | `IN_PROGRESS` |
| 4 | Tasks non-empty, all **settled** (`SUBMITTED` / `APPROVED`), ≥1 still `SUBMITTED` | `UNDER_REVIEW` |
| 5 | Tasks non-empty, all `APPROVED` | `COMPLETED` |
| 6 | Otherwise (no tasks, or all `PENDING`) | `PAID` |

**Dependency-blocked tasks are not rows.** A blocked task (Premium Lawyer before its siblings reach
`SUBMITTED`) is not instantiated as a `PENDING` row until its dependency unlocks, so it never distorts rules
3–5. Required-task counts always come from **tier configuration** (`required_task_count`), never
`COUNT(tasks)`.

### 3.8 Invariants

- **No skipped states.** Only the listed transitions are valid; `StateMachine` rejects anything else.
- **Derived global state.** Every task-mutating handler recomputes `verification.status` via the derivation
  owner and persists once; no endpoint sets it directly. Frontends render what the API returns; the
  customer-facing label mapping (§14.2) is a thin presentation layer.
- **`COMPLETED` requires ALL required tasks `APPROVED`**, and the flip happens only at explicit release.
- **Terminal means terminal.** `CANCELLED`, `REFUNDED`, `FAILED`, report `SUPERSEDED`, message
  `DELIVERED`/`BLOCKED`, erasure `EXECUTED`/`REJECTED`.
- **Every transition is audit-logged** with actor, role, from→to, timestamp, IP, optional note (§24.1).
- **Pause is a flag, not a state.** Admin pause/resume toggles `verification.paused` without touching the
  state machine.

### 3.9 Progress formula

```
Progress % = (Approved tasks ÷ Required tasks for tier) × 100
```

Task counts are tier-specific (Basic 1, Standard 3, Premium 4), read from tier config. Displayed on the
customer dashboard and admin panel.

---

<a id="4-architecture"></a>
## 4. Platform Architecture

Cross-cutting structural choices, all built. File paths are the source of truth.
(Numbering 4.1–4.11 is kept aligned with v2.4 so long-lived references — e.g. CLAUDE.md's §4.8/§4.9 —
stay valid.)

### 4.1 Single state-derivation owner

`derive_status(...)` (`app/core/state/derive.py`) is the sole computation of `verification.status`
(rules in §3.7). Every task/review mutation — assign, accept, decline, start, submit, approve, reject,
release, reopen, fail — recomputes through it and persists once. Why: prevents "dashboard says X, admin says
Y" bugs by keeping state logic in one place.

### 4.2 Data-driven task dependencies

`TASK_DEPENDENCIES` (`app/core/state/dependencies.py`) declares `LAWYER depends-on [REGISTRY, FIELD,
SURVEYOR]` per tier; the unlock check is generic ("are all upstream tasks `SUBMITTED`?") and the graph is
validated acyclic at import. The Lawyer "Awaiting other stages" UI renders the actual blocking roles from
this structure. Adding a dependency is configuration, not code.

### 4.3 Property as a first-class entity

`Property` (`app/domain/property/`) is a thin entity separate from `Verification`: address, coordinates,
type, state, LGA, customer-submitted facts. Verifications point at a property; re-checks and tier upgrades
reuse the same row. No auto-deduplication — dedup intelligence is the post-MVP Property Identity Layer.

### 4.4 Money & currency — gateway-mediated collection

- **All money is integer minor units** (kobo/cents, `BigInteger`) with explicit currency codes
  (`TransactionCurrency`: NGN, USD, GBP, EUR) — never float. Everything reconciles to the kobo.
- **NGN-contractual, NGN-settled.** `amount_minor` (NGN kobo) is the contractual amount used by refunds,
  commissions, disputes, and audit; `charge_currency` / `charge_amount_minor` record how the customer
  actually paid. Diaspora customers pay in USD/GBP/EUR by international card; the gateway converts and
  settles NGN — Veriprops carries no FX risk. Foreign figures are indicative, NGN prominent.
- **Gateway-mediated collection** through Paystack/Flutterwave behind a provider facade
  (`ACTIVE_PAYMENT_METHOD` selects; `PAYMENT_STUB_MODE = True` default gives a deterministic stub, §25.2).
  Veriprops never handles raw card or bank credentials. Gateway webhooks drive
  `PAYMENT_PENDING → PAID`. A `STRIPE` enum value exists but has no integration (§G).
- **Price lock:** `price_locked_minor` + `price_lock_expires_at` (`PRICE_LOCK_TTL_HOURS = 24`); a re-lock
  after expiry that changes the price triggers a mandatory "price updated" interstitial before payment
  (§10.4).
- **FX display:** `PRICING_FX_PROVIDER` facade (STUB default with hardcoded indicative rates;
  OPENEXCHANGERATES option unwired — §G). VAT constant: 7.5%.

### 4.5 Evidence integrity — per-item content hash

On evidence upload, a SHA-256 content hash is computed and stored (`app/core/evidence.py`, constant-time
verify). Combined with immutable object storage and the audit log, any post-submission alteration is
detectable. Server-side GPS/timestamp stamping at capture proves presence (§12.3); the hash proves integrity
after receipt. A per-item hash was chosen over a chained hash deliberately (chaining fights concurrent
uploads for little real gain).

### 4.6 Idempotency & double-submit protection

`app/core/idempotency/` (`IDEMPOTENCY_KEY_TTL_HOURS = 24`):

- **Idempotency keys for payments and entity creation.** Payment initiation takes a client key
  (`begin_or_replay` / `complete`; request-hash mismatch → conflict). The webhook handler claims the gateway
  event ID one-shot (`claim`) so a replayed "payment succeeded" cannot double-transition. Creation endpoints
  (draft, re-check, dispute, payout) use the same client-key mechanism.
- **Optimistic locking for updates.** The `version` column on `BaseEntity` guards mutations of existing rows
  — a double-tapped "Submit" loses the stale write.

### 4.7 Chat message lifecycle & fraud holds

Messages have their own state machine (§3.4). The send-time scan checks for off-platform-contact and
payment-solicitation patterns (phone, email, URLs, banking details, "go outside the platform"). Unflagged
messages deliver immediately (the fast lane); only flagged messages are held for admin approve/reject.
Single hold behaviour today; severity tiers are a data-informed follow-up (§G). System auto-posts skip the
scan. Held-message journeys are audit-logged.

### 4.8 In-process event bus

Every domain event is published **once** through `app/core/events/`
(`await publish_domain_event(DomainEvent(...))`); services never call the SSE emitter or an email sender
directly. Subscribers fan out:

- **`realtime`** — re-emits to the verification SSE stream.
- **`notification`** — consults the declarative rule table (§17.2) for in-app/email/SMS fan-out.
- **`chat_counter`** — per-user unread bumps.
- **`chat_autopost`** — posts a `SYSTEM_AUTO` breadcrumb into the thread on status changes.

Implemented as an in-process synchronous dispatcher backed by the existing DB — not Kafka. A new channel
(e.g. WhatsApp) is a new subscriber, not a rewrite. Redis multi-instance fan-out is deferred (§G).

### 4.9 Real-time transport — SSE throughout

One transport: **SSE** for all server→client pushes; sends are ordinary HTTP POST. Two emitters:
verification-keyed (`app/core/realtime/emitter.py`, `/api/verifications/{id}/stream`) and per-user
(`user_emitter.py`, `/api/chat/stream` — chat + notification events). Heartbeat `SSE_HEARTBEAT_SECONDS=25`,
bounded queues (`SSE_QUEUE_MAXSIZE=100`). **Poll is the source of truth; SSE is a latency-reducing hint** —
frontend SSE handlers only invalidate queries, and a 60-second poll sharing the same snapshot shape is the
durable fallback, so a dropped push never leaves the UI stale or wrong. Publishing is best-effort and never
breaks the emitting transaction. Why SSE over WebSocket: the chat is admin-mediated and fraud-scanned, so
live-presence affordances would misrepresent it; SSE also survives flaky mobile networks with built-in
reconnection.

### 4.10 Verification ID generation & public-lookup safety

`app/core/vid.py` generates `VP-YYYY-XXXXXX` with a **high-entropy, non-sequential** Crockford-alphabet
suffix — the ID space cannot be walked. The unauthenticated lookup (§18.1) returns **indistinguishable
response shapes** for not-found / private / in-progress states so a prober cannot confirm which IDs exist.
(A per-route rate limit on the public lookup endpoint is not yet attached — §G.)

### 4.11 SLA business-day calendar

`app/core/sla.py` computes tier due dates in business days (Mon–Fri) minus Nigerian public holidays,
including computed Easter dates and a maintained table of movable Islamic holidays (2026–2028). `SlaHealth`:
`ON_TRACK / AT_RISK / OVERDUE / NONE`; the at-risk horizon is admin-tunable (`sla_at_risk_days`).

### 4.12 Audit pseudonymisation on erasure

Audit logs and consent records are retained indefinitely for legal defensibility, yet contain PII. NDPA
erasure is resolved by **pseudonymisation, not deletion** (§24.4): the subject's PII is replaced with a
stable opaque token while events, transitions, and timestamps are retained; the erasure itself is recorded
as an event.

### 4.13 Facade pattern — deterministic stubs, live providers

Every external integration sits behind a facade with a deterministic stub default, so tests and local
automation never depend on third parties:

| Integration | Selector | Default | Live option |
|---|---|---|---|
| Payments | `PAYMENT_STUB_MODE` / `ACTIVE_PAYMENT_METHOD` | stub (`True`) | Flutterwave, Paystack |
| KYC | `KYC_PROVIDER` | `STUB` | `DOJAH` |
| Document storage | `DOCUMENT_STORAGE_STUB_MODE` | stub (`True`) | AWS S3 / R2 |
| FX rates | `PRICING_FX_PROVIDER` | `STUB` | `OPENEXCHANGERATES` (unwired, §G) |
| Report PDF | `REPORT_PDF_STUB_MODE` | **real fpdf2 renderer** (`False`) | — |
| Geocoding | `GEOCODING_PROVIDER` | `STUB` | Google Places |
| OTP | `OTP_MODE` | env-enforced (§25.1) | — |

---

<a id="5-cross-cutting"></a>
## 5. Cross-Cutting Concerns

| Concern | Spec |
|---|---|
| **Determinism** | All state machines fully defined (§3); no undefined transitions. |
| **Derived state** | Global verification state derived by one owner (§4.1). |
| **Audit** | Every transition logged: entity, actor, actor role, from→to, timestamp, IP, note. Evidence events carry a per-item content hash. Retained indefinitely (§24). |
| **Idempotency** | Keys for payments + entity creation; optimistic locking for updates (§4.6). |
| **Money** | Integer minor units; NGN contractual; gateway-mediated collection (§4.4). |
| **Agent identity minimisation** | Customer-facing endpoints return only `role`, `first_name`, `avatar_url`, `verified` — enforced at the API layer, not just UI. |
| **Enum references** | Any value with a defining enum is referenced via its enum member in app code; free string literals are prohibited (exceptions: enum definitions, Alembic migrations, wire-compat tests). |
| **Security invariants** | Secrets only in git-ignored `.env.{env}`; prod/staging refuse to boot with placeholder JWT keys or auth bypass; tokens/OTPs from `secrets`; identity server-derived, never client-claimed; client list DTOs inherit `PageRequest` only. See the CLAUDE.md files. |
| **Accessibility** | Full keyboard navigation, tab order, ARIA roles. |
| **Mobile-first** | Diaspora uses mobile heavily; all surfaces responsive. |
| **Embedded education** | Tooltips on technical terms (C of O, encumbrance, trust score); plain English, specific not vague ("5–7 business days"). |
| **Compliance** | NDPA; PII retention per `pii_retention_days`; erasure workflow (§24.4). |
| **Pagination** | Every growable list is paged: backend `page`/`page_size` → `Page[T]`; frontend server-driven `DataTable`. |

---

# Part II — Product Modules

<a id="6-marketing"></a>
## 6. Marketing Site & Public Web

**Where:** `frontend/src/app/(website)/` — landing page, `about/`, `sample-report/`, `legal/[slug]/`
(legal documents served from the backend consent store), `forbidden/`. Static content lives in
`frontend/src/components/website/home.data.ts`.

**Landing page sections, in order:** sticky nav → Hero → Why We Exist → Verification Ecosystem (Trust Score
· Verification ID · Certified Report) → Rigorous Methodology (5-step stepper) → Verified Agents (four
roles) → Pricing → Testimonials → FAQ → CTA → Footer. JSON-LD (`organization`, `website`, `faq`) injected;
public pages crawlable; VID lookup pages `noindex` unless publicly shared.

**Behaviour:**

- CTAs preserve auth intent: "Verify a Property" → `/auth?intent=verify`; "Become an Agent" →
  `/auth?intent=agent` (built via `buildAuthUrl`).
- Pricing cards show Basic / Standard ("Most Popular") / Premium with a client-side currency toggle
  (NGN · USD · GBP · EUR) using **display-only** FX rates. Canonical pricing is the backend quote (§10.2);
  the marketing figures are static copy and currently diverge from the seeded backend prices (§G).
- Footer: dynamic copyright year + the golden line. Social links are placeholders (§G).

---

<a id="7-auth"></a>
## 7. Auth, Accounts & Sessions

**Where:** backend `app/domain/user/auth/` (service, `otp_service.py`, `oauth/`, `session/`, `consent/`,
`signup_draft/`, `cross_portal/`); frontend `frontend/src/app/(website)/auth/` +
`frontend/src/components/website/auth/`.

### 7.1 Signup

A 4-step wizard — **Account → Verify → Residence → Consent** (`SignupContainer.tsx`):

- **Email is always OTP-verified at signup** (6-digit code, `OtpChannel.EMAIL`; recently-verified marker is
  single-use, enforced server-side).
- **Phone verification is config-gated:** `PHONE_VERIFICATION_ENABLED = False` by default — the number is
  collected at signup but verified later, at the payment step (§10.5). When the flag is on, phone OTP is
  required at signup too. Never detect OTP behaviour from `ENVIRONMENT` — read `OTP_MODE` (§25.1).
- **Residence step** collects country/location; **Consent step** records `PLATFORM_TERMS` +
  `PRIVACY_POLICY` (versioned, §2.6).
- **Resumable drafts:** server-side (`signup_drafts`, normalised-email key) + localStorage mirror;
  cross-device resume prefers the server copy.
- Referral capture via `?ref` (invalid codes ignored); server-side password strength check (length,
  diversity, common-password blocklist); device fingerprint captured for the security log.

### 7.2 Login & sessions

- Email/password login with lockout counters (warning, then timed lockout); failures recorded as
  `SecurityEvent`s.
- **JWT session**: HS256 (algorithm pinned), HttpOnly cookies, `__Host-refresh_token` refresh cookie.
  Refresh checks `device_sessions` revocation, so device-revoke and reset-revoke-all genuinely end sessions.
- **Connected devices**: list sessions, revoke one, "log out all". **Security activity log** from
  `SecurityEvent`s.
- **Forgot/reset password**: tokenised single-use email link; reset invalidates all sessions.
  **Set password** for OAuth-only users.
- Route protection: the Next.js proxy gates `/portal/*`, `/admin/*`, `/agents/*`, `/account/*` on cookie
  presence; session validity is enforced server-side on every API call.

### 7.3 OAuth — popup + HttpOnly cookie

Providers: **Google, Apple, Facebook** (`SocialAuthProvider`), modes `auth` / `link`. Popup-only flow with
full-page redirect as the popup-blocked fallback:

1. Frontend synchronously opens a popup, fetches
   `GET /api/users/auth/oauth/{provider}/start?intent=…&mode=…` → `{authorizationUrl}`, navigates the popup.
2. Backend callback validates state + **PKCE (S256)**, exchanges the code, fetches the profile:
   existing identity → login; new email → auto-create (persona from intent) with a profile-completion modal
   for phone; **email collision with a password account → reject** ("log in and link explicitly");
   `link` → attach identity to the authenticated user (unlink is password-guarded).
3. Session issued as HttpOnly cookie; the popup posts `{type:"oauth_result", success, state}` to an
   allowlisted origin (`OAUTH_FRONTEND_ORIGINS`, never `*`) and self-closes. The parent validates origin +
   state; 5-minute timeout; popup-closed = silent cancel.

The `window.__oauth_complete__` automation contract (`null` → `"success"` / `"failed"` +
`CustomEvent`) is a permanent QA hook (§25.4).

### 7.4 Account area (`/account/*`)

Cross-persona surface on the shared `AppShell`: personal info, login & security (password, linked
providers, devices, security activity), consent history (+ CSV download), data & privacy (self-service
erasure request, §24.4), notification preferences (per-portal pages under `…/account/notification-preferences`).

---

<a id="8-agent-onboarding"></a>
## 8. Agent Onboarding & KYC

**Where:** backend `app/domain/user/agent/` (`profile/`, `credential/`, `coverage/`, `kyc/`,
`application_draft/`, `reputation/`); frontend `frontend/src/components/agents/onboarding/`.

**Application wizard (4 steps, resumable via server-side draft):**

1. **Roles** — Field / Surveyor / Registry / Lawyer, multi-select; reviewed per role.
2. **KYC** — **BVN primary; government-ID upload fallback**. Liveness/face-match are deferred entirely to
   the provider behind the facade (`KYC_PROVIDER`: `STUB` default, `DOJAH` live). The platform stores the
   provider's decision, reference, and score (`KycRecord`) — never raw biometrics; documents are stored as
   storage references. A selfie score below `KYC_SELFIE_REVIEW_THRESHOLD` (80) routes to admin review.
3. **Credentials** — conditional: `SURVEYOR_LICENCE` for Surveyor, `NBA_LICENCE` for Lawyer (with expiry
   dates); optional experience, coverage, bio.
4. **Review & submit** — truthfulness declaration + versioned `AGENT_TERMS` acceptance.

The application enters `PENDING` (`AgentApplicationStatus`) and blocks job receipt until an admin approves
(per-role scoping) or rejects with a reason (§11.5). Credentialed roles require a `VERIFIED`, unexpired
licence to be (and stay) active — see role-level suspension, §2.4.

---

<a id="9-admin-rbac"></a>
## 9. Admin Onboarding & RBAC

**Where:** backend `app/domain/user/admin_invitation/`, `user/admin_team/`,
`user/auth/utils/permissions.py`; frontend `/admin/team`, invite acceptance at `/auth/admin-invite/[token]`.

### 9.1 Invitations

Super Admin sends an invite with a sub-role; the token is hashed, valid `ADMIN_INVITE_TTL_HOURS` (72).
Acceptance handles three cases: new user → pre-filled signup; existing user → authenticated accept (email
must match); already admin → friendly message.

### 9.2 The sanctioned elevation path

`user_type` is immutable **except** through a validated admin-invite acceptance, which sets
`user_type = ADMIN` + `admin_sub_role` and is audited (`ADMIN_INVITE_ACCEPTED`). Why: keeps the entire admin
surface on one authorization predicate (`user_type == ADMIN`) while §2.2's immutability rule still blocks
unsanctioned self-promotion. Existing personas are preserved (the portal switcher keeps working).

### 9.3 RBAC & team management

A permissions matrix maps sub-roles to `Permission`s (invite admins, approve agents, assign agents, manage
verifications, approve payouts, configure pricing, view analytics, resolve disputes, release reports,
`MANAGE_COMPLIANCE` — SUPER-only). Every admin endpoint is permission-checked. Team management: list,
deactivate (demotes to plain USER), change sub-role (no self-targeting; only SUPER grants SUPER). All role
changes are audit-logged.

---

<a id="10-submission-payment"></a>
## 10. Customer Submission & Payment

**Where:** backend `app/domain/verification/` (aggregate + `pricing_config/`), `app/domain/payment/`;
frontend `frontend/src/components/portal/submission/`.

### 10.1 Submission wizard (`/portal/verifications/new`)

A full-screen `WizardOverlay` with three in-wizard steps — **Property → Tier → Consent** — then the payment
page (`/portal/verifications/[id]/pay`). A VID is assigned at draft creation (idempotent on mount, §4.6);
every step auto-saves to the backend (`draft_step` / `draft_payload` on the verification row), so drafts
resume across devices. The Property step collects type (Land/Building), address search with coordinates,
and details; the Property entity is created/linked here (§4.3).

### 10.2 Pricing & quotes

- Tier prices and line items are **DB-backed admin config** (`pricing_tier_config` + `pricing_line_items`,
  seeded from static defaults — currently ₦50,000 / ₦120,000 / ₦300,000; provisional pending business
  sign-off, §G). `PricingConfigService.tier_price_kobo` is the single resolver every pricing path reads
  (quote, submit, re-check, upgrade); admin edits take effect on the **next quote**, never on an existing
  lock.
- Quotes show the NGN amount as the prominent, certain figure; foreign figures are indicative
  (§4.4). First-time and referral discounts auto-apply, capped at `max_discount_percent` (§22).

### 10.3 Consent step

One versioned `VERIFICATION_TERMS` acceptance covering five expandable clauses (each also recorded as its
own `ConsentDocumentType`, §2.6). A `consent_snapshot_id` is stored on the verification.

### 10.4 Price lock & re-lock guard

"Continue to Payment" locks the NGN price for `PRICE_LOCK_TTL_HOURS` (24). If the lock has expired at pay
time, the price is refreshed — and if it changed, a mandatory **"price updated" interstitial**
(`PriceRefreshDto.price_changed`) is shown before payment. The customer is never silently charged a new
amount.

### 10.5 Payment

- **Phone-verification gate:** because phone OTP is deferred from signup (§7.1), the customer's phone must
  be verified here before payment proceeds.
- Gateway-mediated (§4.4): card (`PaymentMethodKind.CARD`) returns a hosted `checkoutUrl` on live gateways;
  under `PAYMENT_STUB_MODE` a deterministic stub-confirm path stands in (§25.2). NGN bank transfer via
  gateway-issued virtual account is modelled (`PENDING_TRANSFER`). No direct SWIFT/IBAN wire.
- The **idempotent webhook** (keyed on gateway event ID) drives `PAYMENT_PENDING → PAID` and routes by
  `PaymentPurpose` (`INITIAL` / `RECHECK` / `UPGRADE`). A duplicate webhook cannot double-transition or
  double-receipt.
- Payment confirmation fires `PAYMENT_CONFIRMED` (email + SMS templates) and upgrades the customer to
  `TRUSTED` on first success. Confirmation page: `/portal/verifications/[id]/confirmed` with SLA countdown.
- Refunds (`PaymentService.refund`) are idempotent and flow through the same facade; invoked by admin
  fail-with-refund and upheld disputes.

---

<a id="11-verification-ops"></a>
## 11. Verification Operations (Admin)

**Where:** backend `app/domain/verification/admin/`, `admin_note/`, `task/` (pool mechanics),
`app/jobs/scheduled.py`; frontend `frontend/src/components/admin/verifications/`.

### 11.1 Control panel

`/admin/verifications` is a server-driven DataTable (status, tier, SLA health, location filters);
`/admin/verifications/[id]` is the ops control panel: per-role task rows with assign/reassign, pause/resume
(a flag, §3.8), cancel-with-reason, declare-failure, extend SLA, progress bar, property/payment/commission
panels, chargeback management, audit-pack export, and the report-review entry point.

### 11.2 Assignment

- **Manual:** admin assigns an agent (`PENDING → ASSIGNED`); a ranked **suggested-agents** endpoint filters
  by role eligibility, credential status, coverage, and capacity, then orders by composite reputation score
  with Top-Agent / low-performance annotations (§21.3).
- **Capacity cap:** `agent_max_active_tasks` is enforced on both manual assignment and broadcast accept.
- Reassignments, pauses, and cancellations are audit-logged with reasons.

### 11.3 Broadcast pool (auto-assignment)

When enabled, tasks are broadcast to qualifying agents at `PAID`; **first accept wins**
(`PENDING → ACCEPTED`), everyone else sees "no longer available". The accept path re-checks capacity so a
fast agent cannot hoard jobs.

### 11.4 Scheduled sweeps

Idempotent, claim-based background jobs (APScheduler; disabled under `ENVIRONMENT=test`, each also
triggerable via a dev/admin endpoint for deterministic tests): **no-show timeout** (accepted but idle →
back to `PENDING`, admin alerted, logged against performance), **pool timeout / starvation backstop**
(unclaimed broadcasts escalate to targeted assignment), **SLA-breach detection** (publishes `SLA_BREACHED`
once per verification), plus the clearance/broadcast/retry sweeps of later modules.

### 11.5 Agent approval queue & admin notes

`/admin/agents/applications` reviews pending agent applications (approve with per-role scoping / reject
with reason). Admin notes on a verification are categorized (Operational / Quality / Risk / Handover),
searchable, included in the audit export, and never visible to customers or agents.

---

<a id="12-task-execution"></a>
## 12. Agent Task Execution

**Where:** backend `app/domain/verification/task/` (+ `task/evidence/`); frontend
`frontend/src/components/agents/tasks/` (`AgentTaskList.tsx`, `AgentTaskDetail.tsx`).

### 12.1 Discovery, accept, execute

The agent dashboard shows available jobs (role-matched, coverage-filtered for on-site roles) and active
tasks. Commission for the job is visible **before** accept (§20.1). Accept moves `ASSIGNED/PENDING →
ACCEPTED`; "Start work" → `IN_PROGRESS`; task endpoints are ownership-checked against the JWT subject.
Decline returns the task to the pool; repeated declines feed the reputation penalty (§21.1).

### 12.2 Role-specific submission forms

Structured per role, driven by `ROLE_FORM_FIELDS` (`frontend/src/types/agentTask.ts`) — Registry, Field,
Surveyor, and Lawyer each have their own required field set (observations, boundary assessment, ownership
chain, legal opinion, etc.). At least one evidence item is required before submit. Submission moves
`IN_PROGRESS → SUBMITTED`; when all instantiated tasks are settled the verification derives to
`UNDER_REVIEW`. The agent is upgraded to `TRUSTED` on first submission. The Lawyer task is
dependency-gated (§4.2) and its UI shows the actual blocking roles.

### 12.3 Evidence & proof-of-work

- Evidence kinds: `PHOTO / VIDEO / DOCUMENT / SIGNATURE / CERTIFICATE`. Uploads go through the storage
  facade (stub default; S3/R2 live) with a per-item SHA-256 content hash (§4.5).
- **Server-side GPS + timestamp stamping** at capture is the proof-of-presence control for on-site roles;
  the client's GPS is a hint only. Evidence is immutable after submission.
- Per-task **conflict-of-interest declaration** (versioned attestation) and property-identity confirmation
  are captured with the submission.
- An agent claiming "property inaccessible" must evidence the access attempt; **admin** classifies the
  cause for refund purposes (§2.6).
- **Current limitation (fact):** the agent upload UI is a plain file input with best-effort browser
  geolocation. The offline retry queue (`frontend/src/lib/offlineQueue.ts`) and the compression-capable
  upload manager (`frontend/src/components/ui/upload/`) exist but are **not wired** into the task flow, and
  no image derivatives are generated server-side (§G).

### 12.4 Escalation

"Report Issue" (inaccessible / suspicious / safety / conflicting info / other) alerts the admin, who may
pause. **Agents cannot unilaterally cancel or pause.**

---

<a id="13-review-release"></a>
## 13. Review, Trust Score & Report Release

**Where:** backend `app/domain/verification/review/`, `scoring/`, `report/`; frontend
`/admin/verifications/[id]/report-review` (`AdminReportReview.tsx`).

### 13.1 Task review

Admin reviews each submission read-only with the evidence gallery. **Reject** requires a reason + revision
instructions → task `SUBMITTED → REJECTED → IN_PROGRESS` on rework; the reason auto-posts to the
admin↔agent thread; global state reverts to `IN_PROGRESS`. **Approve** records the `ReviewDecision` and a
per-task quality score (`review_quality`, 0–100, default 100) — it does **not** yet move the task (§3.2).

### 13.2 Conflict detection

Automated flags on rule mismatches between sibling submissions (occupancy, boundary, authenticity). Admin
resolves: reject one/both tasks, or override with a reconciliation note; resolutions are logged.

### 13.3 Release gate

The composite trust score = Σ (weight_role/100 × quality_role), using admin-configured **Trust Score
Weights** per tier × role (sum-to-100 enforced at save; defaults: Basic — Registry 100; Standard —
40/30/30; Premium — Registry 30, Field 20, Surveyor 20, Lawyer 30). On **"Release Report"** the service
atomically flips all reviewed tasks `SUBMITTED → APPROVED`, derives `COMPLETED`, creates/releases the
report version, accrues commissions (§20.1, with a double-accrual guard), and notifies the customer. **No
report reaches a customer without this deliberate action.** "Request Changes" instead reopens any task
(`APPROVED/SUBMITTED → IN_PROGRESS`).

### 13.4 Reopen & recomputation semantics

While a `COMPLETED` verification is reopened (re-check, upgrade, partial dispute), the released report stays
visible with a "Revision in progress" banner (computed from state, not stored). The trust score recomputes
**only at the next release**, from then-current quality scores and weights. Every completed reopen bumps the
version with a `revision_kind` and reason (§3.3).

### 13.5 FAILED

Admin may declare `FAILED` (confirmed fraud / permanent inaccessibility / fraudulent submission): reason +
evidence required, irreversible, refund policy applied through the payment facade, agents' completed work
still logged.

---

<a id="14-tracking"></a>
## 14. Customer Tracking & Evidence

**Where:** backend `app/domain/verification/tracking/`, `task/evidence/`; frontend
`frontend/src/components/portal/verifications/` (`TrackingContainer.tsx`, `EvidenceContainer.tsx`,
`VerificationActivity.tsx`).

### 14.1 Tracking dashboard (`/portal/verifications/[id]`)

Header (VID, tier, status chip, address) · SLA card (expected date, elapsed/total business days, health
label) · progress tracker (per-task rows + `progressPercent`) · assigned agents (role + first name +
verified badge only) · evidence preview · messages preview · activity link. Live via the verification SSE
stream with the 60-second poll fallback (§4.9).

### 14.2 Customer-facing state labels

The backend supplies `statusLabel`; internal states collapse for customers:

| Internal | Customer sees |
|---|---|
| `PAID` | "Payment Confirmed — Agents Being Assigned" |
| `IN_PROGRESS` | "Verification In Progress" |
| `UNDER_REVIEW` | "Under Review" |
| `COMPLETED` | "Completed ✅" |
| `DISPUTED` | "Dispute Under Review" |
| `FAILED` | "Could Not Be Completed" |
| `REFUNDED` | "Refunded" |

Task-level: `PENDING/ASSIGNED/ACCEPTED` → "Pending"; `IN_PROGRESS/SUBMITTED/REJECTED` → "In Progress";
`APPROVED` → "Completed"; a dependency-blocked Lawyer row shows "Awaiting other stages".

### 14.3 Interim reassurance — gated on review approval

As tasks complete, milestones are translated into customer-meaningful language ("What we've found so far").
Guardrail: a role's evidence **and** its interim milestone surface to the customer only once that task is
admin review-approved — a risk-bearing finding is never delivered without context, and interim positives are
framed as provisional. Per-phase reassurance copy exists for `PAID`, `IN_PROGRESS`, and `UNDER_REVIEW`.

### 14.4 Evidence layer (`/portal/verifications/[id]/evidence`)

Chronological gallery of approved-task uploads, tagged by **role not name**, with server-side timestamp/GPS
and content hash. Evidence is immutable; server metadata trumps device EXIF; any alteration makes the
stored hash mismatch. (Progressive low-res derivatives are not yet generated — full-size originals are
served; §G.)

---

<a id="15-report"></a>
## 15. Report Experience

**Where:** backend `app/domain/verification/report/` (+ `report/acknowledgement/`), PDF facade; frontend
`ReportContainer.tsx` / `ReportView.tsx` at `/portal/verifications/[id]/report`.

### 15.1 Features

- **Acknowledgement gate:** the report is blurred until the customer accepts the `REPORT_DISCLAIMER`
  (recorded against the report version).
- **Header:** Verified badge, VID, version label + release date, tier, address; actions — Download PDF,
  Share, Request Re-check / Upgrade / Dispute (§19).
- **Trust Score:** radial gauge with numeric score + band (90+ Safe / 60–89 Caution / 0–59 High Risk) and
  a plain-language verdict framed as professional opinion.
- **Sections** (collapsible, tier-dependent): Executive Summary · Physical Findings (Standard+) · Registry
  & Title (all) · Boundary & Survey (Standard+) · Legal Opinion (Premium — built, hidden behind
  `LEGAL_OPINION_ENABLED`, §2.6) · Risk Summary · Customer-Submitted Documents appendix.
- **Legal footer** on every page and every PDF page (§2.6).
- **PDF:** server-side branded render via **fpdf2** behind the `report_pdf` facade (pure-Python — chosen
  for zero native deps and CI determinism; not pixel-identical to the HTML view), per-page footer, QR
  deep-link to the public lookup, re-downloadable anytime.
- **Versioning:** superseded versions render watermarked with a banner; the customer is notified on each
  release (`REPORT_READY` / `REPORT_VERSIONED`).

---

<a id="16-communication"></a>
## 16. Communication

**Where:** backend `app/domain/communication/` (`conversation/`, `conversation_participant/`,
`chat_message/`); frontend shared `ChatThread.tsx`, portal/agent messages pages, admin held-message queue
at `/admin/messages`.

### 16.1 Channels (`ConversationType`)

| Channel | Shape |
|---|---|
| `CUSTOMER_ADMIN` | One thread per verification; system auto-posts status breadcrumbs (`SYSTEM_AUTO`). |
| `ADMIN_AGENT` | One thread per verification, task-taggable; a task rejection reason auto-posts; an agent's task thread becomes **read-only once that task is APPROVED**. |
| `GENERAL_SUPPORT` | One per user, account/billing/general — the Support page routes here. |

There is deliberately **no direct customer↔agent channel** and no WebSocket/presence layer (§4.9).
`sender_kind` (`CUSTOMER / ADMIN / AGENT / SYSTEM`) is **derived server-side, never client-claimed**.
Ownership gates: a customer must own the verification; an agent must be assigned. Message sends are HTTP
POST; delivery rides the per-user SSE stream. Chat is **text-only** today — the `attachments` column is
reserved for a follow-up (§G).

### 16.2 Fraud scan & held messages

Send-time synchronous scan per §4.7 / §3.4: unflagged messages deliver immediately; flagged messages are
`HELD` with a non-accusatory sender notice and appear in the admin **held-message queue**
(`/admin/messages`) for approve (deliver) or reject (block + warn). Single hold behaviour; severity tiers
are a data-informed fast-follow (§G). All decisions are audit-logged.

### 16.3 Structured clarifications

Routine customer↔agent coordination flows as `CLARIFICATION_REQUEST` / `CLARIFICATION_RESPONSE` message
kinds with a `ClarificationStatus` (`OPEN → ANSWERED`), running the same fraud scan — no admin keystroke
needed per exchange, no direct contact, no separate pipeline.

### 16.4 Admin shared inbox

Admins are not enrolled per-thread; `CommunicationService` treats `user_type == ADMIN` as a shared inbox
over **all** verification threads, with unread computed from each admin's own `last_read_at`. Admin counter
freshness rides the 60-second poll rather than per-message fan-out (bounded by design).

---

<a id="17-notifications"></a>
## 17. Notifications & Event Bus

**Where:** backend `app/core/events/`, `app/domain/notification/` (`rules.py`, `content.py`,
`dispatcher.py`), `notification_preference/`, outbound senders in `app/domain/message/`; frontend
`NotificationBell`, `ChatButton`, notifications pages.

### 17.1 One publish point

Every domain event is published once through the bus (§4.8); the notification subscriber consults the
**declarative rule table** (`notification/rules.py`) — one `NotificationRule` row per `EventType` declaring
`in_app` / `email` / `sms` / `chat_only` and the external template.

### 17.2 Trigger set (as wired)

Customer: payment confirmed (email+SMS) · status change · agents assigned · new evidence · report ready
(email+SMS) · report versioned · SLA breach (email+SMS) · re-check decision · dispute filed/resolved ·
abandonment recovery (email-only) · referral credit earned. Agent: new job (email+SMS) · task rejected /
revision request · commission cleared (in-app only — the positive-movement alert) · payout approved/held ·
dispute defence window. Admin: SLA breach · conflict flags · agent no-show · fraud-held messages · dispute
filed · broadcast announcements. Email/SMS render through the `VERIFICATION_*` template set
(`AvailableTemplate`); external dispatch is bookkept in the `messages` table with a retry ladder
(`MESSAGING_RETRY_INTERVALS_SECONDS = [60, 300, 900]`) swept by the scheduler.

### 17.3 Chat-vs-notification routing

Routine chat messages increment the **Chat** counter only (`chat_only` rows). **High-stakes events about a
chat** (e.g. dispute opened) fire a system notification while the underlying messages stay in Chat. This
rule lives in the one table.

### 17.4 Channels & preferences

In-app is always on (SSE-delivered, cannot be disabled); email and SMS are per-event opt-outs at
`…/account/notification-preferences`. Push/WhatsApp are post-MVP subscribers (§G).

---

<a id="18-lookup-sharing"></a>
## 18. Public Lookup & Sharing

**Where:** backend `app/domain/verification/share/` (`public_controller.py`, `service.py`); frontend
`/verify/[vid]` (server component) and `/shared/[token]`.

### 18.1 Public lookup (`/verify/[vid]`)

Unauthenticated, summary-only, allow-listed fields: VID, ✅ badge, trust **band** (never the number), tier,
report date, property type, state & LGA, version. Never: full address, agent or owner names, documents,
numeric score. `PublicLookupState` drives the render: `SHARED` (summary) / `PRIVATE` ("not enabled") /
`IN_PROGRESS` / `DISPUTED` / `NOT_FOUND` — non-shared states return indistinguishable shapes (§4.10).
`noindex` unless `SHARED`. CTA: "Start a verification →". (Per-route rate limiting is not yet attached —
§G.)

### 18.2 Sharing modes

| Mode | Who sees | Content |
|---|---|---|
| Private (default — no share row) | Customer only | Full report |
| Public (`public_lookup_enabled` flag) | Anyone with the VID | Summary |
| `LINK_SUMMARY` | Anyone with the tokenised link | Summary |
| `NAMED_FULL` | A specific emailed recipient | **Full report**, after a one-time disclaimer acknowledgement |

Shares default to `share_link_default_expiry_days` (30) and are revocable — revocation kills the token
immediately. Named recipients get a magic-link email (`VERIFICATION_REPORT_SHARE`); their view renders the
same `ReportView` as the owner's.

---

<a id="19-aftermarket"></a>
## 19. Re-check, Tier Upgrade & Disputes

**Where:** backend `app/domain/verification/recheck/`, `upgrade/`, `dispute/`; frontend
`ReportActions.tsx` (customer), `/admin/rechecks`, `/admin/disputes`, `/agents/disputes`.

### 19.1 Re-check

Customer requests on a `COMPLETED` report (reason + optional docs) → `RecheckStatus.PENDING`. Admin
approves and **scopes the roles** to re-run (or rejects) → customer pays a secondary charge of
`recheck_price_pct` (default 30%) of the tier base price → on payment confirmation the scoped tasks reopen
(`APPROVED → IN_PROGRESS`), `pending_revision_kind = RECHECK`, and the next release ships `v2.0`.

### 19.2 Tier upgrade

Available on `COMPLETED` or `IN_PROGRESS`, only to a higher tier. Charge = `price(to) − price(from)` from
the pricing resolver. On payment: tier raised, added-scope tasks instantiated (existing approved work
preserved), SLA due date recomputed, next release ships `v3.0`. Idempotent on resubmit.

### 19.3 Disputes

- Window: `dispute_window_days` (default 30) after `COMPLETED`; description ≥ `dispute_min_description_chars`
  (100); typed via `DisputeType`. Filing flips `COMPLETED → DISPUTED`, **freezes related clearing
  commissions**, and fires a system notification.
- **Agent dispute-defence:** when a dispute targets an agent's task, the agent gets a bounded response
  window (`agent_dispute_defence_hours`, default 48) that the admin sees before resolving — admin-mediated;
  the agent never learns the customer's identity.
- Outcomes (`DisputeOutcome`), each with a mandatory resolution note delivered verbatim:
  `REJECTED` → `COMPLETED` (commissions unfreeze) · `FULL_REFUND` → `REFUNDED` (gateway refund + commission
  reversal) · `PARTIAL_RECHECK` → `IN_PROGRESS` (free scoped re-check; next release `v2.0`).

---

<a id="20-earnings"></a>
## 20. Agent Earnings, Commissions & Payouts

**Where:** backend `app/domain/commission/`, `commission_rule/`, `earnings/`, `payout/` (+
`payout/bank_account/`); frontend `/agents/earnings`, `/agents/payouts`, admin `/admin/finance/payouts`,
`/admin/commission-rules`.

### 20.1 Commission accrual

Rates are an admin-configured **`commission_rule` table, per role × tier, in basis points** (exact kobo
math: `commission = price_locked_minor × rate_bps / 10_000`); defaults seeded from a static role-weight map
reproducing `trust-weight % × AGENT_COMMISSION_SHARE (0.40)`. The rate and amount show on the job-accept
screen **before** the agent commits. Accrual happens at report release per approved task, with a
double-accrual guard (a re-released re-check never accrues twice).

### 20.2 Two-stage clearance & reserve

Accrual stamps `clearing_until = approval + commission_clearance_days` (7) for the bulk and
`reserve_until = + chargeback_window_days` (120) for a `commission_reserve_pct` (10%) slice — the reserve
absorbs late card chargebacks. A claim-based sweep flips `CLEARING → AVAILABLE` and releases reserves,
firing the positive-movement `COMMISSION_CLEARED` notification. A dispute or chargeback **freezes** related
clearing commissions; an upheld dispute or lost chargeback **reverses** them. This is a ledger rule on funds
Veriprops already holds — explicitly not escrow.

### 20.3 Earnings dashboard — derived by date

Balances are **derived on read, never stored** (cannot drift): available = cleared bulk + released reserve
− paid − in-flight-locked payouts; with clearing / in-reserve / on-hold / lifetime / paid as explained line
items. "Available to withdraw now" is the hero figure. Available clamps at 0 — a late reversal after payout
is the accepted, bounded tail risk.

### 20.4 Payouts

Agent requests a withdrawal against available balance (stored beneficiary account or one-time entry); a
`REQUESTED/APPROVED/HELD` payout **locks funds** so nothing is double-spent. Finance panel
(`APPROVE_PAYOUT`): approve / hold / reject / adjust, all audit-logged; target settlement
`payout_sla_business_days` (2). **Disbursement is stub-first** — approval marks `PAID` and fires
`PAYOUT_APPROVED`; a real transfer gateway drops in behind the facade (§G).

---

<a id="21-reputation"></a>
## 21. Agent Reputation & Coverage

**Where:** backend `app/domain/user/agent/reputation/`, `coverage/`, `profile/`,
`app/domain/config/nigeria_locations.py`; frontend `/agents/profile`, `/agents/settings/coverage`
(`NigeriaCoverageMap.tsx`, `AvailabilityToggle.tsx`).

### 21.1 Metrics — derived on read

No stored metrics table (cannot drift). Computed per request over the agent's tasks:
**completion rate**, **accuracy** (the admin's `review_quality` aggregated onto a 5-point scale — reuses
the score already captured at approval), **timeliness** (fraction of submissions within `task_sla_hours`,
default 48), and a **composite** (completion + accuracy + timeliness − decline penalty).

### 21.2 Coverage — declared, role-differentiated

Agents declare states (validated against the backend-owned canonical **37-state** list served at
`GET /config/nigeria-locations`), free-text LGAs, and travel radius, via an interactive Nigeria map picker
(a schematic geo-grid, not cartographic paths — §G). **Field/Surveyor are location-bound** (coverage gates
matching); **Registry/Lawyer are remote-capable** (coverage does not gate). Coverage spanning more than
`agent_wide_coverage_states` (6) is flagged for admin review rather than forbidden. Availability
(`GREEN/AMBER/RED`) is agent-set, **forced RED at `agent_max_active_tasks`**.

### 21.3 Ranking & thresholds

The admin suggested-agents endpoint (§11.2) ranks eligible agents by composite score. Agents below
`agent_low_performance_threshold` (40) are sunk/excluded from the ranking; accuracy at or above
`agent_top_agent_accuracy_threshold` (90) earns the admin-visible "Top Agent" badge. (The broadcast pool
itself is untargeted accept-by-id today, so per-agent pool-feed reduction is a follow-up — §G.)

---

<a id="22-growth"></a>
## 22. Growth & Conversion

**Where:** backend `app/domain/referral/` (+ `referral/credit/`); frontend `/portal/referrals`
(`ReferralsPanel.tsx`).

- **Referral:** unique shareable codes (`?ref` capture at signup). The invitee gets the first-time
  discount; the referrer earns `referral_credit_ngn` (₦5,000 default) on the invitee's first payment.
- **Anti-farming:** eligibility requires a distinct verified human — self-referral is rejected and a
  duplicate verified **phone** voids the credit; a `card_fingerprint` column on `Payment` extends the same
  check to payment instruments once a live gateway populates it (null under the stub — §G).
- **Credit clearance mirrors commissions (§20.2):** credits are `PENDING` with
  `clearing_until = paid_at + chargeback_window_days`, swept to `CLEARED` (crediting the referrer's
  spendable `credit_balance_kobo`, firing `REFERRAL_CREDIT_EARNED`), one credit per invitee. This closes the
  refer-then-charge-back loop. Spent credit is debited at `PAID`, idempotently.
- **First-time discount:** `first_time_discount_percent` (10%), auto-applied, never a code; combined
  discounts cap at `max_discount_percent` (25%).
- **Abandonment recovery:** an abandoned draft triggers exactly one recovery email
  (`VERIFICATION_ABANDONMENT_RECOVERY`); the draft is preserved and the price re-lock guard (§10.4)
  protects against silent price changes on return.

---

<a id="23-admin-ops"></a>
## 23. Admin Operations & Analytics

**Where:** backend `app/domain/analytics/`, `finance/`, `broadcast/`, `system_config/`,
`verification/pricing_config/`, `verification/scoring/`; frontend `/admin/dashboard`, `/admin/analytics`,
`/admin/pricing`, `/admin/commission-rules`, `/admin/finance`, `/admin/broadcasts`, `/admin/config/*`.

- **Mission Control** (`/admin/dashboard`): active verifications, pending assignments, SLA-at-risk
  (`sla_at_risk_days` horizon), revenue, available agents; action items (pending agent applications, team
  invitations).
- **Analytics** — computed on read in Python over targeted repo pulls (nothing stored; materialise only if
  it becomes a hotspot): conversion funnel, avg verification time by tier, agent performance trends
  (`analytics_trend_months`, 6), revenue by tier & location, regional performance. RBAC `VIEW_ANALYTICS`;
  the dashboard renders dependency-free CSS bar charts.
- **Pricing** — DB-backed tier prices + line items (§10.2); edits change the next quote without a deploy;
  existing price locks are honoured. **Commission rules** — the bps table (§20.1), RBAC `CONFIGURE_PRICING`.
- **Trust Score Weights** — per tier × role CRUD with sum-to-100 validation (§13.3).
- **System configuration** — the typed `ConfigKey` key-value store (§R), seeded idempotently, RBAC-gated
  CRUD at `/admin/config/system`.
- **Broadcasts** — compose → preview reach → send now or schedule (swept), audiences All / Admins /
  Customers / Agents; fan-out publishes one `BROADCAST_ANNOUNCEMENT` event and the notification subscriber
  does the rest.
- **Finance** — payments/commissions summaries and the payout approval panel (§20.4).

---

<a id="24-audit-compliance"></a>
## 24. Audit & Compliance

**Where:** backend `app/domain/audit/` (+ `audit/pack_service.py`), `compliance/erasure/`; frontend
`/admin/audit/actions`, `/admin/erasure-requests`, `/account/consents`, `/account/data-privacy`.

### 24.1 Audit log

Append-only `AuditLog` (~70 `AuditActionType`s), written on every transition inside the transaction, with
actor, role, from→to, timestamp, IP, note, and per-item evidence hashes on evidence events. Indexed by
`(resource_type, resource_id)` for per-resource packs. Retained indefinitely.

### 24.2 Read models per actor

- **Admin action log** (`/admin/audit/actions`): permission/role changes, payout approvals, config edits.
- **Customer activity** (`/portal/verifications/[id]/activity`): a PII-safe simplified timeline (no actor
  IDs).
- **Agent task history** (`/agents/tasks/[id]/history`): the task's transition trail.

### 24.3 Legal packs & consent history

- **Verification audit-pack export** (admin): one flat CSV per VID gathering the whole verification object
  graph — every child resource's transitions, evidence content hashes, and the customer's versioned consent
  snapshots (`VerificationAuditPackService`). This is the §2.6 evidentiary backbone and the chargeback
  rebuttal input.
- **Consent history**: every user can view and CSV-download their own versioned consent records.

### 24.4 NDPA data erasure — pseudonymisation, not deletion

Self-service: the data subject opens a request from Account → Data & privacy (one open request per subject,
server-enforced). Review/approve/execute is gated on `MANAGE_COMPLIANCE` (**SUPER-only**; execute is
confirm-guarded and idempotent). Execution runs `PiiPseudonymiser`: a deterministic per-subject opaque token
replaces the subject's PII across **eight surfaces in one transaction** — `users` (name/email/phone/avatar/
password → login impossible), `audit_logs` (actor → token, IP nulled, **events retained**),
`device_sessions` (+revoked), `security_events`, `user_consents`, `oauth_identities`, `kyc_records`,
`agent_bank_accounts`. The erasure is itself recorded as an event. Retention knobs: `pii_retention_days`
(2555 ≈ 7 years), `erasure_request_review_sla_days` (30). The post-erasure legal basis is a launch gate
(§G); secondary-PII scope is a documented follow-up (§G).

---

<a id="25-dev-qa"></a>
## 25. Dev, Automation & QA

These are **permanent contracts** for autonomous QA (Playwright + Claude Code) — never remove them. See the
"Automation determinism" section of [CLAUDE.md](CLAUDE.md).

### 25.1 Determinism contracts

- **`OTP_MODE`**: `deterministic` → all OTPs are `TEST_OTP` (654123); `random` → CSPRNG codes.
  `ENVIRONMENT=test` requires `deterministic`; `prod` requires `random`; startup fails otherwise. Never
  infer OTP behaviour from `ENVIRONMENT`.
- **Stub matrix** (§4.13): payment, KYC, storage, FX, and geocoding default to deterministic stubs; the PDF
  renderer is real by default.

### 25.2 Dev endpoints (`app/domain/dev/`)

`POST /dev/reset` (clears domain rows, keeps the super-admin + reference seeds) and `POST /dev/seed`
(deterministic scenario: customer + approved agents across roles + an `UNDER_REVIEW`, SLA-overdue
verification with a recorded `SUCCEEDED` payment + a second "ops" verification crafted for
unhappy-path pool mechanics + a disposable erasable customer; returns credentials/ids). Production-gated
twice: the router only mounts in non-prod, and `_require_non_prod()` 404s in production. Also:
`GET /dev/messages/latest`, `POST /dev/messages/rewind`, and on-demand sweep triggers for the scheduled
jobs.

### 25.3 Email capture

In dev/local/test, SMTP email is captured by **Mailpit** (`localhost:1025`); the SMTP provider hard-fails in
production/staging. No `EMAIL_PROVIDER` setting — the router selects by `ENVIRONMENT`.

### 25.4 Frontend automation hooks

- Stable `data-testid` selectors on auth + wizard surfaces (`login-*`, `signup-*`, `verify-*`, `oauth-*`,
  `verify-new-*`, `verify-pay-*`, `agent-apply-*`). Never remove.
- Window hooks `__app_ready__`, `__auth_snapshot__`, `__oauth_complete__`, `__TEST_MODE__` — exposed only
  when `isAutomationEnvironment()` (from `@lib/automation`) is true; never gated on `NODE_ENV` or feature
  flags. The `__oauth_complete__` per-attempt lifecycle contract is defined in CLAUDE.md.

### 25.5 E2E drive-through suite

`backend/scripts/e2e_drive_through.py` runs the staged live-HTTP suite in `backend/scripts/e2e/` (shared
`harness.py`; `--stages` runs a contiguous prefix): onboarding → agent onboarding → admin team → execution
→ comms → review/release → tracking → sharing → aftermarket (disputes/re-checks/upgrades/payouts) → growth
→ admin ops → premium release → compliance → ops-unhappy (pool mechanics, fail+refund, chargeback) → email
→ messaging-retry. Stages have linear data dependencies; the email stages warn-skip without Mailpit/docker.
The drive-throughs exist because they repeatedly catch the UUID/transaction-boundary bug class that mocked
unit tests cannot (see the runtime-bug notes in [docs/decision-log.md](docs/decision-log.md)).

---

# Part III — Reference

<a id="n-navigation"></a>
## N. Top Navigation & Portal Menus

Authenticated surfaces share `AppShell` (`frontend/src/components/ui/AppShell.tsx`) with the persistent
top-right cluster, in order: **Support → Chat → Notifications → Account**, plus the `PortalSwitcher` (with
the cross-portal badge, §2.5) for multi-role users. Route registry: `frontend/src/lib/routes.ts`.

| Element | Icon | Counter | Behaviour |
|---|---|---|---|
| Support | Headset | None | Support page: FAQ + routes verification-specific issues into that verification's thread, general enquiries into `GENERAL_SUPPORT` |
| Chat | Bubble | Unread conversations, caps "9+", hidden at zero | Conversation list; opening marks read |
| Notifications | Bell | New notifications, caps "9+", hidden at zero | Dropdown + "View all" history page |
| Account | Avatar + first name | None | Account settings, Logout |

Chat carries all person-to-person conversations; the Notifications feed carries system updates only
(§17.3). Both counters are SSE-backed with the poll fallback.

### Customer portal (`/portal`)

Dashboard (backend-derived counts, resumable-draft recovery banner) · Verifications list (`DataTable`) +
New Verification wizard · per-verification: tracking, pay, confirmed, evidence, report, messages, activity ·
Chat · Notifications · Referrals · Support · notification preferences.

### Agent portal (`/agents`)

Dashboard (stats + application-status card) · Apply (onboarding wizard) · Tasks list + task execution /
history / messages · Earnings · Payouts · Disputes (defence view) · Profile (reputation) · Coverage
settings · notification preferences.

### Admin portal (`/admin`)

Dashboard (Mission Control) · Analytics · Verifications (list, detail control panel, messages,
report-review) · Disputes · Re-checks · Held messages · Broadcasts (+ compose) · Agent applications · Team ·
Finance (+ payouts) · Commission rules · Pricing · System config · Trust-score weights · Audit action log ·
Erasure requests.

### Account area (`/account`)

Personal info · Login & security · Devices · Linked accounts · Password · Consents · Data & privacy.

Several routes are declared in `routes.ts` but have no pages yet (admin content CMS, fraud-flags, finance
sub-pages, some detail pages) — the sidebars deliberately omit them; see §G.

---

<a id="r-configuration"></a>
## R. Configuration Reference

Two layers (see backend/CLAUDE.md "Where a knob lives"):

### R.1 Infra/deploy knobs — `Settings` (`.env.{env}` overridable, in-code defaults)

Selected keys (see `backend/main/app/config/settings.py` and `.env.example` for the full set):
`PAYMENT_STUB_MODE=True` · `ACTIVE_PAYMENT_METHOD` · `DOCUMENT_STORAGE_STUB_MODE=True` ·
`REPORT_PDF_STUB_MODE=False` · `KYC_PROVIDER=STUB` · `GEOCODING_PROVIDER=STUB` · `PRICING_FX_PROVIDER=STUB`
· `PHONE_VERIFICATION_ENABLED=False` · `LEGAL_OPINION_ENABLED=False` · `PRICE_LOCK_TTL_HOURS=24` ·
`IDEMPOTENCY_KEY_TTL_HOURS=24` · `ADMIN_INVITE_TTL_HOURS=72` · `KYC_SELFIE_REVIEW_THRESHOLD=80` ·
`AGENT_COMMISSION_SHARE=0.40` · `SSE_HEARTBEAT_SECONDS=25` · `SSE_QUEUE_MAXSIZE=100` ·
`MESSAGING_RETRY_INTERVALS_SECONDS=[60,300,900]` · `OTP_MODE` (env-enforced, §25.1).

### R.2 Admin-tunable business rules — `system_config` `ConfigKey` store

Typed KV (`app/domain/system_config/models.py`), seeded idempotently, editable at `/admin/config/system`
without a redeploy:

| Key | Default | Meaning |
|---|---|---|
| `dispute_window_days` | 30 | Days after COMPLETED during which a dispute may be filed |
| `recheck_price_pct` | 30 | Re-check fee as % of the original tier price |
| `agent_dispute_defence_hours` | 48 | Agent's window to respond to a dispute on their task |
| `commission_clearance_days` | 7 | Days after approval before the commission bulk is withdrawable |
| `commission_reserve_pct` | 10 | % of commission held until the chargeback window closes |
| `chargeback_window_days` | 120 | Card-chargeback window (reserve release; referral-credit clearance) |
| `task_sla_hours` | 48 | Accept→submit target feeding the timeliness metric |
| `agent_low_performance_threshold` | 40 | Composite below which ranking visibility is reduced |
| `agent_top_agent_accuracy_threshold` | 90 | Accuracy at/above which the Top Agent badge is earned |
| `agent_wide_coverage_states` | 6 | Coverage state-count above which an agent is flagged for review |
| `first_time_discount_percent` | 10 | Auto discount on a customer's first verification |
| `referral_credit_ngn` | 5,000 | Referrer credit (whole NGN) on invitee's first payment |
| `max_discount_percent` | 25 | Combined discount cap |
| `cancellation_surcharge_pct` | 20 | Surcharge on cancellation after assignment |
| `pii_retention_days` | 2555 | PII retention before the NDPA erasure window (≈7 years) |
| `erasure_request_review_sla_days` | 30 | SLA to review an erasure request |
| `sla_at_risk_days` | 2 | Dashboard horizon for at-risk verifications |
| `payout_sla_business_days` | 2 | Target business days to settle an approved payout |
| `dispute_min_description_chars` | 100 | Minimum characters to file a dispute |
| `share_link_default_expiry_days` | 30 | Default lifetime of a report share link |
| `analytics_trend_months` | 6 | Trailing months in analytics trend series |

Defaults are working placeholders; the money-adjacent ones (pricing, discounts, reserve %, surcharge) still
need business sign-off (§G).

---

<a id="g-known-gaps"></a>
## G. Known Gaps & Roadmap

The single consolidated list of deliberately deferred work. Every entry with a code home is marked
**`TODO(gap):`** at that location — `grep -rn "TODO(gap)"` enumerates them all.

### G.1 Stub-first integrations pending live wiring

| Gap | Code home |
|---|---|
| Live Paystack/Flutterwave collection (checkout, webhooks, refunds run against the deterministic stub) | `backend/main/app/domain/payment/service.py` |
| Card-fingerprint capture (referral anti-farming's payment-instrument half is dark under the stub) | `backend/main/app/domain/payment/models.py` |
| `STRIPE` enum value has no integration | `backend/main/app/config/settings.py` (`PaymentMethod`) |
| Live Dojah KYC (facade built; STUB default) | `backend/main/app/domain/user/agent/kyc/service.py` |
| Live document storage (S3/R2 behind the facade; stub default) | storage facade (`appodus_utils` integrations) |
| Live FX rates (`OPENEXCHANGERATES` option unwired; hardcoded indicative stub rates) | `backend/main/appodus_utils/db/types/money.py` |
| Real payout disbursement (approval marks `PAID` under the stub) | `backend/main/app/domain/payout/service.py` |

### G.2 Deferred features

| Gap | Code home |
|---|---|
| Offline evidence upload queue + client compression (libs exist, unwired) & server-side image derivatives / progressive viewing | `frontend/src/components/agents/tasks/AgentTaskDetail.tsx`, `frontend/src/lib/uploadService.ts` |
| Chat attachments (JSONB column reserved; no upload UI/endpoint) | `backend/main/app/domain/communication/chat_message/models.py` |
| Message-hold severity tiers (single hold behaviour; tune from false-positive data) | fraud scan in `backend/main/app/domain/communication/service.py` |
| Chargeback rebuttal-pack placeholder fields (`report`, `evidence_hashes`) | `backend/main/app/domain/payment/chargeback/service.py` |
| Redis multi-instance SSE fan-out (in-process emitter today; poll fallback keeps correctness) | `backend/main/app/core/realtime/emitter.py` |
| Per-agent pool-feed visibility reduction (ranking-only today; pool is untargeted accept-by-id) | `backend/main/app/domain/user/agent/reputation/service.py` |
| Richer per-role quality rubric feeding the composite score | `backend/main/app/domain/verification/review/service.py` |
| Secondary-PII erasure scope (card fingerprints, share-recipient emails, property addresses — each needs its own retention basis) | `backend/main/app/domain/compliance/erasure/service.py` |
| Role-specific agent dashboard variants (one unified dashboard today) | `frontend/src/components/agents/dashboard/AgentDashboard.tsx` |
| Cartographic Nigeria map paths (schematic geo-grid today) | `frontend/src/components/agents/reputation/NigeriaCoverageMap.tsx` |
| Declared-but-unbuilt routes: admin content CMS (how-it-works / FAQs / testimonials / spotlights / area insights), fraud-flags, finance payments/commissions sub-pages, dispute/broadcast/task detail pages, portal payments page | `frontend/src/lib/routes.ts` |
| Marketing footer social links are placeholders | `frontend/src/components/website/home.data.ts` |

### G.3 Launch gates (business/legal — not code)

- **Tier pricing sign-off** — seeded prices (₦50k/₦120k/₦300k) and all §R.2 money defaults are placeholders.
- **Limitation-of-liability final clause copy** (1× fees cap + carve-outs) — blocks paid go-live.
- **NBA counsel sign-off + lawyer-role PI cover** — gates flipping `LEGAL_OPINION_ENABLED` (Premium Legal
  Opinion display).
- **Admin staffing commitment** ("N admins sustain M verifications/day") — pre-launch gate for the ops SLAs.
- **Post-erasure legal basis + re-identification risk** sign-off (§24.4).
- **Cross-border enforceability** of the Nigeria forum clause — per-market, as volume warrants.

### G.4 Post-MVP roadmap

| Initiative | Description |
|---|---|
| **Property Identity Layer** | Market-wide layer on the already-separate Property entity: price & ownership history, dedup intelligence |
| **Escrow / Transaction Layer** | Facilitate the purchase itself — hold funds, release on title transfer (separate regulated product) |
| **Deep Trust & Anti-Fraud** | Cross-verification pattern detection, document-hash registry, fraudulent-seller database; device-graph referral detection |
| **Trust-gated auto-approval** | High-accuracy agents skip manual review — first post-launch priority once reputation data accrues |
| **Verification Academy / Content Hub** | Education content (pairs with the unbuilt admin content CMS) |
| **WhatsApp / push delivery** | New event-bus subscribers |
| **Mobile apps (iOS/Android)** | Native parity for customers and field agents |

---

<a id="x-phase-map"></a>
## X. Appendix: v2.4 Phase → Module Map

Older documents and code comments cite v2.4 phase/section numbers. Translate:

| v2.4 phase | This document |
|---|---|
| Phase 0 — Platform Foundation | §4 Architecture, §5 Cross-cutting |
| Phase 1 — Marketing Site | §6 |
| Phase 2 — Auth & Onboarding Shell | §7 |
| Phase 3 — Agent Onboarding & KYC | §8 |
| Phase 4 — Admin Onboarding & RBAC | §9 |
| Phase 5 — Customer Submission & Payment | §10 |
| Phase 6 — Admin Verification Control Panel | §11 |
| Phase 6a — Chargeback Handling | §20.2 + `payment/chargeback/` (flag + rebuttal pack + won/lost; never a verification state) |
| Phase 7 — Agent Task Execution | §12 |
| Phase 8 — Admin Review & Report Release | §13 |
| Phase 9 — Customer Tracking & Evidence | §14 |
| Phase 10 — Final Report Experience | §15 |
| Phase 11 — Communication Layer | §16 |
| Phase 12 — Notification System & Event Bus | §17 |
| Phase 13 — Public Lookup & Sharing | §18 |
| Phase 14 — Revision, Re-verification & Disputes | §19 |
| Phase 15 — Agent Earnings & Commission | §20 |
| Phase 16 — Agent Reputation & Coverage | §21 |
| Phase 17 — Growth & Conversion | §22 |
| Phase 18 — Admin Operations & Analytics | §23 |
| Phase 19 — Audit & Compliance Maturity | §24 |
| §2 State Machines · §4 Architecture Decisions | §3 · §4 (numbering 4.1–4.11 preserved) |
| §A Resolved Decisions | [docs/decision-log.md](docs/decision-log.md) (D1–D41) |
| §B Open Items · §D Hardening Backlog | §G |
| §N Top-Nav · §M Menu Maps | §N |

---

<a id="c-success-metrics"></a>
## C. Success Metrics

| Metric | Definition | Target |
|---|---|---|
| Avg completion time | `PAID` → `COMPLETED`, by tier | Basic ≤5d · Standard ≤7d · Premium ≤10d |
| % completed without revision | No task ever hit `REJECTED` | > 80% |
| Median task acceptance time | Assignment/broadcast → `ACCEPTED` | < 2 hours |
| Agent no-show rate | Tasks timed out unaccepted | < 5% |
| SLA breach rate | Exceeded tier SLA | < 10% |
| Customer trust rating | Post-report satisfaction (1–5) | ≥ 4.5 |
| Admin report release time | All tasks reviewed → released | < 4 hours |
| Message false-positive rate | Held messages later approved | Track & minimise |
| Chargeback rate / win rate | Chargebacks ÷ paid · rebuttals won | Track & minimise / maximise |
| Pool-starvation rate | Broadcasts hitting the starvation backstop | Low; flags underserved areas |
| Signup → payment conversion | First-verification activation | TBD |
| Abandoned-draft recovery rate | Drafts paid within 7 days of the recovery email | TBD |

---

*v3.0 as-built consolidation. State machines (§3) and architecture (§4) are authoritative over all prose.
Implementation rationale: [docs/decision-log.md](docs/decision-log.md). Verification of completeness:
[docs/final-audit.md](docs/final-audit.md). Deferred work: §G, mirrored as `TODO(gap):` markers in code.*
