# Veriprops — User Onboarding & Authentication
## Product Requirements Document (PRD)

**Product:** Veriprops  
**Module:** User Onboarding & Authentication  
**Version:** 1.1  
**Stack:** Next.js (App Router), FastAPI REST API backend  
**Status:** Draft  

**Changelog:**
| Version | Date | Changes |
|---|---|---|
| 1.0 | Apr 2026 | Initial draft |
| 1.1 | Apr 2026 | Added: expanded signup fields (country, timezone, currency); broadened OAuth first-time flow; formalized user_type/user_persona model; versioned consent; resume flow; OAuth→password set; failed attempt tracking; trust designation logic |

---

## Table of Contents

1. [Overview](#1-overview)
2. [User Types & Role Architecture](#2-user-types--role-architecture)
3. [Entry Points & Routing Logic](#3-entry-points--routing-logic)
4. [Shared Authentication Flows](#4-shared-authentication-flows)
   - 4.1 Sign Up (Email/Password)
   - 4.2 Login (Email/Password)
   - 4.3 OAuth Authentication
   - 4.4 Email Verification (OTP)
   - 4.5 Phone Verification (OTP)
   - 4.6 Forgot Password / Password Reset
   - 4.7 OAuth Account Linking
   - 4.8 Set Password for OAuth-Only Users
   - 4.9 Versioned Consent & Legal Acknowledgement
5. [Customer Onboarding Flow](#5-customer-onboarding-flow)
6. [Agent Onboarding Flow](#6-agent-onboarding-flow)
7. [Admin Onboarding Flow](#7-admin-onboarding-flow)
8. [Post-Auth Redirect Logic](#8-post-auth-redirect-logic)
9. [Session & Security Management](#9-session--security-management)
10. [Notification System (Auth Events)](#10-notification-system-auth-events)
11. [UI/UX Specifications](#11-uiux-specifications)
12. [Error, Loading & Success States](#12-error-loading--success-states)
13. [Next.js Implementation Notes](#13-nextjs-implementation-notes)
14. [API Contract (Auth Endpoints)](#14-api-contract-auth-endpoints)
15. [Open Questions](#15-open-questions)

---

## 1. Overview

### 1.1 Purpose

This document defines the complete product requirements for user onboarding and authentication across all user types on the Veriprops platform. It covers the full spectrum of identity flows: account creation, login, OTP verification, OAuth integration, role-based redirects, KYC for agents, and invite-based admin onboarding.

### 1.2 Goals

- **Frictionless entry:** Users should reach their destination (verification form, agent application, or admin dashboard) with minimal steps.
- **Trust from step one:** Every interaction during auth must reflect Veriprops' brand promise — security, legitimacy, and professionalism.
- **Verified identity:** Email and phone verification are mandatory before any role-specific flow begins.
- **Role intelligence:** The system automatically routes users to the correct dashboard without requiring them to select a portal.
- **Security-first:** Devices, OAuth accounts, and sessions are fully managed and auditable.

### 1.3 Scope

| In Scope | Out of Scope |
|---|---|
| All auth flows (signup, login, OAuth, OTP, password reset) | Payment auth/authorization |
| Customer, Agent, and Admin onboarding | Verification workflow itself |
| Role-based redirect logic | Report generation |
| Session & device management | Agent commission logic |
| KYC flow for agents | Admin analytics |
| Admin invite flow | |

---

## 2. User Types & Role Architecture

### 2.1 Roles

| Role | Description | How Created |
|---|---|---|
| **Customer** | Submits property details for verification. Pays per verification. | Self-signup |
| **Agent** | Independent contributor who performs verification tasks. Earns commission. | Self-signup + Admin approval |
| **Admin** | Administers the platform. Multiple privilege levels. | Admin invite only |

### 2.2 Agent Sub-Types

A single user account can be assigned one or more agent types. Each type has a distinct onboarding form and dashboard:

| Agent Type | Responsibility |
|---|---|
| Field Agent | Physical site inspection |
| Surveyor | Boundary and location confirmation |
| Registry Agent | Registry search |
| Lawyer | Title doc verification, ownership, legal opinion, encumbrances & risk |

### 2.3 Admin Sub-Roles

| Sub-Role | Capabilities |
|---|---|
| Super Admin | Full system access, can invite other admins, configure all settings |
| Operations Manager | Assign agents, manage verifications, view reports |
| Finance Admin | Approve payouts, view payment data, manage commissions |

### 2.4 Dual-Role Users (Agent + Customer)

A user who is both an Agent and a Customer:
- Is redirected to the **Agent Portal** by default after login.
- Has a visible **"Switch to Customer Portal"** toggle in the agent portal header.
- Switching is instant (client-side route change with shared session token).
- The reverse (Customer → Agent switch) is available in the customer portal as well.

### 2.5 User Data Model

The user model has two distinct role fields that serve different purposes and must not be conflated:

#### `user_type` — System Authority Layer

| Value | Meaning |
|---|---|
| `USER` | Standard platform user (Customer or Agent) |
| `ADMIN` | Platform administrator with elevated system privileges |

**Rules:**
- Immutable after account creation. Cannot be changed by any user action, including by the user themselves.
- Set at account creation: all self-signup users get `USER`. Admin-invited users get `ADMIN`.
- Controls access to the admin portal and system-level capabilities.

#### `user_persona` — Behaviour Layer

| Value | Meaning |
|---|---|
| `CUSTOMER` | User has initiated the customer experience (submitted a verification, etc.) |
| `AGENT` | User has applied to or been accepted as an agent |

**Rules:**
- Mutable. Stored as a **list** — a user can hold both `CUSTOMER` and `AGENT` simultaneously.
- Added to, never removed (personas are additive — a user doesn't lose their customer persona when they become an agent).
- Default: `[]` (empty list) at account creation. Populated as the user engages with each persona's flow.
- Drives portal access and post-auth redirect logic (see Section 8).

#### Trust Status

A user is elevated to **trusted** status once they demonstrate meaningful platform engagement:

| Persona | Trust Event | Trigger |
|---|---|---|
| Customer | First successful payment completed | Payment confirmed by payment gateway |
| Agent | First task/report submitted | Agent submits first job report |

Trust status is stored on the user record and influences:
- Reduced friction on subsequent flows
- Eligibility for certain platform features (Phase 2)
- Risk scoring and fraud detection thresholds

---

## 3. Entry Points & Routing Logic

### 3.1 Homepage CTAs

The two primary onboarding triggers are on the homepage:

| CTA Button | User Intent | Next Step |
|---|---|---|
| **"Verify a Property"** | Customer wants to submit a verification | → Auth Gate → Customer Onboarding |
| **"Become an Agent"** | User wants to join as an agent | → Auth Gate → Agent Onboarding |
| **"Sign In"** (navbar) | Returning user | → Auth Form → Role-based Redirect |

### 3.2 Auth Gate

The **Auth Gate** is a shared interstitial that appears when a CTA requires authentication. Its behavior:

1. If user is **not logged in** → Show the login form with context ("Sign in to verify a property" / "Sign in to become an agent").
2. If user **has no account** → User clicks "Create account" link on the login form → Signup form.
3. If user **is already logged in** → Skip auth gate entirely, proceed directly to the destination flow.

The destination intent (e.g., `?intent=verify-property` or `?intent=become-agent`) is stored in the URL query string and preserved through the auth flow.

### 3.3 Protected Routes

| Route | Access |
|---|---|
| `/portal/*` | Customer (authenticated) |
| `/agent/*` | Agent (authenticated + approved) |
| `/admin/*` | Admin (authenticated + admin role) |
| `/auth/*` | Public (unauthenticated only — redirect if logged in) |
| `/verify/[id]` | Public (verification public lookup) |

---

## 4. Shared Authentication Flows

### 4.1 Sign Up (Email / Password)

**Route:** `/auth/signup`

**Trigger:** User clicks "Create account" on the login form.

#### Form Fields

| Field | Type | Validation |
|---|---|---|
| First Name | Text | Required, min 2 chars |
| Last Name | Text | Required, min 2 chars |
| Email | Email input | Required, valid email format, verified via OTP |
| Phone | Phone input with country flag selector | Required, verified via OTP |
| Country of Residence | Searchable dropdown (country list) | Required |
| Timezone | Searchable dropdown (filtered by country selection) | Required; auto-suggested from Country of Residence |
| Preferred Currency | Dropdown: NGN / USD / GBP / EUR | Required; default: NGN |
| Password | Password input | See Password Rules below |
| Confirm Password | Password input | Must match Password field |

> **UX note:** Country of Residence, Timezone, and Preferred Currency are grouped in a collapsible "Preferences" section below the core fields to reduce visual overwhelm. Timezone auto-populates based on the selected country but remains editable. These preferences drive currency display and SLA communication (e.g., "Report ready by 3pm your time") throughout the platform.

#### Password Rules

- Minimum 8 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character
- Real-time strength indicator (Weak / Fair / Strong / Very Strong) displayed as a color-coded bar beneath the input
- Inline validation messages appear on blur (not on every keystroke)

#### OTP Verification (Inline)

Both **email** and **phone** fields have an inline **"Verify"** button that appears once the field has valid input:

1. User types a valid email/phone → "Verify" button activates.
2. User clicks "Verify" → Backend sends OTP → OTP modal appears (see Section 4.4 / 4.5).
3. On success → Field shows ✅ verified badge. Verify button is replaced.
4. Both fields must be verified before the form can be submitted.

#### Submission

- Disabled until: all fields valid + email verified + phone verified.
- On submit: account is created and user is automatically authenticated (no separate login step).
- System detects `intent` from URL and redirects to the appropriate onboarding flow (Customer or Agent) or dashboard.

#### Resume Flow

If a user begins signup but abandons before completing (e.g., closes the tab before verifying phone), the system:
- Saves their partial progress server-side against their email.
- On next visit, detects the incomplete registration and restores their progress to the furthest completed step.
- Shows a contextual message: _"Welcome back. Continue where you left off."_
- This applies to all multi-step flows: signup, agent onboarding wizard, verification wizard.

---

### 4.2 Login (Email / Password)

**Route:** `/auth/login`

#### Form Fields

| Field | Type | Validation |
|---|---|---|
| Email | Email input | Required |
| Password | Password input | Required |

#### Behavior

- "Forgot password?" link → `/auth/forgot-password`
- "Create account" link → `/auth/signup`
- OAuth buttons (Google, [others TBD]) displayed below the form divider
- On success → Role-based redirect (see Section 8)

#### Rate Limiting & Lockout (UI Feedback)

- After 5 failed attempts: show warning ("2 attempts remaining before temporary lockout")
- After 7 failed attempts: 15-minute lockout with countdown timer shown on screen
- After lockout: prompt to reset password

#### Failed Attempt Tracking

All failed login and OTP attempts are tracked at the backend:
- Logged against the user account with timestamp, IP address, and device fingerprint.
- Surfaced in the user's Security Activity Log (Section 9.4).
- Used by the fraud detection layer to flag suspicious patterns (e.g., multiple failed attempts from different IPs).
- Admins can view aggregate failure data per user in the Admin panel.

---

### 4.3 OAuth Authentication

**Supported Providers (Phase 1):** Google  
**Additional providers (Phase 2):** Apple, Facebook

#### Flow Architecture

OAuth is **backend-initiated** on Veriprops. The frontend does not handle tokens directly.

1. User clicks OAuth button (e.g., "Continue with Google").
2. Frontend calls backend endpoint: `GET /api/auth/oauth/google/init` → receives a redirect URL.
3. Frontend redirects user to that URL (Google consent screen).
4. Google redirects back to: `/auth/oauth/callback?provider=google&code=...`
5. Frontend sends code to backend: `POST /api/auth/oauth/google/verify`
6. Backend returns: `{ user, token, is_new_user, needs_phone }` 
7. Frontend handles response (see scenarios below).

#### Scenario A — First-Time OAuth User (New Account)

1. Account is created automatically using data from the OAuth profile (name, email, avatar).
2. A **"Complete your profile"** modal appears with all signup fields that were not provided by the OAuth profile. This typically includes:
   - Phone number (mandatory — must be verified via OTP before proceeding)
   - Country of Residence
   - Timezone
   - Preferred Currency
   - Any other fields missing from the OAuth payload
3. Fields already populated from OAuth (e.g., name, email) are pre-filled and editable — the user may override them.
4. The modal cannot be dismissed without completing mandatory fields (phone + verification).
5. After all fields are collected and phone is verified → proceed to role-specific onboarding or dashboard based on `intent`.

#### Scenario B — Returning OAuth User

1. Login completes normally.
2. Redirect to role-based dashboard.

#### Scenario C — OAuth Email Matches Existing Password Account

1. Backend detects email already exists with a password-based account.
2. UI shows: _"An account with this email already exists. Please log in with your password first, then link Google from your security settings."_
3. User is redirected to the login form with email pre-filled.
4. After login, they can link the OAuth account from Security Settings.

#### Scenario D — OAuth Failure

1. If OAuth callback returns an error:
   - Show error message: _"Google sign-in failed. Please try again or use email/password."_
   - Retry button + "Use email instead" link
2. Log error details for debugging.

---

### 4.4 Email Verification (OTP)

**Trigger:** Clicking "Verify" next to the email field during signup, or manually from account settings.

#### OTP Modal

| Element | Spec |
|---|---|
| Title | "Verify your email" |
| Description | "We sent a 6-digit code to [email]. Enter it below." |
| Input | 6 individual digit boxes (auto-advance on input) |
| Timer | Countdown from 10:00 (MM:SS format) |
| Resend Button | Disabled until timer hits 0:00. On click: resend OTP, reset timer. Max 3 resends before 30-min lockout. |
| Submit Button | "Verify Code" — disabled until all 6 digits entered |
| Cancel | Closes modal, resets verification state |

#### States

- **Pending:** Timer running, awaiting input.
- **Verifying:** Spinner on submit button, inputs disabled.
- **Success:** Modal closes, email field shows ✅ badge.
- **Error (wrong code):** Inline error "Incorrect code. X attempts remaining." Inputs shake animation.
- **Expired:** "Your code has expired. Click Resend to get a new one."
- **Locked:** "Too many attempts. Please try again in 30 minutes."

---

### 4.5 Phone Verification (OTP)

**Trigger:** Clicking "Verify" next to the phone field during signup, or during first-time OAuth, or from account settings.

Identical UX to Email OTP (Section 4.4) with the following differences:

| Element | Spec |
|---|---|
| Title | "Verify your phone number" |
| Description | "We sent a 6-digit code via SMS to [phone number]." |
| Phone Input | E.164 format. Country flag dropdown (searchable). Defaults to Nigeria 🇳🇬 (+234). |
| OTP Delivery | SMS (primary). WhatsApp delivery (Phase 2). |

---

### 4.6 Forgot Password / Password Reset

**Route:** `/auth/forgot-password`

#### Step 1 — Request Reset

- Email input field
- "Send Reset Link" button
- Success message: _"If an account exists with this email, you'll receive a reset link shortly."_ (same message regardless of whether email exists — prevents email enumeration)

#### Step 2 — Reset Link (Email)

Email contains a tokenized link:  
`https://veriprops.com/auth/reset-password?token=...`  
Token validity: 1 hour. Single-use.

#### Step 3 — New Password Form

**Route:** `/auth/reset-password?token=...`

- Validate token on page load. If invalid/expired → show error with link to request again.
- Fields: New Password + Confirm Password
- Same password rules and strength indicator as signup
- On success: Password changed, user auto-logged in, redirected to dashboard.
- All existing sessions are invalidated on password change.
- Notification sent to user's email: _"Your Veriprops password was changed."_

---

### 4.7 OAuth Account Linking

**Location:** Account Settings → Security → Linked Accounts

#### Link a New OAuth Account

1. User clicks "Link Google Account" button.
2. OAuth flow initiates (same backend-initiated flow as Section 4.3).
3. If email matches current account → account linked. Success toast.
4. If email does NOT match → Error: _"This Google account is associated with a different email. You can only link accounts with the same email address."_

#### Unlink an OAuth Account

- **Condition:** Cannot unlink if user is currently logged in via that OAuth provider (would lose access).
- If user is logged in via password → unlink is allowed.
- If user has no password set → prompt them to set a password before unlinking.
- Unlink shows confirmation dialog: _"Are you sure you want to unlink your Google account? You can re-link it anytime."_

#### Display

- Each linked provider shown as a row with: Provider icon, email, "Linked" badge, Unlink button.
- "Link [Provider]" button shown for unlinked providers.

---

### 4.8 Set Password for OAuth-Only Users

Users who created their account via OAuth (Google, etc.) and have no password set can add email/password login from their account settings.

**Route:** Account Settings → Security → Sign-in Methods → "Add Password"

#### Flow

1. User clicks "Add Password".
2. Form shown:
   - New Password field (with strength indicator)
   - Confirm Password field
3. On submit → backend sets password on the account.
4. User can now login with both OAuth and email/password.
5. Success notification: _"Password added. You can now sign in with your email and password."_

#### Rules

- The user's email is already verified (from OAuth), so no re-verification is needed when adding a password.
- Adding a password does **not** unlink the OAuth provider.
- If the user later changes this password, all existing sessions are invalidated (same as the standard password reset flow in Section 4.6).

---

### 4.9 Versioned Consent & Legal Acknowledgement

Veriprops operates in a high-liability legal domain. All user consent must be versioned and each acceptance event must be recorded against the exact version of the terms that was shown.

#### Consent Model

Each consent document has:
- A **consent type** (e.g., `PLATFORM_TERMS`, `PRIVACY_POLICY`, `AGENT_TERMS`, `VERIFICATION_TERMS`)
- A **version identifier** (e.g., `v1.0`, `v1.1`)
- A **published date**

Each user consent record captures:
- User ID
- Consent type
- Consent version (at the time of acceptance)
- Timestamp
- IP address
- Device fingerprint

This creates a legally defensible audit trail: _"User X accepted Platform Terms v1.2 on [date] from IP [X] on device [Y]."_

#### When Consent Is Collected

| Trigger | Consent Type | Mandatory |
|---|---|---|
| Account creation (signup) | Platform Terms + Privacy Policy | ✅ Yes |
| Agent application submission | Agent Independent Contributor Terms | ✅ Yes |
| Before each verification payment | Verification Disclaimer + Liability Terms | ✅ Yes |
| Report access (first view) | Report Disclaimer | ✅ Yes |

#### Version Update Handling

If a consent document is updated after a user has already accepted a previous version:
- On next login (or next relevant action), the user is shown a modal highlighting what changed.
- The user must re-accept before proceeding.
- Declining blocks access to the relevant feature (e.g., declining updated Platform Terms blocks portal access).
- This modal cannot be dismissed without an explicit accept or decline action.

#### UI Requirements

- Consent checkboxes must not be pre-checked.
- Full terms must be accessible (expandable text or link to full document) before the checkbox.
- The checkbox label states the version explicitly: _"I agree to the Veriprops Platform Terms of Service (v1.2) and Privacy Policy (v1.0)."_
- "I Agree" button is disabled until the checkbox is checked.

---

## 5. Customer Onboarding Flow

### 5.1 Trigger

User clicks **"Verify a Property"** on the homepage.

### 5.2 Flow Sequence

```
Homepage CTA
  └── Auth Gate (if not logged in)
        └── Login / Signup (email or OAuth)
              └── Email + Phone OTP verification
                    └── Auto-authenticated
                          └── [SKIP if already logged in]
                                └── New Verification Wizard (Step 1)
```

### 5.3 Post-Auth Destination

After successful auth (or if already logged in), user is taken directly to the **New Verification Wizard** — not the dashboard. The wizard is the customer's first real product experience.

**Route:** `/portal/verifications/new`

The New Verification Wizard is a multi-step form (out of scope for this PRD — documented in the Verification PRD). From an auth perspective, the requirement is:

- The wizard is accessible immediately after first login.
- Progress is auto-saved (draft state) so if the user closes the tab and returns, they land back on the wizard where they left off.

### 5.4 Customer Profile Completeness

The customer does not have any additional onboarding steps beyond basic user creation (name, email, phone). Profile fields like country of residence or preferred currency are collected progressively inside the portal.

### 5.5 Returning Customer

On subsequent logins, returning customers are redirected to `/portal/dashboard` (not the wizard), unless they have an abandoned verification draft — in which case a persistent banner appears: _"You didn't complete your verification request. Continue where you left off."_

---

## 6. Agent Onboarding Flow

### 6.1 Trigger

User clicks **"Become an Agent"** on the homepage.

### 6.2 Flow Sequence

```
Homepage CTA
  └── Auth Gate (if not logged in)
        └── Login / Signup (email or OAuth)
              └── Email + Phone OTP verification
                    └── Auto-authenticated
                          └── [SKIP if already logged in]
                                └── Agent Application Wizard (Step 1)
```

**Route for wizard:** `/agent/onboarding`

### 6.3 Agent Application Wizard

The wizard is a multi-step flow presented immediately after authentication. It is only shown once. If the user leaves and returns before completing it, they resume from where they left off.

---

#### Step 1 — Agent Type Selection

**Heading:** "What type of agent would you like to be?"

Display 4 cards side-by-side (2×2 grid on mobile):

| Card | Icon | Title | Description |
|---|---|---|---|
| Field Agent | 🏠 | Field Agent | Visit properties and submit physical inspection reports |
| Surveyor | 📐 | Surveyor | Confirm boundaries and geographic coordinates |
| Registry Agent | 📋 | Registry Agent | Search land registries and verify documents |
| Lawyer | ⚖️ | Lawyer | Provide legal opinions and encumbrance assessments |

- User may select **one or more** agent types.
- Selection is toggle-based (active state shows checkmark + border highlight).
- At least one must be selected to proceed.
- **Help text:** _"You can apply for multiple roles. Each requires its own credential verification."_

---

#### Step 2 — KYC (Know Your Customer)

**Heading:** "Verify your identity"

This step is the same for all agent types, with additional credential uploads shown conditionally in Step 3.

##### Sub-step 2A — Identity Verification Method (select one)

**Option A: BVN Verification**
- BVN input field (11-digit number)
- "Verify BVN" button → calls backend → real-time BVN validation
- On success: name from BVN shown as confirmation (e.g., _"BVN verified: Chukwuemeka Obi"_)
- On failure: _"We could not verify this BVN. Please check and try again, or use ID upload."_

**Option B: Government ID Upload**
- ID Type selector: NIN Slip / International Passport / Driver's Licence / Voter's Card
- ID Number input field
- Front of ID: file upload
- Back of ID (if applicable): file upload
- Upload specs: JPG/PNG/PDF, max 5MB per file

##### Sub-step 2B — Selfie Verification

- Instruction: _"Take a clear selfie. Your face must be fully visible and well-lit."_
- Upload method: Camera capture (preferred) or file upload
- Selfie is matched against the BVN photo or uploaded ID photo by the backend.
- States:
  - Uploading: progress bar
  - Processing: spinner with message "Comparing with your ID..."
  - Matched: ✅ "Identity confirmed"
  - Unmatched: ❌ "Face doesn't match your ID. Please try again with better lighting."

---

#### Step 3 — Professional Credentials

This step is shown **conditionally** based on agent types selected in Step 1.

| Agent Type | Required Uploads |
|---|---|
| Field Agent | No professional credentials required |
| Registry Agent | No professional credentials required |
| Surveyor | Valid surveying license + any certifications |
| Lawyer | Valid Nigerian Bar Association (NBA) license + any certifications |

**For each required credential:**

- Document name / type (labelled clearly)
- File upload (JPG/PNG/PDF, max 10MB)
- Optional: Registration number / license number input

**For all agent types (optional but recommended):**
- Years of experience (number input)
- Coverage area(s): State and City multi-select (drives job matching)
- Brief professional bio (textarea, max 300 characters)

---

#### Step 4 — Review & Submit

**Heading:** "Review your application"

A read-only summary of all submitted information:
- Agent type(s) selected
- Identity method used (BVN verified or ID uploaded)
- Selfie verification status
- Credentials uploaded (list of file names)
- Coverage areas

**Terms acknowledgement (mandatory):**
- Checkbox: _"I confirm that all information provided is accurate and I understand that false information will result in permanent disqualification."_
- Checkbox: _"I have read and agree to the Veriprops Agent Terms & Conditions."_

**Submit button:** "Submit Application"

On submit → Application enters **pending review** state.

---

#### Step 5 — Application Submitted (Confirmation Screen)

**Heading:** "Application submitted! ✅"

Content:
- _"Thank you for applying to be a Veriprops agent. Our team will review your application and credentials within 2–5 business days."_
- _"You will receive an email and in-app notification when your application is reviewed."_
- Application reference number shown.
- CTA: "Go to my Agent Dashboard"

Agent dashboard shows the **approval status screen** (not full agent tools) until approved.

---

### 6.4 Approval Status Dashboard

**Route:** `/agent/dashboard` (pre-approval)

Shown to agents whose application is under review.

```
┌──────────────────────────────────────────┐
│  Application Status                      │
│                                          │
│  ⏳ Under Review                         │
│                                          │
│  Submitted: Jan 5, 2025                  │
│  Estimated review: 2–5 business days     │
│                                          │
│  [View Application Summary]              │
└──────────────────────────────────────────┘
```

States:
- **Pending ⏳** — Under review. No actions available.
- **Approved ✅** — Full agent dashboard unlocked. Notification sent.
- **Rejected ❌** — Reason displayed. Option to re-apply or appeal.

On rejection, display the admin-provided reason and a link to the agent's submitted documents so they can understand the issue.

---

### 6.5 Returning Agent (Already Applied / Approved)

On subsequent logins, agents are redirected to:
- `/agent/dashboard` — if approved (full dashboard)
- `/agent/dashboard` — if pending (status screen)
- `/agent/onboarding` — if application was never completed (resume wizard)

---

## 7. Admin Onboarding Flow

### 7.1 Policy

Admin accounts **cannot** be self-created. They are only created through an invitation issued by an existing admin with the appropriate privilege (Super Admin only can invite other admins).

### 7.2 Invitation Flow

#### Step 1 — Admin Issues Invite (Admin Portal)

**Route:** `/admin/settings/team` → "Invite Admin" button

Admin fills in:
- Invitee email address
- Admin sub-role: Super Admin / Operations Manager / Finance Admin

System sends an invitation email.

#### Step 2 — Invitation Email

Email to invitee contains:
- Sender context: _"[Name] has invited you to join Veriprops as an [Role]."_
- Tokenized link: `https://veriprops.com/auth/admin-invite?token=...`
- Token validity: 72 hours
- If token expired: user sees expiry message with option to request a new invite.

#### Step 3 — Invitee Completes Onboarding

**Route:** `/auth/admin-invite?token=...`

Page validates token. If valid, shows:

**Scenario A — Invitee has no Veriprops account:**
- Standard sign-up form (First Name, Last Name, Email pre-filled from invite, Phone + verification)
- Password creation (or OAuth option)
- On completion → Admin account created → Redirected to `/admin/dashboard`

**Scenario B — Invitee already has a Veriprops account (as Customer or Agent):**
- Page shows: _"Welcome back, [Name]. This invite will add admin access to your existing Veriprops account."_
- User must **log in** to confirm identity (not re-register)
- After login → Admin role added to existing account → Redirected to `/admin/dashboard`
- The user now has multiple roles (e.g., Agent + Admin). Post-auth redirect logic handles this correctly.

**Scenario C — Invitee already has an admin account:**
- _"You already have admin access on Veriprops."_ Link to login.

#### Step 4 — Admin Account Created

Admin is logged in and directed to `/admin/dashboard`.

---

## 8. Post-Auth Redirect Logic

This is the system's role-routing intelligence. Executed on every successful authentication event.

### 8.1 Logic Flow

```
User authenticates
  └── Fetch user roles from token/session
        ├── Has pending intent in URL? (e.g., ?intent=verify-property)
        │     └── Redirect to intent destination (preserving roles)
        │
        └── No pending intent — use default redirect by role:
              │
              ├── ADMIN role present → /admin/dashboard
              │
              ├── AGENT role present (no ADMIN)
              │     ├── Application complete + approved → /agent/dashboard
              │     ├── Application complete + pending/rejected → /agent/dashboard (status screen)
              │     └── Application not started/incomplete → /agent/onboarding
              │
              └── CUSTOMER only
                    ├── Has incomplete verification draft → /portal/verifications/new (with resume state)
                    └── No draft → /portal/dashboard
```

### 8.2 Multi-Role Priority

| Role Combination | Default Redirect |
|---|---|
| Admin only | `/admin/dashboard` |
| Agent + Customer | `/agent/dashboard` (with switch to customer portal) |
| Admin + Agent + Customer | `/admin/dashboard` (highest privilege wins) |
| Customer only | `/portal/dashboard` |

### 8.3 Portal Switching (Agent ↔ Customer)

Available in the top navigation bar when user has both Agent and Customer roles:

```
[Agent Portal] ↔ [Switch to Customer Portal]
```

- Toggle is a button in the header nav, not a full page reload — client-side route change.
- Session/token is shared. No re-authentication needed.
- State (notifications, drafts) is scoped to the active portal view.

---

## 9. Session & Security Management

### 9.1 Session Tokens

- JWT-based authentication (short-lived access token + longer-lived refresh token).
- Access token: 15-minute expiry.
- Refresh token: 30-day expiry with sliding window.
- Tokens stored in **httpOnly cookies** (not localStorage) — XSS protection.
- Silent refresh handled client-side before access token expiry.

### 9.2 Connected Devices

**Route:** Account Settings → Security → Connected Devices

Every active session is listed:

| Field | Description |
|---|---|
| Device Name | Inferred from User-Agent (e.g., "Chrome on MacBook") |
| Current Device | Highlighted with "This device" badge |
| Browser | Browser name + version |
| Location | City, Country (IP-based geolocation) |
| Last Active | Relative timestamp (e.g., "2 hours ago") |
| Revoke | Button (disabled for current device) |

**Actions:**
- **Revoke** individual device: Invalidates that session's refresh token. Device is logged out silently.
- **"Log out from all devices"**: Invalidates ALL refresh tokens except the current device.
- Notification sent on any device revocation: _"A device was removed from your Veriprops account."_

### 9.3 Linked OAuth Accounts

**Route:** Account Settings → Security → Linked Accounts

| Field | Description |
|---|---|
| Provider | Google icon + "Google" |
| Email | The Google account email |
| Status | "Linked" badge |
| Action | "Unlink" button (with conditions in Section 4.7) |

### 9.4 Activity Log

**Route:** Account Settings → Security → Activity History

Chronological log of auth-related events:

- Account created
- Login (with device + location)
- Password changed
- OAuth account linked/unlinked
- Device revoked
- Failed login attempts

Each row shows: Event, Date/Time, Device, Location.

### 9.5 Account Lockout Policy

| Event | Threshold | Action |
|---|---|---|
| Failed login attempts | 7 attempts | 15-minute lockout |
| Failed OTP attempts | 5 attempts | 30-minute lockout |
| Suspicious IP | Backend-defined | Flag + email alert to user |

---

## 10. Notification System (Auth Events)

All auth events trigger notifications through at least one channel.

| Event | In-App | Email |
|---|---|---|
| Account created | ✅ | ✅ Welcome email |
| Email verified | ✅ | — |
| Phone verified | ✅ | — |
| Login from new device | ✅ | ✅ Alert email |
| Password changed | ✅ | ✅ Alert email |
| OAuth account linked | ✅ | ✅ Alert email |
| OAuth account unlinked | ✅ | ✅ Alert email |
| Device revoked | ✅ | ✅ Alert email |
| Agent application submitted | ✅ | ✅ Confirmation email |
| Agent application approved | ✅ | ✅ Approval email |
| Agent application rejected | ✅ | ✅ Rejection email (with reason) |
| Admin invite sent | — | ✅ Invite email |
| Admin invite accepted | ✅ (to issuer) | ✅ (to issuer) |
| Account lockout triggered | ✅ | ✅ |

---

## 11. UI/UX Specifications

### 11.1 Auth Pages Layout

All auth pages (`/auth/*`) use a **split-panel layout**:

- **Left panel (60%):** Veriprops branding panel
  - Logo
  - Trust statement: _"Verify everything. Trust nothing blindly."_
  - Rotating trust signals (verified properties count, agent count, testimonial quotes)
  - Background: deep navy with geometric map-line pattern

- **Right panel (40%):** Auth form
  - Clean white/off-white background
  - Form centered with generous padding
  - Back link at top (returns to previous page or homepage)

On **mobile** (< 768px): Left panel collapses to a slim header bar (logo + brand tagline only). Right panel takes full screen.

### 11.2 Form Design Principles

- Each form field has: Label (above), Input, Helper text (below — for guidance), Error message (below — replaces helper text on error).
- Field validation is **on-blur** (when user leaves the field), not on every keystroke. Exception: password strength meter updates in real-time.
- Tab key navigation must be fully functional.
- All inputs are keyboard accessible.

### 11.3 OTP Input

- 6 individual single-character input boxes displayed in a row.
- Auto-advance to next box on input.
- Auto-back to previous box on Backspace.
- Paste support: Pasting a 6-digit code auto-fills all boxes.
- Input type: `tel` (numeric keyboard on mobile).
- On error: inputs shake (CSS animation), cleared for re-entry.

### 11.4 Phone Input

- Uses libphonenumber for E.164 formatting and validation.
- Country flag dropdown is searchable (type country name or dial code).
- Default country: 🇳🇬 Nigeria (+234)
- Format: `+234 800 000 0000` (shown with spaces, stored as E.164)
- Validates phone format per country before enabling the "Verify" button.

### 11.5 Onboarding Wizard Progress

- Multi-step wizard shows a **step indicator** at the top: numbered steps with connecting line.
  - Completed steps: filled circle, checkmark icon
  - Current step: filled circle, step number, bold label
  - Future steps: empty circle, muted label
- "Back" button available on all steps except Step 1.
- Progress is auto-saved to backend as a draft on each step completion.
- No data is lost if user navigates away and returns.

### 11.6 KYC File Upload

- Drag-and-drop zone with upload icon.
- Accepted file types shown (JPG, PNG, PDF).
- Max file size shown (5MB for ID, 10MB for credentials).
- Upload progress bar per file.
- Uploaded files shown as thumbnails (images) or file name rows (PDFs).
- Individual file delete/replace capability.

### 11.7 Approval Status Dashboard (Agent Pre-Approval)

Minimalist dashboard with:
- Large status indicator (icon + color + label)
- Application reference number
- Submitted date
- Estimated review timeframe
- Link to view submitted application details
- Contact support link

---

## 12. Error, Loading & Success States

### 12.1 Global Error Handling

| Error Type | Display Method |
|---|---|
| Field validation error | Inline below field, red text, field border turns red |
| Form submission error (network) | Toast notification (top-right), auto-dismiss after 5s |
| Form submission error (server, e.g., email taken) | Inline below the relevant field |
| Auth error (wrong password) | Inline below the password field |
| Session expired | Redirect to login with message: "Your session expired. Please sign in again." |
| 403 Unauthorized | Redirect to login |
| 500 Server Error | Full-page error state with retry button and support link |

### 12.2 Loading States

- All async actions show a spinner within the triggering button. Button is disabled during loading.
- Forms are not re-submittable during loading (prevent duplicate submissions).
- Page-level loading (e.g., route change): skeleton screens, never bare white screens.

### 12.3 Success States

- Form submission success: Success toast + redirect (no confusing empty form left on screen).
- OTP verification success: Modal closes + inline ✅ badge on field.
- Agent application submitted: Full-page confirmation screen (Section 6.3, Step 5).
- Password reset: Success screen with "Go to login" button.

---

## 13. Next.js Implementation Notes

### 13.1 App Router Structure

```
app/
  (auth)/
    layout.tsx          ← Split-panel auth layout
    login/
      page.tsx
    signup/
      page.tsx
    forgot-password/
      page.tsx
    reset-password/
      page.tsx
    oauth/
      callback/
        page.tsx        ← Handles OAuth callback
    admin-invite/
      page.tsx
  (portal)/
    layout.tsx          ← Customer portal layout (auth guard)
    dashboard/
      page.tsx
    verifications/
      new/
        page.tsx
  (agent)/
    layout.tsx          ← Agent portal layout (auth guard + approval guard)
    onboarding/
      page.tsx
    dashboard/
      page.tsx
  (admin)/
    layout.tsx          ← Admin portal layout (auth guard + admin role guard)
    dashboard/
      page.tsx
```

### 13.2 Auth Guard (Middleware)

Implement route protection in `middleware.ts` using Next.js middleware:

- Read auth token from httpOnly cookie.
- Validate token (or call a lightweight token-check endpoint).
- If unauthenticated → redirect to `/auth/login?redirect=[current-path]`.
- If authenticated but wrong role → redirect to correct portal.
- Preserve the `intent` query parameter through redirects.

### 13.3 OAuth Callback Page

The `/auth/oauth/callback` page:

1. Reads `code` and `state` from URL query params.
2. Sends to backend for verification.
3. Backend returns user data + token.
4. Sets auth cookie (via Set-Cookie response header from backend, or client-side for non-httpOnly scenarios).
5. Redirects using the post-auth redirect logic (Section 8).

### 13.4 State Management

- Auth state: React Context + `useReducer` (or Zustand/Jotai for larger teams).
- Wizard state: Local component state + backend draft sync on each step.
- Do not store sensitive tokens in component state or localStorage.

### 13.5 Server Components vs Client Components

| Component | Type | Reason |
|---|---|---|
| Auth layout | Server | Static shell, no interactivity |
| Login form | Client | Form interactions, validation |
| Signup form | Client | Real-time validation, OTP |
| OTP Modal | Client | Timer, dynamic state |
| OAuth callback | Client | Query param reading, redirect |
| Agent onboarding wizard | Client | Multi-step state, file uploads |
| Approval status | Server | Mostly static, fetch-on-load |

### 13.6 Performance Considerations

- Auth pages must load in < 1.5s LCP. Forms are lightweight — no heavy libraries on auth routes.
- Phone input library (libphonenumber-js): lazy-load on phone field focus.
- File upload component: lazy-loaded. Not included in auth bundle.
- OAuth provider scripts: not loaded on auth pages (only load on demand when OAuth button clicked).

---

## 14. API Contract (Auth Endpoints)

These are the frontend-consumed endpoints. Backend owns implementation.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/signup` | Create account (email + password) |
| POST | `/api/auth/login` | Login (email + password) |
| POST | `/api/auth/logout` | Logout current session |
| POST | `/api/auth/logout-all` | Logout all sessions |
| GET | `/api/auth/oauth/:provider/init` | Get OAuth redirect URL |
| POST | `/api/auth/oauth/:provider/verify` | Verify OAuth callback code |
| POST | `/api/auth/otp/email/send` | Send email OTP |
| POST | `/api/auth/otp/email/verify` | Verify email OTP |
| POST | `/api/auth/otp/phone/send` | Send phone OTP |
| POST | `/api/auth/otp/phone/verify` | Verify phone OTP |
| POST | `/api/auth/forgot-password` | Request password reset email |
| POST | `/api/auth/reset-password` | Submit new password (with token) |
| POST | `/api/auth/set-password` | Set password for OAuth-only account |
| GET | `/api/auth/me` | Get current user (roles, personas, trust status, profile) |
| PATCH | `/api/auth/me` | Update profile (country, timezone, currency, etc.) |
| POST | `/api/auth/oauth/link` | Link OAuth account to existing account |
| DELETE | `/api/auth/oauth/unlink/:provider` | Unlink OAuth account |
| GET | `/api/auth/devices` | Get connected devices |
| DELETE | `/api/auth/devices/:id` | Revoke a device session |
| DELETE | `/api/auth/devices` | Revoke all devices (except current) |
| GET | `/api/consent/pending` | Get consent documents pending acceptance for current user |
| POST | `/api/consent/accept` | Record user acceptance of a consent version |
| POST | `/api/agent/onboarding` | Submit agent application |
| GET | `/api/agent/onboarding/status` | Get agent approval status |
| POST | `/api/admin/invite` | Issue admin invite |
| POST | `/api/admin/invite/accept` | Accept admin invite (with token) |

---

## 15. Open Questions

The following decisions require input from the product owner, engineering lead, or legal team before implementation begins:

| # | Question | Impact | Owner |
|---|---|---|---|
| 1 | Which OAuth providers are in scope for Phase 1? (Google confirmed. Apple? Facebook?) | Auth UI, backend | Product |
| 2 | Which SMS provider will be used for phone OTP? (Termii, Twilio, etc.) | Backend, delivery reliability | Engineering |
| 3 | Will WhatsApp OTP delivery be included in Phase 1 or Phase 2? | UX for Nigerian users | Product |
| 4 | What is the BVN verification provider? (e.g., Mono, Dojah, Okra) | Agent KYC reliability | Engineering |
| 5 | What is the selfie matching technology? (Third-party API or in-house?) | Agent KYC step | Engineering |
| 6 | Should agents be able to apply as multiple types simultaneously? (Currently: yes, per spec.) | Onboarding UX | Product |
| 7 | What is the admin review SLA for agent applications? (Spec mentions 2–5 days — is this contractual?) | Email copy, agent expectations | Operations |
| 8 | Should agents who are also customers be redirected to the agent portal by default? (Currently: yes, per spec. Confirm priority.) | Redirect logic | Product |
| 9 | Is there a mobile app (iOS/Android) in scope alongside the web app? | Auth flows (deep links, mobile OAuth) | Product |
| 10 | What data is stored from OAuth profiles? (Name, avatar, email only?) | Privacy policy, NDPR compliance | Legal |
| 11 | Will agent KYC documents be reviewed manually by the Veriprops team, or via automated ID verification API? | Admin workflow, approval time | Operations |
| 12 | Who manages the consent document versioning? (Legal team publishes new versions, ops team triggers re-consent prompts?) | Consent lifecycle | Legal / Ops |
| 13 | What is the exact content of the Verification Disclaimer shown before each payment? Needs legal sign-off before UI is built. | Liability UX | Legal |
| 14 | Should the trust status (trusted/untrusted) be visible to other users (e.g., admins, agents on a job) or remain internal? | UI surface area | Product |
| 15 | What is the country/timezone source dataset? (e.g., IANA timezone list, country-timezone mapping library) | Signup UX correctness | Engineering |

---

*Document prepared for Veriprops product development.*  
*All specifications are subject to revision based on technical feasibility and business requirements.*  
*Last updated: April 2026 — v1.1*