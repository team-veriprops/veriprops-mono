# templates/domain/

Annotated TypeScript templates for domain file generation.

Each file is a valid TypeScript file that the skill reads, annotates, and uses to generate real domain files in `qa/domains/<name>/`.

## How the skill uses these files

1. The skill reads `core/types.ts` to understand the current `DomainContract` and `Domain` shape
2. It reads these templates to understand the expected file structure and annotation conventions
3. It inspects the codebase (routes, API endpoints, DB models, UI components)
4. It generates domain files by combining template structure with real codebase values

## Annotation conventions

- `[DOMAIN_NAME]` — replaced with the kebab-case domain name
- `[PLACEHOLDER]` — replaced with a value derived from codebase inspection
- `// [CLAUDE: ...]` — instruction to the skill; removed from generated output
- Commented-out code blocks — optional patterns shown as examples; included or excluded based on domain needs

## Files

| File | Purpose |
|---|---|
| `contract.ts.tpl` | Domain identity, schema version, flags |
| `selectors.ts.tpl` | UI element selector map |
| `fixtures.ts.tpl` | Session declarations and bootstrap steps |
| `journeys.ts.tpl` | User flow step sequences |
| `assertions.ts.tpl` | Domain-specific assertion functions |
| `README.md.tpl` | Domain documentation scaffold |
