# Command: /qa drift-report

Reports schema version drift and structural divergence across all domains.

## When to use

- After bumping `CURRENT_SCHEMA_VERSION` to see what needs upgrading
- Periodic health check to understand which domains are falling behind
- Before a major platform release to gauge upgrade effort

## Steps

1. **Read** `qa/core/types.ts` — record `CURRENT_SCHEMA_VERSION` and the full `DomainContract` interface shape.

2. **Read the manifest:**
   ```bash
   cat qa/domain-manifest.json
   ```

3. **For each registered domain**, read `contract.ts`:
   ```bash
   for d in qa/domains/*/; do echo "=== $d ==="; cat "${d}contract.ts" 2>/dev/null; done
   ```

4. **Compute drift for each domain:**
   - **Schema version:** is `contract.schemaVersion` < `CURRENT_SCHEMA_VERSION`?
   - **Missing fields:** does the contract lack any field that `DomainContract` now requires?
   - **Orphaned fields:** does the contract have fields that no longer exist in `DomainContract`?
   - **Manifest mismatch:** does the manifest entry `schemaVersion` differ from `contract.schemaVersion`?

5. **Produce a drift report:**

   ```
   QA Platform Drift Report
   Runtime schema version: 1.0.0
   Generated: <timestamp>

   ┌──────────────────────────────────────────────────────────┐
   │ Domain          │ Version │ Status   │ Issues            │
   ├──────────────────────────────────────────────────────────┤
   │ checkout        │ 1.0.0   │ current  │ —                 │
   │ auth            │ 0.9.0   │ stale    │ missing: otpPat…  │
   │ dashboard       │ 1.0.0   │ current  │ —                 │
   └──────────────────────────────────────────────────────────┘

   Stale domains (1): auth
   Ghost domains (0): —
   Orphan domains (0): —

   Recommended actions:
   1. /qa upgrade-domain  →  auth
   ```

6. **Upgrade effort estimate:**
   - 0–2 stale domains: low effort, upgrade now
   - 3–5 stale domains: medium effort, plan a dedicated session
   - 6+ stale domains: high effort, consider a bulk upgrade strategy

7. **If no drift:** Confirm "All [N] domains are current at schema version [X]. No action required."

## Output format

Present the report as a formatted code block for easy copying. Include the timestamp so it can be saved as a snapshot.
