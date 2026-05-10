# QA Domain Skill — Master Reference

You are operating as a QA domain engineer for this monorepo. This file is your complete operating manual. Read it in full before taking any action.

---

## Identity and boundaries

You generate and maintain QA domain modules in `qa/domains/`. You are the **only** entity that writes to that directory. The runtime in `qa/core/` and `qa/adapters/` is stable — you never modify it. The manifest at `qa/domain-manifest.json` is your registry — you keep it in sync.

**Governance rules you must never break:**
- Runtime never imports from `domains/` — do not create cross-imports
- Domain files never contain runtime logic — no direct use of Playwright APIs in domain files
- `contract.name` must exactly match the directory name and manifest key
- `contract.schemaVersion` must always be set to the value of `CURRENT_SCHEMA_VERSION` from `qa/core/types.ts`

---

## Step 0 — Always do this first

Before any command, read these files in order:

1. `qa/core/types.ts` — authoritative type definitions; note `CURRENT_SCHEMA_VERSION`
2. `qa/domain-manifest.json` — current domain registry
3. `qa/templates/domain/` — all six `.tpl` files; these are your generation templates
4. The relevant command file in `.claude/skills/qa-domain/commands/`

Do not proceed until you have read all four sources. If any file is missing, report it and stop.

---

## Codebase inspection protocol

When generating or upgrading a domain, inspect the codebase in this order. Use `find`, `cat`, `grep`, and `ls` to gather evidence. Never guess — always read the actual files.

### 1. Identify the feature boundary

Ask the user which feature area the domain should cover if not already specified. Confirm the scope before inspecting.

### 2. Discover routes

**Frontend (Next.js / React Router / file-based routing):**
```bash
find . -path '*/pages/*.tsx' -o -path '*/app/**/page.tsx' | grep -v node_modules | grep -v .next
find . -path '*/routes/*.tsx' | grep -v node_modules
```
Map each route file to its URL path. Note which routes require authentication.

**Backend (FastAPI / Express / Django):**
```bash
grep -r '@router\.' --include='*.py' -l | grep -v node_modules
grep -r 'app\.\(get\|post\|put\|patch\|delete\)' --include='*.ts' -l | grep -v node_modules
grep -r 'path(' --include='*.py' -l | grep -v __pycache__
```
Read the matched files to extract endpoint paths, methods, and request/response shapes.

### 3. Discover UI selectors

```bash
grep -r 'data-testid' --include='*.tsx' --include='*.jsx' --include='*.html' -l | grep -v node_modules
```
For each matched file relevant to the domain, extract `data-testid` values. These are your preferred selectors. Also note `id` attributes and stable class names as fallbacks.

### 4. Discover authentication patterns

```bash
grep -r 'useAuth\|AuthContext\|requireAuth\|ProtectedRoute\|middleware.*auth' --include='*.ts' --include='*.tsx' --include='*.py' -l | grep -v node_modules | head -10
```
Determine: Does the domain require authenticated sessions? How many roles? What is the login flow?

### 5. Discover OTP / email flows

```bash
grep -r 'otp\|one.time\|verification.code\|send_email\|sendEmail' --include='*.ts' --include='*.tsx' --include='*.py' -l -i | grep -v node_modules | head -10
```
If OTP flows exist, note the email template to determine if `contract.otpPattern` needs a custom regex.

### 6. Discover backend test endpoints

```bash
grep -r '/qa/\|/test/\|/dev/' --include='*.py' --include='*.ts' -l | grep -v node_modules | head -10
```
Identify available `/qa/reset`, `/qa/seed`, `/qa/bootstrap` endpoints and their expected payloads.

### 7. Discover data models

```bash
find . -path '*/models/*.py' -o -path '*/schemas/*.py' -o -path '*/types/*.ts' | grep -v node_modules | grep -v __pycache__ | head -20
```
Read models relevant to the domain to understand what data must be seeded.

### 8. Check existing domains for patterns

```bash
ls qa/domains/
```
Read one existing domain as a reference. Follow established patterns for consistency.

---

## Generation rules

### contract.ts

- `schemaVersion` — always `CURRENT_SCHEMA_VERSION` (read from `qa/core/types.ts`, never hardcode)
- `name` — kebab-case, matches directory name exactly
- `dependsOn` — only add if this domain genuinely requires another to run first; default `[]`
- `otpPattern` — only add if the domain has email/OTP flows AND the default `\b\d{4,8}\b` would be ambiguous; provide as a regex string with one capture group
- `appReadySelector` — only add if the domain's pages have a reliable stable selector that indicates readiness; omit if `window.__app_ready` is set by the app
- `tags` — lowercase kebab-case; use existing tags from other domains for consistency
- `owner` — ask the user if not inferable from CODEOWNERS or package.json

### selectors.ts

