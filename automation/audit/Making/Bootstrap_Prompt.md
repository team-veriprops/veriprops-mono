
You are an elite Principal Engineer responsible for transforming this codebase into a fully deterministic, automation-ready system for autonomous QA using Playwright and Claude Code.

This is NOT feature development.

This is SYSTEM TESTABILITY ENGINEERING.

---

# CONTEXT

Architecture:
- Backend: FastAPI (JWT cookie auth + CSRF double submit)
- Frontend: NextJS 16 App Router (reverse proxy to FastAPI)
- OAuth: popup + postMessage flow
- Email: Mailpit in test/local environments
- Phone OTP: deterministic override in test mode
- Database: PostgreSQL with Alembic migrations

Goal:
Enable fully autonomous end-to-end testing using Playwright and Claude Code.

---

# PHASE 1 — BACKEND TEST DETERMINISM

## 1. SYSTEM RESET CONTRACT (MANDATORY)

Create or refactor:

POST /dev/reset

Must:
- drop or truncate all database state
- re-run Alembic migrations
- reset Redis/cache/session storage
- reset OTP storage
- reset OAuth state storage

Constraints:
- MUST be idempotent
- MUST be safe to run repeatedly
- MUST be disabled in production via strict ENV guard (ENV=local/test only)

---

## 2. SYSTEM SEED CONTRACT (MANDATORY)

Create or refactor:

POST /dev/seed

Must seed deterministic data:

- fixed test users (no randomness)
- email/password login user
- OAuth-linked test users
- phone-enabled test user
- admin user

Constraints:
- no time-based IDs
- no UUID randomness for core test entities
- must be identical across runs

---

## 3. EMAIL TESTING VIA MAILPIT

Integrate Mailpit for test/local environments:

- all outgoing emails in test/local must route to Mailpit
- verification emails must be accessible for automated retrieval
- email verification links must be usable by Playwright

Must NOT affect production email provider.

---

## 4. DETERMINISTIC PHONE OTP SYSTEM

Implement:

Config:
- PHONE_OTP_MODE=test
- PHONE_TEST_OTP=123456

Behavior:
- In test mode, OTP generation is deterministic
- In production mode, OTP must remain secure and random

HARD SAFETY RULE:
- deterministic OTP MUST NEVER be enabled in production

---

## 5. ENVIRONMENT SAFETY GUARDS

Ensure:
- /dev/* endpoints are disabled in production
- OTP override disabled in production
- Mailpit only active in test/local
- reset/seed endpoints cannot execute outside test environment

---

# PHASE 2 — FRONTEND AUTOMATION STABILITY (NEXTJS)

## 6. STABLE SELECTOR SYSTEM (MANDATORY)

In NextJS frontend:

Add stable automation attributes:

- data-testid for all critical elements

Required coverage:
- signup form fields
- login form fields
- OTP input fields (email + phone)
- OAuth buttons
- submit buttons
- navigation elements
- logout button

RULE:
Playwright must NOT rely on CSS classes or text content for critical flows.

---

## 7. AUTH STATE DETERMINISM

Ensure frontend auth state is stable:

- React Query cache invalidation on login/logout must be correct
- Zustand state must not drift from backend session state
- refresh must reconstruct auth state from cookies correctly
- no ghost-auth UI states

Fix:
- stale user session after logout
- inconsistent protected route rendering

---

## 8. OAUTH POPUP STABILITY

Ensure OAuth flow is deterministic:

- postMessage listener initialized BEFORE popup opens
- window.opener must be validated
- add explicit signal:

  window.__oauth_complete__ = true

Playwright must be able to reliably detect completion.

---

## 9. ROUTING + HYDRATION STABILITY

Ensure NextJS App Router behaves deterministically:

- no auth flicker during route transitions
- loading states are stable and testable
- no UI rendering before auth resolution
- prevent hydration mismatches in auth-critical flows

---

## 10. FORM STABILITY (React Hook Form + Zod)

Ensure:
- all forms have deterministic validation behavior
- submit buttons disabled during submission
- duplicate submission is impossible
- error states are stable and consistent

---

## 11. REACT QUERY STABILITY

Ensure TanStack Query behavior is deterministic:

- auth-related cache is invalidated correctly
- no stale user data after login/logout
- no retry loops causing flaky tests
- test mode disables non-deterministic retries

---

## 12. TEST OBSERVABILITY HOOKS

Expose ONLY in test mode:

- window.__test_mode__ = true
- window.__app_ready__ = true after hydration
- window.__auth_snapshot__ (non-sensitive)

These are strictly for automation only.

---

## 13. REMOVE FLAKINESS SOURCES

Eliminate:
- unstable keys in lists
- uncontrolled suspense boundaries in auth flows
- race conditions in route transitions
- UI rendering before state resolution

---

# PHASE 3 — GOVERNANCE LAYER (MANDATORY)

You MUST create and update the following files:

---

## 14. ROOT CLAUDE.md (REQUIRED)

Create or update:

/CLAUDE.md

Must include:
- system architecture overview
- test determinism rules
- reset/seed contract
- Mailpit + OTP rules
- frontend stability requirements
- Playwright automation constraints
- "no external dependency assumption" rule for tests

---

## 15. BACKEND CLAUDE.md (REQUIRED)

Create or update:

/backend/CLAUDE.md

Must include:
- FastAPI auth architecture
- reset/seed endpoints contract
- OTP rules
- Redis/session handling rules
- OAuth flow specification
- production safety constraints

---

## 16. FRONTEND CLAUDE.md (REQUIRED)

Create or update:

/frontend/CLAUDE.md

Must include:
- NextJS App Router constraints
- auth state handling rules
- data-testid requirement policy
- OAuth popup rules
- React Query + Zustand state rules
- Playwright stability requirements

---

# STRICT RULES

- DO NOT implement Playwright yet
- DO NOT implement autonomous QA system yet
- DO NOT introduce unrelated refactors
- ONLY build determinism + testability foundation
- ALL changes must improve automation reliability

---

# SUCCESS CRITERIA

System is ready for Phase 3 when:

Backend:
- reset/seed fully deterministic
- OTP is deterministic in test mode
- Mailpit is integrated
- system can be restarted identically

Frontend:
- stable selectors everywhere
- no auth flicker
- OAuth is observable and deterministic
- no UI race conditions in auth flows

Repo:
- CLAUDE.md files exist and enforce rules across backend + frontend + root
