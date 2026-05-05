# OTP Service Specification

## Overview

The OTP subsystem is controlled by `OTP_MODE`, which determines whether codes are deterministic (test/dev) or random (production). The mode is enforced at startup — misconfiguration fails loudly.

## OTP_MODE Values

| Value | Behaviour | Allowed Environments |
|---|---|---|
| `deterministic` | Always returns `TEST_OTP` (654123) | local, dev, test, staging |
| `random` | Generates a random 6-digit integer | all; **required** in prod |

`OTP_MODE` defaults to `deterministic` in `AppodusBaseSettings`. Loaded from `.env.{appodus_active_env}`.

## Startup Enforcement

`AppodusBaseSettings._enforce_otp_mode_policy()` (a `@model_validator`) runs at import time:

```
ENVIRONMENT=test  + OTP_MODE=random        → ValueError (startup fails)
ENVIRONMENT=prod  + OTP_MODE=deterministic → ValueError (startup fails)
```

No other combination is rejected.

## TEST_OTP Value

`654123` — defined in `AppodusBaseSettings.TEST_OTP`. This is the **canonical deterministic OTP** for Veriprops. Never change this value without updating all automation scripts.

## Redis Key Schema

OTP state is stored as Redis keys (or DB KV if Redis is not configured). Prefixes:

| Prefix | Purpose |
|---|---|
| `otp:` | Active OTP code for a session |
| `otp_resend:` | Resend rate-limit state |
| `otp_fail:` | Failed attempt counter |
| `otp_verified:` | Verified flag (prevents replay) |
| `oauth:` | OAuth state tokens |

`POST /dev/reset` calls `RedisUtils.delete_by_prefix(p)` for all five prefixes.

## Implementation

- `Utils.get_otp_code()` — [backend/main/appodus_utils/common/commons.py](../../../backend/main/appodus_utils/common/commons.py)
- `AppodusBaseSettings.OTP_MODE` — [backend/main/appodus_utils/config/settings.py](../../../backend/main/appodus_utils/config/settings.py)

## Automation Usage

```bash
# .env.test
OTP_MODE=deterministic
TEST_OTP=654123
```

```python
# After triggering an OTP send, use:
otp_code = "654123"  # always
```

```python
# Playwright
await page.fill('[data-testid="otp-input"]', "654123")
```
