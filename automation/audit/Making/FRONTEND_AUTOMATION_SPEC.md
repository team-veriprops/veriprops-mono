# Frontend Automation Specification

## Overview

The frontend exposes stable automation contracts: `data-testid` selectors on auth elements and three `window.*` hooks for Playwright synchronization. These are permanent — do not remove them.

---

## data-testid Selectors

All selectors use the form `{flow}-{element}`. They are present in all environments (selectors do not need to be hidden in production).

### Login Flow

| Selector | Element | File |
|---|---|---|
| `login-form` | `<form>` | `LoginContainer.tsx` |
| `login-email` | Email `<Input>` | `LoginContainer.tsx` |
| `login-password` | Password `<Input>` | `LoginContainer.tsx` |
| `login-password-toggle` | Show/hide password `<button>` | `LoginContainer.tsx` |
| `login-submit` | Submit `<Button>` | `LoginContainer.tsx` |

### Signup Flow

| Selector | Element | File |
|---|---|---|
| `signup-stepper` | `<Stepper>` `<ol>` element | `Stepper.tsx` |
| `signup-basics-form` | Step 1 `<form>` | `AccountBasicsStep.tsx` |
| `signup-first-name` | First name `<Input>` | `AccountBasicsStep.tsx` |
| `signup-last-name` | Last name `<Input>` | `AccountBasicsStep.tsx` |
| `signup-email` | Email `<Input>` | `AccountBasicsStep.tsx` |
| `signup-password` | Password `<Input>` | `AccountBasicsStep.tsx` |
| `signup-basics-submit` | Continue `<Button>` | `AccountBasicsStep.tsx` |
| `verify-form` | Verify step `<form>` | `VerifyEmailPhoneStep.tsx` |
| `verify-submit` | Continue `<Button>` | `VerifyEmailPhoneStep.tsx` |
| `verify-back` | Back `<Button>` | `VerifyEmailPhoneStep.tsx` |

### OAuth Buttons

| Selector | Provider |
|---|---|
| `oauth-google` | Google |
| `oauth-apple` | Apple |
| `oauth-facebook` | Facebook |

Generated as `data-testid={`oauth-${provider.toLowerCase()}`}` in `SocialAuthButtons.tsx`.

### Playwright Usage

```typescript
// Login
await page.fill('[data-testid="login-email"]', 'test.verified@veriprops.test');
await page.fill('[data-testid="login-password"]', 'TestPass123!');
await page.click('[data-testid="login-submit"]');

// OAuth
await page.click('[data-testid="oauth-google"]');
```

---

## Window Hooks

Available only when `NODE_ENV !== 'production'`. Set by React effects — poll after load is complete.

### `window.__app_ready__`

- **Type:** `boolean | undefined`
- **Set:** After `ClientWrapperProvider` mounts (first `useEffect`).
- **Use:** Wait for this before interacting with any UI element.

```typescript
await page.waitForFunction(() => window.__app_ready__ === true);
```

### `window.__auth_snapshot__`

- **Type:** `{ isAuthenticated: boolean, userId: string|null, personas: string[] } | undefined`
- **Set:** After every `useCurrentSession` query resolves.
- **Use:** Assert auth state without inspecting cookies or API calls.

```typescript
await page.waitForFunction(() => window.__auth_snapshot__?.isAuthenticated === true);
const snapshot = await page.evaluate(() => window.__auth_snapshot__);
```

### `window.__oauth_complete__`

- **Type:** `boolean | undefined`
- **Set to `false`:** At the start of `startOauthPopup`.
- **Set to `true`:** When the OAuth popup posts a `{ type: "oauth_result", success: true }` message.
- **Use:** Wait for OAuth popup completion.

```typescript
await page.waitForFunction(() => window.__oauth_complete__ === true, { timeout: 30_000 });
```

---

## Auth Hydration

`ClientWrapperProvider` renders children immediately (no null-return guard). Do not add `if (!mounted) return null` — it causes a blank render flash and breaks `waitForLoadState`.

If theme flicker is a concern, use `suppressHydrationWarning` on the affected wrapper element.
