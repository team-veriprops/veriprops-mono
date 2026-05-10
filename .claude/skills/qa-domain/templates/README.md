# Skill Templates

Prose descriptions of each domain file's purpose, rules, and generation patterns. Used by the skill alongside the TypeScript `.tpl` files in `qa/templates/domain/`.

## How these relate to the `.tpl` files

| Skill template (here) | TypeScript template (qa/templates/domain/) | Generated file |
|---|---|---|
| `contract.md` | `contract.ts.tpl` | `domains/<name>/contract.ts` |
| `selectors.md` | `selectors.ts.tpl` | `domains/<name>/selectors.ts` |
| `fixtures.md` | `fixtures.ts.tpl` | `domains/<name>/fixtures.ts` |
| `journeys.md` | `journeys.ts.tpl` | `domains/<name>/journeys.ts` |
| `assertions.md` | `assertions.ts.tpl` | `domains/<name>/assertions.ts` |

The `.tpl` files show **structure**. The `.md` files here explain **intent and rules**. The skill reads both.

## Additional templates

| File | Purpose |
|---|---|
| `upgrade-domain.md` | Decision guide for upgrade vs full regeneration |
| `validate-domain.md` | Deep validation checklist for a single domain |

## Usage

The skill reads these files during `add-domain` and `upgrade-domain` to understand the reasoning behind each file's shape before generating code.
