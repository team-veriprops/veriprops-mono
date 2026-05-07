# Template: validate-domain deep checklist

Extended validation reference used during `/qa validate-domain` and `/qa validate-all-domains`.

---

## contract.ts checks

| Check | How to verify |
|---|---|
| `schemaVersion` matches `CURRENT_SCHEMA_VERSION` | Read `qa/core/types.ts`, compare |
| `name` is kebab-case | Visual inspection |
| `name` matches directory name | `ls qa/domains/` |
| `name` matches manifest key | `cat qa/domain-manifest.json` |
| `dependsOn` entries exist in manifest | Check each name against manifest keys |
| `dependsOn` creates no cycle | Mentally trace or run `pnpm qa:validate` |
| `otpPattern` (if present) is valid regex | `new RegExp(pattern)` mentally or in Node |
| `otpPattern` (if present) has one capture group | Count `(` in the pattern |
| `appReadySelector` (if present) is a valid CSS selector | Visual inspection |
| `tags` are lowercase kebab-case | Visual inspection |

---

## selectors.ts checks

| Check | How to verify |
|---|---|
| All keys referenced in `journeys.ts` exist here | Cross-reference journey `selector` fields |
| No raw CSS strings in journey steps | Search `journeys.ts` for strings containing `.`, `#`, `[` not in selectors map |
| No positional selectors (`:nth-child` etc) | grep for `:nth`, `:first`, `:last` |
| Keys are camelCase | Visual inspection |
| `data-testid` preferred over class selectors | Check if `data-testid` exists in the app for non-testid selectors |
| TODOs documented for missing `data-testid` | Visual inspection |

---

## fixtures.ts checks

| Check | How to verify |
|---|---|
| All `sessionKey` values in journeys exist here | Cross-reference `journeys.ts` `sessionKey` fields |
| Bootstrap step order is logical (reset → seed → specific) | Visual inspection |
| `idempotent: true` steps are genuinely idempotent | Reason about whether re-running changes state |
| Payloads match backend endpoint expectations | Check backend route handler if possible |
| Teardown included only when necessary | Ask: does leftover state corrupt other domains? |

---

## journeys.ts checks

| Check | How to verify |
|---|---|
| All `selector` values are keys in `selectors.ts` | Cross-reference |
| All `sessionKey` values are keys in `fixtures.ts` | Cross-reference |
| No raw CSS strings in `selector` fields | Search for `.`, `#`, `[` in selector values |
| `{{token}}` paths are plausible | Trace state flow — is the key set by a prior step? |
| No `skip: true` on production journeys | Visual inspection |
| Journey names are verb phrases in plain English | Visual inspection |
| No Playwright API calls directly in steps | Search for `page.`, `context.`, `browser.` |
| `api-call` steps have `apiOptions` defined | Visual inspection |
| `custom` steps have `handler` defined | Visual inspection |
| `assert` steps have `assertion` defined | Visual inspection |

---

## assertions.ts checks

| Check | How to verify |
|---|---|
| All functions return `AssertionResult` | Check return type annotations |
| No functions throw | Search for `throw` keyword |
| Core helpers imported from `../../core/assertions.js` | Check imports |
| No network requests inside assertion functions | Search for `fetch`, `axios`, `http` |
| No state mutations | Search for `ctx.state`, `page.evaluate` with side effects |
| Naming follows `assert` + Subject + Condition | Visual inspection |

---

## index.ts checks

| Check | How to verify |
|---|---|
| Default export is a `Domain` object | Check export statement |
| All five properties present: `contract`, `fixtures`, `selectors`, `journeys`, `assertions` | Visual inspection |
| All imports use `.js` extension | Visual inspection |
| No additional exports that could confuse the registry | Check for `export const`, `export function` |

---

## Manifest entry checks

| Check | How to verify |
|---|---|
| Entry `name` matches `contract.name` | Compare |
| Entry `path` points to correct directory | `ls qa/domains/<path>/index.ts` |
| Entry `schemaVersion` matches `contract.schemaVersion` | Compare |
| Entry `enabled` is intentional | Ask user if `false` |
| `dependsOn` in manifest matches `contract.dependsOn` | Compare — they must be in sync |
| `addedAt` and `updatedAt` are valid ISO timestamps | Visual inspection |

---

## Scoring

After completing all checks, produce a score:

- 0 errors, 0 warnings → **Valid** ✅
- 0 errors, 1+ warnings → **Valid with warnings** ⚠️ — list warnings
- 1+ errors → **Invalid** ❌ — list errors with fix instructions

Always fix errors before marking a domain as ready to run.
