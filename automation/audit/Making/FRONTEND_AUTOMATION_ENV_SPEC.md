# Frontend Automation Environment Spec

## NEXT_PUBLIC_ENVIRONMENT

Set in `.env.local` / `.env.test` / CI environment variables. Consumed at build time by Next.js.

| Value | isAutomationEnvironment() | Use case |
|-------|--------------------------|----------|
| `local` | `true` | Local developer machine |
| `development` | `true` | Shared dev server |
| `test` | `true` | CI / Playwright runs |
| `staging` | `false` | Pre-production staging |
| `production` | `false` | Live production |
| (unset) | `false` | Safe default — hooks off |

## isAutomationEnvironment()

**Location:** `frontend/src/lib/automation.ts`
**Import alias:** `@lib/automation`

```typescript
import { isAutomationEnvironment } from "@lib/automation";
```

Returns `true` if and only if `NEXT_PUBLIC_ENVIRONMENT` is one of `local`, `development`, or `test`.

### Contract

- Pure function — no side effects.
- Safe to call in both SSR and browser contexts (`process.env.NEXT_PUBLIC_ENVIRONMENT` is inlined at build time by Next.js).
- Returns `false` by default when `NEXT_PUBLIC_ENVIRONMENT` is unset.

### Usage

```typescript
if (isAutomationEnvironment()) {
  (window as any).__some_hook__ = value;
}
```

### What NOT to use

```typescript
// WRONG — staging deployments may have NODE_ENV=production
if (process.env.NODE_ENV !== "production") { ... }

// WRONG — do not duplicate the env logic inline
if (process.env.NEXT_PUBLIC_ENVIRONMENT === "test") { ... }
```

## Automation hooks governed by this contract

All of these must use `isAutomationEnvironment()` and nothing else:

- `window.__app_ready__` — set in `ClientWrapperProvider` useEffect
- `window.__TEST_MODE__` — set in `ClientWrapperProvider` useEffect
- `window.__auth_snapshot__` — set in `useCurrentSession` queryFn
- `window.__oauth_complete__` — managed by `oauthPopup.ts`

Any future automation-only browser hook must also use `isAutomationEnvironment()`.

## .env example

```bash
# .env.local
NEXT_PUBLIC_ENVIRONMENT=local

# .env.test (CI)
NEXT_PUBLIC_ENVIRONMENT=test
```
