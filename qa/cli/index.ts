#!/usr/bin/env tsx
// ─────────────────────────────────────────────────────────────────────────────
// cli/index.ts
// QA platform CLI entry point.
// Commands: init | run | validate | report
// ─────────────────────────────────────────────────────────────────────────────

import { Command } from "commander";
import { initCommand } from "./commands/init.js";
import { runCommand } from "./commands/run.js";
import { validateCommand } from "./commands/validate.js";
import { reportCommand } from "./commands/report.js";

const program = new Command();

program
  .name("qa")
  .description("Domain-agnostic QA platform CLI")
  .version("1.0.0");

// ── init ──────────────────────────────────────────────────────────────────────
program
  .command("init")
  .description("Initialise the QA platform: check connectivity, create artifacts dir, seed manifest")
  .option("--skip-checks", "Skip connectivity checks (useful in CI without services)")
  .action(initCommand);

// ── run ───────────────────────────────────────────────────────────────────────
program
  .command("run")
  .description("Run all enabled QA domains")
  .option("--parallel", "Run domains in parallel (use only when test isolation is guaranteed)")
  .option("--domain <names...>", "Run specific domains by name")
  .option("--filter <names...>", "Alias for --domain")
  .option("--run-id <id>", "Override the generated run UUID")
  .option("--max-runs <n>", "Override MAX_RUNS artifact retention for this run", parseInt)
  .action(runCommand);

// ── validate ──────────────────────────────────────────────────────────────────
program
  .command("validate")
  .description("Validate all domains: shape, schema versions, dependency cycles, ghost/orphans")
  .option("--fix", "Auto-repair fixable issues (manifest sync, name mismatches)")
  .option("--domain <name>", "Validate a single domain by name")
  .action(validateCommand);

// ── report ────────────────────────────────────────────────────────────────────
program
  .command("report")
  .description("Display the report from the latest (or specified) run")
  .option("--run-id <id>", "Display report for a specific run ID")
  .option("--format <fmt>", "Output format: text | json | html", "text")
  .option("--tail", "Live-tail the NDJSON event stream for an in-progress run")
  .option("--max-runs <n>", "Prune runs older than this count before displaying", parseInt)
  .action(reportCommand);

program.parseAsync(process.argv).catch((err: unknown) => {
  console.error("[qa] Fatal error:", err instanceof Error ? err.message : err);
  process.exit(1);
});
