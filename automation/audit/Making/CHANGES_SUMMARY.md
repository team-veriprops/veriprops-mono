# Automation Readiness Changes Summary

## What Changed and Why

This batch of changes establishes a deterministic, automation-stable foundation for autonomous QA using Playwright + Claude Code. No test framework was added — this is system testability engineering only.

---

## Backend Changes

### 1. OTP determinism contract (`backend/main/appodus_utils/`)

**Files:** `config/settings.py`, `common/commons.py`

**What:** Added `OTP_MODE: str` setting (`deterministic` | `random`) with a startup `@model_validator` that hard-fails if:
- `ENVIRONMENT=test` and `OTP_MODE != "deterministic"`
- `ENVIRONMENT=prod` and `OTP_MODE != "random"`

`Utils.get_otp_code()` now reads `OTP_MODE` env var directly instead of doing brittle string comparisons against `ENVIRONMENT`.

**Why:** The old code compared `os.environ["ENVIRONMENT"]` to `"Environment.LOCAL"` — a string representation of an enum — which silently broke whenever the env var serialization changed. The new contract is explicit, enforced at startup, and independent of environment naming.

### 2. Dev reset/seed endpoints (`backend/main/app/domain/dev/`)

**Files:** `dev/__init__.py`, `dev/controller.py`, `domain/__init__.py`

**What:** New domain with two endpoints:
- `POST /dev/reset` — drops + recreates all SQLAlchemy tables; clears OTP/OAuth KV keys via `RedisUtils.delete_by_prefix`. Returns `{"ok": true}`.
- `POST /dev/seed` — inserts 4 deterministic test users with stable UUIDs and emails. Idempotent. Returns created emails + `test_otp`.

Both are gated by `_require_non_prod()` (404 in production) AND the router is only mounted when `ENVIRONMENT != prod`.

**Why:** Automated tests need a clean, known-state database before each run. Without a reset endpoint, test suites must manage DB state externally (fragile) or rely on test ordering (non-deterministic).

### 3. RedisUtils.delete_by_prefix

**Files:** `appodus_utils/db/redis_utils.py`, `domain/key_value/service.py`, `domain/key_value/repo.py`

**What:** Added `delete_by_prefix(prefix: str) -> int` to all three layers:
- Redis path: cursor-based `SCAN` + batched `DELETE` (non-blocking)
- KV fallback: SQL `DELETE WHERE key LIKE '{prefix}%'`

**Why:** The `/dev/reset` endpoint must flush OTP and OAuth state that lives in Redis or the DB-backed KV store. Previously there was no batch-delete API on the prefix boundary.

### 4. Mailpit SMTP provider (`backend/main/appodus_utils/integrations/messaging/`)

**Files:** `providers/email/smtp.py`, `providers/__init__.py`, `router.py`, `models.py`

**What:**
- Added `SMTP = "SMTP"` to `MessageProviderName` enum.
- Added `SmtpEmailProvider(IMessageProvider)` that sends email via `smtplib.SMTP` in `run_in_executor` (non-blocking). Hard-fails in production/staging.
- Added `"email"` routing rule in `MessageRouter._load_routing_rules()`: when `ENVIRONMENT not in {PRODUCTION, STAGING}`, route to SMTP; fallback to Mailjet/SendGrid.
- Added SMTP connection settings to `AppodusBaseSettings` (defaults: `localhost:1025`, no auth).

**Why:** Without email capture, automated tests that trigger emails (OTP, welcome, verification) cannot verify delivery without external mail servers. Mailpit captures all SMTP email in a local UI, making email assertions possible in automation.

---

## Frontend Changes

### 5. data-testid selectors on auth forms

**Files:** `LoginContainer.tsx`, `AccountBasicsStep.tsx`, `SignupContainer.tsx`, `VerifyEmailPhoneStep.tsx`, `Stepper.tsx`, `SocialAuthButtons.tsx`

**What:** Added stable `data-testid` attributes to all interactive auth elements (forms, inputs, buttons, OAuth providers).

**Why:** Playwright selectors must be stable across refactors. CSS classes and text content change; `data-testid` attributes are explicit automation contracts.

### 6. Window automation hooks

**Files:** `providers/client-wrapper.tsx`, `auth/libs/useAuthQueries.ts`, `auth/libs/auth/oauthPopup.ts`

**What:**
- `window.__app_ready__ = true` — set after React tree mounts in `ClientWrapperProvider`.
- `window.__auth_snapshot__ = { isAuthenticated, userId, personas }` — updated after every `useCurrentSession` query in non-production.
- `window.__oauth_complete__ = true` — set when OAuth popup posts a success message; reset to `false` at popup start.

**Why:** Playwright needs deterministic wait conditions. `waitForFunction(() => window.__app_ready__)` is more reliable than `waitForLoadState('networkidle')` in an SPA.

### 7. Hydration flicker fix

**File:** `providers/client-wrapper.tsx`

**What:** Removed `if (!mounted) return null` guard that caused a blank render on first paint.

**Why:** The null-return caused Playwright's `waitForLoadState` to see a momentarily empty page, making selectors temporarily unavailable and introducing race conditions in test scripts.
