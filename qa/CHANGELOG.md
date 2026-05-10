# Changelog

## [1.0.0] — Initial release

### Added

- Three-layer architecture: Skill → Domain → Runtime
- `core/types.ts` — full typed surface with `schemaVersion`, `dependsOn`, `otpPattern`, `appReadySelector`, `idempotent`, event types
- `core/event-bus.ts` — typed singleton event emitter for observability
- `core/dependency-graph.ts` — Kahn's algorithm topological sort with DFS cycle detection
- `core/cache.ts` — SHA-256 keyed, TTL-aware, file-backed idempotent step cache
- `core/preflight.ts` — pre-run validation gate (env vars, schema versions, dep cycles, ghost domains)
- `core/manifest.ts` — schema version validation on load with major/minor mismatch distinction
- `core/registry.ts` — domain registry with stale schema version detection
- `core/forensic.ts` — artifact capture with `MAX_RUNS` retention pruning
- `core/flow-engine.ts` — `{{token}}` interpolation with named warnings on `undefined` resolution
- `core/orchestrator.ts` — NDJSON event stream, topological execution order, pre-flight gate
- `adapters/backend.ts` — absorbs `storage.ts` snapshot/serialise helpers
- `adapters/mailpit.ts` — per-domain `otpPattern` override with RegExp compilation and fallback
- `adapters/playwright.ts` — three-tier `waitForAppReady` with domain contract override
- `adapters/logger.ts` — event bus progress subscriber, `attachProgressLogger()`
- CLI: `init`, `run`, `validate`, `report` commands
- `--max-runs` flag on `run` and `report` for per-invocation retention override
- `--tail` flag on `report` for live NDJSON stream following
- Cycle detection output in `validate` command
- Annotated TypeScript domain templates with `// [CLAUDE: ...]` annotations
- Full documentation: README, ARCHITECTURE, CONTRIBUTING, per-directory READMEs
- Claude Code skill: SKILL.md, 9 commands, 7 templates

### Design decisions

- `storage.ts` removed — `snapshot()` merged into `BackendAdapter`
- Sequential execution default, `--parallel` opt-in
- Fixtures declare bootstrap needs (not auto-reset)
- `qa/.env` for local dev, pure env vars in CI
