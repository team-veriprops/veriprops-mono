# QA Hardening Fixes Summary

Phase 3 determinism pass. All changes close non-determinism gaps that would cause Playwright tests to be flaky or non-reproducible. No new features were added.

---

## Fix 1 — Email Routing: Remove Last-Resort Fallback in Test Mode

**Problem:** `MessageRouter._handle_fallback()` had a "last resort" block (lines 248-255) that tried ALL remaining registered providers after exhausting `fallback_order`. Even with `"fallback_order": []`, a failed `SmtpEmailProvider` in test/dev could silently fall back to Mailjet or Sendgrid — real external providers.

**Change:**
- Added `"exclusive": True` to the non-prod email routing rule
- Added exclusive guard in `_handle_fallback()` that raises `IntegrationFatalException` immediately (before the last-resort block) when the failed provider's rule has `"exclusive": True`

**Files:**
- `backend/main/appodus_utils/integrations/messaging/router.py`

**Result:** SMTP failure in test/dev surfaces immediately as a hard error. No silent fallback to real email providers.

---

## Fix 2 — SMS Routing: MockSmsProvider + Test-Environment Isolation

**Problem:** In test/dev environments, SMS routing hit real providers (Termii, Twilio). No deterministic suppression existed.

**Changes:**
1. Added `MOCK_SMS = "MOCK_SMS"` to `MessageProviderName` enum
2. Created `MockSmsProvider` — logs the suppressed message, returns `SENT`, hard-fails in production/staging
3. Added SMS test routing rule (first in rules list, matches before Nigerian-number and high-priority rules):
   - condition: `ENVIRONMENT in {test, dev, local}`
   - providers: `[MOCK_SMS]`
   - `fallback_order: []`, `exclusive: True`
4. Migrated SMS provider names in existing rules from string literals to `MessageProviderName` enum values

**Files:**
- `backend/main/appodus_utils/integrations/messaging/models.py` — added `MOCK_SMS`
- `backend/main/appodus_utils/integrations/messaging/providers/sms/mock.py` — new file
- `backend/main/appodus_utils/integrations/messaging/providers/__init__.py` — import added
- `backend/main/appodus_utils/integrations/messaging/router.py` — routing rule added

**Result:** All SMS in test/dev/local is intercepted by `MockSmsProvider`. No real SMS is ever sent. Log line: `[MockSmsProvider] SMS suppressed in {env}. To: {number} | Text: ...`

---

## Fix 3 — OAuth Completion: Boolean → `null | true` Model

**Problem:** `window.__oauth_complete__` was reset to `false` at the start of each OAuth attempt. `false` is ambiguous — automation cannot distinguish "not yet started" from "started but incomplete". Stale `false` between retries could mislead polling scripts.

**Change:** Reset value changed from `false` to `null`.
- `null` = not started / reset between attempts
- `true` = completed successfully

**File:** `frontend/src/components/website/auth/libs/auth/oauthPopup.ts`

**Playwright impact:** None. `=== true` check excludes both `null` and `false`:
```typescript
await page.waitForFunction(() => window.__oauth_complete__ === true, { timeout: 30_000 });
```

---

## Fix 4 — `window.__TEST_MODE__` Flag

**Problem:** No canonical, stable signal for automation to confirm it is running in test mode. Automation scripts had to infer state from other signals.

**Change:** Set `window.__TEST_MODE__ = true` in `ClientWrapperProvider.useEffect` alongside `window.__app_ready__`, guarded by `NODE_ENV !== "production"`.

**File:** `frontend/src/providers/client-wrapper.tsx`

**Usage:**
```typescript
await page.waitForFunction(() => window.__TEST_MODE__ === true);
```

---

## Fix 5 — OTP State Consistency (Verified No Change Needed)

The startup validator `_enforce_otp_mode_policy()` in `AppodusBaseSettings` already enforces:
- `ENVIRONMENT=test + OTP_MODE=random` → startup fails
- `ENVIRONMENT=prod + OTP_MODE=deterministic` → startup fails

No code change was required. The OTP contract is correct as-is and documented in `OTP_CONTRACT_REPORT.md`.

---

## Files Changed

| File | Change |
|---|---|
| `backend/main/appodus_utils/integrations/messaging/models.py` | Added `MOCK_SMS` enum value |
| `backend/main/appodus_utils/integrations/messaging/providers/sms/mock.py` | New file — `MockSmsProvider` |
| `backend/main/appodus_utils/integrations/messaging/providers/__init__.py` | Added `MockSmsProvider` import |
| `backend/main/appodus_utils/integrations/messaging/router.py` | Exclusive guard + SMS mock rule + email rule hardened |
| `frontend/src/components/website/auth/libs/auth/oauthPopup.ts` | `false` → `null` for `__oauth_complete__` |
| `frontend/src/providers/client-wrapper.tsx` | Added `__TEST_MODE__` alongside `__app_ready__` |
