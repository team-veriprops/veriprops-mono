# Veriprops — Verification Lifecycle
## Product Requirements Document (PRD)

**Product:** Veriprops  
**Module:** Verification Lifecycle — Customer Flow, Agent Lifecycle, Admin Approvals  
**Version:** 2.0  
**Stack:** Next.js (App Router), REST API backend  
**Status:** Draft  

**Changelog:**
| Version | Date | Changes |
|---|---|---|
| 1.0 | Apr 2026 | Initial draft — customer verification flow, payment, report |
| 2.0 | Apr 2026 | Rewritten as full lifecycle PRD. Added: deterministic state machine (global + task), ACCEPTED task state, FAILED terminal state, derived state logic, progress formula, forward-only invariants, conflicting reports handling, agent no-show/timeout, agent lifecycle (all role types), admin approval workflow, audit logging, success metrics |

---

## Table of Contents

**PART A — ARCHITECTURE**
1. [Overview](#1-overview)
2. [Domain Model](#2-domain-model)
3. [State Machines](#3-state-machines)

**PART B — CUSTOMER FLOW**
4. [Entry Points & Flow Architecture](#4-entry-points--flow-architecture)
5. [Property Submission Wizard](#5-property-submission-wizard)
6. [Pricing Transparency UI](#6-pricing-transparency-ui)
7. [Legal Consent & Disclaimer](#7-legal-consent--disclaimer)
8. [Payment Experience](#8-payment-experience)
9. [Post-Payment Confirmation & Verification Activation](#9-post-payment-confirmation--verification-activation)
10. [Verification Tracking Dashboard](#10-verification-tracking-dashboard)
    - 10.3 In Progress Expanded View
    - 10.4 PAID State Experience
    - 10.5 Under Review Expanded View
11. [Evidence & Transparency Layer](#11-evidence--transparency-layer)
12. [Final Report Experience](#12-final-report-experience)
13. [Revision & Re-verification Flow](#13-revision--re-verification-flow)
13a. [Public Verification Lookup](#13a-public-verification-lookup)
13b. [Dispute Flow (Customer)](#13b-dispute-flow-customer)
14. [Communication Layer](#14-communication-layer)
    - 14.3 Admin ↔ Agent Channel
    - 14.4 Agent Identity Display Rule
    - 14.5 Message Fraud Detection
15. [Notification System](#15-notification-system)
16. [Growth & Conversion Mechanics](#16-growth--conversion-mechanics)
17. [Location Intelligence UX](#17-location-intelligence-ux)
18. [History & Record Keeping](#18-history--record-keeping)

**PART C — AGENT LIFECYCLE**
19. [Agent Task Dashboard](#19-agent-task-dashboard)
20. [Job Discovery & Acceptance](#20-job-discovery--acceptance)
21. [Role-Specific Submission UIs](#21-role-specific-submission-uis)
22. [Agent Escalation & Issue Reporting](#22-agent-escalation--issue-reporting)
23. [Agent Commission & Earnings System](#23-agent-commission--earnings-system)
24. [Agent Reputation System](#24-agent-reputation-system)
25. [Agent Location & Coverage Management](#25-agent-location--coverage-management)
26. [Agent Role-Based Dashboard Differentiation](#26-agent-role-based-dashboard-differentiation)

**PART D — ADMIN LIFECYCLE**
27. [Verification Control Panel](#27-verification-control-panel)
28. [Agent Assignment & Coordination](#28-agent-assignment--coordination)
29. [Task Approval & Report Release](#29-task-approval--report-release)
30. [Conflict Detection & Failure Handling](#30-conflict-detection--failure-handling)

**PART E — CROSS-CUTTING**
31. [Audit & Compliance Logging](#31-audit--compliance-logging)
32. [Edge Cases](#32-edge-cases)
33. [Success Metrics](#33-success-metrics)
34. [UI/UX Specifications](#34-uiux-specifications)
35. [Error, Loading & Success States](#35-error-loading--success-states)
36. [API Contract](#36-api-contract)
37. [Open Questions](#37-open-questions)

---

# PART A — ARCHITECTURE

---

## 1. Overview

### 1.1 Purpose

This document defines the complete product requirements for the Veriprops verification lifecycle — from the moment a customer initiates a request through every agent task, admin review gate, and final report delivery.

It covers three actor perspectives:
- **Customer** — submits, pays, tracks, and receives the report.
- **Agent** — discovers jobs, submits structured findings per role.
- **Admin** — assigns agents, approves or rejects submissions, releases the report.

### 1.2 Core Design Principles

1. **Deterministic state machine.** No undefined transitions. No hidden states. Every actor always knows exactly what state the system is in.
2. **Dual-layer model.** The verification has a global state. Each agent role has an independent task state. The global state is *derived* from task states — not set manually.
3. **Admin-controlled quality gate.** No report reaches the customer without admin approval of every task.
4. **Customer abstraction layer.** Customers see a simplified, trust-building progress view — not the raw internal task states.
5. **Forward-only progression.** The verification state machine moves forward only. The only permitted backward movement is `REJECTED → IN_PROGRESS` at the *task level* — not at the verification level.
6. **Legal defensibility.** Every state transition is logged with actor, timestamp, and context. All consent is versioned and recorded per-verification.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| Verification global state machine | Platform pricing configuration (Admin PRD) |
| Task state machine (per agent role) | Agent KYC and onboarding (Auth PRD) |
| Customer submission wizard (full) | Commission payout logic |
| Payment (full depth: FX, retry, refund) | Agent performance scoring algorithm |
| Tracking dashboard, evidence viewer | Escrow / transaction layer (Post-MVP) |
| Final report (UI, PDF, sharing) | Auto agent assignment AI (Post-MVP) |
| Agent task flows (all 4 role types) | |
| Admin assignment, approval, release | |
| Audit logging | |

### 1.4 Prerequisites

- Customer is authenticated with verified email + phone (Auth PRD).
- Agent is authenticated, KYC-approved, and their application is in `APPROVED` status (Auth PRD).
- Admin is authenticated with appropriate role (Auth PRD).
- Platform Terms (current version) accepted by all actors.

---

## 2. Domain Model

### 2.1 Entities

#### Verification
| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Internal system ID |
| `verification_id` | String | Public-safe ID. Format: `VP-YYYY-XXXXXX` e.g. `VP-2026-048291` |
| `status` | Enum | Global state (see Section 3.1) |
| `tier` | Enum | `BASIC` / `STANDARD` / `PREMIUM` |
| `property_id` | UUID | FK → Property |
| `customer_id` | UUID | FK → User |
| `consent_snapshot_id` | UUID | FK → ConsentSnapshot accepted at time of submission |
| `price_locked_at` | Timestamp | When price was locked |
| `price_locked_ngn` | Decimal | NGN amount locked at checkout |
| `sla_deadline` | Timestamp | Computed from `PAID` timestamp + tier SLA |
| `created_at` | Timestamp | |
| `updated_at` | Timestamp | |

#### Task
| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `verification_id` | UUID | FK → Verification |
| `role_type` | Enum | `FIELD_AGENT` / `SURVEYOR` / `REGISTRY_AGENT` / `LAWYER` |
| `assigned_agent_id` | UUID | FK → User (Agent) — nullable until assigned |
| `status` | Enum | Task state (see Section 3.2) |
| `accepted_at` | Timestamp | When agent accepted the job |
| `started_at` | Timestamp | When agent began work |
| `submitted_at` | Timestamp | When agent submitted findings |
| `approved_at` | Timestamp | When admin approved |
| `deadline` | Timestamp | Task-level SLA deadline |
| `rejection_reason` | Text | Set by admin when rejecting |

#### Report
| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `verification_id` | UUID | FK → Verification |
| `version` | String | e.g. `v1.0`, `v1.1`, `v2.0` |
| `status` | Enum | `DRAFT` / `APPROVED` |
| `trust_score` | Integer | 0–100, computed on approval |
| `generated_at` | Timestamp | |
| `approved_at` | Timestamp | Set by admin on release |

#### AuditLog
| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `entity_type` | String | `VERIFICATION` / `TASK` / `REPORT` |
| `entity_id` | UUID | |
| `actor_id` | UUID | FK → User |
| `actor_role` | String | `CUSTOMER` / `AGENT` / `ADMIN` / `SYSTEM` |
| `from_state` | String | |
| `to_state` | String | |
| `note` | Text | Optional context (e.g. rejection reason) |
| `timestamp` | Timestamp | |

### 2.2 Tier → Required Task Roles

| Tier | REGISTRY_AGENT | FIELD_AGENT | SURVEYOR | LAWYER |
|---|---|---|---|---|
| Basic | ✅ | ❌ | ❌ | ❌ |
| Standard | ✅ | ✅ | ✅ | ❌ |
| Premium | ✅ | ✅ | ✅ | ✅ |

> **Lawyer dependency:** The Lawyer task cannot begin until all other tasks for the tier reach `SUBMITTED`. The system enforces this at the task level — the Lawyer's task status remains `PENDING` until the condition is met, then transitions to `ASSIGNED` automatically once a lawyer has been assigned.

---

## 3. State Machines

### 3.1 Verification State Machine (Global)

#### States

| State | Code | Description |
|---|---|---|
| Draft | `DRAFT` | Wizard started. Verification ID assigned. Not yet submitted. |
| Submitted | `SUBMITTED` | Wizard complete. Awaiting payment initiation. |
| Payment Pending | `PAYMENT_PENDING` | Payment initiated. Awaiting gateway confirmation. |
| Paid | `PAID` | Payment confirmed. Awaiting agent assignment by admin. |
| In Progress | `IN_PROGRESS` | ≥1 task has been assigned. Work underway. |
| Under Review | `UNDER_REVIEW` | All tasks submitted. Admin reviewing for approval. |
| Completed | `COMPLETED` | All tasks approved. Report published to customer. |
| Disputed | `DISPUTED` | Customer raised a formal post-completion dispute. Admin must resolve. |
| Cancelled | `CANCELLED` | Cancelled by customer or admin. Refund rules applied. Terminal. |
| Refunded | `REFUNDED` | Dispute upheld by admin. Refund issued. Terminal. |
| Failed | `FAILED` | Critical failure (confirmed fraud, permanent inaccessibility). Terminal. |

#### Transitions

| From | To | Trigger | Actor | Condition |
|---|---|---|---|---|
| `DRAFT` | `SUBMITTED` | Customer completes wizard | Customer | All required fields valid |
| `SUBMITTED` | `PAYMENT_PENDING` | Payment initiated | System | — |
| `PAYMENT_PENDING` | `PAID` | Payment confirmed | System | Gateway success event |
| `PAYMENT_PENDING` | `SUBMITTED` | Payment failed / abandoned | System | Gateway failure / timeout |
| `PAID` | `IN_PROGRESS` | First task assigned | Admin | ≥1 required task assigned |
| `IN_PROGRESS` | `UNDER_REVIEW` | All tasks submitted | System | ALL tasks = `SUBMITTED` or `APPROVED` |
| `UNDER_REVIEW` | `IN_PROGRESS` | Any task rejected | System | ANY task → `REJECTED` |
| `UNDER_REVIEW` | `COMPLETED` | All tasks approved + report released | Admin | ALL tasks = `APPROVED` |
| `COMPLETED` | `DISPUTED` | Customer files formal dispute | Customer | Within dispute window (admin-configured, e.g. 30 days) |
| `DISPUTED` | `COMPLETED` | Admin rejects dispute | Admin | Dispute found unsubstantiated |
| `DISPUTED` | `REFUNDED` | Admin upholds dispute | Admin | Veriprops at fault; refund issued |
| `ANY` | `CANCELLED` | Cancellation requested | Customer or Admin | Refund rules handled by backend |
| `IN_PROGRESS` | `FAILED` | Critical failure declared | Admin or System | Confirmed fraud / permanent inaccessibility |

#### Invariants

- States cannot be skipped. Transitions must follow the table above.
- The verification state machine is **forward-only** at the global level. The only permitted backward movements are: `UNDER_REVIEW → IN_PROGRESS` (task rejection loop), `DISPUTED → COMPLETED` (dispute rejected).
- `CANCELLED`, `REFUNDED`, and `FAILED` are terminal states. No further transitions permitted.
- `COMPLETED` requires ALL tasks to be `APPROVED` — not merely `SUBMITTED`. `COMPLETED` is not terminal — it can transition to `DISPUTED` within the dispute window.
- `DISPUTED` suspends the dispute window clock. The report remains accessible to the customer throughout.

#### Derived Global State Logic

The verification's global state is *derived* from task states — not set by a human clicking a button. The system applies these rules in order:

| Condition | Global State |
|---|---|
| Payment not confirmed | `PAYMENT_PENDING` |
| Payment confirmed, no tasks assigned | `PAID` |
| ≥1 task is `ASSIGNED`, `ACCEPTED`, or `IN_PROGRESS` | `IN_PROGRESS` |
| ALL tasks are `SUBMITTED` or `APPROVED`, and ≥1 is still `SUBMITTED` | `UNDER_REVIEW` |
| ALL tasks are `APPROVED` | `COMPLETED` (system triggers, admin confirms release) |
| ANY task moves to `REJECTED` from `UNDER_REVIEW` | `IN_PROGRESS` (revision loop) |
| Admin declares critical failure | `FAILED` |
| Customer files dispute post-completion | `DISPUTED` |
| Admin rejects dispute | `COMPLETED` |
| Admin upholds dispute | `REFUNDED` |

---

### 3.2 Task State Machine (Per Agent Role)

#### States

| State | Description |
|---|---|
| `PENDING` | Task created for this role. No agent assigned yet. |
| `ASSIGNED` | Admin assigned an agent. Agent has not yet accepted. |
| `ACCEPTED` | Agent explicitly accepted the job. Clock starts. |
| `IN_PROGRESS` | Agent has begun active work. |
| `SUBMITTED` | Agent submitted findings. Awaiting admin review. |
| `REJECTED` | Admin rejected submission. Agent must rework. |
| `APPROVED` | Admin approved submission. Task is complete. |

#### Transitions

| From | To | Trigger | Actor | Notes |
|---|---|---|---|---|
| `PENDING` | `ASSIGNED` | Assign agent | Admin | |
| `ASSIGNED` | `ACCEPTED` | Accept job | Agent | Agent confirms they will take the job |
| `ASSIGNED` | `PENDING` | Decline / timeout | Agent or System | Timeout window configured by admin. Task re-enters pool. |
| `ACCEPTED` | `IN_PROGRESS` | Start work | Agent | |
| `IN_PROGRESS` | `SUBMITTED` | Submit findings | Agent | |
| `SUBMITTED` | `APPROVED` | Approve submission | Admin | |
| `SUBMITTED` | `REJECTED` | Reject submission | Admin | Rejection reason required |
| `REJECTED` | `IN_PROGRESS` | Agent begins rework | Agent | Only permitted backward transition in the system |

#### Invariants

- Only **Admin** can `APPROVE` or `REJECT` a task.
- Only an **Agent** can `SUBMIT` a task.
- Only an **Agent** can `ACCEPT` or `DECLINE` a task.
- The transition `REJECTED → IN_PROGRESS` is the **only** backward movement permitted anywhere in the system.
- Approving or rejecting a task does not affect sibling tasks for the same verification.

#### Progress Formula

```
Progress % = (Approved Tasks ÷ Total Required Tasks for Tier) × 100
```

- Displayed on both the customer tracking dashboard and the admin control panel.
- Task counts are tier-specific (Basic: 1 task, Standard: 3, Premium: 4).
- Example: Standard tier, 1 of 3 tasks approved → Progress = 33%.

---

# PART B — CUSTOMER FLOW

---

## 4. Entry Points & Flow Architecture

### 4.1 High-Level Flow

```
Customer clicks "Verify a Property"
  │
  ├── [Not authenticated] → Auth gate → Login/Signup → Return here
  │
  └── [Authenticated, CUSTOMER persona]
        │
        └── Property Submission Wizard (Steps 1–4)
              │
              ├── Step 1: Property Details          → DRAFT created, ID assigned
              ├── Step 2: Tier Selection + Pricing
              ├── Step 3: Legal Consent             → SUBMITTED
              └── Step 4: Payment                  → PAYMENT_PENDING → PAID
                    │
                    ├── [Payment failed] → Retry → back to SUBMITTED
                    │
                    └── [Payment confirmed] → PAID
                          │
                          └── Admin assigns agents → IN_PROGRESS
                                │
                                ├── Tracking Dashboard (live)
                                ├── Evidence Viewer
                                ├── Per-verification Chat
                                │
                                └── All tasks APPROVED → COMPLETED
                                      │
                                      └── Report published
                                            ├── View in-app
                                            ├── Download PDF
                                            └── Share
```

### 4.2 Verification Identity

Every verification is assigned a canonical identity at `DRAFT` creation:

| Field | Description |
|---|---|
| **Verification ID** | Human-readable, unique, public-safe. Format: `VP-YYYY-XXXXXX`. Shareable. |
| **Internal UUID** | System UUID for backend operations. Never exposed publicly. |
| **Certificate** | Issued at `COMPLETED`. "This property has been verified by Veriprops." Linked to Verification ID. |

The Verification ID is shown to the customer immediately on Step 1, displayed on the dashboard, report, and all communications, and usable in the public lookup (`/verify/[id]`).

### 4.3 Customer Actions by State

| Verification State | Available Customer Actions |
|---|---|
| `DRAFT` | Edit wizard / Submit |
| `SUBMITTED` | — (awaiting payment initiation) |
| `PAYMENT_PENDING` | Retry payment |
| `PAID` | View confirmation, download receipt |
| `IN_PROGRESS` | View progress, view evidence, send message |
| `UNDER_REVIEW` | View status, view evidence, send message |
| `COMPLETED` | View/download report, share report, request re-check, upgrade tier |
| `ANY` | Request cancellation, contact support |

### 4.4 Customer Restrictions

- No direct agent interaction.
- Cannot modify the verification workflow after submission.
- Cannot approve or reject any task.
- Cannot access other customers' verifications.

---

## 5. Property Submission Wizard

**Route:** `/portal/verifications/new`

**Entry point:** "Verify a Property" CTA (homepage or portal dashboard). Incomplete drafts are resumed automatically.

The submission wizard is a **4-step guided flow**. A persistent step indicator is shown at the top. Progress is auto-saved to the backend on each step completion.

```
[1. Property Details] → [2. Tier & Pricing] → [3. Consent] → [4. Payment]
```

A Verification ID (`DRAFT` state) is generated when the user first lands on Step 1.

---

### 5.1 Step 1A — Property Source

**Heading:** "Tell us about the property"

| Option | Description |
|---|---|
| **Enter details manually** | Structured form (default) |
| **Paste a listing URL** | URL from PropertyPro, Nigeria Property Centre, etc. — backend pre-fills available fields |

**Listing URL Parsing:**
- URL input + "Import" button.
- Backend extracts: title, location, price, property type, images, seller contact.
- Pre-filled fields marked with "Imported" badge. All editable.
- If parsing fails: friendly error, fallback to manual entry.

---

### 5.2 Step 1B — Property Type

Two selectable cards:

| Card | Icon | Label | Sub-label |
|---|---|---|---|
| Land | 🌍 | Land / Plot | Bare land, developed plots, agricultural land |
| Building | 🏠 | Building / Structure | Houses, flats, commercial buildings, under construction |

Selection drives conditional fields in Step 1D.

---

### 5.3 Step 1C — Property Location

| Field | Type | Validation | Notes |
|---|---|---|---|
| Address | Google Maps autocomplete | Required | Restricted to Nigeria. Returns `lat`, `lng`, state, LGA. |
| State | Auto-filled | Required | Editable override |
| LGA | Auto-filled | Required | Editable override |
| Landmark / Description | Textarea (max 300 chars) | Optional | Helps agents find the property |

Map preview pin shown after address selection.

> **UX note:** Label the landmark field: "Help the agent find it: nearest junction, landmark, or local description." This is a critical escape valve for diaspora customers who may not know exact street addresses.

---

### 5.4 Step 1D — Property Details (Conditional)

#### Land Fields

| Field | Type | Validation |
|---|---|---|
| Plot Size | Number + unit selector (sqm / hectares / plots) | Optional |
| Land Use | Dropdown: Residential / Commercial / Agricultural / Mixed / Unknown | Required |
| Survey Plan Available? | Yes / No / Unknown | Required |
| Current State | Dropdown: Bare / Fenced / Partially Developed | Required |

#### Building Fields

| Field | Type | Validation |
|---|---|---|
| Building Type | Dropdown: Detached / Semi-detached / Flat / Commercial / Under Construction | Required |
| Number of Floors | Number | Optional |
| Approximate Age | Dropdown: <5 yrs / 5–10 / 10–20 / 20+ / Unknown | Optional |
| Current Occupancy | Dropdown: Owner-occupied / Tenanted / Vacant / Unknown | Required |
| C of O Available? | Yes / No / Unknown | Required |

---

### 5.5 Step 1E — Document Upload

Optional — but significantly improves report quality and speed.

| Document Type | Formats | Max Size |
|---|---|---|
| Survey Plan | JPG, PNG, PDF | 10MB |
| Title Document (C of O, Deed, etc.) | JPG, PNG, PDF | 10MB |
| Previous Purchase Agreement | PDF | 10MB |
| Other Documents | JPG, PNG, PDF | 10MB each |

Upload UI: drag-and-drop, progress bar, per-file delete/replace, thumbnail preview.

> "Your documents are encrypted and only accessible to verified agents assigned to your case. We never share your documents with third parties."

---

### 5.6 Step 1F — Seller / Owner Information

Optional. Labelled: "Recommended — helps our agents verify ownership faster."

| Field | Type |
|---|---|
| Seller Name | Text |
| Seller Phone | Phone with country flag |
| Seller Email | Email |
| Relationship to Property | Dropdown: Owner / Agent / Developer / Unknown |
| Additional Notes | Textarea (max 500 chars) |

---

### 5.7 Step 1 — Summary & Review

Read-only collapsible summary before advancing to Step 2. User can expand any section to edit.

---

## 6. Pricing Transparency UI

**Route:** `/portal/verifications/new?step=2`

### 6.1 Tier Selection Cards

Three selectable cards. Tier content:

| Tier | Includes | SLA |
|---|---|---|
| 🟦 **Basic** "Confirm the paperwork" | Registry search, Title doc verification, Ownership confirmation | 3–5 business days |
| 🟨 **Standard** "See it and verify it" | Everything in Basic + Physical site inspection + Boundary/location confirmation | 5–7 business days |
| 🟥 **Premium** "Full due diligence" | Everything in Standard + Encumbrances & fraud assessment + Legal opinion | 7–10 business days |

**Recommendation engine:** If customer indicated "C of O: Unknown" or "Survey Plan: Unknown" in Step 1, show soft banner: "Based on your property details, we recommend Standard or Premium."

### 6.2 Tier Comparison Modal

"Compare tiers" opens a modal with a full feature/tier matrix.

### 6.3 Pricing Breakdown

Expands below tier cards on selection. Line-item breakdown fetched dynamically from admin-configured pricing API. Example:

```
Verification Breakdown — Standard Tier
─────────────────────────────────────────
Registry Search                  ₦ 15,000
Title Document Review            ₦ 20,000
Ownership Confirmation           ₦ 10,000
Physical Site Inspection         ₦ 35,000
Boundary & Location Survey       ₦ 30,000
─────────────────────────────────────────
Subtotal                         ₦110,000
Service Fee (10%)                ₦ 11,000
─────────────────────────────────────────
Total                            ₦121,000
```

### 6.4 Currency Display & FX Transparency

Currency pill tabs: `NGN` | `USD` | `GBP` | `EUR`. Defaults to user's preferred currency.

Non-NGN selection: real-time conversion with FX rate shown:
```
Total        ₦121,000   ($75.40 USD)
FX Rate: 1 USD = ₦1,605.60 (Refreshed 3 mins ago)
```

FX rates fetched at page load, cached 5 minutes. If > 30 minutes old: show stale warning.

### 6.5 Price Lock

On "Continue to Payment": price (including FX rate) is **locked** and stored on the verification record.

- Lock validity: 24 hours. After expiry, re-locks at current rate.
- Lock displayed prominently on payment screen: "Price locked today at 2:47 PM. Valid for 24 hours."

### 6.6 First-Time Customer Discount

Applied automatically on first verification. Amount configured by admin. Shown as:
```
🎉 First verification discount: 10% off — applied automatically
```

### 6.7 Referral Discount

Auto-applied if customer arrived via referral link. Stacks with first-time discount up to admin-configured cap.

---

## 7. Legal Consent & Disclaimer

**Route:** `/portal/verifications/new?step=3`

Required checkpoint. Payment is locked until all items accepted. No checkboxes are pre-checked.

### 7.1 Consent Items

**① Verification Disclaimer** — "Veriprops provides a professional verification service, not a guarantee. The report represents findings of independent agents at the time of inspection. Veriprops reduces uncertainty — it does not eliminate it."

**② Findings & Opinion Acknowledgement** — "Agent findings are professional opinions, not absolute facts. Veriprops is not liable for undisclosed disputes, future registry changes, or unavailable information."

**③ Jurisdiction & Platform-Only Transactions** — "Veriprops operates under Nigerian jurisdiction and is not responsible for any transactions made outside the platform."

**④ Communication Recording** — "All communications on the Veriprops platform are recorded for quality, security, and audit purposes."

**⑤ Refund & Cancellation Policy** — "If I cancel before IN_PROGRESS status, a cancellation surcharge of [X]% applies. No refunds after work has begun, except where Veriprops is at fault."

Each item has an expandable "Read full text" section with plain-language detail.

### 7.2 Consent Recording

On "Agree & Continue to Payment":
- Each consent item recorded against its current version (see Auth PRD §4.9).
- Stored: user ID, consent type, consent version, timestamp, IP, device fingerprint.
- Verification record stores `consent_snapshot_id` — the legal trail for this specific verification.

---

## 8. Payment Experience

**Route:** `/portal/verifications/new?step=4`

### 8.1 Payment Summary Header

Locked summary showing property, tier, Verification ID, locked amount, FX rate, and lock time. "Change tier" and "Change currency" return to Step 2 without data loss.

### 8.2 Payment Currency Selection

| Currency | Methods Available |
|---|---|
| NGN (₦) | Card, Bank Transfer |
| USD ($) | Card (international), Wire Transfer |
| GBP (£) | Card (international), Wire Transfer |
| EUR (€) | Card (international), Wire Transfer |

Non-NGN: shows converted amount using locked rate + bank fee disclaimer.

### 8.3 Payment Methods

**💳 Card** — Visa, Mastercard, Verve. Embedded gateway iframe (PCI-DSS). Optional save card (opt-in).

**🏦 Bank Transfer (NGN only)** — Dedicated virtual account per transaction. 24-hour expiry. "I've made the transfer" button triggers polling. Auto-activates within 15 minutes of receipt.

**🌍 International Wire (USD/GBP/EUR)** — SWIFT/IBAN details shown. Customer uploads proof or enters reference. Admin confirms receipt manually. Takes 1–3 business days.

### 8.4 Payment Status UI

| State | Icon | Heading | Notes |
|---|---|---|---|
| Initiated | ⏳ | "Processing your payment..." | Do not close. |
| Processing | 🔄 | "Verifying with your bank..." | < 30 seconds. |
| Succeeded | ✅ | "Payment confirmed!" | Auto-redirect in 3s. |
| Failed | ❌ | "Payment was not completed" | Show reason + retry. |
| Pending (Bank Transfer) | ⌛ | "Waiting for transfer confirmation" | ~15 min. |
| Pending (Wire) | ⌛ | "Wire transfer pending" | 1–3 business days. |

### 8.5 Payment Retry Flow

1. Plain-language error message (never raw gateway codes).
2. Retry options: same card / different card / bank transfer.
3. Price lock preserved during retry.
4. After 3 consecutive failures: show support link with Verification ID.
5. All failed attempts logged against verification record (visible to admin).

### 8.6 Payment Receipt

Generated immediately on success. Emailed to customer. Contains: receipt number, Verification ID, customer details, property address, tier, line-item breakdown, total, currency, FX rate, payment method, date/time.

### 8.7 Refund Policy

| Scenario | Fault | Action |
|---|---|---|
| Cancel before `IN_PROGRESS` | Customer | Partial refund: total minus [X]% surcharge |
| Cancel after `IN_PROGRESS` | Customer | No refund |
| Wrong property info / fraud | Customer | No refund |
| Wrong agent type assigned | Veriprops | Full/partial refund + free re-verification |
| Required step skipped | Veriprops | Full/partial refund + free re-verification |
| Registry error / missing records | External | No refund; transparent reporting |
| Property inaccessible | External | Partial refund (field inspection component only) |
| Payment confirmed, verification never activated | Veriprops | Full refund + free re-verification |

Refunds returned to original payment method. Customer notified in-app + email. Status visible on verification detail page.

---

## 9. Post-Payment Confirmation & Verification Activation

**Route:** `/portal/verifications/[id]/confirmed`

Displayed immediately after payment succeeds.

```
┌──────────────────────────────────────────────────────┐
│   ✅ Verification Request Confirmed                  │
│                                                      │
│   Verification ID:   VP-2026-048291  [Copy] [Share]  │
│   Property:          [Address]                       │
│   Tier:              Standard                        │
│   Paid:              ₦121,000  (Receipt sent)        │
│                                                      │
│   What happens next:                                 │
│   1. Our team assigns verified agents (≤24 hours)   │
│   2. Agents begin checks                            │
│   3. We notify you at every step                    │
│   4. Report delivered within 5–7 business days      │
│                                                      │
│   Estimated completion:  [Date]                      │
│   SLA countdown:  5 days, 23 hours remaining         │
│                                                      │
│   [Track my verification →]   [Download Receipt]    │
└──────────────────────────────────────────────────────┘
```

### 9.1 SLA Definitions

SLA clock starts at `PAID` state. Business days = Mon–Fri, excluding Nigerian public holidays.

| Tier | SLA Target |
|---|---|
| Basic | 3–5 business days |
| Standard | 5–7 business days |
| Premium | 7–10 business days |

---

## 10. Verification Tracking Dashboard

**Route:** `/portal/verifications/[id]`

The trust-building engine. Modelled on order tracking (Amazon / Uber Eats) — but for a high-stakes property investment.

### 10.1 Page Structure

```
┌─────────────────────────────────────────────────────────┐
│  VP-2026-048291  │  Standard  │  🟡 In Progress         │
│  [Address, LGA, State]                                  │
├─────────────────────────────────────────────────────────┤
│  SLA TRACKER                                            │
│  Expected:  Fri, 2 May 2026                             │
│  ████████░░░░░░░░░░  3 of 7 days elapsed  ✅ On track  │
├─────────────────────────────────────────────────────────┤
│  PROGRESS                              Progress: 33%    │
│                                                         │
│  ✅ Submitted                  Mon, 28 Apr — 2:47 PM   │
│  ✅ Payment Confirmed          Mon, 28 Apr — 2:48 PM   │
│  ✅ Agents Assigned            Mon, 28 Apr — 5:12 PM   │
│  ✅ Registry Check Complete    Tue, 29 Apr — 10:00 AM  │
│  ⏳ Field Inspection            In progress...          │
│  ⬜ Boundary Survey            Pending                  │
│  ⬜ Admin Review               —                        │
│  ⬜ Report Ready               —                        │
├─────────────────────────────────────────────────────────┤
│  ASSIGNED AGENTS                                        │
│  [Registry icon]   Verified Registry Agent ✅           │
│  [Field icon]      Verified Field Agent ✅              │
│  [Survey icon]     Verified Surveyor ✅                 │
├─────────────────────────────────────────────────────────┤
│  EVIDENCE  (3 items)                  [View all →]      │
│  [thumb] [thumb] [thumb] +1 more                        │
├─────────────────────────────────────────────────────────┤
│  MESSAGES                             [Open →]          │
│  Admin: "Field inspection scheduled for tomorrow."      │
├─────────────────────────────────────────────────────────┤
│  [Download Receipt]  [Request Re-check]  [Support]      │
└─────────────────────────────────────────────────────────┘
```

### 10.2 Customer-Facing State Labels

Customers see simplified state labels — not internal state codes:

| Internal State | Customer Sees |
|---|---|
| `DRAFT` | "Draft" |
| `SUBMITTED` | "Submitted" |
| `PAYMENT_PENDING` | "Payment Pending" |
| `PAID` | "Payment Confirmed — Agents Being Assigned" |
| `IN_PROGRESS` | "Verification In Progress" |
| `UNDER_REVIEW` | "Under Review" |
| `COMPLETED` | "Completed ✅" |
| `DISPUTED` | "Dispute Under Review" |
| `CANCELLED` | "Cancelled" |
| `REFUNDED` | "Refunded" |
| `FAILED` | "Could Not Be Completed" |

### 10.3 "Verification In Progress" Expanded View

When a verification is in `IN_PROGRESS` state, the customer sees an **expanded status panel** — a compact, portable component that gives at-a-glance progress visibility. This component appears in three surfaces:

1. **Verifications list** (`/portal/verifications`) — displayed inline under the verification card when status = `IN_PROGRESS`. Visible without navigating to the full detail page.
2. **Tracking detail page** — shown as the primary status block at the top, above the full timeline.
3. **Notification detail** — included in the body of any "status changed" notification while `IN_PROGRESS`.

#### Component Spec

```
┌──────────────────────────────────────────────────────┐
│  Verification In Progress                            │
│                                                      │
│  Progress:   ████████░░░░░░░░  33%  (1 of 3 done)  │
│  Estimated completion:  Fri, 2 May 2026              │
│  Time remaining:  4 days, 6 hours                    │
│                                                      │
│  Stage Breakdown:                                    │
│                                                      │
│  Registry Check        ✅  Completed                 │
│  Field Inspection      ⏳  In Progress               │
│  Boundary Survey       ⬜  Pending                   │
│  Legal Review          ⬜  Awaiting other stages     │
│                                                      │
│  [View full details →]                               │
└──────────────────────────────────────────────────────┘
```

#### Rules

- **Progress %** is computed from the formula: `Approved Tasks ÷ Total Required Tasks × 100`. Shown as both a bar and a fraction (e.g., "1 of 3 done").
- **Estimated completion** = `PAID` timestamp + tier SLA target. Shown as an absolute date, not just a duration, so diaspora customers can calendar it.
- **Time remaining** = estimated completion date − now. Switches to "Overdue" label (amber) if past the SLA date without `COMPLETED`.
- **Stage breakdown** shows one row per task role required for the tier. Stage labels are plain English — not internal state codes:

| Task State | Customer Label | Icon |
|---|---|---|
| `PENDING` | Pending | ⬜ |
| `ASSIGNED` | Pending | ⬜ |
| `ACCEPTED` | Pending | ⬜ |
| `IN_PROGRESS` | In Progress | ⏳ |
| `SUBMITTED` | In Progress | ⏳ |
| `REJECTED` | In Progress | ⏳ |
| `APPROVED` | Completed | ✅ |

> **Design rationale:** Customers do not need to see the distinction between `ASSIGNED`, `ACCEPTED`, and `IN_PROGRESS` at the task level — these are internal operational states. From the customer's perspective, anything before the agent submits reads as "Pending" or "In Progress." Only `APPROVED` means "done" to the customer. This abstraction protects the internal workflow while still delivering meaningful progress visibility.

- The **Lawyer row** shows a special label when its dependency is unmet: "⬜ Awaiting other stages" — not just "Pending" — so customers understand why legal review hasn't started.
- "View full details →" links to the full tracking detail page (`/portal/verifications/[id]`).

---

### 10.4 `PAID` State — Awaiting Agent Assignment

Between payment confirmation and the first agent being assigned, the verification is in `PAID` state. This can last up to 24 hours (admin's target assignment SLA). The customer needs visibility during this window — not a blank screen.

**On the verifications list and tracking detail page, while status = `PAID`:**

```
┌──────────────────────────────────────────────────────┐
│  Payment Confirmed — Agents Being Assigned           │
│                                                      │
│  ✅ Payment received: ₦121,000                       │
│  Your Verification ID: VP-2026-048291                │
│                                                      │
│  ⏳ Our team is reviewing your request and           │
│     assigning verified agents to your case.          │
│     This usually takes less than 24 hours.           │
│                                                      │
│  Estimated start: By tomorrow, 2 May 2026            │
│                                                      │
│  [Download Receipt]   [Contact Support]              │
└──────────────────────────────────────────────────────┘
```

- "Estimated start" = payment timestamp + 24 hours (admin assignment SLA).
- If 24 hours elapse without assignment, a banner appears: "Agent assignment is taking a little longer than expected. We're on it." + support link.
- Admin receives an automated alert if assignment SLA is breached.

---

### 10.5 `UNDER_REVIEW` State — Expanded Customer View

When all tasks have been submitted and admin is reviewing before releasing the report, the customer is in `UNDER_REVIEW`. This appears on the verifications list card, tracking detail page, and notification detail — parallel to the `IN_PROGRESS` expanded view.

```
┌──────────────────────────────────────────────────────┐
│  Under Review                                        │
│                                                      │
│  Progress:   ████████████████  100%  (3 of 3 done)  │
│  All checks complete. Our team is reviewing          │
│  findings before releasing your report.              │
│                                                      │
│  Estimated report: Within 4 hours                    │
│                                                      │
│  Stage Breakdown:                                    │
│                                                      │
│  Registry Check       ✅  Completed                  │
│  Field Inspection     ✅  Completed                  │
│  Boundary Survey      ✅  Completed                  │
│  Legal Review         ✅  Completed                  │
│                                                      │
│  ⏳ Admin quality review in progress...              │
│                                                      │
│  [View full details →]                               │
└──────────────────────────────────────────────────────┘
```

- Progress = 100% (all tasks approved).
- "Estimated report: Within X hours" = admin report release SLA (admin-configurable, e.g. 4 hours).
- All stage rows show ✅ Completed.
- The final row "Admin quality review in progress..." communicates that the delay is intentional and quality-driven — not a problem.
- If admin release SLA is breached, row updates to: "⚠️ Review is taking longer than expected. We'll notify you as soon as your report is ready."
- Customer cannot take any action here except contact support. No buttons other than "View full details."

---

### 10.6 SLA Tracker

- Progress bar: elapsed days vs. total SLA.
- Status labels:
  - "On track ✅" — within SLA
  - "Running late ⚠️" — past expected date
  - "Delayed — [Reason]" — admin has flagged delay with mandatory reason text

**Delay banner:**
```
⚠️ This verification is taking longer than expected.
Reason: Registry office closed for public holiday.
New estimated completion: Wed, 7 May 2026.
No additional charges will apply.  [Contact Support]
```

### 10.7 Progress Tracker

Step rows adapt to tier. Each row: status icon ✅/⏳/⬜, step label, timestamp (if complete), optional admin note.

### 10.8 Assigned Agents Display

Per agent role required for tier:
- Role icon + type label
- "Verified Agent ✅" badge once assigned
- First name only (last name hidden; contact details never shown)
- "Awaiting assignment..." if not yet assigned

### 10.9 Real-Time Updates

WebSocket / SSE for live status pushes. 60-second polling fallback. "Last updated: just now / 2 min ago" indicator.

---

## 11. Evidence & Transparency Layer

**Route:** `/portal/verifications/[id]/evidence`

What makes Veriprops unique for diaspora customers: **seeing without being there.**

### 11.1 Evidence Feed

Chronological feed of all media and documents uploaded by agents. Items push in real-time as agents upload.

Each item shows: thumbnail or file icon, type badge (`Photo` / `Video` / `Document` / `Map`), agent role (not name), date/time, GPS mini-map if available.

### 11.2 Media Viewer

Full-screen viewer on click. Image: pan + zoom. Video: inline player. PDF: inline viewer. Metadata panel: capture time (EXIF), GPS coordinates → Google Maps link, agent role, upload timestamp.

### 11.3 Evidence Categories

| Category | Uploaded By | Examples |
|---|---|---|
| Site Photos | Field Agent | Exterior, interior, surroundings |
| Site Video | Field Agent | Walkthrough footage |
| Neighbourhood Notes | Field Agent | Written observations |
| Boundary Map | Surveyor | Survey map / coordinates |
| Registry Documents | Registry Agent | Scanned registry records |
| Legal Documents | Lawyer | Reviewed title documents |

### 11.4 Evidence Integrity

- Evidence cannot be deleted after agent submission.
- Timestamps and GPS metadata recorded server-side at upload (not relying on device metadata alone).
- Tamper-evident record.

---

## 12. Final Report Experience

**Route:** `/portal/verifications/[id]/report`

**Trigger:** Status = `COMPLETED`. Customer notified in-app + email.

### 12.1 Report Access Gate

One-time acknowledgement modal before first view:

> "This report represents the professional findings of independent agents at the time of inspection. It is an opinion, not a legal guarantee. The final decision on any property transaction remains yours."
>
> *"We reduce uncertainty. We do not eliminate it."*
>
> [I Understand — View My Report]

Acceptance recorded against report version.

### 12.2 Report Header

```
┌──────────────────────────────────────────────────────────┐
│  ✅ VERIPROPS VERIFIED                                   │
│  Verification ID: VP-2026-048291  │  Report: v1.0        │
│  Date: 30 April 2026              │  Tier: Standard       │
│  Property: [Full Address]                                │
│  [Download PDF]   [Share Report]   [Request Re-check]   │
└──────────────────────────────────────────────────────────┘
```

### 12.3 Trust Score Display

```
┌─────────────────────────────────────┐
│         TRUST SCORE                 │
│           72 / 100                  │
│       ████████████░░░               │
│          🟡  CAUTION                │
│  Proceed carefully. Some issues     │
│  require further investigation.     │
│  [What does this mean? ℹ️]         │
└─────────────────────────────────────┘
```

| Score | Indicator | Meaning |
|---|---|---|
| 90–100 | 🟢 Safe | No significant issues found. |
| 60–89 | 🟡 Caution | Some concerns. Proceed carefully. |
| 0–59 | 🔴 High Risk | Significant issues. Do not proceed without legal advice. |

Score = weighted composite from agent-submitted scores. Weighting formula defined by admin.

### 12.4 Report Sections

All sections are collapsible. Sections shown are tier-dependent.

**12.4.1 Executive Summary** — Plain-language summary, risk badge, key flags, recommended action.

**12.4.2 Physical Findings** *(Standard + Premium)* — Property condition checklist, occupancy, neighbourhood, site photos/video, GPS confirmation. Embedded education tooltips on technical terms.

**12.4.3 Registry & Title Findings** *(All tiers)* — Registry search status, title document type, authenticity assessment, ownership chain, discrepancies.

**12.4.4 Boundary & Survey Results** *(Standard + Premium)* — Boundary confirmation, coordinates, uploaded survey plan, map with plotted boundaries, encroachments.

**12.4.5 Legal Opinion** *(Premium only)* — Encumbrances, fraud indicators, ownership confirmation, risk flags (government acquisition, mortgage, litigation, multiple claimants), structured legal opinion. Includes section-level disclaimer: "This legal opinion is provided by an independent licensed lawyer... It does not constitute a guarantee of title."

**12.4.6 Risk Summary** — Consolidated risk table across all categories with 🟢/🟡/🔴 per row.

**12.4.7 Customer-Submitted Documents Appendix**

Documents uploaded by the customer in the wizard (Step 1E) appear in a dedicated appendix section, clearly distinguished from agent-uploaded evidence.

| Column | Content |
|---|---|
| Document | File name + type icon |
| Uploaded by | "You (submitted with request)" |
| Date | Date of wizard submission |
| Used by | Which agent roles referenced this document |

This matters for diaspora customers: they submitted documents in good faith and need to see them acknowledged and referenced in the final report — especially if an agent found a discrepancy against a document the customer provided. The appendix directly addresses the question: "Did they actually look at what I sent?"

If no documents were submitted by the customer, this section shows: "No documents were submitted with this request. Agents worked from registry records and physical inspection only."

### 12.5 Report Footer (Legal)

Every page and every PDF page carries:
```
This report represents a professional opinion, not a legal guarantee.
Findings are based on information available at the time of verification.
Veriprops | Jurisdiction: Nigeria | Verification ID: VP-2026-048291
Report Version: v1.0 | Date: 30 April 2026
"We reduce uncertainty. We do not eliminate it."
```

### 12.6 Downloadable PDF

Server-side generation on demand. Contents: branded cover page, table of contents, all report sections, evidence thumbnails with captions, document appendix, legal footer on every page, QR code linking to public lookup. Re-downloadable at any time.

### 12.7 Report Versioning

| Version | Trigger |
|---|---|
| v1.0 | First completed report |
| v1.1 | Minor agent revision at admin request |
| v2.0 | Customer re-check (new agent activity) |
| v3.0 | Tier upgrade (new sections added) |

Old versions are read-only and watermarked "SUPERSEDED". Customers notified on each new version.

### 12.8 Report Sharing

| Mode | Visible To | Content |
|---|---|---|
| Private (default) | Customer only | Full report |
| Link-only | Anyone with link | Summary (trust score, key flags, no agent details) |
| Public | Anyone with Verification ID | Summary only |
| Named recipient | Specific email | Full report, time-limited, view-only, revocable |

Share links: 30-day expiry (renewable or permanent). Customer can revoke any share at any time. Recipients must acknowledge the disclaimer before viewing.

---

## 13a. Public Verification Lookup

**Route:** `/verify/[verification-id]` — publicly accessible, no authentication required.

This page is the shareable proof layer — what a customer sends to a family member, lawyer, or co-investor to confirm a property has been verified by Veriprops.

### Display Rules

The page shows a **summary only** — never the full report. Sensitive data (agent identities, owner names, full documents) is never exposed publicly.

| Field | Shown | Notes |
|---|---|---|
| Verification ID | ✅ | Prominently displayed |
| ✅ Veriprops Verified badge | ✅ | Green badge if `COMPLETED` |
| Trust score **band** | ✅ | 🟢 Safe / 🟡 Caution / 🔴 High Risk — not the numeric score |
| Verification tier | ✅ | Basic / Standard / Premium |
| Report date | ✅ | Date of `COMPLETED` status |
| Property type | ✅ | Land / Building |
| State & LGA | ✅ | Location — not full address |
| Full address | ❌ | Never shown publicly |
| Agent names / details | ❌ | Never shown publicly |
| Owner / seller names | ❌ | Never shown publicly |
| Documents | ❌ | Never shown publicly |
| Numeric trust score | ❌ | Band only, never the number |
| Report version | ✅ | e.g. "Report v2.0" |

### States & Page Variations

| Verification Status | Page Shows |
|---|---|
| `COMPLETED`, public sharing enabled | Full summary panel with ✅ badge |
| `COMPLETED`, sharing = Private | "This verification is private. The owner has not enabled public sharing." |
| `IN_PROGRESS` or `UNDER_REVIEW` | "Verification VP-XXXX is currently in progress. Check back when complete." |
| `DISPUTED` | "This verification is currently under dispute review." |
| ID not found | "No verification found with this ID. Please check the ID and try again." |

### Page Layout

```
┌──────────────────────────────────────────────────────┐
│  ✅ Veriprops Verified                               │
│                                                      │
│  Verification ID:  VP-2026-048291                    │
│  Report Date:      30 April 2026  (v2.0)             │
│  Tier:             Standard                          │
│  Property Type:    Land                              │
│  Location:         Eti-Osa LGA, Lagos State          │
│                                                      │
│  Trust Level:      🟡 CAUTION                        │
│                                                      │
│  ──────────────────────────────────────────────────  │
│  This property has been independently verified       │
│  by Veriprops using qualified, approved agents.      │
│  "We reduce uncertainty. We do not eliminate it."    │
│  ──────────────────────────────────────────────────  │
│                                                      │
│  Want to verify a property?                          │
│  [Start a verification →]                            │
└──────────────────────────────────────────────────────┘
```

The "Start a verification" CTA drives new customer acquisition from shared links — this page is a growth surface, not just an info page. The page is search-indexable only if status = `COMPLETED` and sharing = Public. Otherwise `noindex`.

---

## 13b. Dispute Flow (Customer)

**Available from:** Completed report page within the admin-configured dispute window (e.g. 30 days from `COMPLETED` date).

### Trigger

"Raise a Dispute" button in the report page footer. Only visible when:
- Status = `COMPLETED`
- Current date is within the dispute window
- No active dispute already exists for this verification

### Dispute Submission Form

```
Raise a Dispute — VP-2026-048291

Dispute type (select one):
○ Report contains factual errors
○ Required checks were not performed
○ Agent was not qualified for this role
○ Property information was misrepresented
○ I believe there was fraud or misconduct
○ Other

Describe your dispute: [textarea, min 100 chars]
Supporting evidence: [optional file upload]

⚠️ Disputes are reviewed within 5 business days.

[Submit Dispute]   [Cancel]
```

On submit: verification → `DISPUTED`. Admin notified immediately. Customer sees status change on dashboard.

### Customer View While `DISPUTED`

- Status label: "Dispute Under Review"
- Shows: dispute type, date filed, expected response time
- Report remains accessible throughout the review
- No customer actions available except contact support

### Resolution Outcomes (Customer-Facing)

| Admin Decision | Customer Sees | Next State |
|---|---|---|
| Rejected — unsubstantiated | "Your dispute was reviewed. Our team found no evidence of error. The report stands." | `COMPLETED` |
| Upheld — full refund | "Your dispute has been upheld. A refund of ₦X has been initiated." | `REFUNDED` |
| Upheld — partial / re-check | "Your dispute has been partially upheld. We are offering a free re-verification of the flagged section." | `IN_PROGRESS` (new cycle) |

All resolutions delivered via in-app notification + email.

---

## 13. Revision & Re-verification Flow

### 13.1 Request a Re-check

Available on completed verifications. Customer clicks "Request Re-check", provides free-text reason + optional document upload. Admin reviews and approves. New cycle begins for flagged scope. Report updates to next version. Pricing admin-configured (partial or full).

### 13.2 Upgrade Verification Tier

Available in `COMPLETED` or `IN_PROGRESS` state. Customer selects target tier. Shown: feature diff + upgrade delta price (not full tier price). Consent + payment for delta. New tasks created for additional scope. Report updated with new sections in next version.

### 13.3 Tier Downgrade

Not permitted. Customer may cancel (subject to refund policy) and start a new verification at a lower tier.

---

## 14. Communication Layer

### 14.1 Policy

| Rule | |
|---|---|
| ❌ | No direct customer ↔ agent chat |
| ✅ | Customer ↔ Admin (mediated, per-verification thread) |
| ✅ | Admin ↔ Agent (separate per-task thread) |
| ✅ | All messages logged and auditable |
| ❌ | No report edits via chat |
| ✅ | Formal re-check and revision workflow only |
| ⚠️ | Agent identity visible to customer; contact details always hidden |
| 🚨 | Automated fraud detection on all messages |

### 14.2 Per-Verification Chat (Customer ↔ Admin)

**Route:** `/portal/verifications/[id]/messages`

Thread between Customer and Admin only. System auto-posts status changes as timestamped system messages (e.g. "Field inspection completed — 29 Apr, 11:30 AM"). Agents cannot participate directly — admin relays agent clarification requests in structured format.

Character limit: 2,000 per message. All messages stored permanently. File attachments allowed (customer can upload supporting documents).

### 14.3 Admin ↔ Agent Communication Channel

**Route (agent-facing):** `/agent/tasks/[id]/messages`
**Route (admin-facing):** `/admin/verifications/[id]/tasks/[id]/messages`

A separate per-task thread between Admin and the assigned agent for that task. Customers never see this channel.

**Features:**
- Admin initiates: sends revision instructions, clarification requests, or feedback.
- Agent replies with context, questions, or confirmation.
- System auto-posts task state changes as system messages (e.g. "Task submitted by agent — 30 Apr, 2:15 PM").
- Character limit: 2,000 per message.
- Admin can attach documents or reference specific evidence items by ID.
- Thread is read-only for the agent after task = `APPROVED`.

**When admin rejects a task**, the rejection reason entered in the approval UI is automatically posted as the first message in the task thread, so the agent has full context in one place.

**Admin broadcast to all agents on a verification:**
From the verification detail page, admin can send a single message that is delivered to all assigned agents' task threads simultaneously. Used for: updated property information, site access changes, deadline extensions.

### 14.4 Agent Identity Display Rule

Across all customer-facing surfaces (tracking dashboard, report, evidence feed, chat), agents are displayed as follows:

| Field | Customer Sees | Notes |
|---|---|---|
| Role | ✅ "Field Agent" / "Surveyor" etc. | Always shown |
| First name | ✅ e.g. "Tunde" | First name only |
| Last name | ❌ | Never shown to customer |
| Photo / avatar | ✅ | If agent has set one |
| "Verified Agent" badge | ✅ | Always shown |
| Phone number | ❌ | Never shown to customer |
| Email | ❌ | Never shown to customer |
| Rating / performance metrics | ❌ | Internal only |

This rule is enforced at the API level — the customer-facing agent endpoint (`GET /api/verifications/:id/agents`) returns only `role`, `first_name`, `avatar_url`, and `verified` fields. No other agent data is ever returned on customer-facing endpoints.

### 14.5 Message Fraud Detection

All messages sent on the platform (customer ↔ admin and admin ↔ agent threads) are scanned automatically at send time for patterns that indicate fraud or policy violations.

**Flagging triggers:**
- Phone numbers (any format: local, international, formatted, unformatted)
- Email addresses
- External URLs (non-Veriprops domains)
- Payment requests or banking details (account numbers, sort codes)
- Social media handles or usernames
- Requests to communicate "outside the platform" or "directly"

**On flag:**
1. Message is held (not delivered) pending review.
2. Sender sees: "Your message is being reviewed before delivery. This usually takes a few minutes."
3. Admin receives an alert: "Flagged message in VP-XXXX — [snippet]."
4. Admin reviews: **Approve** (message delivered) or **Reject** (message blocked, sender warned).
5. Repeated flags by the same user trigger an account-level review.

**False positive handling:**
- If a legitimate message contains a phone number (e.g., customer sharing a seller's contact for agent cross-reference), admin approves and it is delivered.
- Admin approval is logged in the audit trail.

### 14.6 General Support Chat

**Route:** `/portal/support`

Separate from verification threads. For account issues, billing, general questions. Each message can reference a Verification ID. Support options: in-app chat, "Call us" link, FAQs.

---

## 15. Notification System

### 15.1 Customer Notification Triggers

| Event | In-App | Email | SMS |
|---|---|---|---|
| Payment confirmed | ✅ | ✅ | ✅ |
| Agents assigned | ✅ | ✅ | — |
| Status change (any) | ✅ | ✅ | — |
| New evidence uploaded | ✅ | — | — |
| New admin message | ✅ | ✅ | ✅ |
| SLA breach / delay | ✅ | ✅ | ✅ |
| Report ready | ✅ | ✅ | ✅ |
| New report version | ✅ | ✅ | — |
| Refund initiated | ✅ | ✅ | — |
| Re-check approved/rejected | ✅ | ✅ | — |

Customer can toggle email/SMS per event type. In-app notifications cannot be disabled.

---

## 16. Growth & Conversion Mechanics

### 16.1 Abandoned Verification Recovery

24 hours after wizard abandonment without payment:

- **In-app (next login):** Banner with property address, tier, locked price, "Continue" and "Discard" CTAs.
- **Email:** Sent once. "Your verification request is still waiting." Direct resume link.
- Draft preserves all entered data. Price lock refreshed if > 24 hours old.

### 16.2 Referral System

Each customer gets a unique referral link. On invitee's first payment: invitee gets first-time discount; referrer gets credit (amount admin-configured). Credit displayed on dashboard, auto-applied at next checkout. "My Referrals" section shows stats and credit balance.

### 16.3 First-Time Discount

Auto-applied on first verification. Amount admin-configured. Never requires a code. Shown clearly in pricing breakdown and payment summary.

---

## 17. Location Intelligence UX

- **Property map:** Google Maps embed, satellite view, pin at verified location.
- **Nearby landmarks:** Sourced from Google Places API — schools, hospitals, markets. Distance + direction.
- **Area insights:** LGA name, area type (Residential/Commercial/Rural), known risk factors for the area. Maintained by Veriprops content team.

---

## 18. History & Record Keeping

**Route:** `/portal/verifications`

List of all past and active verifications: Verification ID, address, tier badge, status badge, date, trust score (completed), actions (View / Download PDF / Share).

Filters: Status, Tier, Date range, Trust score band. Sort: Date (default newest first), Trust score.

Reports stored permanently. "Download all as ZIP" option. No expiry on report access.

---

# PART C — AGENT LIFECYCLE

---

## 19. Agent Task Dashboard

**Route:** `/agent/dashboard`

The agent's home screen after login. Scoped to tasks relevant to their role type(s). An agent who is both a Field Agent and a Surveyor sees tasks for both roles, clearly labelled.

### 19.1 Dashboard Structure

```
┌──────────────────────────────────────────────────────────┐
│  Good morning, Emeka.   [🔔 2 new jobs]                  │
├──────────────────────────────────────────────────────────┤
│  AVAILABLE JOBS (near you)                               │
│                                                          │
│  🏠 VP-2026-048291  ·  Field Agent  ·  Lekki, Lagos     │
│  Standard tier  ·  Deadline: Fri 2 May                   │
│  [Accept]  [View details]                                │
│                                                          │
│  🏠 VP-2026-048305  ·  Field Agent  ·  Ikeja, Lagos     │
│  Premium tier  ·  Deadline: Mon 5 May                    │
│  [Accept]  [View details]                                │
├──────────────────────────────────────────────────────────┤
│  MY ACTIVE TASKS (3)                                     │
│                                                          │
│  VP-2026-047800  ·  ⏳ IN_PROGRESS  ·  Abuja            │
│  Premium  ·  Deadline: Tomorrow                          │
│  [Continue]                                              │
│                                                          │
│  VP-2026-047650  ·  🔴 REJECTED    ·  Port Harcourt     │
│  "Please re-upload clearer photos of the boundary."     │
│  [Rework & Resubmit]                                    │
├──────────────────────────────────────────────────────────┤
│  COMPLETED  (12)          Earnings this month: ₦84,000  │
│  [View history]           [Request payout →]            │
└──────────────────────────────────────────────────────────┘
```

### 19.2 Task States (Agent's Perspective)

| State | What Agent Sees | Available Actions |
|---|---|---|
| `ASSIGNED` | "New job available" | Accept / Decline |
| `ACCEPTED` | "Job reserved" | Start work |
| `IN_PROGRESS` | "Work ongoing" | Upload evidence / Submit findings |
| `SUBMITTED` | "Awaiting review" | View submission (read-only) |
| `REJECTED` | "Needs correction — [reason]" | Edit & resubmit |
| `APPROVED` | "Completed ✅" | View final (read-only) |

### 19.3 Agent Task View (Per Job)

**Route:** `/agent/tasks/[task-id]`

```
┌──────────────────────────────────────────────────────────┐
│  VP-2026-048291  ·  Your Role: Field Agent               │
│  Status: IN_PROGRESS  ·  Deadline: Fri, 2 May 2026       │
│  ⚠️  2 days remaining                                    │
├──────────────────────────────────────────────────────────┤
│  PROPERTY                                                │
│  Address:     [Address, LGA, State]                      │
│  Type:        Building — Detached house                  │
│  Landmark:    "Behind First Bank, Admiralty Way"         │
│  [View on map]                                           │
├──────────────────────────────────────────────────────────┤
│  CUSTOMER DOCUMENTS (2 uploaded)                         │
│  [Survey Plan.pdf]  [Title Doc.pdf]                      │
├──────────────────────────────────────────────────────────┤
│  OTHER AGENTS ON THIS JOB (read-only)                    │
│  Surveyor:        ⏳ In Progress                         │
│  Registry Agent:  ✅ Submitted                           │
│  [You are the Field Agent]                               │
├──────────────────────────────────────────────────────────┤
│  YOUR SUBMISSION                                         │
│  [Submission form — see Section 21]                      │
└──────────────────────────────────────────────────────────┘
```

**Key rule:** Agent can see the status of sibling agents on the same job (read-only). They cannot see each other's submission content.

---

## 20. Job Discovery & Acceptance

### 20.1 Job Discovery

Available jobs are served to agents based on:
- **Role match:** Only tasks matching the agent's approved role type(s).
- **Location match:** Jobs in the agent's declared coverage areas (state/city), sorted by proximity.
- **Availability:** System checks the agent's current active task load before surfacing new jobs.

Jobs are shown on a first-come, first-served basis within the eligible pool. Admin can also manually assign directly.

### 20.2 Accept / Decline Flow

When a new job appears:

1. Agent sees job card with property location, tier, role, and deadline.
2. "View details" expands: property address, map preview, expected task deadline.
3. Agent clicks **"Accept"**:
   - Task transitions: `ASSIGNED → ACCEPTED`
   - Job is removed from the available pool for other agents of the same role.
   - Countdown to task deadline begins.
   - Admin notified of acceptance.
4. Agent clicks **"Decline"**:
   - Task transitions: `ASSIGNED → PENDING`
   - Job re-enters the pool for reassignment.
   - Agent's decline is logged (repeated declines flagged in reputation system).

### 20.3 Agent No-Show / Timeout

If an agent does not accept or decline within the admin-configured timeout window (e.g., 4 hours):

- System auto-transitions the task: `ASSIGNED → PENDING`.
- Task re-enters the available pool.
- Admin receives an alert: "Agent [Name] did not respond to job VP-XXXX. Task returned to pool."
- The agent's non-response is logged against their performance record.
- Admin may manually reassign immediately without waiting for timeout.

---

## 21. Role-Specific Submission UIs

Each agent type has a distinct structured submission form. These are NOT generic forms — they are purpose-built for each role. Submission is only available when task status = `IN_PROGRESS`.

### 21.1 Field Agent Submission

**Route:** `/agent/tasks/[id]/submit`

---

**Section A — Property Access**
- Was the property accessible? Yes / No / Partially
- If No/Partially: explain (required) + attach evidence

**Section B — Property Condition Checklist**

| Item | Options |
|---|---|
| Access road condition | Good / Fair / Poor / No road |
| Boundary markers present | Yes / No / Partial |
| Structures on land | Yes / No |
| Utilities available (electricity/water) | Yes / No / Partial |
| Property matches description provided | Yes / No / Significant discrepancy |

**Section C — Physical Observations**
- Property condition narrative (textarea, required, min 100 chars)
- Occupancy status: Owner-occupied / Tenanted / Vacant / Unknown
- Signs of dispute or conflict: Yes / No — if Yes, describe

**Section D — Neighbourhood Assessment**
- Neighbourhood type: Residential / Commercial / Mixed / Industrial / Rural
- General security impression: Good / Fair / Poor
- Notable concerns (textarea, optional)

**Section E — Media Upload** *(required — minimum 5 photos)*
- Minimum: Front exterior, rear/sides, access road, surrounding area, any notable features
- Video walkthrough (optional but strongly recommended)
- Each photo/video: auto-stamped with upload timestamp and GPS coordinates server-side
- No more than 50 files total

**Section F — Agent Trust Score Input**
- Agent's own risk assessment: slider 0–100
- Rationale for score (textarea, required if score < 60 or > 90)
- This score feeds into the weighted composite trust score on the report. Admin defines weighting.

**Section G — Declaration**
- Checkbox: "I confirm that I physically visited this property on [date] and that all information submitted is accurate to the best of my knowledge."
- Visit date (date picker, required)
- GPS confirmation: "Your current location will be recorded at the time of submission."

---

### 21.2 Surveyor Submission

**Section A — Survey Confirmation**
- Was a physical survey conducted? Yes / No / Partial
- If No/Partial: reason (required)

**Section B — Boundary Assessment**
- Boundaries match submitted survey plan: Yes / No / Not applicable (no plan provided)
- If mismatch: describe discrepancy (required)
- Encroachments found: Yes / No — if Yes, describe (required)

**Section C — Coordinates**
- GPS coordinates of property corners (min 2, max unlimited): lat/lng pairs
- Or: upload of georeferenced map file (JPG, PNG, PDF, KMZ)

**Section D — Survey Plan**
- Upload updated/confirmed survey plan (required if available)
- Comments on plan quality/accuracy (textarea)

**Section E — Agent Trust Score Input**
- Same slider + rationale as Field Agent.

**Section F — Declaration**
- Checkbox: "I confirm that I conducted boundary verification for this property on [date] and that all findings are accurate."

---

### 21.3 Registry Agent Submission

**Section A — Registry Search**
- Registry office searched: State Land Registry / Federal Ministry / Other (specify)
- Search date (date picker, required)
- Registry entry found: Yes / No / Inconclusive

**Section B — Title Document Assessment**
- Title document type: Certificate of Occupancy / Deed of Assignment / Right of Occupancy / Lease / Governor's Consent / Other
- Document condition: Original / Certified copy / Photocopy / Digital only
- Document authenticity assessment: Appears authentic / Questionable / Likely forged
  - If Questionable or Likely forged: mandatory explanation

**Section C — Ownership**
- Name(s) on title document match claimed owner: Yes / No / Partial
  - If No/Partial: describe discrepancy (required)
- Ownership chain summary (textarea)
- Any previous transactions found: Yes / No — if Yes, describe

**Section D — Document Uploads** *(required)*
- Scanned registry record (redact where legally required)
- Copy of title document reviewed
- Any supporting registry printouts

**Section E — Agent Trust Score Input**

**Section F — Declaration**
- Checkbox: "I confirm that I conducted a registry search for this property on [date] and that all findings reflect the actual registry records."

---

### 21.4 Lawyer Submission

> **Dependency rule:** The Lawyer task status remains `PENDING` until all other tasks for the tier reach `SUBMITTED`. Once that condition is met and a lawyer has been assigned, the task auto-transitions to `ACCEPTED`. The lawyer cannot begin or submit until all non-lawyer tasks are submitted.

**Section A — Documents Reviewed**
- Checklist of documents reviewed (multi-select): C of O / Deed of Assignment / Survey Plan / Registry Search Result / Field Inspection Report / Other
- Documents not reviewed (and why): textarea

**Section B — Title Opinion**
- Overall title assessment: Clean / Questionable / Problematic / Unverifiable
- Ownership: Confirmed / Disputed / Unverifiable
- Explanation (required, min 150 chars)

**Section C — Encumbrances**
- Encumbrances found: Yes / No / Unknown
- If Yes: list each encumbrance
  - Type: Government acquisition / Mortgage / Court injunction / Caveat / Other
  - Date (if known)
  - Description

**Section D — Fraud & Risk Flags**
- Fraud indicators: None detected / Suspected / Confirmed
  - If Suspected/Confirmed: mandatory description
- Risk flags (multi-select): None / Government acquisition notice / Existing mortgage / Ongoing litigation / Multiple claimants / Forged documents / Other
- For each flagged: date (if known), description

**Section E — Legal Opinion Statement** *(structured free text, required)*
> "Based on the documents reviewed and checks performed at the time of this assessment, it is my opinion that..."

Minimum 200 characters. Plain English — no excessive legalese.

**Section F — Recommendation**
- Recommended action: Safe to proceed / Proceed with caution / Do not proceed / Seek further investigation

**Section G — Agent Trust Score Input**
- Same slider + rationale. Given the lawyer's role as final reviewer, their score carries higher weight in the composite (admin-defined).

**Section H — Professional Declaration**
- Checkbox: "I confirm that I am a qualified legal practitioner licensed by the Nigerian Bar Association, and that this legal opinion is based on the documents reviewed and my professional judgement at the time of assessment."
- NBA licence number (pre-filled from agent profile, editable)

---

### 21.5 Draft Saving & Offline Support

- Submission forms auto-save locally on every field change.
- "Save Draft" button explicitly saves to backend.
- Offline mode: local save continues. Upload queue retries automatically when connection restores.
- Sync indicator: "Saving..." / "Saved ✅" / "Offline — will sync when reconnected ⚠️"
- Agent can leave and return to an in-progress submission without losing data.

---

## 22. Agent Escalation & Issue Reporting

**Available at any point when task is `ACCEPTED` or `IN_PROGRESS`.**

Agent clicks "Report Issue" on the task page. Escalation modal:

| Issue Type | Description |
|---|---|
| Property inaccessible | Could not access the site |
| Suspicious activity | Fraudulent documents or behaviour observed |
| Safety concern | Agent felt unsafe at the property |
| Conflicting information | Property details don't match what was provided |
| Other | Free text |

- Mandatory: description (textarea, min 50 chars)
- Optional: evidence upload (photos, documents)
- On submit: Admin immediately notified. Task flagged. Verification may be paused by admin.

**Agent cannot unilaterally pause or cancel a verification.** Only admin can do that. The escalation is a request for admin action.

---

## 23. Agent Commission & Earnings System

The earnings system is what keeps agents engaged. It must be transparent, real-time, and easy to act on.

### 23.1 Earnings Dashboard

**Route:** `/agent/earnings`

```
┌──────────────────────────────────────────────────────┐
│  Earnings Overview                                   │
│                                                      │
│  This month:       ₦84,000    (6 jobs)               │
│  Last month:       ₦112,000   (9 jobs)               │
│  All time:         ₦640,000   (51 jobs)              │
│  Available balance: ₦61,000   [Request Payout]       │
│  Pending:           ₦23,000   (2 jobs awaiting admin)│
├──────────────────────────────────────────────────────┤
│  JOB BREAKDOWN                          [Filter ↓]   │
│                                                      │
│  VP-2026-048291  ·  Field Agent                      │
│  Completed 29 Apr  ·  ₦18,000  ·  ✅ Paid            │
│                                                      │
│  VP-2026-047800  ·  Field Agent                      │
│  Completed 27 Apr  ·  ₦18,000  ·  ⏳ Pending payout  │
│                                                      │
│  VP-2026-047200  ·  Field Agent                      │
│  Completed 20 Apr  ·  ₦18,000  ·  ✅ Paid            │
└──────────────────────────────────────────────────────┘
```

**Commission per job** = defined by admin per agent role per tier. Not visible to the customer. Example structure (admin-configured):

| Role | Basic | Standard | Premium |
|---|---|---|---|
| Registry Agent | ₦X | ₦X | ₦X |
| Field Agent | — | ₦X | ₦X |
| Surveyor | — | ₦X | ₦X |
| Lawyer | — | — | ₦X |

### 23.2 Payment Status Labels

| Status | Meaning |
|---|---|
| ⏳ Pending | Task approved; payout not yet approved by finance admin |
| ✅ Paid | Payout approved and transferred |
| 🔴 On Hold | Finance admin has placed a hold (reason shown on hover) |

### 23.3 Withdrawal Flow

**Available balance** = sum of all `PAID` (approved) commissions minus previous withdrawals.

1. Agent clicks "Request Payout."
2. Selects payout amount (up to available balance).
3. Bank details:
   - Stored bank account shown (pre-filled from agent profile).
   - "Use a different account" option (one-time entry, not saved unless agent chooses).
4. Confirmation screen: "₦61,000 will be sent to [Bank] ••••1234. Payout requests are processed within 2 business days."
5. Agent clicks "Confirm Payout Request."
6. Finance admin receives payout request in the Admin Financial Management panel.
7. On approval: agent notified in-app + email. Funds transferred.
8. On hold: agent notified with reason. Can contact support.

### 23.4 Commission Visibility Rules

- Agents see their own earnings only — never another agent's.
- The commission amount per job is visible to the agent on their job detail page before they accept (so they can make an informed decision).
- Admin sees all agent earnings and can approve, hold, or adjust payouts.

---

## 24. Agent Reputation System

The reputation system drives quality, earns agent trust, and powers the assignment ranking logic.

### 24.1 Performance Metrics

Each agent has three tracked metrics, computed automatically from historical task data:

| Metric | Definition | Calculation |
|---|---|---|
| **Completion Rate** | % of accepted tasks that were completed without abandonment | (Approved tasks ÷ Accepted tasks) × 100 |
| **Accuracy Score** | Admin's quality rating of submitted findings | Average of admin-assigned quality scores per task (1–5 stars) |
| **Timeliness Score** | How often the agent meets their task deadline | (Tasks completed on time ÷ Total tasks) × 100 |

### 24.2 Rating System

After each task is `APPROVED`, admin assigns a **quality score** (1–5 stars) with an optional note. This is internal — agents see their average rating but not individual scores.

- Agent can see: their overall average score, completion rate %, timeliness %.
- Agent cannot see: individual task quality scores, admin notes, or comparative rankings.

### 24.3 Agent Profile — Reputation Display

**Route:** `/agent/profile` (agent's own view)

```
┌──────────────────────────────────────────────────────┐
│  Tunde A.   ·  Field Agent  ·  ✅ Verified           │
│                                                      │
│  Completion Rate:   94%   ████████████░░  (High)     │
│  Accuracy Score:    4.6 / 5   ★★★★½                  │
│  Timeliness:        88%   ███████████░░  (Good)      │
│                                                      │
│  Total jobs:  51   ·   Active since: Jan 2025        │
│  Coverage:    Lagos State (Eti-Osa, Ikeja, VI)       │
└──────────────────────────────────────────────────────┘
```

### 24.4 Reputation Impact

- **Assignment ranking:** Higher-performing agents surface first in admin's suggested list.
- **Job visibility:** Agents below a defined performance threshold (admin-configured, e.g. completion rate < 60%) have reduced job visibility — fewer jobs shown in their discovery feed.
- **Suspension trigger:** Admin can flag an agent for review if any metric falls below a critical threshold.
- **Trust badge:** Agents above a defined excellence threshold (admin-configured) earn a "Top Agent" badge visible to admin during assignment. Not visible to customers.

---

## 25. Agent Location & Coverage Management

### 25.1 Coverage Settings

**Route:** `/agent/settings/coverage`

Agents declare their working areas. This is the primary driver for geo-based job matching.

| Field | Type | Notes |
|---|---|---|
| States covered | Multi-select (all 36 Nigerian states + FCT) | Required. At least one. |
| LGAs covered | Multi-select per state (filtered dynamically) | Optional but strongly recommended — improves match precision |
| Maximum travel distance | Number (km) | Optional — "I'll travel up to X km from my declared areas" |

**Rules:**
- Coverage can be updated at any time.
- Changes take effect immediately for new job matching.
- Jobs already assigned are not affected by coverage changes.
- Admin can override location matching for a specific assignment (manual assign bypasses geo rules).

### 25.2 Coverage Map Preview

After setting coverage, agent sees a Nigeria map with their covered states/LGAs shaded. Gives visual confirmation their settings are correct.

### 25.3 Availability Status

**Route:** `/agent/settings/availability`

| Status | Meaning |
|---|---|
| 🟢 Available | Accepting new jobs |
| 🟡 Limited | Accepting jobs but at reduced capacity (near max load) |
| 🔴 Unavailable | Not accepting new jobs (e.g., on leave) |

- Agents set this manually.
- System auto-sets to 🔴 Unavailable when agent reaches max active task capacity.
- Unavailable agents are excluded from the job discovery feed and admin's suggested list.

---

## 26. Agent Role-Based Dashboard Differentiation

The spec principle: "Lawyer dashboard ≠ Field Agent dashboard." Each agent type sees a UI shaped around their specific workflow, not a generic agent portal.

### 26.1 Role-Based Navigation

| Nav Item | Field Agent | Surveyor | Registry Agent | Lawyer |
|---|---|---|---|---|
| Available Jobs | ✅ | ✅ | ✅ | ✅ |
| My Tasks | ✅ | ✅ | ✅ | ✅ |
| Submit Report | Field form | Survey form | Registry form | Legal form |
| Evidence Upload | ✅ Photos/Video | ✅ Maps/Plans | ✅ Documents | ✅ Documents |
| Earnings | ✅ | ✅ | ✅ | ✅ |
| Coverage Settings | ✅ | ✅ | ✅ | ✅ |
| Professional Credentials | — | License renewal | — | NBA licence |
| Offline Mode | ✅ Priority | ✅ Priority | — | — |

### 26.2 Dashboard Default View by Role

| Role | Default View Focus |
|---|---|
| **Field Agent** | Map of nearby available jobs + active task with upload prompt |
| **Surveyor** | Nearby jobs with map preview + active task with coordinate entry |
| **Registry Agent** | Available jobs list (no map needed) + document checklist |
| **Lawyer** | Tasks waiting for dependency (other agents submitted) + legal opinion queue |

The Lawyer dashboard specifically shows a dedicated **"Waiting for other agents"** queue — tasks that are assigned but locked until dependency is met. This prevents confusion: the lawyer can see they have work coming, just not yet unlocked.

### 26.3 Conditional UI Elements

- Field Agent and Surveyor: GPS location prompt on task page ("Enable location to verify your proximity to the property").
- Lawyer: dependency status bar on locked tasks ("Registry Agent: ✅ Done · Field Agent: ⏳ Pending — Legal review unlocks when all are submitted").
- Registry Agent: no map, no GPS — their work is document-based.
- All roles: offline save indicator is most prominent for Field Agent and Surveyor (who are physically on-site with poor connectivity).

---

# PART D — ADMIN LIFECYCLE

---

## 23. Verification Control Panel

**Route:** `/admin/verifications`

Mission control. Real-time view of the entire verification operation.

### 23.1 Verification List

| Column | Content |
|---|---|
| Verification ID | `VP-2026-048291` (link to detail) |
| Property | Address (truncated) + State |
| Tier | Badge |
| Status | Colour-coded badge |
| Progress | `X / Y tasks approved` |
| SLA | Days remaining or ⚠️ overdue |
| Assigned Agents | Avatar row per role, greyed out if unassigned |
| Last Updated | Relative timestamp |

Filters: Status, Tier, SLA status (on track / at risk / overdue), State/LGA, Date range.

### 23.2 Verification Detail View

**Route:** `/admin/verifications/[id]`

Full breakdown on a single screen:

```
┌──────────────────────────────────────────────────────────┐
│  VP-2026-048291  ·  Standard  ·  🟡 IN_PROGRESS          │
│  Progress: 33%  ·  SLA: 2 days remaining ✅              │
├──────────────────────────────────────────────────────────┤
│  CUSTOMER            PROPERTY                            │
│  [Name, email]       [Full address + map]                │
│  [Contact support]   [Property type, details]            │
│                      [Customer documents: 2]             │
├──────────────────────────────────────────────────────────┤
│  MULTI-AGENT COORDINATION                                │
│                                                          │
│  Registry Agent  ✅ APPROVED     Amara O.    29 Apr      │
│  Field Agent     ⏳ IN_PROGRESS  Tunde A.    ETA: 2 May  │
│  Surveyor        ⬜ PENDING      [Assign →]              │
│  Lawyer          ⬜ PENDING      Waiting for others...   │
├──────────────────────────────────────────────────────────┤
│  ADMIN ACTIONS                                           │
│  [Assign Agent]  [Reassign]  [Pause]  [Cancel]  [Flag]  │
└──────────────────────────────────────────────────────────┘
```

### 23.3 Admin Actions (Verification Level)

| Action | When Available | Effect |
|---|---|---|
| Assign Agent | Task is `PENDING` | Opens agent assignment modal → task → `ASSIGNED` |
| Reassign Agent | Task is `ASSIGNED` or `ACCEPTED` | Reassigns; previous agent notified; task → `ASSIGNED` for new agent |
| Pause Verification | `IN_PROGRESS` | Halts all task activity. Agents notified. Customer notified with reason. |
| Resume Verification | Paused | Restores all tasks to their previous state. |
| Cancel Verification | Any non-terminal state | Triggers refund logic. All tasks terminated. Customer notified. |
| Declare Failure | `IN_PROGRESS` | Sets global state to `FAILED`. Reasons required. Customer notified. |
| Set Delay | Any active state | Sets delay flag + mandatory reason text. Customer-facing delay banner activated. |
| Add Admin Note | Any | Internal note attached to verification record. See below. |
| Resolve Dispute | `DISPUTED` | Admin reviews and resolves with one of three outcomes. |

#### Admin Notes System

Admin notes are internal observations attached to a verification record. They are never visible to customers or agents.

**What can be noted:**
- Operational context ("Awaiting registry office to reopen after strike")
- Quality observations ("Field agent photos were low quality — keep for future reference")
- Risk flags ("Customer phone number flagged in fraud database — proceed with caution")
- Handover notes ("Assigned to Ops team B for week of 5 May")

**Notes UI:**
- Notes panel on the right side of the verification detail view.
- Each note: author (admin name), timestamp, note text, optional tag (Operational / Quality / Risk / Handover).
- Notes are searchable within the admin panel.
- Notes are included in the full audit export for a verification.
- A note can be pinned — appears at the top of the panel for all admins viewing that verification.

#### Dispute Resolution (Admin)

When a verification is in `DISPUTED` state, the admin sees a dedicated dispute resolution panel:

```
┌──────────────────────────────────────────────────────┐
│  ⚠️ DISPUTE — VP-2026-048291                         │
│  Filed: 30 April 2026  ·  By: [Customer name]        │
│  Type: Report contains factual errors                │
│                                                      │
│  Customer's description:                             │
│  "[Customer's dispute text]"                         │
│                                                      │
│  Evidence uploaded: [file list]                      │
│                                                      │
│  RESOLUTION                                          │
│  ○ Reject dispute — report stands                    │
│  ○ Uphold dispute — full refund                      │
│  ○ Uphold dispute — partial / offer re-check         │
│                                                      │
│  Admin resolution note (required, shown to customer):│
│  [textarea]                                          │
│                                                      │
│  [Submit Resolution]                                 │
└──────────────────────────────────────────────────────┘
```

Resolution note is mandatory and is delivered verbatim to the customer. Admin must write it in plain, professional language — not internal shorthand.

---

## 24. Agent Assignment & Coordination

### 24.1 Agent Assignment Modal

Triggered by "Assign Agent" on a task row.

```
┌────────────────────────────────────────────────┐
│  Assign Field Agent — VP-2026-048291           │
│  Location: Lekki, Lagos                        │
├────────────────────────────────────────────────┤
│  SUGGESTED AGENTS (sorted by match score)      │
│                                                │
│  🥇 Tunde A.   ★ 4.8  ·  Lekki  ·  2 active  │
│     Field Agent  ·  Verified ✅                │
│     [Assign]                                   │
│                                                │
│  🥈 Chidi O.   ★ 4.6  ·  VI  ·  1 active     │
│     Field Agent  ·  Verified ✅                │
│     [Assign]                                   │
│                                                │
│  🥉 Fatima I.  ★ 4.3  ·  Ikoyi  ·  0 active  │
│     Field Agent  ·  Verified ✅                │
│     [Assign]                                   │
│                                                │
│  [Search all agents]                           │
└────────────────────────────────────────────────┘
```

**Suggested agent ranking factors:**
1. Geographic proximity to property (primary)
2. Current task load (agents with fewer active tasks ranked higher)
3. Agent performance score (completion rate, accuracy, timeliness)
4. Agent availability (not on leave / suspended)

Suggestions are advisory. Admin always makes the final assignment decision.

### 24.2 Multi-Agent Coordination View

The coordination panel (Section 23.2) shows all required roles for the tier in a single checklist view:

| Role | Agent | Status | Last Update | Actions |
|---|---|---|---|---|
| Registry Agent | Amara O. | ✅ APPROVED | 29 Apr | View submission |
| Field Agent | Tunde A. | ⏳ IN_PROGRESS | 30 Apr, 9:00 AM | View / Reassign |
| Surveyor | — | ⬜ PENDING | — | Assign |
| Lawyer | — | ⬜ PENDING | Waiting for non-lawyer tasks | — |

The Lawyer row is read-only until all non-lawyer tasks are `SUBMITTED`.

### 24.3 Load Balancing View

**Route:** `/admin/agents`

A capacity view of all approved agents:

| Agent | Role | Active Tasks | Capacity | Status | Actions |
|---|---|---|---|---|---|
| Tunde A. | Field Agent | 3 | 5 max | 🟡 Busy | View / Reassign |
| Amara O. | Registry Agent | 1 | 5 max | 🟢 Available | View |
| Chidi O. | Field Agent | 5 | 5 max | 🔴 Full | — |
| Fatima I. | Field Agent | 0 | 5 max | 🟢 Available | View |

Max capacity per agent is admin-configurable. Agents at max capacity are excluded from the suggested list.

---

## 25. Task Approval & Report Release

### 25.1 Task Review Interface

**Route:** `/admin/verifications/[id]/tasks/[task-id]/review`

Admin reviews the agent's submission before approving or rejecting.

```
┌──────────────────────────────────────────────────────────┐
│  Task Review: Field Agent — VP-2026-048291               │
│  Agent: Tunde A.  ·  Submitted: 30 Apr, 2:15 PM         │
├──────────────────────────────────────────────────────────┤
│  [Full submission displayed — all sections]              │
│  [Evidence gallery — photos, videos]                     │
├──────────────────────────────────────────────────────────┤
│  Agent Trust Score:  74 / 100                            │
├──────────────────────────────────────────────────────────┤
│  ADMIN REVIEW NOTES (internal only)                      │
│  [Textarea for admin observations]                       │
├──────────────────────────────────────────────────────────┤
│  [✅ Approve Submission]   [❌ Request Revision]          │
└──────────────────────────────────────────────────────────┘
```

### 25.2 Approve Submission

- Admin clicks "Approve Submission".
- Confirmation modal: "Approve [Role]'s submission for VP-2026-048291?"
- On confirm: Task → `APPROVED`.
- System checks derived state logic: if ALL tasks are now `APPROVED` → global state → `UNDER_REVIEW` (admin report release gate activates).
- Agent notified: "Your submission for VP-2026-048291 has been approved."

### 25.3 Reject Submission (Request Revision)

- Admin clicks "Request Revision".
- Modal: rejection reason field (required, min 30 chars) + specific revision instructions.
- On confirm: Task → `REJECTED`. Global state reverts to `IN_PROGRESS` if previously `UNDER_REVIEW`.
- Agent notified immediately: "Admin has requested a revision on VP-2026-048291. Reason: [reason]."
- Rejection is logged in the audit trail.

> **Rejection UX for agent:** The task card on the agent's dashboard turns red and shows the rejection reason prominently. The "Rework & Resubmit" CTA replaces all other actions.

### 25.4 Report Release Gate

When ALL tasks are `APPROVED`, the system:
1. Computes the composite trust score from agent-submitted scores using admin-defined weights.
2. Assembles the report draft (structured data from all agent submissions).
3. Admin receives an alert: "All tasks approved. Report ready for release — VP-2026-048291."

**Report Release Review** (`/admin/verifications/[id]/report-review`):

Admin reviews the assembled report draft in full, including:
- All agent sections
- Trust score and its composition
- Any flagged items or conflicts (see Section 26)

Admin actions:
- **"Release Report"** → Report published to customer. Global state → `COMPLETED`. Customer notified.
- **"Request Changes"** → Admin can reject one or more specific tasks even at this stage, restarting their revision loop.

This is the final quality gate. No report reaches the customer without admin's deliberate release action.

---

## 26. Conflict Detection & Failure Handling

### 26.1 Conflicting Reports

**Trigger:** System detects significant discrepancies between agent submissions (e.g., Field Agent confirms property is vacant; Registry Agent records show tenanted with a 5-year lease).

**Detection rules** (configured by admin, examples):
- Physical occupancy reported by Field Agent conflicts with registry/legal occupancy status.
- Surveyor boundary coordinates do not match the customer's submitted survey plan.
- Lawyer flags forgery but Registry Agent marked documents as authentic.

**When a conflict is detected:**
1. Admin receives an alert: "⚠️ Conflicting reports detected — VP-2026-048291. [Description of conflict]."
2. Conflict flag shown on the verification detail page.
3. Admin reviews both submissions side-by-side.
4. Admin chooses:
   - **Reject one or both tasks** (agents must rework).
   - **Override** (admin adds a reconciliation note explaining the discrepancy — both findings included in report with admin's note).
   - **Flag for customer** (conflict noted in the report's risk summary as a finding requiring further investigation).

All conflict detections and admin resolutions are logged in the audit trail.

### 26.2 FAILED State

The `FAILED` state is distinct from `CANCELLED`. It represents a **critical failure** that makes the verification impossible to complete honestly.

**Triggers:**
- Confirmed document fraud (lawyer or admin determination).
- Property permanently inaccessible (physically impossible to inspect — demolished, under water, no legal access route).
- Customer submitted fraudulent property information.

**Admin action to declare `FAILED`:**
1. Admin clicks "Declare Failure" on the verification detail.
2. Required: failure reason (from dropdown + free text), supporting evidence.
3. Confirmation: "This action is irreversible. The verification will be closed as FAILED."
4. On confirm: global state → `FAILED` (terminal).
5. Customer notified with reason. Refund logic applied per policy.
6. All assigned agents' tasks are closed. Their completed work is still logged.

**Customer-facing message for `FAILED`:**
```
⚠️ This verification could not be completed.
Reason: [Admin-written reason]
Please contact our support team for assistance.
[Contact Support]  [Request Refund]
```

---

# PART E — CROSS-CUTTING

---

## 27. Audit & Compliance Logging

Every state transition — at both the verification level and the task level — is logged to the `AuditLog` entity (Section 2.1).

### 27.1 Logged Fields Per Event

- Entity type (`VERIFICATION` / `TASK` / `REPORT`)
- Entity ID
- Actor ID + role (`CUSTOMER` / `AGENT` / `ADMIN` / `SYSTEM`)
- From state → To state
- Timestamp
- IP address
- Optional note (e.g., rejection reason, delay reason)

### 27.2 What Gets Logged

| Event | Actor |
|---|---|
| Verification created | CUSTOMER |
| Payment confirmed | SYSTEM |
| Agent assigned to task | ADMIN |
| Agent accepted/declined task | AGENT |
| Agent started work | AGENT |
| Agent submitted findings | AGENT |
| Admin approved task | ADMIN |
| Admin rejected task (+ reason) | ADMIN |
| Report released to customer | ADMIN |
| Verification cancelled (+ reason) | CUSTOMER or ADMIN |
| Verification declared FAILED (+ reason) | ADMIN |
| Conflict flag raised | SYSTEM |
| Conflict resolved (+ resolution note) | ADMIN |
| Delay flag set (+ reason) | ADMIN |
| Agent no-show timeout | SYSTEM |

### 27.3 Audit Log Access

- **Admin:** Full audit log per verification. Filterable by actor, event type, date.
- **Customer:** Simplified activity log (timestamps of status changes only — no internal details).
- **Agent:** Their own task transition history only.

### 27.4 Retention

Audit logs are retained indefinitely. They are the primary evidence layer for:
- Legal disputes.
- Refund adjudication.
- Regulatory compliance.
- Platform quality control.

---

## 28. Edge Cases

### 28.1 Partial Task Completion

Some tasks complete while others remain pending. The verification stays in `IN_PROGRESS`. The completed tasks' findings are locked and included in the final report when all tasks eventually complete.

### 28.2 Rejection Loop

A task is rejected by admin. The task returns to `IN_PROGRESS`. The revision does **not** affect sibling tasks — other agents continue working. The verification's global state reverts from `UNDER_REVIEW` to `IN_PROGRESS` if the rejection occurs while the verification is under review. Once the rejected task is resubmitted and approved, the global state advances again.

### 28.3 Agent No-Show

Agent does not accept within the timeout window → Task returns to `PENDING`. Admin alerted. Non-response logged against agent's performance record. Admin reassigns.

### 28.4 Conflicting Reports

Conflict detected between agent submissions → Admin alerted. Admin resolves via task rejection, override note, or customer-facing flag. All resolutions logged. See Section 26.1.

### 28.5 Tier Upgrade Mid-Verification

Customer upgrades from Basic to Standard while verification is `IN_PROGRESS`:
1. New tasks created for the additional scope (Field Agent, Surveyor).
2. Existing approved tasks are preserved and carry into the upgraded verification.
3. Global state remains `IN_PROGRESS`.
4. SLA is extended to match the new tier.
5. Report gains new sections in the next version.

### 28.6 Lawyer Task Unlock Condition

Lawyer's task remains `PENDING` until all non-lawyer tasks (Field Agent, Surveyor, Registry Agent — as applicable for the tier) reach `SUBMITTED`. Once the condition is met, the Lawyer task auto-transitions from `PENDING` to `ASSIGNED` (if a lawyer has already been assigned) or remains `PENDING` with an alert to admin to assign a lawyer.

### 28.7 Payment Abandoned Mid-Wizard

Customer completes wizard but does not pay. Verification remains in `SUBMITTED` state. Draft is preserved. Abandoned verification recovery flow activates (Section 16.1). Price lock refreshes after 24 hours.

---

## 29. Success Metrics

These are the platform-level measurements that indicate the verification lifecycle is working correctly.

| Metric | Definition | Target |
|---|---|---|
| Average verification completion time | Time from `PAID` to `COMPLETED`, by tier | Basic ≤5 days, Standard ≤7, Premium ≤10 |
| % completed without any task revision | Verifications where no task was `REJECTED` | > 80% |
| Task acceptance time | Time from `ASSIGNED` to `ACCEPTED` | < 2 hours (median) |
| Agent no-show rate | Tasks that timed out without acceptance | < 5% |
| SLA breach rate | Verifications that exceeded tier SLA | < 10% |
| Customer trust rating | Post-report customer satisfaction | ≥ 4.5 / 5 |
| Admin report release time | Time from all tasks `APPROVED` to admin releasing report | < 4 hours |

---

## 30. UI/UX Specifications

### 30.1 Wizard Step Indicator

```
[1. Property] ──●── [2. Pricing] ──○── [3. Consent] ──○── [4. Payment]
```
Completed: filled + check. Current: filled + number. Future: empty + muted. Clicking completed steps navigates back (non-destructive).

### 30.2 Auto-Save Behaviour

- Wizard: saved to backend on each step completion. Local `sessionStorage` save on every keystroke as fallback.
- Agent submission: local auto-save on every field change. "Save Draft" sends to backend. Resume on reconnect.

### 30.3 Mobile Optimisation

Diaspora customers are often on mobile. Every component is mobile-first:
- Tier cards: stacked vertically on mobile.
- File upload: native camera trigger on mobile.
- Tracking dashboard: swipeable timeline, compact badges.
- Report: collapsible sections, sticky trust score header.

### 30.4 Offline / Low-Connectivity (Nigeria Reality)

- Form data auto-saved locally on every keystroke.
- File upload queue: auto-retry on reconnect.
- Sync indicator: "Saving..." / "Saved ✅" / "Offline — syncing when reconnected ⚠️"
- Evidence viewer: lazy-load with low-res placeholders.
- PDF generation: queued server-side; customer notified when ready.

### 30.5 Tooltips & Embedded Education

Consistent ℹ️ tooltip pattern on technical terms throughout all views (customer, agent, admin):
- "What is a C of O?" / "What is an encumbrance?" / "What is the trust score?" / "What is UNDER_REVIEW?"
- 50–100 words, plain English.
- Part of the Veriprops education system — building ideological power by making every actor smarter.

### 30.6 Language & Tone

- Plain English throughout (except formal disclaimer sections).
- Specific not vague: "5–7 business days", not "a few days."
- Empathetic to the diaspora context.
- The golden line appears where appropriate: **"We reduce uncertainty. We do not eliminate it."**

---

## 31. Error, Loading & Success States

### 31.1 Wizard Errors

| Error | Display |
|---|---|
| Required field missing | Inline red text below field. Submit disabled. |
| Google Maps address not found | "We couldn't find that address in Nigeria. Try a nearby landmark or major road." |
| Listing URL parse failure | "We couldn't read that listing page. Please enter details manually." |
| File too large | "This file is [X]MB. Maximum is [Y]MB." |
| Step save failed | Toast: "Couldn't save progress. Retrying..." — 3 retries, then: "Check your connection." |

### 31.2 Payment Errors

All gateway error codes mapped to plain-language messages (see Section 8.5).

### 31.3 Agent Submission Errors

| Error | Display |
|---|---|
| Minimum photos not met | "Please upload at least 5 photos before submitting." |
| Declaration not checked | "You must confirm the declaration to submit." |
| Trust score rationale missing | "Please explain your score if it is below 60 or above 90." |
| Upload failed | "One or more files failed to upload. Please retry." |

### 31.4 Admin Errors

| Error | Display |
|---|---|
| Rejection reason missing | "Please provide a reason for the revision request." |
| Failure reason missing | "Please provide a reason for declaring failure." |
| Assigning agent at max capacity | "This agent has reached their maximum active task limit." |

### 31.5 Loading States

| Action | State |
|---|---|
| Wizard step transition | Skeleton of next step |
| Listing URL import | "Reading listing..." spinner, 8s timeout |
| Payment processing | Full-screen status UI |
| Report loading | Skeleton, sections fill progressively |
| PDF generation | Inline progress bar |
| Evidence loading | Low-res placeholders, progressive load |
| Agent submission save | "Saving..." indicator in form header |

---

## 32. API Contract

### Verification

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | `/api/verifications` | Create draft | Customer |
| GET | `/api/verifications` | List verifications | Customer (own) / Admin (all) |
| GET | `/api/verifications/:id` | Get verification detail | Customer (own) / Agent (assigned) / Admin |
| PATCH | `/api/verifications/:id` | Update draft | Customer |
| POST | `/api/verifications/:id/submit` | Submit wizard → `SUBMITTED` | Customer |
| POST | `/api/verifications/:id/cancel` | Cancel verification | Customer / Admin |
| POST | `/api/verifications/:id/recheck` | Request re-check | Customer |
| POST | `/api/verifications/:id/upgrade` | Request tier upgrade | Customer |
| GET | `/api/verifications/:id/status` | Status + history | Customer / Agent / Admin |
| POST | `/api/verifications/:id/pause` | Pause verification | Admin |
| POST | `/api/verifications/:id/resume` | Resume verification | Admin |
| POST | `/api/verifications/:id/fail` | Declare FAILED | Admin |
| POST | `/api/verifications/:id/delay` | Set delay flag + reason | Admin |
| POST | `/api/verifications/:id/release-report` | Release report to customer | Admin |

### Tasks

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/tasks` | List available tasks (geo-filtered) | Agent |
| GET | `/api/tasks/:id` | Get task detail | Agent (assigned) / Admin |
| POST | `/api/tasks/:id/assign` | Assign agent to task | Admin |
| POST | `/api/tasks/:id/reassign` | Reassign task to different agent | Admin |
| POST | `/api/tasks/:id/accept` | Agent accepts task | Agent |
| POST | `/api/tasks/:id/decline` | Agent declines task | Agent |
| POST | `/api/tasks/:id/start` | Start work | Agent |
| PATCH | `/api/tasks/:id/draft` | Save submission draft | Agent |
| POST | `/api/tasks/:id/submit` | Submit findings | Agent |
| POST | `/api/tasks/:id/approve` | Approve submission | Admin |
| POST | `/api/tasks/:id/reject` | Reject submission + reason | Admin |
| POST | `/api/tasks/:id/escalate` | Agent issue escalation | Agent |

### Evidence

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/verifications/:id/evidence` | Get all evidence | Customer / Agent (assigned) / Admin |
| POST | `/api/tasks/:id/evidence` | Upload evidence item | Agent |
| GET | `/api/verifications/:id/evidence/:item-id` | Get single evidence item | Customer / Agent / Admin |

### Report

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/verifications/:id/report` | Get current report | Customer / Admin |
| GET | `/api/verifications/:id/report/versions` | List all versions | Customer / Admin |
| GET | `/api/verifications/:id/report/:version` | Get specific version | Customer / Admin |
| GET | `/api/verifications/:id/report/pdf` | Generate + download PDF | Customer / Admin |
| POST | `/api/verifications/:id/report/share` | Create share link | Customer |
| GET | `/api/verifications/:id/report/shares` | List active shares | Customer |
| DELETE | `/api/verifications/:id/report/shares/:token` | Revoke share | Customer |
| POST | `/api/verifications/:id/report/share-email` | Share with named recipient | Customer |

### Pricing & FX

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/pricing/tiers` | Get tiers with breakdown + SLA |
| GET | `/api/pricing/fx-rates` | Current FX rates |
| POST | `/api/pricing/lock` | Lock price for draft |
| GET | `/api/pricing/upgrade/:from/:to` | Upgrade delta price |

### Payment

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/payments/initiate` | Initiate payment |
| GET | `/api/payments/:ref/status` | Poll status |
| POST | `/api/payments/:ref/retry` | Retry failed payment |
| POST | `/api/payments/bank-transfer/confirm` | Confirm bank transfer |
| GET | `/api/payments/:ref/receipt` | Get receipt data |
| GET | `/api/payments/receipt/:ref/pdf` | Download receipt PDF |
| POST | `/api/payments/wire/proof` | Upload wire proof |

### Audit Log

| Method | Endpoint | Description | Access |
|---|---|---|---|
| GET | `/api/verifications/:id/audit` | Full audit log for verification | Admin |
| GET | `/api/tasks/:id/audit` | Audit log for task | Admin |

### Notifications

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/notifications` | Get user notifications |
| PATCH | `/api/notifications/:id/read` | Mark read |
| PATCH | `/api/notifications/read-all` | Mark all read |
| GET | `/api/account/notification-preferences` | Get preferences |
| PATCH | `/api/account/notification-preferences` | Update preferences |

### Referral

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/referrals` | Referral data + credit balance |
| GET | `/api/referrals/history` | Conversion history |

---

## 33. Open Questions

| # | Question | Impact | Owner |
|---|---|---|---|
| 1 | What is the cancellation surcharge percentage? | Refund policy, consent copy | Business |
| 2 | What are the exact pricing figures per tier and per line-item? | Pricing display | Business |
| 3 | What is the service fee percentage? | Pricing breakdown | Business |
| 4 | What is the first-time customer discount percentage? | Growth mechanics | Business |
| 5 | What is the referral credit (referrer) and discount (invitee) amount? | Growth mechanics | Business |
| 6 | What is the maximum discount cap (first-time + referral combined)? | Pricing logic | Business |
| 7 | Which payment gateway(s) are in scope? (Paystack/NGN, Flutterwave/multi-currency) | Payment experience | Engineering |
| 8 | What is the FX rate source? (Live API vs admin-set rates) | FX display | Engineering / Business |
| 9 | What is the price lock validity window? (24 hours suggested) | Payment UX | Business |
| 10 | Which listing sites should URL import support? (PropertyPro, NPC — full list needed) | Listing URL parser | Engineering |
| 11 | What is the trust score weighting formula per agent role? | Report accuracy | Business / Ops |
| 12 | Should trust score be visible to agents before they submit? | Agent UX | Product |
| 13 | What is the agent no-show timeout window? (Suggested: 4 hours — confirm) | Task assignment | Ops |
| 14 | What is the max active task capacity per agent? (Suggested: 5 — confirm) | Load balancing | Ops |
| 15 | What conflict detection rules should the system apply automatically? | Fraud detection | Ops / Engineering |
| 16 | Should wire transfer proof uploads be manually reviewed or auto-matched by reference? | Payment ops | Ops / Engineering |
| 17 | What Nigerian public holidays are excluded from SLA calculation? | SLA accuracy | Ops |
| 18 | Is SMS notification in scope for Phase 1? If so, which provider? | Notifications | Engineering |
| 19 | What is the re-check pricing model? (Flat fee / per-agent / percentage of original) | Re-verification | Business |
| 20 | What is the content source for Area Insights? Who maintains it? | Location UX | Ops / Content |
| 21 | What are the admin-configurable weights for the composite trust score? Who sets initial values? | Report | Business / Ops |
| 22 | What is the admin report release SLA target? (Suggested: < 4 hours — confirm) | Success metrics | Ops |
| 23 | Should share links be 30-day expiry by default, and is this configurable per customer? | Report sharing | Product |

---

*Document prepared for Veriprops product development.*  
*All specifications are subject to revision based on technical feasibility and business requirements.*  
*Last updated: April 2026 — v2.0*