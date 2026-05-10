# Command: /qa add-domain

Generates a complete new QA domain from codebase inspection.

## When to use

When a feature area does not yet have a QA domain and you want to create one.

## Pre-conditions

- Platform initialised (`pnpm qa:init` has been run)
- The feature area exists in the codebase (routes, endpoints, or UI components are present)

## Steps

1. **Read** `SKILL.md` fully, especially the "Codebase inspection protocol" section.

2. **Read current state:**
   - `qa/core/types.ts` — note `CURRENT_SCHEMA_VERSION`
   - `qa/domain-manifest.json` — check for existing domains with similar scope
   - All six `qa/templates/domain/*.tpl` files

3. **Clarify scope with the user:**
   Ask: "Which feature area should this domain cover?" if not specified.
   Ask: "Are there existing domains this one should run after (dependsOn)?"
   Do not proceed until scope is confirmed.

4. **Inspect the codebase** using the full protocol in `SKILL.md`:
   - Routes and URL patterns
   - UI selectors (`data-testid` attributes)
   - Auth requirements and session roles
   - OTP / email flows
   - Backend test endpoints and seed payloads
   - Relevant data models

5. **Summarise findings** before generating:
   > "I found: [N] routes, [N] data-testid attributes, [auth/no-auth], [OTP/no-OTP]. I will generate [N] journeys covering [flow1, flow2, ...]."
   Wait for user confirmation before generating.

6. **Generate domain files** in `qa/domains/<domain-name>/`:
   - `contract.ts`
   - `selectors.ts`
   - `fixtures.ts`
   - `journeys.ts`
   - `assertions.ts`
   - `index.ts`
   - `README.md`

   Follow all generation rules in `SKILL.md`. Apply the templates from `qa/templates/domain/`.

7. **Update the manifest** — add the new domain entry with `enabled: true`.

8. **Validate the domain:**
   ```bash
   cd qa && pnpm qa:validate --domain <domain-name>
   ```
   Fix any reported errors before continuing.

9. **Run typecheck:**
   ```bash
   cd qa && pnpm typecheck
   ```
   Fix any type errors before continuing.

10. **Summary report:**
    - Files created (list each with one-line description)
    - Journeys generated (list with mode and session key)
    - Any TODOs or assumptions
    - Next step: `pnpm qa:run -- --domain <domain-name>`

## Quality checklist (run before declaring complete)

Apply the full checklist from `SKILL.md` — do not skip items.

## Common issues

**No `data-testid` attributes found:** Add `// TODO:` comments in `selectors.ts` and use `id` or semantic fallbacks. Note in README under "Known limitations".

**Unknown session structure:** Ask the user how authentication works for this feature before generating fixtures.

**Dependency on another domain:** Set `dependsOn` in the contract and verify the referenced domain exists in the manifest.
