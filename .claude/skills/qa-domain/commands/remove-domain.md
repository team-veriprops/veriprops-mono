# Command: /qa remove-domain

Removes a domain and deregisters it from the manifest.

## When to use

- A feature area has been removed from the application
- A domain is being replaced by a different domain with a different scope
- A domain was generated incorrectly and needs to be rebuilt from scratch

## Steps

1. **Identify the domain** to remove. If not specified, ask the user.

2. **Read the manifest** to confirm the domain exists:
   ```bash
   cat qa/domain-manifest.json
   ```

3. **Confirm with the user** before deleting anything:
   > "I will remove `qa/domains/<domain-name>/` and deregister `<domain-name>` from the manifest. This cannot be undone. Confirm?"
   Do not proceed without explicit confirmation.

4. **Check for dependents** — domains that list this domain in `dependsOn`:
   ```bash
   grep -r "dependsOn" qa/domains/*/contract.ts | grep "<domain-name>"
   ```
   If any dependents exist, report them and ask how to proceed. Do not remove the domain if active dependents exist without the user resolving the dependency first.

5. **Remove the domain directory:**
   ```bash
   rm -rf qa/domains/<domain-name>/
   ```

6. **Update the manifest** — remove the domain key from `domains` and update `updatedAt`.

7. **Validate remaining domains:**
   ```bash
   cd qa && pnpm qa:validate
   ```
   Confirm no remaining domains have broken `dependsOn` references.

8. **Summary:** Confirm what was removed and that the manifest is clean.

## Safety rules

- Never remove without explicit user confirmation
- Never remove if active `dependsOn` dependents exist
- Always validate remaining domains after removal
