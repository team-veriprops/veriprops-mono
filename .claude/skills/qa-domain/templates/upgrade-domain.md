# Template: upgrade-domain decision guide

## When to upgrade vs when to regenerate from scratch

Use this guide during `/qa upgrade-domain` to decide how much of a domain to rewrite.

---

## Decision matrix

| Change in the app | Recommended action |
|---|---|
| Selector renamed or removed | Update `selectors.ts` — targeted edit |
| New UI element added | Add entry to `selectors.ts` |
| Route URL changed | Update `url` fields in `journeys.ts` |
| New step added to an existing flow | Add step to the relevant journey |
| Journey flow completely redesigned | Rewrite the affected journey |
| New user role introduced | Add new `SessionFixture` to `fixtures.ts` |
| API endpoint path changed | Update `apiOptions.path` in affected steps |
| API request/response shape changed | Update `assertions.ts` body key checks |
| `CURRENT_SCHEMA_VERSION` bumped (minor) | Update `schemaVersion` in `contract.ts` and manifest |
| `CURRENT_SCHEMA_VERSION` bumped (major) | Full regeneration recommended |
| New required field on `DomainContract` | Add field to `contract.ts` with correct value |
| Entire feature area redesigned | Full regeneration — treat as new domain |

---

## Partial upgrade checklist

When doing a targeted upgrade (not full regeneration):

1. Read the existing domain files before touching anything
2. Note any manual edits or TODOs — preserve them
3. Make only the changes the matrix above indicates
4. Re-run the quality checklist from `SKILL.md` on all modified files
5. Update `contract.schemaVersion` if `CURRENT_SCHEMA_VERSION` has changed
6. Update manifest `updatedAt` and `schemaVersion`
7. Run `pnpm qa:validate --domain <name>` and `pnpm typecheck`

---

## Preserving manual edits

Before generating any output, search the domain files for signs of manual editing:

- Comments that do not follow the `// [CLAUDE: ...]` annotation format
- Steps or assertions not producible from the `.tpl` templates
- `// Manual:` or `// Hand-written:` markers
- Any logic more complex than what the template produces

When found:
1. Quote the manual content in your response
2. Confirm with the user that it should be preserved
3. Integrate app changes around it — never overwrite without confirmation

---

## Schema version upgrade only

When the only change is a `CURRENT_SCHEMA_VERSION` bump:

1. Read `qa/core/types.ts` — identify what fields changed
2. For each domain: add/remove/rename affected fields in `contract.ts`
3. Update `contract.schemaVersion` to the new version
4. Update manifest entry `schemaVersion`
5. Run typecheck — type errors pinpoint remaining mismatches

This is safe to do in bulk across all stale domains in a single session.

---

## Full regeneration signals

Regenerate from scratch (use `add-domain` flow on the existing directory) when:

- More than 60% of journeys need to change
- The feature's routing structure has been completely redesigned
- A major schema version bump introduces breaking type changes
- The domain's test strategy needs rethinking (wrong user roles, missing flows, wrong session model)

When regenerating: read the old domain first, extract any valid selectors and assertions to reuse, then generate fresh.
