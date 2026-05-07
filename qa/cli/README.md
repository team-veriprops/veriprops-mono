# cli/

Command-line interface for the QA platform.

## Commands

### `qa init [--skip-checks]`

Initialises the platform: creates the artifacts directory, clears the step cache, seeds the manifest if absent, and checks connectivity to backend, frontend, and Mailpit.

Use `--skip-checks` in CI environments where services start after this step.

### `qa run [options]`

Runs all enabled domains through the orchestrator.

| Flag | Description |
|---|---|
| `--parallel` | Run domains concurrently (use only with isolated test environments) |
| `--domain <names...>` | Run specific domains by name |
| `--filter <names...>` | Alias for `--domain` |
| `--run-id <id>` | Override the auto-generated run UUID |
| `--max-runs <n>` | Override artifact retention for this run |

Exits `0` on pass, `1` on any failure or error.

### `qa validate [options]`

Validates all registered domains without executing them.

Checks: domain shape, schema version, dependency cycles, ghost/orphan detection, unregistered directories.

| Flag | Description |
|---|---|
| `--fix` | Auto-repair fixable issues (remove ghosts, register orphans as disabled) |
| `--domain <name>` | Validate a single domain |

Exits `0` if no errors, `1` if errors found.

### `qa report [options]`

Displays the report from the latest completed run.

| Flag | Description |
|---|---|
| `--run-id <id>` | Display a specific run by UUID |
| `--format text\|json\|html` | Output format (default: `text`) |
| `--tail` | Live-tail the NDJSON event stream |
| `--max-runs <n>` | Prune old runs before displaying |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All domains passed |
| `1` | One or more domains failed, errored, or validation found errors |
