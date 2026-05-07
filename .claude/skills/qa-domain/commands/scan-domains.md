# Command: /qa scan-domains

Lists all QA domains and their current status.

## When to use

- Getting an overview of the QA platform state
- Before adding a domain to check for overlapping coverage
- After pulling changes to see what domains others have added

## Steps

1. **Read the manifest:**
   ```bash
   cat qa/domain-manifest.json
   ```

2. **Scan the filesystem:**
   ```bash
   ls qa/domains/
   ```

3. **Read each domain's contract** for current metadata:
   ```bash
   for d in qa/domains/*/; do cat "${d}contract.ts" 2>/dev/null; echo "---"; done
   ```

4. **Read `qa/core/types.ts`** to get `CURRENT_SCHEMA_VERSION`.

5. **Produce a status table** for each domain:

   | Domain | Status | Schema | Owner | Tags | Depends On |
   |---|---|---|---|---|---|
   | `name` | enabled/disabled/orphan/ghost | current/stale | owner | tags | deps |

   Status definitions:
   - **enabled** — in manifest, `enabled: true`, directory exists
   - **disabled** — in manifest, `enabled: false`, directory exists
   - **ghost** — in manifest but directory missing from disk
   - **orphan** — directory exists on disk but not in manifest
   - **stale** — schema version behind `CURRENT_SCHEMA_VERSION`

6. **Summary counts:**
   - Total domains, enabled, disabled, ghosts, orphans, stale

7. **Recommendations** (if any):
   - Suggest `/qa sync-domains` if ghosts or orphans exist
   - Suggest `/qa drift-report` if stale domains exist
   - Suggest `/qa validate-all-domains` for a deeper check
