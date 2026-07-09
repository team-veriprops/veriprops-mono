# OAuth Automation Contract

## State Machine

```
                  startOauthPopup() called
                          │
                          ▼
               window.__oauth_complete__ = null
                       (pending)
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
      success          failure         cancel /
    (postMessage)    (any error)      timeout
          │               │               │
          ▼               ▼               ▼
      "success"        "failed"        "failed"
          │               │               │
          └───────────────┴───────────────┘
                          │
                          ▼
          CustomEvent("__oauth_complete__", { detail: { status } })
```

## Terminal States

| State | Value | Meaning |
|-------|-------|---------|
| Pending | `null` | Attempt in progress — do not read yet |
| Success | `"success"` | Provider confirmed; session is being established |
| Failed | `"failed"` | Attempt ended without success |

## Lifecycle Guarantees

1. **Reset is per-attempt.** `null` is set at the top of `startOauthPopup()`, before the popup opens. Every new call to `startOauthPopup()` resets the state regardless of the previous outcome.

2. **Every terminal path emits.** All exit paths from `startOauthPopup()` set a terminal value and dispatch the event:
   - Provider success message → `"success"`
   - Provider failure message → `"failed"`
   - User cancels (closes popup) → `"failed"`
   - Hard timeout (5 min default) → `"failed"`
   - Popup blocked by browser → `"failed"`
   - `authorizationUrl` missing from API → `"failed"`
   - Popup navigation throws → `"failed"`
   - Network/API error on `startOauth` → `"failed"`

3. **Event is always dispatched.** On every terminal transition, `window.dispatchEvent(new CustomEvent("__oauth_complete__", { detail: { status } }))` fires. Playwright can observe via `waitForFunction` or event listener.

4. **Active only in automation environments.** All signals are no-ops when `isAutomationEnvironment()` returns `false` (staging, production).

5. **Safe for repeated attempts.** Calling `startOauthPopup()` again in the same session (retry) resets `__oauth_complete__` to `null` before the new attempt proceeds.

## Playwright Usage Pattern

```typescript
// Trigger OAuth click
await page.click('[data-testid="oauth-google"]');

// Wait for terminal state
await page.waitForFunction(() => (window as any).__oauth_complete__ !== null);

// Read outcome
const status = await page.evaluate(() => (window as any).__oauth_complete__);
expect(status).toBe("success"); // or "failed"
```

## Implementation Location

`frontend/src/components/website/auth/libs/auth/oauthPopup.ts`

The `signalOauthComplete(status)` helper is private to that module. It guards with `isAutomationEnvironment()` internally — callers do not need their own guards.
