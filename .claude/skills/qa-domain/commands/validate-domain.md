# Command: /qa validate-domain

Performs a deep validation of a single domain.

## When to use

- Before merging a new or upgraded domain
- When a domain is failing at runtime and you need to diagnose why
- When `pnpm qa:validate --domain <name>` reports issues

## Steps

1. **Identify the domain.** Ask if not specified.

2. **Read current types:**
   ```bash
   cat qa/core/types.ts
   ```
   Note `CURRENT_SCHEMA_VERSION` and all required fields on `DomainContract` and `Domain`.

3. **Read all domain files:**
   ```bash
   cat qa/domains/<name>/contract.ts
   cat qa/domains/<name>/selectors.ts
   cat qa/domains/<name>/fixtures.ts
   cat qa/domains/<name>/journeys.ts
   cat qa/domains/<name>/assertions.ts
   cat qa/domains/<name>/index.ts
   ```

4. **Read the manifest entry:**
   ```bash
   cat qa/domain-manifest.json | grep -A 20 '"<name>"'
   ```

5. **Check each validation point:**

   **Contract:**
   - [ ] `schemaVersion` matches `CURRENT_SCHEMA_VERSION`
   - [ ] `name` matches directory name
   - [ ] `name` matches manifest key
   - [ ] `dependsOn` references exist in manifest

   **Selectors:**
   - [ ] All keys referenced in `journeys.ts` exist in `selectors.ts`
   - [ ] No raw CSS strings in journey step `selector` fields

   **Fixtures:**
   - [ ] All `sessionKey` values in `journeys.ts` exist in `fixtures.ts`
   - [ ] Bootstrap steps reference valid `action` names
   - [ ] `idempotent: true` steps are genuinely idempotent (flag if uncertain)

   **Journeys:**
   - [ ] No journeys reference selectors not in `selectors.ts`
   - [ ] No journeys reference session keys not in `fixtures.ts`
   - [ ] `{{interpolation}}` tokens reference plausible state paths
   - [ ] No `skip: true` journeys unless intentional (ask user)

   **Assertions:**
   - [ ] All functions return `AssertionResult`
   - [ ] No Playwright API calls directly in assertion functions

   **Index:**
   - [ ] Default export is a valid `Domain` object
   - [ ] All imports resolve correctly

   **Manifest:**
   - [ ] Entry `schemaVersion` matches `contract.schemaVersion`
   - [ ] `path` points to the correct directory

6. **Run CLI validation:**
   ```bash
   cd qa && pnpm qa:validate --domain <name>
   cd qa && pnpm typecheck
   ```

7. **Report:** List each check with pass/fail. For failures, explain the issue and the fix. Apply fixes if they are straightforward; flag complex ones for the user.
