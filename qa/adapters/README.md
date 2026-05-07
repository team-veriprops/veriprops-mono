# adapters/

Service integrations consumed by the runtime. Adapters are the only layer that talks to external services (browser, backend, email).

## Files

| File | Role |
|---|---|
| `logger.ts` | Config loader, structured Logger, event bus progress subscriber. |
| `backend.ts` | HTTP client for backend dev/test endpoints (`/qa/reset`, `/qa/seed`, etc). Includes `snapshot()` (merged from deleted `storage.ts`). |
| `mailpit.ts` | Mailpit email testing client. OTP extraction with per-domain `otpPattern` override. |
| `playwright.ts` | Playwright browser factory and context helpers. `waitForAppReady` with three-tier fallback. Cookie extract/inject for hybrid sessions. |

## Config loading

`loadConfig()` in `logger.ts` is the authoritative config loader. It reads environment variables first, then falls back to `qa/.env`. Call it once at CLI startup — the result is cached.

## OTP extraction

`MailpitAdapter.extractOTP(messageId, otpPattern?)` accepts an optional regex pattern string from `domain.contract.otpPattern`. If the pattern is invalid or omitted, it falls back to the default `\b\d{4,8}\b`. The pattern must contain one capture group for the OTP digits.

## App readiness

`waitForAppReady(page, config, domainSelector?)` in `playwright.ts` tries three strategies in order: `window.__app_ready`, a CSS selector, and `networkidle`. Priority: domain contract → QAConfig → `__app_ready` signal.
