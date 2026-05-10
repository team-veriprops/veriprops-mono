// ─────────────────────────────────────────────────────────────────────────────
// cli/commands/report.ts
// Displays reports from completed runs. Supports text, JSON, and HTML formats.
// Can live-tail the NDJSON event stream for in-progress runs (--tail).
// Prunes old artifact directories when --max-runs is specified.
// ─────────────────────────────────────────────────────────────────────────────

import fs from "node:fs";
import path from "node:path";
import readline from "node:readline";
import { loadConfig, Logger } from "../../adapters/logger.js";
import { pruneOldRuns } from "../../core/forensic.js";
import type { RunReport } from "../../core/types.js";

const logger = new Logger("report");

interface ReportOptions {
  runId?: string;
  format?: "text" | "json" | "html";
  tail?: boolean;
  maxRuns?: number;
}

export async function reportCommand(options: ReportOptions): Promise<void> {
  const config = loadConfig();
  const format = options.format ?? "text";

  // Optional pruning before display
  if (options.maxRuns !== undefined && options.maxRuns > 0) {
    pruneOldRuns(config.artifactsDir, options.maxRuns);
  }

  const runsDir = path.resolve(config.artifactsDir, "runs");

  // ── Resolve run directory ─────────────────────────────────────────────────
  let runDir: string;

  if (options.runId) {
    runDir = path.join(runsDir, options.runId);
    if (!fs.existsSync(runDir)) {
      logger.error(`Run "${options.runId}" not found in ${runsDir}`);
      process.exit(1);
    }
  } else {
    // Find the most recently modified run directory
    runDir = findLatestRunDir(runsDir);
    if (!runDir) {
      logger.error(`No runs found in ${runsDir}. Run "pnpm qa:run" first.`);
      process.exit(1);
    }
  }

  // ── Live tail mode ────────────────────────────────────────────────────────
  if (options.tail) {
    await tailNdjson(runDir);
    return;
  }

  // ── Load report ───────────────────────────────────────────────────────────
  const reportPath = path.join(runDir, "report.json");
  if (!fs.existsSync(reportPath)) {
    logger.error(`report.json not found in ${runDir}. The run may still be in progress — use --tail.`);
    process.exit(1);
  }

  const report: RunReport = JSON.parse(fs.readFileSync(reportPath, "utf-8"));

  // ── Render ────────────────────────────────────────────────────────────────
  switch (format) {
    case "json":
      console.log(JSON.stringify(report, null, 2));
      break;
    case "html":
      console.log(renderHtml(report));
      break;
    case "text":
    default:
      renderText(report, runDir);
  }
}

// ─── Text renderer ────────────────────────────────────────────────────────────

function renderText(report: RunReport, runDir: string): void {
  const statusIcon: Record<string, string> = {
    pass: "✅", fail: "❌", partial: "⚠️ ", error: "💥", skipped: "⏭️ ",
  };

  console.log("\n─────────────────────────────────────────");
  console.log(`  Run ID   : ${report.runId}`);
  console.log(`  Status   : ${statusIcon[report.status] ?? "?"} ${report.status.toUpperCase()}`);
  console.log(`  Env      : ${report.environment}`);
  console.log(`  Started  : ${report.startedAt}`);
  console.log(`  Duration : ${(report.durationMs / 1000).toFixed(2)}s`);
  console.log(`  Artifacts: ${runDir}`);
  console.log("─────────────────────────────────────────\n");

  for (const domain of report.domains) {
    const icon = statusIcon[domain.status] ?? "?";
    console.log(`  ${icon}  ${domain.domainName}  (${domain.durationMs}ms)`);
    if (domain.error) {
      console.log(`       ✗ Error: ${domain.error}`);
    }
    for (const journey of domain.journeys) {
      const jIcon = statusIcon[journey.status] ?? "?";
      console.log(`       ${jIcon}  ${journey.journeyName}  (${journey.durationMs}ms)`);
      for (const step of journey.steps) {
        if (step.status === "fail") {
          console.log(`            ✗ ${step.label}: ${step.error ?? "(no detail)"}`);
        }
      }
    }
  }

  console.log("\n─────────────────────────────────────────");
  const s = report.summary;
  console.log(
    `  ✅ ${s.passed} passed  ❌ ${s.failed} failed  ⚠️  ${s.partial} partial  💥 ${s.errors} errors  ⏭️  ${s.skipped} skipped`
  );
  console.log("─────────────────────────────────────────\n");
}

