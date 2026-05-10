// ─────────────────────────────────────────────────────────────────────────────
// cli/commands/run.ts
// Executes the QA suite via the orchestrator.
// Attaches progress logger, supports --parallel, --domain filter, --max-runs.
// Exits with code 0 on pass, 1 on any failure.
// ─────────────────────────────────────────────────────────────────────────────

import { loadConfig, attachProgressLogger, Logger } from "../../adapters/logger.js";
import { runAll } from "../../core/orchestrator.js";

const logger = new Logger("run");

interface RunOptions {
  parallel?: boolean;
  domain?: string[];
  filter?: string[];
  runId?: string;
  maxRuns?: number;
}

export async function runCommand(options: RunOptions): Promise<void> {
  const config = loadConfig();

  // --max-runs CLI flag overrides env/config
  if (options.maxRuns !== undefined && options.maxRuns > 0) {
    config.maxRuns = options.maxRuns;
  }

  // Normalise domain filter (--domain and --filter are aliases)
  const domainFilter = [
    ...(options.domain ?? []),
    ...(options.filter ?? []),
  ];

  // Attach live progress output to the event bus
  const detachProgress = attachProgressLogger();

  try {
    const report = await runAll(config, {
      parallel: options.parallel ?? false,
      domainFilter: domainFilter.length > 0 ? domainFilter : undefined,
      runId: options.runId,
    });

    const exitCode =
      report.status === "pass" ? 0 : 1;

    if (exitCode !== 0) {
      logger.error(
        `Run completed with status: ${report.status.toUpperCase()}. ` +
          `${report.summary.failed + report.summary.errors} domain(s) failed.`
      );
    }

    process.exit(exitCode);
  } catch (err) {
    logger.error("Unexpected error during run:", err instanceof Error ? err.message : err);
    process.exit(1);
  } finally {
    detachProgress();
  }
}
