# Command: /qa sync-domains

Reconciles the manifest with the filesystem — removes ghost entries, registers orphan directories.

## When to use

- After manually deleting or moving domain directories
- After pulling changes where someone added domain files without updating the manifest
- After running `/qa scan-domains` that reported ghosts or orphans

## Steps

1. **Read the manifest:**
   ```bash
   cat qa/domain-manifest.json
   ```

2. **Scan the filesystem:**
   ```bash
   ls qa/domains/
   find qa/domains -name "index.ts" -maxdepth 2
   ```

3. **Identify discrepancies:**
   - **Ghosts** — manifest entries with no matching directory
   - **Orphans** — directories with `index.ts` not in manifest

4. **Report findings** before making changes:
   > "I found [N] ghost(s): [names]. I found [N] orphan(s): [names]. I will remove ghost entries and register orphans as disabled. Confirm?"

5. **For each ghost:** Remove the entry from the manifest.

6. **For each orphan:**
   - Read `qa/domains/<name>/contract.ts` to extract metadata
   - Add to manifest with `enabled: false` (disabled until explicitly reviewed)
   - Use `contract.schemaVersion`, `contract.tags`, `contract.owner`, `contract.dependsOn` from the file

7. **Save the manifest** with updated `updatedAt`.

8. **Run CLI sync as a double-check:**
   ```bash
   cd qa && pnpm qa:validate
   ```

9. **Summary:** Report what was removed (ghosts) and what was added (orphans). Remind the user that orphans are registered as disabled and must be explicitly enabled via the manifest.

## Safety rules

- Never delete domain directories — only manifest entries
- Always register orphans as `enabled: false`; the user decides when to enable them
- Confirm before making any changes
