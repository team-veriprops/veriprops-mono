# Template: fixtures.ts

## Purpose

Declares the sessions a domain needs and the steps required to prepare the backend before journeys run. The runner executes bootstrap steps before any journey, and teardown steps after all journeys complete.

## Sessions

Each `SessionFixture` represents one authenticated user context. Define one session per user role the domain tests.

Common session key patterns:
- `adminUser` — a user with administrative privileges
- `customerUser` — a standard authenticated customer
- `guestUser` — unauthenticated state (typically no bootstrap needed)
- `staffUser`, `managerUser`, `supportAgent` — role-specific sessions

The `key` value is referenced by `sessionKey` in each journey in `journeys.ts`. They must match exactly.

## Bootstrap steps

Steps execute in array order. Sequence matters.

### Typical order

1. **reset** — wipe the database to a clean baseline
2. **seed** — load reference and fixture data (product catalogues, config, etc.)
3. **Domain-specific** — create the user accounts, orders, or state specific to this domain
4. **Role-specific** — any per-session setup needed for the specific user role

### idempotent flag

Mark `idempotent: true` only when ALL of the following are true:
- The step seeds reference data (not user-specific state)
- The data does not change between runs
- Running the step twice produces identical state (no duplicates, no side effects)
- You are confident the data will not change during a typical development session

Never mark these as idempotent:
- User account creation steps (duplicate users cause auth failures)
- Order or transaction creation steps
- Steps that modify shared state other domains may also touch

When a cached step is skipped, the runner emits a `cache:hit` event and logs it. The cache key is a SHA-256 hash of `(domainName, stepLabel, action, payload)`. Changing any of these automatically invalidates the cache.

### payload

The `payload` object is forwarded as the JSON body to the backend's `/qa/<action>` endpoint. Structure it to match what the backend seeder expects. If the backend endpoint shape is unknown, use `payload: {}` and add a `// TODO:` comment.

### Custom actions

For actions beyond `reset`/`seed`/`bootstrap`, set `action` to any string. The `BackendAdapter` will POST to `/qa/<action>`. Ensure the backend has the corresponding endpoint.

## Teardown steps

Teardown is optional. Include it only when:
- The domain creates persistent state (user accounts, files, external records) that must be cleaned up
- Leaving the state would cause failures in other domains that run afterwards
- The domain's own subsequent runs would be corrupted by leftover state

Teardown steps are never cached, regardless of `idempotent: true` — they always execute.

## Empty sessions

If the domain has only unauthenticated or fully public flows:

```typescript
export const fixtures: DomainFixtures = {
  sessions: [],
};
```

If it has API-only journeys with auth handled via header injection in custom steps, you may still need a session for the bootstrap steps.
