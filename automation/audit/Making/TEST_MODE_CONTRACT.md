# Test Mode Contract — `window.__TEST_MODE__`

## Definition

```typescript
window.__TEST_MODE__: true | undefined
```

- `true` — the React tree is mounted and the app is running in a non-production build.
- `undefined` — either not yet mounted, or running in production (never set).

## Set Location

**File:** `frontend/src/providers/client-wrapper.tsx`

```typescript
useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
        (window as any).__app_ready__ = true;
        (window as any).__TEST_MODE__ = true;
    }
}, []);
```

Set once on mount (empty dependency array). Never cleared. Set in the same effect as `window.__app_ready__` so both are always present together in non-production builds.

## Invariants

- Present in: `local`, `dev`, `test`, `staging` builds (`NODE_ENV !== "production"`)
- Absent in: production builds (`NODE_ENV === "production"`)
- Never gated on feature flags
- Never conditionally removed based on other state
- Always set after `window.__app_ready__` (same `useEffect`, same statement sequence)

## Playwright Usage

```typescript
// Wait for test mode to be confirmed
await page.waitForFunction(() => window.__TEST_MODE__ === true);

// Typically not needed separately — __app_ready__ fires at the same time
await page.waitForFunction(() => window.__app_ready__ === true);
```

## Intended Future Use

This flag is a **stable automation contract** for features that need to behave differently in test environments:

- Disable CSS animations (reduces `waitForAnimationEnd` flakiness)
- Suppress retry logic in data-fetching hooks (makes test flow deterministic)
- Enable synthetic event injection (e.g. simulated OTP auto-fill)

These behaviours are not yet implemented. When they are, they MUST be gated on `window.__TEST_MODE__` (not on environment variables, cookies, or other runtime state), so automation scripts have a single stable signal to wait on.

## What Not To Do

- Do not remove `__TEST_MODE__` during refactors.
- Do not gate it behind a feature flag.
- Do not set it to `false` — use `undefined` (absence) instead of `false` to signal non-test mode.
- Do not check `window.__TEST_MODE__ === false` in application code — check `!= true` or `=== undefined`.
