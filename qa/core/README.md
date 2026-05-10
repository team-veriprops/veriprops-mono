# core/

The stable, domain-agnostic runtime engine. These files are never generated and should be edited with care — changes here affect every domain.

## Files

| File | Role |
|---|---|
| `types.ts` | All platform types. The single source of truth. |
| `event-bus.ts` | Typed singleton event emitter. Orchestrator emits; CLI and logger subscribe. |
| `dependency-graph.ts` | Topological sort (Kahn's algorithm) and DFS cycle detection for `dependsOn`. |
| `cache.ts` | File-backed, TTL-aware cache for idempotent bootstrap steps. |
| `manifest.ts` | Reads/writes `domain-manifest.json`. Validates `schemaVersion` on load. |
| `registry.ts` | In-memory domain registry. Detects ghost, orphan, and stale-schema domains. |
| `discovery.ts` | Dynamic domain import, shape validation, and filesystem scanning. |
| `preflight.ts` | Pre-run validation gate. Blocks on errors; warns and continues on warnings. |
| `assertions.ts` | Pure assertion helpers returning `AssertionResult`. Never throw. |
| `forensic.ts` | Screenshot/DOM/JSON capture on step failure. Manages artifact retention. |
| `flow-engine.ts` | Step dispatcher. Resolves selectors and `{{interpolation}}` tokens. |
| `api-runner.ts` | Stateful HTTP client with cookie jar for API-mode journeys. |
| `browser-runner.ts` | Playwright browser lifecycle. Three-tier app-readiness detection. |
| `runner.ts` | Single domain execution: bootstrap → journeys → teardown. |
| `orchestrator.ts` | Full run: preflight → topo sort → execute → NDJSON stream → report → prune. |

## Governance

> The runtime must never import from `qa/domains/`. Domains import from `qa/core/`. The skill bridges the two.

## Schema versioning

`CURRENT_SCHEMA_VERSION` in `types.ts` is the authoritative version string. When the `DomainContract` or `Domain` interface gains a required field, bump this version and update the skill templates. See `CONTRIBUTING.md` for the full process.
