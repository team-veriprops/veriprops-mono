# OTP Contract Report

## Final OTP Rules

| `ENVIRONMENT` | Required `OTP_MODE` | Effect |
|---|---|---|
| `local` | `deterministic` (default) | Always returns `654123` |
| `dev` | `deterministic` (default) | Always returns `654123` |
| `test` | `deterministic` (required) | Always returns `654123`; startup fails if `random` |
| `staging` | `deterministic` or `random` | No constraint — use `random` in staging |
| `prod` | `random` (required) | Real 6-digit code; startup fails if `deterministic` |

## Safety Guards

`AppodusBaseSettings._enforce_otp_mode_policy()` is a Pydantic `@model_validator(mode="after")` that runs at import time (before the server starts accepting requests):

```python
# ENVIRONMENT=test + OTP_MODE=random → startup fails
# ENVIRONMENT=prod + OTP_MODE=deterministic → startup fails
```

Misconfiguration is detected immediately on startup, not at runtime when a user tries to verify.

## `TEST_OTP` Value

```
654123
```

Defined in `AppodusBaseSettings.TEST_OTP`. This is the **canonical deterministic OTP** for Veriprops. Do not change it — all automation scripts hard-code this value.

## OTP Code Generation

`Utils.get_otp_code()` in `backend/main/appodus_utils/common/commons.py`:

```python
otp_mode = os.environ.get("OTP_MODE", "deterministic").lower()

if otp_mode == "deterministic":
    return str(settings.TEST_OTP)    # always "654123"

# random: 6-digit integer
otp = random.randint(100000, 999999)
return str(otp)
```

**Critical:** reads `OTP_MODE` from `os.environ` directly, not from `settings.OTP_MODE`. This ensures determinism in pytest environments where settings may be partially mocked.

## Redis Key Schema

OTP state stored as Redis keys (or DB KV fallback). Prefixes:

| Prefix | Purpose |
|---|---|
| `otp:` | Active OTP code for a session |
| `otp_resend:` | Resend rate-limit state |
| `otp_fail:` | Failed attempt counter |
| `otp_verified:` | Verified flag (prevents replay) |
| `oauth:` | OAuth state tokens |

`POST /dev/reset` clears all five prefixes via `RedisUtils.delete_by_prefix(prefix)`.

## Automation Usage

```bash
# .env.test
OTP_MODE=deterministic
TEST_OTP=654123
```

```python
# After triggering an OTP send:
otp_code = "654123"  # always in deterministic mode
```

```typescript
// Playwright
await page.fill('[data-testid="otp-input"]', "654123");
```

## What Not To Do

- Do not set `OTP_MODE=random` in `.env.test` — startup fails.
- Do not compare `ENVIRONMENT` string to choose OTP behaviour — always read `OTP_MODE`.
- Do not change `TEST_OTP = 654123` without updating all automation scripts.
