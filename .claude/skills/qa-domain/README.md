# QA Domain Skill

Claude Code skill for generating and managing QA domains in this monorepo.

## What this skill does

Reads the codebase to understand routes, API endpoints, UI components, and data models — then generates complete, type-correct QA domain modules in `qa/domains/`.

## Commands

| Command | Description |
|---|---|
| `/qa init-qa-platform` | First-time platform setup |
| `/qa add-domain` | Generate a new domain from codebase inspection |
| `/qa upgrade-domain` | Regenerate a domain after app changes |
| `/qa remove-domain` | Remove a domain and deregister it |
| `/qa scan-domains` | List all domains and their status |
| `/qa sync-domains` | Sync manifest with filesystem |
| `/qa validate-domain` | Validate a single domain |
| `/qa validate-all-domains` | Validate all domains |
| `/qa drift-report` | Report schema version drift |

## Quick start

```
/qa add-domain
```

Claude will ask which feature area to cover, inspect the codebase, and generate a complete domain.

## Reference

- Full instructions: `SKILL.md`
- Command details: `commands/`
- File templates: `templates/`
- Runtime types: `qa/core/types.ts`
- Domain templates: `qa/templates/domain/`
