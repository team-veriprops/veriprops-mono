# Architecture

## Three-layer model

```
┌─────────────────────────────────────────────────────┐
│  Claude Code Skill  (.claude/skills/qa-domain/)     │
│  Reads codebase → generates domains                 │
│  Only bridge between runtime and domains            │
└───────────────────┬─────────────────────────────────┘
                    │ generates
                    ▼
┌─────────────────────────────────────────────────────┐
│  Domain Layer  (qa/domains/<name>/)                 │
│  contract · selectors · fixtures · journeys         │
│  assertions · index.ts                              │
│  Generated — never hand-edited                      │
└───────────────────┬─────────────────────────────────┘
                    │ loaded by
                    ▼
┌─────────────────────────────────────────────────────┐
│  Runtime Layer  (qa/core/ · qa/adapters/)           │
│  Stable, domain-agnostic engine                     │
│  Never knows about specific domains                 │
└─────────────────────────────────────────────────────┘
```

**Governance rules:**
- Runtime never imports from `domains/`
- Domains never contain runtime logic
- The skill is the only entity that knows both

## Core modules

| Module | Role |
|---|---|
| `types.ts` | Single source of truth for all types |
| `manifest.ts` | Reads/writes `domain-manifest.json` |
| `registry.ts` | In-memory domain registry |
| `discovery.ts` | Dynamic domain import and shape validation |
| `event-bus.ts` | Typed event emitter for observability |
| `dependency-graph.ts` | Topological sort and cycle detection |
| `cache.ts` | Idempotent bootstrap step cache |
| `preflight.ts` | Pre-run validation gate |
| `assertions.ts` | Pure assertion helpers |
| `forensic.ts` | Failure artifact capture and run pruning |
| `flow-engine.ts` | Step dispatcher and journey executor |
| `api-runner.ts` | Stateful HTTP client with cookie jar |
| `browser-runner.ts` | Playwright lifecycle and app-ready detection |
| `runner.ts` | Single domain execution (bootstrap → journeys → teardown) |
| `orchestrator.ts` | Full run coordination |

## Execution flow

```
pnpm qa:run
  │
  ├─ loadConfig()          Read env vars / .env file
  ├─ pruneExpiredCache()   Housekeeping
  ├─ loadManifest()        Read domain-manifest.json
  ├─ discoverDomains()     Dynamic import + shape validation
  ├─ runPreflight()        Env vars · schema versions · dep cycles · ghosts
  ├─ topologicalSort()     Resolve dependsOn ordering
  ├─ pruneOldRuns()        Enforce MAX_RUNS retention
  │
  └─ for each domain (sequential) / Promise.allSettled (parallel):
       ├─ runBootstrap()   Execute session fixtures (cache-aware)
       ├─ runJourneys()    Browser or API mode
       │    └─ FlowEngine.executeJourney()
       │         └─ for each step: dispatch → capture on fail → emit events
       └─ runTeardown()    Clean up session state
```

## Schema versioning

Every domain contract and the manifest carry `schemaVersion`. The runtime declares `CURRENT_SCHEMA_VERSION` in `core/types.ts`.

- **Major version mismatch** → hard error, run blocked
- **Minor version mismatch** → warning, run proceeds
- **Missing version** → warning on load

## App readiness detection

The browser runner uses a three-tier strategy per domain:

1. `window.__app_ready === true` (set by frontend after hydration)
2. `appReadySelector` visible (from `domain.contract.appReadySelector` → `QAConfig.appReadySelector`)
3. `networkidle` fallback (always attempted if 1 and 2 time out)

## Artifact structure

```
artifacts/
  runs/
    <run-uuid>/
      run.ndjson          Live event stream
      report.json         Final structured report
      <domain>/
        <journey>/
          screenshot-*.png
          dom-*.html
          data-*.json
          run.log
```

Runs are pruned to `MAX_RUNS` at the start of each new run.
