# /dev/reset Endpoint Specification

## Overview

`POST /dev/reset` provides a single-call idempotent database and state reset for test automation. It is never available in production.

## Endpoint

```
POST /dev/reset
```

No request body required. No authentication required.

## What It Does

1. **Drops all SQLAlchemy-managed tables** using `BaseEntity.metadata.drop_all()` via a fresh `NullPool` async engine (does not interfere with the app's connection pool).
2. **Recreates all tables** using `BaseEntity.metadata.create_all()` — same engine, same transaction.
3. **Flushes OTP and OAuth KV state** by calling `RedisUtils.delete_by_prefix(p)` for each prefix:
   - `otp:`
   - `otp_resend:`
   - `otp_fail:`
   - `otp_verified:`
   - `oauth:`
   - Returns total count of deleted keys.

## Response

```json
{
  "ok": true,
  "message": "Database reset and KV cache cleared."
}
```

## Idempotency

Safe to call multiple times. `drop_all` is a no-op if tables don't exist; `create_all` is a no-op if they already exist. Key flushes tolerate empty stores.

## Production Safety

Two independent guards prevent this from running in production:

1. **Router not mounted.** `domain/__init__.py` only includes the dev router when `settings.ENVIRONMENT != Environment.PRODUCTION`.
2. **Dependency guard.** `_require_non_prod()` is a FastAPI `Depends` on the endpoint. In production it raises `HTTP 404 Not Found` — not 403, to avoid leaking the endpoint's existence.

## Usage in Automation

```python
# Playwright / httpx
import httpx

async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
    r = await client.post("/dev/reset")
    assert r.json()["ok"] is True
```

## Implementation

- [backend/main/app/domain/dev/controller.py](../../../backend/main/app/domain/dev/controller.py)
- [backend/main/app/domain/__init__.py](../../../backend/main/app/domain/__init__.py)
- [backend/main/appodus_utils/db/redis_utils.py](../../../backend/main/appodus_utils/db/redis_utils.py)
