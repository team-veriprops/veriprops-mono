# OAuth Completion Signaling — Fix Report

## Previous Model (boolean)

```typescript
window.__oauth_complete__ = false;   // reset at start
// ...
window.__oauth_complete__ = true;    // set on success
```

**Problems:**
- `false` is ambiguous: it means both "not started" and "started but not yet complete"
- A stale `false` from a previous failed attempt looks identical to a fresh reset
- Automation polling `=== false` to detect reset would be unreliable after page navigation

---

## New Model (`null | true`)

| Value | Meaning |
|---|---|
| `undefined` | Page just loaded, `startOauthPopup` has not been called |
| `null` | `startOauthPopup` was called; OAuth flow is in progress |
| `true` | OAuth popup received a success `postMessage`; flow complete |

`false` is never set. The flag is never cleared back to `null` after `true` — a successful flow stays `true` until the page navigates.

---

## Lifecycle Guarantees

1. **Before any OAuth call:** `window.__oauth_complete__` is `undefined` (not set).
2. **Start of `startOauthPopup`:** set to `null` immediately (synchronous, before any async work).
3. **Popup message received with `success: true`:** set to `true` before `onSuccess()` is called.
4. **Popup closed without success (cancel/timeout/error):** flag is not changed — stays `null` or `undefined`.
5. **Subsequent `startOauthPopup` call:** reset to `null` again.

---

## Playwright Usage

```typescript
// Wait for OAuth popup to complete
await page.waitForFunction(() => window.__oauth_complete__ === true, { timeout: 30_000 });

// Verify flow is in progress (optional — usually not needed)
await page.waitForFunction(() => window.__oauth_complete__ === null);

// Full OAuth test pattern
await page.click('[data-testid="oauth-google"]');
// null means flow started
await page.waitForFunction(() => window.__oauth_complete__ !== undefined);
// true means flow completed
await page.waitForFunction(() => window.__oauth_complete__ === true, { timeout: 30_000 });
```

---

## Implementation

**File:** `frontend/src/components/website/auth/libs/auth/oauthPopup.ts`

```typescript
// Reset (at start of startOauthPopup):
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
    (window as any).__oauth_complete__ = null;
}

// Complete (in onMessage handler, when data.success is true):
if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") {
    (window as any).__oauth_complete__ = true;
}
```

The flag is only set in `NODE_ENV !== "production"` builds. It is absent in production.

---

## Safety

- No race condition: `null` is set synchronously before the popup opens. The popup must load and complete OAuth before posting the `postMessage`. By the time the popup can post, the message listener is already registered (line 111).
- Safe for repeated attempts: each `startOauthPopup` call resets to `null`.
- Safe across navigation: the next page load starts with `window.__oauth_complete__ === undefined`.
