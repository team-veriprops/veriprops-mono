# QA Platform

Domain-agnostic integration testing platform for the monorepo. Generates, runs, and reports on QA domains using Playwright and a typed runtime.

## Quick start

```bash
# Install dependencies
pnpm install

# Copy environment config
cp .env.example .env
# Edit .env with your local service URLs

# Initialise (checks connectivity, creates artifacts dir)
pnpm qa:init

# Run all domains
pnpm qa:run

# View the latest report
pnpm qa:report
```

## Commands

| Command | Description |
|---|---|
| `pnpm qa:init` | Initialise platform, check connectivity |
| `pnpm qa:run` | Run all enabled domains (sequential) |
| `pnpm qa:run:parallel` | Run all domains in parallel |
| `pnpm qa:validate` | Validate domain shape, schema, deps |
| `pnpm qa:validate:fix` | Validate and auto-repair fixable issues |
| `pnpm qa:report` | Display latest run report |
| `pnpm qa:report --format html` | HTML report |
| `pnpm qa:report --tail` | Live-tail an in-progress run |
| `pnpm typecheck` | TypeScript type check (no emit) |

## Adding a new domain

Use the Claude Code skill:

```
/qa add-domain
```

The skill inspects the codebase, generates a complete domain scaffold, and registers it in the manifest.

## Directory structure

```
qa/
  core/         Runtime engine — never edit directly
  adapters/     Service integrations (Playwright, Mailpit, Backend)
  cli/          Command-line interface
  templates/    Annotated TypeScript templates used by the skill
  domains/      Generated domain modules — one subdirectory per domain
  artifacts/    Run outputs, screenshots, reports (gitignored)
```

## Environment variables

See `.env.example` for the full reference. Key variables:

| Variable | Default | Description |
|---|---|---|
| `BASE_URL` | `http://localhost:3000` | Frontend URL |
| `API_BASE_URL` | `http://localhost:8000` | Backend API URL |
| `MAILPIT_URL` | `http://localhost:8025` | Mailpit email server |
| `OTP_MODE` | `mailpit` | `mailpit` or `static` |
| `HEADLESS` | `true` | Run browser headless |
| `APP_READY_SELECTOR` | — | CSS selector fallback for app readiness |
| `MAX_RUNS` | `20` | Artifact directories to retain |
| `CACHE_TTL` | `3600` | Idempotent step cache TTL (seconds) |

## Further reading

- [ARCHITECTURE.md](./ARCHITECTURE.md) — Design decisions and layer boundaries
- [CONTRIBUTING.md](./CONTRIBUTING.md) — How to work with this platform
- [core/README.md](./core/README.md) — Runtime internals
- [.claude/skills/qa-domain/SKILL.md](../.claude/skills/qa-domain/SKILL.md) — Claude Code skill reference
