# /dev/seed Endpoint Specification

## Overview

`POST /dev/seed` inserts deterministic test fixtures into the database. Idempotent — skips users that already exist. Designed to be called after `/dev/reset` for a clean slate, or standalone to top-up missing fixtures.

## Endpoint

```
POST /dev/seed
```

No request body. No authentication required. Non-production only (same guards as `/dev/reset`).

## Response

```json
{
  "ok": true,
  "created": ["test.verified@veriprops.test"],
  "skipped": ["test.unverified@veriprops.test", "test.admin@veriprops.test", "test.agent@veriprops.test"],
  "test_otp": "654123",
  "test_password": "TestPass123!"
}
```

## Seeded Users

| Email | UUID | Role | email_verified | phone_verified | password |
|---|---|---|---|---|---|
| `test.verified@veriprops.test` | `00000000-0000-0000-0000-000000000001` | CUSTOMER | yes | yes | `TestPass123!` |
| `test.unverified@veriprops.test` | `00000000-0000-0000-0000-000000000002` | CUSTOMER | no | no | `TestPass123!` |
| `test.admin@veriprops.test` | `00000000-0000-0000-0000-000000000003` | ADMIN | yes | yes | `TestPass123!` |
| `test.agent@veriprops.test` | `00000000-0000-0000-0000-000000000004` | AGENT+CUSTOMER | yes | yes | `TestPass123!` |

All users share:
- `phone_country_code: "NG"`, `phone_dial_code: "+234"`
- `country_of_residence: "NG"`, `timezone: "Africa/Lagos"`, `preferred_currency: "NGN"`
- Phone numbers: `+23480100000{01-04}`

## Idempotency

Uses `session.get(User, uid)` to check existence before inserting. Existing users are added to `skipped` and not modified. Call order (reset → seed) does not matter for idempotency within a session.

## OTP for Seeded Users

When `OTP_MODE=deterministic`, all OTP operations return `654123`. The response includes `test_otp` as a convenience — it is always `str(settings.TEST_OTP)`.

## Usage in Automation

```python
r = await client.post("/dev/reset")
assert r.json()["ok"]

r = await client.post("/dev/seed")
body = r.json()
assert body["ok"]
test_otp = body["test_otp"]   # "654123"
test_pass = body["test_password"]  # "TestPass123!"
```

## Implementation

- [backend/main/app/domain/dev/controller.py](../../../backend/main/app/domain/dev/controller.py) — `_SEED_USERS`, `_upsert_seed_users()`
