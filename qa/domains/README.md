# domains/

Generated domain modules live here. Each subdirectory is one QA domain.

## Structure

```
domains/
  <domain-name>/
    index.ts        Default export — the Domain object consumed by the runtime
    contract.ts     Identity, schema version, dependencies, flags
    selectors.ts    CSS/XPath selector map
    fixtures.ts     Session declarations and bootstrap steps
    journeys.ts     User flow definitions
    assertions.ts   Domain-specific assertion functions
    README.md       Human-readable domain documentation
```

## Rules

- **Never hand-edit these files.** Use the Claude Code skill (`/qa add-domain`, `/qa upgrade-domain`).
- **One domain per directory.** The directory name must match `contract.name`.
- **Domains are registered in `domain-manifest.json`.** A domain directory without a manifest entry is an orphan — run `pnpm qa:validate --fix` to register it.

## Adding a domain

```
/qa add-domain
```

## Upgrading a domain after an app change

```
/qa upgrade-domain
```

## Listing domain status

```
pnpm qa:validate
```