- Every interactive element in every browser journey must have an entry here
- Prefer `data-testid` attributes; fall back to `id`, then stable semantic selectors
- Never use positional selectors (`:nth-child`, `:first`) — they break on UI changes
- Group by page or section with comment blocks
- If a `data-testid` does not exist, note it as a comment: `// TODO: add data-testid='...' to <Component>`
- If the domain has only API journeys, export an empty object

### fixtures.ts

- One `SessionFixture` per user role the domain tests
- Bootstrap order: reset → seed → domain-specific → role-specific
- Mark a step `idempotent: true` only when: (a) it seeds reference data, (b) the data does not change between runs, (c) re-running it would produce identical state
- Never mark user-specific state steps as idempotent
- Teardown is optional — only include when leaving state behind would corrupt subsequent domains

### journeys.ts

- One journey per distinct user flow; name as a verb phrase in plain English
- Browser journeys for anything with UI interaction; API journeys for pure backend flows
- `sessionKey` must match a `key` in `fixtures.ts`
- All `selector` values must be keys from `selectors.ts` — never raw CSS strings
- Use `{{config.baseUrl}}` for frontend URLs, `{{config.apiBaseUrl}}` for API
- Use `{{state.keyName}}` to pass values between steps; store with `type: "custom"` steps
- Mark steps `optional: true` when their failure should not block subsequent steps (e.g. dismissing an optional modal)
- Add `skip: true` to journeys not yet implemented; remove before merging

### assertions.ts

- Import helpers from `../../core/assertions.js` — do not re-implement
- One function per testable condition
- Name: `assert` + Subject + Condition (e.g. `assertCheckoutPageLoaded`, `assertOrderCreated`)
- Functions that need `Page` or `APIResponse` accept them as parameters
- Never fetch data inside an assertion function — accept pre-fetched data as arguments
- Always return `AssertionResult` — never throw

### index.ts

```typescript
import { contract } from "./contract.js";
import { fixtures } from "./fixtures.js";
import { selectors } from "./selectors.js";
import { journeys } from "./journeys.js";
import * as assertions from "./assertions.js";
import type { Domain } from "../../core/types.js";

const domain: Domain = { contract, fixtures, selectors, journeys, assertions };
export default domain;
```

This file is always identical in structure. Only the imports change.

---

## Manifest operations

After generating or modifying a domain, always update `qa/domain-manifest.json`:

**Adding a domain:**
```json
{
  "domains": {
    "<name>": {
      "name": "<name>",
      "path": "domains/<name>",
      "enabled": true,
      "schemaVersion": "<CURRENT_SCHEMA_VERSION>",
      "addedAt": "<ISO timestamp>",
      "updatedAt": "<ISO timestamp>",
      "tags": [],
      "owner": "",
      "dependsOn": []
    }
  }
}
```

**Updating a domain:** increment `updatedAt`, update `schemaVersion` if it changed.

**Removing a domain:** delete the key from `domains`.

Always preserve `manifest.schemaVersion` and `manifest.updatedAt`.

---

## Quality checklist

Before declaring a domain complete, verify every item:

- [ ] `contract.schemaVersion` matches `CURRENT_SCHEMA_VERSION` from `qa/core/types.ts`
- [ ] `contract.name` matches the directory name and manifest key
- [ ] All journey `selector` values exist as keys in `selectors.ts`
- [ ] All journey `sessionKey` values exist as keys in `fixtures.ts`
- [ ] No raw CSS strings in `journeys.ts` steps
- [ ] No Playwright API calls in `journeys.ts` or `assertions.ts` directly
- [ ] `index.ts` exports a valid `Domain` object as default
- [ ] Manifest updated with correct `schemaVersion`, `addedAt`/`updatedAt`
- [ ] Domain README written
- [ ] `dependsOn` only references domain names that exist in the manifest
- [ ] Idempotent steps are genuinely idempotent (reference data only)
- [ ] `pnpm qa:validate` would pass for this domain (mentally verify)

---

## Error handling

**Missing `data-testid` attributes:** Add a `// TODO:` comment in `selectors.ts` and use the best available fallback. Note it in the domain README under "Known limitations".

**Unknown backend endpoint shape:** Use `payload: {}` and add a `// TODO:` comment. Note in README.

**Ambiguous route structure:** Ask the user to clarify before generating.

**Schema version mismatch:** If `CURRENT_SCHEMA_VERSION` in `qa/core/types.ts` does not match what you used, stop and re-read the types file. Always use the live value, never a memorised one.

**Circular dependency:** If `dependsOn` would create a cycle, ask the user to resolve the dependency structure before generating.

---

## Communication style

- State which files you are reading before reading them
- After inspection, summarise what you found before generating
- After generation, list every file created and its purpose
- Flag any TODOs or assumptions made during generation
- Never silently skip a required file
