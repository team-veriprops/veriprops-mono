# Command: /qa validate-all-domains

Validates every registered domain in one pass.

## When to use

- After bumping `CURRENT_SCHEMA_VERSION`
- After a large refactor affecting routes or selectors across features
- As a pre-merge gate before releasing changes to the QA platform
- On a schedule (e.g. weekly) to catch silent drift

## Steps

1. **Read** `qa/core/types.ts` — note `CURRENT_SCHEMA_VERSION`.

2. **Read the manifest** to get the list of all registered domains.

3. **Run CLI validation first** for a fast summary:
   ```bash
   cd qa && pnpm qa:validate
   cd qa && pnpm typecheck
   ```

4. **For each domain with errors** reported by the CLI, perform the deep validation from `validate-domain.md`.

5. **For all domains**, check:
   - `contract.schemaVersion` vs `CURRENT_SCHEMA_VERSION`
   - `dependsOn` references — all must exist in manifest
   - Selector/session key cross-references within each domain

6. **Dependency graph check:**
   Read all `contract.dependsOn` arrays and verify:
   - No circular dependencies
   - All referenced domain names exist in the manifest

7. **Produce a summary table:**

   | Domain | Shape | Schema | Deps | Selectors | Sessions | TypeScript |
   |---|---|---|---|---|---|---|
   | name | ✅/❌ | current/stale | ✅/❌ | ✅/❌ | ✅/❌ | ✅/❌ |

8. **Prioritised fix list:** Group issues by severity — errors first, then warnings. For each, state the domain, the issue, and the recommended fix command.

9. **If all pass:** Confirm "All [N] domains are valid against schema version [X]."

## Escalation

If more than 3 domains have schema version mismatches, recommend running `/qa upgrade-domain` on each stale domain sequentially rather than attempting a bulk upgrade — it reduces the risk of cascading errors.
