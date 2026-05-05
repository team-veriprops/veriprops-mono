# Claude Governance Specification

Permanent engineering rules for autonomous agents working in the Veriprops monorepo. These rules exist to maintain the automation-stable foundation. Future Claude agents MUST follow them.

---

## Backend Rules

### 1. OTP_MODE is the switch — not ENVIRONMENT

Never compare `ENVIRONMENT` string to choose OTP behaviour. Always read `OTP_MODE` env var.

```python
# WRONG
if os.environ.get("ENVIRONMENT") == "Environment.LOCAL":
    return "654123"

# CORRECT
if os.environ.get("OTP_MODE", "deterministic").lower() == "deterministic":
    return str(settings.TEST_OTP)
```

### 2. /dev/reset and /dev/seed must remain double-gated

Both endpoints must be protected by:
1. Router not mounted in production (`domain/__init__.py` condition).
2. `_require_non_prod()` dependency on the endpoint.

Never remove either guard. Never add `ALLOW_DEV_ENDPOINTS` config that weakens this.

### 3. Seed users are immutable fixtures

The 4 seed users (emails, UUIDs, password) are automation contracts. Do not change them. If adding seed users, add new entries; never modify existing ones.

| Email | UUID suffix |
|---|---|
| `test.verified@veriprops.test` | `...0001` |
| `test.unverified@veriprops.test` | `...0002` |
| `test.admin@veriprops.test` | `...0003` |
| `test.agent@veriprops.test` | `...0004` |

### 4. Mailpit routing must not be changed to a config flag

The email routing condition in `MessageRouter._load_routing_rules()` is:

```python
"condition": lambda msg: settings.ENVIRONMENT not in {Environment.PRODUCTION, Environment.STAGING}
```

Do not introduce `EMAIL_PROVIDER`, `SMTP_ENABLED`, or similar settings. The condition is the switch.

### 5. SmtpEmailProvider hard-fail guard must not be softened

`SmtpEmailProvider.send_message()` must raise `ValueError` in production and staging. Logging a warning is not sufficient.

### 6. Production safety pattern

Any integration that must not fire in production must raise (not log) in its send method. Configuration-only guards are insufficient — a misconfigured env would bypass them silently.

---

## Frontend Rules

### 7. data-testid selectors are permanent

`data-testid` attributes on auth form elements are automation contracts. Never remove them. Never rename them without updating all automation scripts. Never hide them behind a feature flag.

New auth forms must follow the naming scheme: `{flow}-{element}`.

### 8. Window hooks must be present when NODE_ENV !== 'production'

`window.__app_ready__`, `window.__auth_snapshot__`, `window.__oauth_complete__` must be set in all non-production builds. They must not be gated on feature flags or any other condition.

### 9. ClientWrapperProvider must not null-return on first render

`if (!mounted) return null` is forbidden in `ClientWrapperProvider`. It causes Playwright to see a blank page and makes selector waits unreliable. If theme hydration causes issues, use `suppressHydrationWarning` on the affected wrapper.

### 10. __auth_snapshot__ must update after every session query

`useCurrentSession` must update `window.__auth_snapshot__` after every query resolves — both authenticated and unauthenticated states. Automation scripts wait on `isAuthenticated` to become `true` or `false`.

---

## Workflow Rules

### 11. Reset → seed before automation test runs

Any automated test suite must call:
1. `POST /dev/reset` — clean slate
2. `POST /dev/seed` — known fixtures

Do this in a `beforeAll` or test setup hook, not in individual tests.

### 12. Use deterministic values in assertions

```python
# Email verification OTP
assert otp == "654123"  # always in deterministic mode

# Seed user credentials
email = "test.verified@veriprops.test"
password = "TestPass123!"
user_id = "00000000-0000-0000-0000-000000000001"
```

### 13. Mailpit API for email assertions

```python
# Check email was sent
r = await httpx.get("http://localhost:8025/api/v1/messages")
assert len(r.json()["messages"]) > 0

# Clear between tests
await httpx.delete("http://localhost:8025/api/v1/messages")
```

---

---

## Backend Rules (continued)

### 14. MockSmsProvider must be used for all SMS in test/dev/local

`ENVIRONMENT in {test, dev, local}` routes ALL SMS to `MockSmsProvider`, which logs and suppresses. Never route to Termii or Twilio in those environments. The SMS routing rule must remain first (evaluated before Nigerian-number and high-priority rules).

```python
# CORRECT
{
    "condition": lambda msg: settings.ENVIRONMENT in {
        Environment.TEST, Environment.DEVELOPMENT, Environment.LOCAL
    },
    "providers": [MessageProviderName.MOCK_SMS],
    "fallback_order": [],
    "exclusive": True,
},
```

### 15. `"exclusive": True` must not be removed from test-mode routing rules

Both the SMS test rule and the email non-prod rule carry `"exclusive": True`. This prevents `_handle_fallback()` from falling through to the "last resort" block, which would try real providers. Without it, SMTP or MockSmsProvider failures would silently contact Mailjet, Sendgrid, Termii, or Twilio.

Never remove `"exclusive": True` from environment-gated routing rules.

---

## Frontend Rules (continued)

### 16. `window.__TEST_MODE__` must be set alongside `window.__app_ready__`

Both flags are set in the same `useEffect` in `ClientWrapperProvider`. They must always be present together in non-production builds. Do not move `__TEST_MODE__` to a different hook, file, or condition.

```typescript
useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
        (window as any).__app_ready__ = true;
        (window as any).__TEST_MODE__ = true;  // always alongside __app_ready__
    }
}, []);
```

### 17. `window.__oauth_complete__` uses `null | true` model (not boolean)

- Reset value is `null` (not `false`) at the start of every `startOauthPopup` call.
- Set to `true` on OAuth popup success.
- Never set to `false`.

```typescript
// WRONG
(window as any).__oauth_complete__ = false;

// CORRECT
(window as any).__oauth_complete__ = null;
```

Automation waits with `=== true`, which correctly excludes both `null` and `undefined`.

---

## What Not To Do

- Do not add `OTP_MODE=random` to `.env.test` — this causes startup failure.
- Do not remove `/dev/reset` or `/dev/seed` routes, even if unused.
- Do not add `EMAIL_PROVIDER` or similar settings to control Mailpit routing.
- Do not add `if (!mounted) return null` to providers.
- Do not remove `data-testid` attributes during UI refactors.
- Do not move window hooks behind feature flags.
- Do not remove `"exclusive": True` from test-mode routing rules — it prevents real provider fallback.
- Do not route SMS to Termii or Twilio in test/dev/local environments.
- Do not set `window.__oauth_complete__ = false` — use `null` for reset.
- Do not omit `window.__TEST_MODE__` when setting `window.__app_ready__` in non-production builds.
