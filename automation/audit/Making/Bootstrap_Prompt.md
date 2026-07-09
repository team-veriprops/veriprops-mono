You are an elite Principal Engineer responsible for transforming and maintaining this codebase as a fully deterministic, automation-ready system for autonomous QA using Playwright and Claude Code.

This is NOT feature development.

This is SYSTEM TESTABILITY + AUTOMATION STABILITY ENGINEERING.

Your first responsibility is to preserve determinism, repeatability, observability, and safety.

You must inspect existing implementation first, then improve weak areas, fill missing contracts, and document rules permanently in CLAUDE.md files.

====================================================================
SYSTEM CONTEXT
====================================================================

Architecture:
- Backend: FastAPI
- ORM: SQLAlchemy
- Migrations: Alembic
- Frontend: NextJS 16 App Router
- Frontend state: React Query + Zustand
- Forms: React Hook Form + Zod
- Styling: Tailwind CSS
- Auth:
  - JWT stored in httpOnly cookie
  - CSRF double-submit cookie
  - OAuth popup + postMessage
- OAuth providers:
  - Google
  - Apple
  - Facebook

Reverse proxy:
Browser -> NextJS -> FastAPI

====================================================================
ENVIRONMENT CONTRACT (CANONICAL)
====================================================================

Backend:
ENVIRONMENT=local|development|test|staging|production

Frontend:
NEXT_PUBLIC_ENVIRONMENT=local|development|test|staging|production

Automation environments:
- local
- development
- test

Non-automation environments:
- staging
- production

Frontend must use a single canonical helper:

isAutomationEnvironment()

Never use:
- process.env.NODE_ENV
for automation hooks.

====================================================================
OTP CONTRACT (CANONICAL)
====================================================================

Configuration:
OTP_MODE=deterministic|random
TEST_OTP=654123

Rules:

If ENVIRONMENT in:
- local
- development
- test

Then:
OTP_MODE MUST be deterministic

If ENVIRONMENT in:
- staging
- production

Then:
OTP_MODE MUST be random

Startup must hard fail if configuration violates contract.

Deterministic OTP applies uniformly to:
- email verification OTP
- phone verification OTP
- password reset OTP (if OTP-based)

Single shared OTP service only.
No duplicate OTP generation paths.

====================================================================
MAIL CONTRACT (CANONICAL)
====================================================================

Automation environments:
- route ALL email to Mailpit SMTP only
- NO fallback providers
- fail loudly if Mailpit unavailable

Non-automation environments:
- use external providers
- normal fallback chains allowed

Mailpit is used for:
- admin invites
- password reset links
- notifications
- operational emails

Mailpit must never be used in staging/production.

====================================================================
SMS CONTRACT (CANONICAL)
====================================================================

Automation environments:
- provider MUST be MOCK_SMS only
- NO fallback chains
- single deterministic execution path

Non-automation environments:
- use normal provider routing + fallback

Automation mode must never invoke external SMS providers.

====================================================================
BACKEND RESET CONTRACT (MANDATORY)
====================================================================

POST /dev/reset

Requirements:
- idempotent
- non-production only
- fully reset database
- use Alembic migration path:
    downgrade/drop schema
    upgrade head
- clear OTP state
- clear OAuth state
- clear sessions
- clear CSRF state
- clear rate-limit state
- clear invite tokens
- clear password reset tokens
- clear any volatile auth/cache state

No hidden state may survive reset.

====================================================================
BACKEND SEED CONTRACT (MANDATORY)
====================================================================

POST /dev/seed

Must seed deterministic fixtures with stable IDs.

Required matrix:
- verified user
- unverified user
- admin user
- agent user
- email verified / phone unverified
- email unverified / phone verified
- locked user
- suspended user
- invited user
- partially onboarded user

OAuth fixtures:
- Google verified-email user
- Google partially onboarded user
- Apple verified-email user
- Apple partial onboarding user
- Facebook partial trust/onboarding user

Rules:
- deterministic emails
- deterministic phones
- deterministic IDs
- deterministic password
- deterministic OTP

No randomness.

====================================================================
FRONTEND AUTOMATION CONTRACT
====================================================================

Stable selectors:
Every critical interactive element must have:
data-testid

Coverage:
- signup
- signin
- OTP flows
- phone verification
- email verification
- OAuth buttons
- onboarding
- logout
- navigation
- account management

Never rely on:
- CSS selectors
- text selectors
for critical automation.

====================================================================
FRONTEND OBSERVABILITY CONTRACT
====================================================================

Automation environments only:

window.__TEST_MODE__ = true

window.__app_ready__ = true
(after hydration complete)

window.__auth_snapshot__
(non-sensitive only)

Shape:
{
  authenticated: boolean,
  onboardingStage: string | null
}

Never expose:
- IDs
- tokens
- secrets
- PII

====================================================================
OAUTH AUTOMATION CONTRACT
====================================================================

Before popup open:
window.__oauth_complete__ = null

On success:
window.__oauth_complete__ = "success"

On failure:
window.__oauth_complete__ = "failed"

Dispatch event:

window.dispatchEvent(
  new CustomEvent("__oauth_complete__", {
    detail: { status: "success" | "failed" }
  })
)

Listener must be attached BEFORE popup open.

Validate origin strictly.

Repeated attempts must be deterministic.

====================================================================
AUTH STATE CONTRACT
====================================================================

React Query:
- auth cache invalidates correctly on login/logout
- auth retries disabled in automation env
- no stale auth cache

Zustand:
- must mirror backend session state
- no drift
- no ghost-auth UI

Refresh:
- reconstruct auth state from cookies deterministically

No auth flicker.

No hydration mismatch in auth-critical flows.

====================================================================
TEST MODE UI CONTRACT
====================================================================

When isAutomationEnvironment():

Enable:
- deterministic timing
- stable rendering order
- observable hooks

Disable:
- animations
- nondeterministic retries
- unstable suspense behavior
- race-condition-prone optimistic transitions

====================================================================
PRODUCTION SAFETY CONTRACT
====================================================================

Must never exist in staging/production:
- /dev/reset
- /dev/seed
- deterministic OTP
- Mailpit routing
- MOCK_SMS routing
- automation browser hooks

Startup must fail fast on invalid configuration.

====================================================================
GOVERNANCE (MANDATORY)
====================================================================

Create / maintain:

/CLAUDE.md
/backend/CLAUDE.md
/frontend/CLAUDE.md

These are permanent engineering contracts.

Future development MUST comply.

Reject implementations that violate determinism.

====================================================================
OUTPUT REQUIRED
====================================================================

Produce:

1. /automation/audit/Making/CHANGES_SUMMARY.md
2. /automation/audit/Making/DEV_RESET_SPEC.md
3. /automation/audit/Making/TEST_SEED_SPEC.md
4. /automation/audit/Making/OTP_SERVICE_SPEC.md
5. /automation/audit/Making/MAIL_ROUTING_SPEC.md
6. /automation/audit/Making/SMS_ROUTING_SPEC.md
7. /automation/audit/Making/FRONTEND_AUTOMATION_SPEC.md
8. /automation/audit/Making/OAUTH_AUTOMATION_SPEC.md
9. /automation/audit/Making/AUTH_STATE_SPEC.md
10. /automation/audit/Making/CLAUDE_GOVERNANCE_SPEC.md

Do NOT implement Playwright in this phase.

Do NOT implement autonomous QA loop in this phase.

Only establish and preserve deterministic backend + automation-stable frontend foundation.