// ─── HTML renderer ────────────────────────────────────────────────────────────

function renderHtml(report: RunReport): string {
  const statusColour: Record<string, string> = {
    pass: "#22c55e", fail: "#ef4444", partial: "#f59e0b",
    error: "#dc2626", skipped: "#6b7280",
  };

  const rows = report.domains
    .map((d) => {
      const colour = statusColour[d.status] ?? "#6b7280";
      const journeyRows = d.journeys
        .map(
          (j) =>
            `<tr><td style="padding-left:2em">${j.journeyName}</td>` +
            `<td style="color:${statusColour[j.status] ?? "#6b7280"}">${j.status}</td>` +
            `<td>${j.durationMs}ms</td></tr>`
        )
        .join("");
      return (
        `<tr><td><strong>${d.domainName}</strong></td>` +
        `<td style="color:${colour}">${d.status}</td>` +
        `<td>${d.durationMs}ms</td></tr>` +
        journeyRows
      );
    })
    .join("");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>QA Report — ${report.runId}</title>
  <style>
    body { font-family: monospace; padding: 2rem; background: #0f172a; color: #e2e8f0; }
    h1 { color: #94a3b8; font-size: 1.25rem; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th { text-align: left; padding: 0.5rem 1rem; background: #1e293b; color: #94a3b8; }
    td { padding: 0.35rem 1rem; border-bottom: 1px solid #1e293b; }
    .meta { color: #64748b; font-size: 0.85rem; margin-bottom: 1rem; }
  </style>
</head>
<body>
  <h1>QA Run Report</h1>
  <p class="meta">
    ID: ${report.runId} &nbsp;|&nbsp;
    Status: <strong style="color:${statusColour[report.status] ?? "#fff"}">${report.status.toUpperCase()}</strong> &nbsp;|&nbsp;
    ${(report.durationMs / 1000).toFixed(2)}s &nbsp;|&nbsp;
    ${report.environment}
  </p>
  <table>
    <thead><tr><th>Domain / Journey</th><th>Status</th><th>Duration</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
</body>
</html>`;
}

// ─── NDJSON live tail ─────────────────────────────────────────────────────────

async function tailNdjson(runDir: string): Promise<void> {
  const ndjsonPath = path.join(runDir, "run.ndjson");
  const pollMs = 500;
  const maxWaitMs = 60000;
  let waited = 0;

  // Wait for the file to appear if run just started
  while (!fs.existsSync(ndjsonPath) && waited < maxWaitMs) {
    await sleep(pollMs);
    waited += pollMs;
  }

  if (!fs.existsSync(ndjsonPath)) {
    logger.error(`run.ndjson not found in ${runDir} after ${maxWaitMs / 1000}s`);
    process.exit(1);
  }

  console.log(`\nTailing: ${ndjsonPath}\n`);

  let offset = 0;
  let complete = false;

  while (!complete) {
    const stat = fs.statSync(ndjsonPath);
    if (stat.size > offset) {
      const buffer = Buffer.alloc(stat.size - offset);
      const fd = fs.openSync(ndjsonPath, "r");
      fs.readSync(fd, buffer, 0, buffer.length, offset);
      fs.closeSync(fd);
      offset = stat.size;

      const lines = buffer.toString("utf-8").split("\n").filter(Boolean);
      for (const line of lines) {
        try {
          const event = JSON.parse(line) as { type?: string };
          console.log(line);
          if (event.type === "run:complete") complete = true;
        } catch {
          console.log(line);
        }
      }
    }

    if (!complete) await sleep(pollMs);
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function findLatestRunDir(runsDir: string): string {
  if (!fs.existsSync(runsDir)) return "";

  const entries = fs
    .readdirSync(runsDir, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => ({
      fullPath: path.join(runsDir, e.name),
      mtimeMs: fs.statSync(path.join(runsDir, e.name)).mtimeMs,
    }))
    .sort((a, b) => b.mtimeMs - a.mtimeMs);

  return entries[0]?.fullPath ?? "";
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
