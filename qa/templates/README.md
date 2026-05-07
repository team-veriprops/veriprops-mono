# templates/

Annotated TypeScript templates used by the Claude Code skill when generating domain files.

These files are read by the skill — they are not executed by the runtime.

## Domain templates

Located in `templates/domain/`. Each `.tpl` file is an annotated TypeScript file with `// [CLAUDE: ...]` comments that guide the skill on how to fill in real values.

| Template | Generated file |
|---|---|
| `contract.ts.tpl` | `domains/<name>/contract.ts` |
| `selectors.ts.tpl` | `domains/<name>/selectors.ts` |
| `fixtures.ts.tpl` | `domains/<name>/fixtures.ts` |
| `journeys.ts.tpl` | `domains/<name>/journeys.ts` |
| `assertions.ts.tpl` | `domains/<name>/assertions.ts` |
| `README.md.tpl` | `domains/<name>/README.md` |

## Annotation format

```typescript
// [CLAUDE: Instruction for the skill about this line or block.]
// [CLAUDE: Multiple annotation lines can stack.]
someField: "[PLACEHOLDER]", // [CLAUDE: Replace [PLACEHOLDER] with real value.]
```

The skill reads these annotations and replaces placeholders and examples with values derived from codebase inspection.

## Updating templates

When `core/types.ts` gains a new field on `DomainContract` or `Domain`, update the relevant template(s) to include the new field with an appropriate `[CLAUDE: ...]` annotation. Then bump `CURRENT_SCHEMA_VERSION` and update the skill's `upgrade-domain` command.
