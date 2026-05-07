// ─────────────────────────────────────────────────────────────────────────────
// core/orchestrator.ts
// Top-level run coordinator.
// Pre-flight validation → topological sort → sequential/parallel execution
// → NDJSON streaming → final report → artifact pruning.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import type {
  DomainRunResult,
  QAConfig,
  RunReport,
  RunSummary,
  ValidationIssue,
} from "./types.js";
import { loadManifest } from "./manifest.js";
import { discoverDomains } from "./discovery.js";
import { registry } from "./registry.js";
import { eventBus } from "./event-bus.js";
import { DomainRunner } from "./runner.js";
import { pruneOldRuns } from "./forensic.js";
import { pruneExpiredCache } from "./cache.js";
import {
  topologicalSort,
  formatSortDiagnostics,
  type GraphNode,
} from "./dependency-graph.js";
import { runPreflight } from "./preflight.js";

export interface RunOptions {
  parallel?: boolean;
  domainFilter?: string[];
  runId?: string;
}

// ─── Main entry point ─────────────────────────────────────────────────────────

export async function runAll(
  config: QAConfig,
  options: RunOptions = {}
): Promise<RunReport> {
  const runId = options.runId ?? crypto.randomUUID();
  const startedAt = new Date().toISOString();

  // ── Housekeeping ──────────────────────────────────────────────────────────
  pruneExpiredCache(config.cacheTtl);

  // ── Load manifest and discover domains ───────────────────────────────────
  const manifest = loadManifest();
  await discoverDomains(manifest);

  let domains = registry.getAll();

  // Apply domain filter if provided
  if (options.domainFilter && options.domainFilter.length > 0) {
    domains = domains.filter((d) =>
      options.domainFilter!.includes(d.contract.name)
    );
  }

  // ── Pre-flight validation ─────────────────────────────────────────────────
  const preflight = await runPreflight(config, manifest, domains);

  if (!preflight.valid) {
    await eventBus.emit("preflight:fail", {
      runId,
      issues: preflight.issues,
    });

    const errors = preflight.issues.filter((i) => i.severity === "error");
    if (errors.length > 0) {
      console.error("\n[orchestrator] Pre-flight failed. Fix the following errors:\n");
      for (const issue of errors) {
        const loc = issue.domain ? ` [${issue.domain}]` : "";
        console.error(`  ✗${loc} ${issue.message}`);
      }
      console.error('\nRun "pnpm qa:validate --fix" to auto-repair where possible.\n');
      process.exit(1);
    }

    // Warnings only — proceed with notice
    console.warn("\n[orchestrator] Pre-flight warnings:\n");
    for (const issue of preflight.issues) {
      const loc = issue.domain ? ` [${issue.domain}]` : "";
      console.warn(`  ⚠${loc} ${issue.message}`);
    }
    console.warn("");
  } else {
    await eventBus.emit("preflight:pass", {
      runId,
      domainsChecked: domains.length,
    });
  }

  // ── Topological sort ──────────────────────────────────────────────────────
  const nodes: GraphNode[] = domains.map((d) => ({
    name: d.contract.name,
    dependsOn: d.contract.dependsOn ?? [],
  }));

  const sortResult = topologicalSort(nodes);

  if (!sortResult.ok) {
    const diagnostics = formatSortDiagnostics(sortResult);
    console.error("\n[orchestrator] Dependency resolution failed:\n");
    for (const line of diagnostics) console.error(`  ${line}`);
    process.exit(1);
  }

  if (sortResult.missing.length > 0) {
    console.warn("\n[orchestrator] Missing dependency references:");
    for (const m of sortResult.missing) console.warn(`  ⚠ ${m}`);
    console.warn("");
  }

  // Reorder domains according to topo sort
  const domainMap = new Map(domains.map((d) => [d.contract.name, d]));
  const orderedDomains = sortResult.order
    .map((name) => domainMap.get(name))
    .filter(Boolean) as (typeof domains)[number][];

  // ── Artifact setup ────────────────────────────────────────────────────────
  const artifactsRunDir = path.resolve(config.artifactsDir, "runs", runId);
  fs.mkdirSync(artifactsRunDir, { recursive: true });
  pruneOldRuns(config.artifactsDir, config.maxRuns);

  // ── NDJSON stream setup ───────────────────────────────────────────────────
  const ndjsonPath = path.join(artifactsRunDir, "run.ndjson");
  const ndjsonStream = fs.createWriteStream(ndjsonPath, { flags: "a" });

  const writeNdjson = (record: unknown) => {
    try {
      ndjsonStream.write(JSON.stringify(record) + "\n");
    } catch {
      // Non-fatal — NDJSON is supplementary
    }
  };

  // Subscribe event bus to stream events
  const unsub = eventBus.on("domain:end", (event) => {
    writeNdjson(event);
  });

  // ── Emit run start ────────────────────────────────────────────────────────
  await eventBus.emit("run:start", {
    runId,
    domains: orderedDomains.map((d) => d.contract.name),
  });

  writeNdjson({
    type: "run:start",
    runId,
    startedAt,
    domains: orderedDomains.map((d) => d.contract.name),
  });

  console.log(`\n[orchestrator] Run ${runId}`);
  console.log(`  Domains : ${orderedDomains.length}`);
  console.log(`  Mode    : ${options.parallel ? "parallel" : "sequential"}`);
  console.log(`  Started : ${startedAt}\n`);

  // ── Execute domains ───────────────────────────────────────────────────────
  let domainResults: DomainRunResult[];

  if (options.parallel) {
    domainResults = await runParallel(orderedDomains, config, runId);
  } else {
    domainResults = await runSequential(orderedDomains, config, runId);
  }

  // ── Build final report ────────────────────────────────────────────────────
  const completedAt = new Date().toISOString();
  const durationMs =
    new Date(completedAt).getTime() - new Date(startedAt).getTime();

  const summary = buildSummary(domainResults);
  const runStatus =
    summary.failed > 0 || summary.errors > 0
      ? summary.passed > 0
        ? "partial"
        : "fail"
      : "pass";

  const report: RunReport = {
    runId,
    startedAt,
    completedAt,
    durationMs,
    status: runStatus,
    environment: config.environment,
    domains: domainResults,
    summary,
  };

  // ── Write report ──────────────────────────────────────────────────────────
  const reportPath = path.join(artifactsRunDir, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2) + "\n", "utf-8");

  writeNdjson({ type: "run:complete", runId, completedAt, summary });
  ndjsonStream.end();
  unsub();

  await eventBus.emit("run:complete", { runId, report });

  // ── Print summary ─────────────────────────────────────────────────────────
  printSummary(report);

  return report;
}

