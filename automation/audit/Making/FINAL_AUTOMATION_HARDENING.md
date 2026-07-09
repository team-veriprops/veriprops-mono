# Final Automation Hardening

## Files Changed

| File | Change |
|------|--------|
| `frontend/src/lib/automation.ts` | **Created** — single source of truth for `isAutomationEnvironment()` |
| `frontend/src/lib/config/public.ts` | Added `environment: NEXT_PUBLIC_ENVIRONMENT` to `publicConfig` |
| `frontend/src/providers/client-wrapper.tsx` | Replaced `NODE_ENV !== "production"` with `isAutomationEnvironment()` |
| `frontend/src/components/website/auth/libs/useAuthQueries.ts` | Replaced `NODE_ENV !== "production"` with `isAutomationEnvironment()` |
| `frontend/src/components/website/auth/libs/auth/oauthPopup.ts` | Replaced `NODE_ENV` guards; full `null/"success"/"failed"` lifecycle + `CustomEvent` dispatch |
| `CLAUDE.md` | Updated window hooks rule; added OAuth lifecycle contract |
| `frontend/CLAUDE.md` | Updated window hooks contract; documented `isAutomationEnvironment()` requirement |

## Environment Contract

```
NEXT_PUBLIC_ENVIRONMENT=local        → isAutomationEnvironment() = true
NEXT_PUBLIC_ENVIRONMENT=development  → isAutomationEnvironment() = true
NEXT_PUBLIC_ENVIRONMENT=test         → isAutomationEnvironment() = true
NEXT_PUBLIC_ENVIRONMENT=staging      → isAutomationEnvironment() = false
NEXT_PUBLIC_ENVIRONMENT=production   → isAutomationEnvironment() = false
NEXT_PUBLIC_ENVIRONMENT=(unset)      → isAutomationEnvironment() = false
```

`NODE_ENV` is no longer used for any automation hook guard.

## OAuth Completion Lifecycle Contract

```
startOauthPopup() called
  → window.__oauth_complete__ = null          (pending)

Provider confirmed success:
  → window.__oauth_complete__ = "success"
  → CustomEvent("__oauth_complete__", { detail: { status: "success" } })

Any terminal failure (provider error, timeout, popup blocked,
navigation failure, user cancel):
  → window.__oauth_complete__ = "failed"
  → CustomEvent("__oauth_complete__", { detail: { status: "failed" } })
```

Terminal paths that emit `"failed"`:
- `onMessage` with `data.success === false`
- `cancel()` (user closed popup or explicit cancel)
- Timeout after `timeoutMs`
- Popup blocked (both `.then()` and `.catch()` branches)
- `authorizationUrl` missing from API response
- `popup.location.href` navigation throws
- `authService.startOauth` network/API error

## Playwright Observability

```typescript
// Wait for OAuth to reach a terminal state
await page.waitForFunction(() => window.__oauth_complete__ !== null);
const status = await page.evaluate(() => window.__oauth_complete__);
// status is "success" | "failed"

// Or listen for the event
page.on('console', ...); // not needed — use waitForEvent
await page.evaluate(() => {
  return new Promise((resolve) => {
    window.addEventListener('__oauth_complete__', (e) => resolve(e.detail.status), { once: true });
  });
});
```
