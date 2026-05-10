# Contributing

## Adding a domain

Always use the Claude Code skill — never scaffold domains by hand:

```
/qa add-domain
```

The skill reads the codebase, inspects routes and API endpoints, and generates a complete, type-correct domain. Hand-written domains will fail shape validation.

## Editing a domain

Domains in `qa/domains/` are generated artefacts. If you need to change a domain:

1. Edit the relevant source in your application (routes, endpoints, selectors)
2. Run `/qa upgrade-domain` to regenerate the affected domain
3. Review the diff and commit both the app change and the domain update together

If you must make a small manual fix, do it directly and note it in the domain's README so the next upgrade doesn't silently overwrite it.

## Runtime changes

The `qa/core/` and `qa/adapters/` directories are stable runtime code. Changes here affect every domain. Before changing runtime files:

- Check that `CURRENT_SCHEMA_VERSION` in `core/types.ts` does not need bumping
- Run `pnpm typecheck` after any change
- Run `pnpm qa:validate` to confirm no domains are broken

## Bumping schema version

When the `DomainContract` or `Domain` interface gains a required field:

1. Increment `CURRENT_SCHEMA_VERSION` in `core/types.ts` (minor for backwards-compatible additions, major for breaking changes)
2. Update the skill templates in `.claude/skills/qa-domain/templates/` to include the new field
3. Run `/qa validate-all-domains` — stale domains will be flagged
4. Run `/qa upgrade-domain` on each flagged domain

## Running locally

```bash
# Full run
pnpm qa:run

# Single domain
pnpm qa:run -- --domain my-domain

# With visible browser
HEADLESS=false pnpm qa:run

# Validate only (no execution)
pnpm qa:validate
```

## CI integration

```yaml
- name: Run QA
  run: pnpm qa:run
  env:
    ENVIRONMENT: ci
    BASE_URL: ${{ env.FRONTEND_URL }}
    API_BASE_URL: ${{ env.BACKEND_URL }}
    MAILPIT_URL: ${{ env.MAILPIT_URL }}
    OTP_MODE: mailpit
    HEADLESS: true
```

The CLI exits with code `1` on any failure, blocking the pipeline.

## Debugging failures

1. Run `pnpm qa:report` after a failure — failed steps print error detail
2. Check `artifacts/runs/<run-id>/<domain>/<journey>/` for screenshots and DOM snapshots
3. Run `pnpm qa:report --tail` to watch an in-progress run live
4. Set `QA_DEBUG=true` to enable verbose logging from all adapters
