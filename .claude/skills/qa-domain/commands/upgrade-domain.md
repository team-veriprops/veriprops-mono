# Command: /qa upgrade-domain

Regenerates an existing domain after application changes or schema version bumps.

## When to use

- Routes, endpoints, or UI selectors have changed in the application
- `CURRENT_SCHEMA_VERSION` has been bumped and this domain is stale
- A journey is failing because the domain no longer reflects the app

## Pre-conditions

- The domain exists in `qa/domains/` and is registered in the manifest

## Steps

1. **Read** `SKILL.md` fully.

2. **Identify the domain** to upgrade. If not specified, ask the user.

3. **Read the existing domain:**
   ```bash
   cat qa/domains/<domain-name>/contract.ts
   cat qa/domains/<domain-name>/selectors.ts
   cat qa/domains/<domain-name>/fixtures.ts
   cat qa/domains/<domain-name>/journeys.ts
   cat qa/domains/<domain-name>/assertions.ts
   cat qa/domains/<domain-name>/README.md
   ```
   Note all existing journeys, selectors, and decisions before touching anything.

4. **Read current types:**
   ```bash
   cat qa/core/types.ts
   ```
   Note the current `CURRENT_SCHEMA_VERSION`.

5. **Inspect the codebase** for what has changed — use the full protocol in `SKILL.md`. Focus on:
   - New or changed routes
   - Added, renamed, or removed `data-testid` attributes
   - Changed API endpoint paths or request shapes
   - New user roles or auth flows

6. **Diff summary:** Report what changed in the app vs what the domain currently has. Wait for user confirmation before regenerating.

7. **Regenerate affected files only.** Do not rewrite files that have not changed — preserve any manual annotations or TODOs.

   Typical upgrade touches:
   - `contract.ts` — bump `schemaVersion` if needed
   - `selectors.ts` — add/update/remove selector entries
   - `journeys.ts` — update URLs, selector keys, step sequences
   - `assertions.ts` — update if endpoint shapes changed
   - `README.md` — update journey table

8. **Check for manual edits** in the existing domain files. If any file contains non-template content (hand-written steps, custom logic), preserve it and note it explicitly in your summary.

9. **Update the manifest** — set `updatedAt` and `schemaVersion` for the domain entry.

10. **Validate:**
    ```bash
    cd qa && pnpm qa:validate --domain <domain-name>
    cd qa && pnpm typecheck
    ```

11. **Summary report:**
    - Files modified (list each with what changed)
    - Preserved manual edits (list if any)
    - New selectors added, removed selectors
    - Schema version before → after
    - Next step: `pnpm qa:run -- --domain <domain-name>`

## Handling manual edits

If you find hand-written content in a generated file:
1. Preserve it exactly
2. Integrate the app changes around it
3. Call it out explicitly in your summary: "Preserved manual step in [journey name] — [description]"

Never silently discard manual changes.