// ─── Sequential execution ─────────────────────────────────────────────────────

async function runSequential(
  domains: ReturnType<typeof registry.getAll>,
  config: QAConfig,
  runId: string
): Promise<DomainRunResult[]> {
  const results: DomainRunResult[] = [];
  const runner = new DomainRunner(config, runId);

  for (const domain of domains) {
    console.log(`  → ${domain.contract.name}`);
    const result = await runner.runDomain(domain);
    results.push(result);
  }

  return results;
}

// ─── Parallel execution ───────────────────────────────────────────────────────

async function runParallel(
  domains: ReturnType<typeof registry.getAll>,
  config: QAConfig,
  runId: string
): Promise<DomainRunResult[]> {
  const settled = await Promise.allSettled(
    domains.map((domain) => {
      const runner = new DomainRunner(config, runId);
      return runner.runDomain(domain);
    })
  );

  return settled.map((result, i) => {
    if (result.status === "fulfilled") return result.value;
    return {
      domainName: domains[i]?.contract.name ?? "unknown",
      status: "error" as const,
      journeys: [],
      durationMs: 0,
      error: result.reason instanceof Error ? result.reason.message : String(result.reason),
    };
  });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function buildSummary(results: DomainRunResult[]): RunSummary {
  return {
    total: results.length,
    passed: results.filter((r) => r.status === "pass").length,
    failed: results.filter((r) => r.status === "fail").length,
    partial: results.filter((r) => r.status === "partial").length,
    skipped: results.filter((r) => r.status === "skipped").length,
    errors: results.filter((r) => r.status === "error").length,
  };
}

function printSummary(report: RunReport): void {
  const statusIcon: Record<string, string> = {
    pass: "✅",
    fail: "❌",
    partial: "⚠️ ",
    error: "💥",
    skipped: "⏭️ ",
  };

  console.log("\n─────────────────────────────────────────");
  console.log(`  Run ID  : ${report.runId}`);
  console.log(`  Status  : ${statusIcon[report.status] ?? "?"} ${report.status.toUpperCase()}`);
  console.log(`  Duration: ${(report.durationMs / 1000).toFixed(2)}s`);
  console.log("─────────────────────────────────────────");

  for (const domain of report.domains) {
    const icon = statusIcon[domain.status] ?? "?";
    console.log(`  ${icon}  ${domain.contract?.name ?? domain.domainName}`);
    for (const journey of domain.journeys) {
      const jIcon = statusIcon[journey.status] ?? "?";
      console.log(`       ${jIcon}  ${journey.journeyName} (${journey.durationMs}ms)`);
    }
  }

  console.log("─────────────────────────────────────────");
  console.log(
    `  ✅ ${report.summary.passed}  ❌ ${report.summary.failed}  ⚠️  ${report.summary.partial}  💥 ${report.summary.errors}  ⏭️  ${report.summary.skipped}`
  );
  console.log("─────────────────────────────────────────\n");
}
