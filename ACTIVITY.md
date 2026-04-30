# Phase 2 — Auth & Onboarding Shell · Activity Log

PRD reference: `PRD.md` § Phase 2.
Detailed spec: `BRAIN PICK PRDS/user-auth-onboarding_prd.md` §§1–5, 8–14 (referenced; we work from PRD master).
Design system: `references/estate_assurance/DESIGN.md` ("Sovereign Curator").

> **Scope note** — backend auth domain does not yet exist in `backend/main/app/domain/`.
> This phase delivers the **frontend shell + mock service layer**. The mock service calls `/api/users/auth/...` paths so the same code wires to a real backend once Phase 0/2 backend lands. Backend implementation tracked separately.

Legend: `[ ]` todo · `[x]` done · `[~]` in progress · `[>]` deferred (out of scope for this pass).

---

## 1. Foundations & shared layer
- [x] 1.1 Create `ACTIVITY.md` plan
- [x] 1.2 Add auth route constants in `src/lib/routes.ts`
- [x] 1.3 Add Phase 2 user/auth domain types in `src/types/models.ts`
- [x] 1.4 Add timezone & country reference data (`src/lib/auth/locale.ts`)
- [x] 1.5 Add versioned consent reference (`src/lib/auth/consent.ts`)
- [x] 1.6 Auth Zustand store (`src/stores/useAuthStore.ts`)
- [x] 1.7 Auth mock service (`src/components/website/auth/libs/auth-service.ts`)
- [x] 1.8 Auth React Query hooks (`src/components/website/auth/libs/useAuthQueries.ts`)

## 2. Shared auth UI primitives
- [x] 2.1 `AuthShell` layout
- [x] 2.2 `AuthFormCard` & `AuthHeading`
- [x] 2.3 `SocialAuthButtons`
- [x] 2.4 `PasswordStrengthMeter`
- [x] 2.5 `ConsentCheckbox`

## 3. Auth gate & intent preservation
- [x] 3.1 `/auth` interstitial preserving `intent`
- [x] 3.2 Post-auth redirect helper

## 4. Signup flow (`/auth/signup`)
- [x] 4.1 Zod `signupSchema`
- [x] 4.2 Step 1: account basics
- [x] 4.3 Step 2: phone + email/phone OTP
- [x] 4.4 Step 3: residence + timezone + currency
- [x] 4.5 Step 4: consent + Create account
- [x] 4.6 Resumable draft (localStorage)
- [x] 4.7 Signup page glue
- [x] 4.8 Signup schema tests

## 5. Login flow (`/auth/login`)
- [x] 5.1 Zod `loginSchema`
- [x] 5.2 Form with show/hide password
- [x] 5.3 Forgot password + Create account links
- [x] 5.4 Rate-limit UX (warn @ 5, lockout @ 7)
- [x] 5.5 OAuth buttons row
- [x] 5.6 Login page + tests

## 6. Forgot / reset password
- [x] 6.1 `/auth/forgot-password`
- [x] 6.2 `/auth/reset-password/[token]`
- [x] 6.3 `/auth/set-password` (OAuth users)

## 7. OAuth (Google) shell
- [x] 7.1 `/auth/oauth/[provider]/callback`
- [x] 7.2 `ProfileCompletionModal`
- [~] 7.3 Email-collision prompt (UI complete; full link flow deferred)

## 8. Security & sessions (account pages)
- [x] 8.1 `/account/security` — activity log
- [x] 8.2 `/account/devices` — connected devices
- [x] 8.3 `/account/linked` — linked accounts

## 9. Tests
- [x] 9.1 Signup schema test
- [x] 9.2 Login schema test
- [x] 9.3 Forgot/reset schema test
- [x] 9.4 Redirect helper test
- [x] 9.5 Consent registry test
- [x] 9.6 Locale data test (+ password-strength + routes tests)

## 10. Wire-up & polish
- [x] 10.1 Update `LandingNav` / `LandingFooter` auth links — existing landing already routes to `/auth?intent=...&tier=...`, no changes needed
- [x] 10.2 Run `pnpm test` — 128 / 128 passing across 10 files
- [x] 10.3 Run `pnpm build` — 15 routes built, type check clean

---

## 11. Backend — `user` / `auth` / `consent` / `session` domains
- [x] 11.1 `domain/user` — User + OAuth identity entities + DTOs + repo + service + validator
- [x] 11.2 `domain/consent` — ConsentDocument + UserConsent entities + service + seed loader
- [x] 11.3 `domain/session` — DeviceSession + SecurityEvent + PasswordResetToken entities + service
- [x] 11.4 `domain/auth` — AuthService, OtpService, OAuth helpers, JWT cookie wiring (libre_fastapi_jwt)
- [x] 11.5 Auth controller — 22 endpoints under `/users/auth/...`
- [x] 11.6 Alembic migration `a1b2c3d4e5f6_phase2_auth.py`
- [x] 11.7 Pytest — 23 unit tests passing (OTP, OAuth, password, signup DTOs)
- [x] 11.8 Seed first Super Admin via `DataSeeder._seed_super_admin` (uses `SUPER_ADMIN_PASSWORD` env)

## 12. Real transports & external integrations
- [x] 12.1 Email OTP via SendGrid (`OtpDeliveryService._send_email`) with dev-mode log fallback
- [x] 12.2 SMS OTP via Termii (`OtpDeliveryService._send_sms`) with dev-mode log fallback
- [x] 12.3 Real Google OAuth — `/users/auth/oauth/google/{start,callback}` with KV-stored state

## 13. Email-collision OAuth account merging
- [x] 13.1 Backend collision detection at OAuth callback (`AuthService.find_or_create_oauth_user` raises `UserAlreadyExistsException`)
- [x] 13.2 Backend "link OAuth to existing account" endpoint — `POST /users/auth/oauth/links/link`
- [x] 13.3 Frontend wires the collision flow: callback → login w/ `link=<provider>` → auto-call `linkPendingOauth` after success

## 14. Versioned consent re-acceptance modal
- [x] 14.1 Backend `GET /users/auth/consents/missing` (returns missing required docs)
- [x] 14.2 Frontend `ConsentReacceptanceModal` — non-dismissible until all docs accepted
- [x] 14.3 Mounted in `ClientWrapperProvider` — auto-suppressed without a session

## 15. Device fingerprint
- [x] 15.1 Frontend `lib/auth/fingerprint.ts` — UA/platform/canvas/timezone hash, cached in localStorage
- [x] 15.2 Login + signup payloads carry `deviceFingerprint`; backend persists on every `SecurityEvent` + `DeviceSession`
