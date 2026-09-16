/**
 * `pnpm e2e` entry point: the parallel lane, then the `@serial` lane — always both.
 *
 * Specs that touch shared state (`@serial`) must never run beside the rest, and must still run
 * when the parallel lane has failures. Playwright project dependencies can order the lanes but
 * skip the dependants on any failure, so the lanes are two invocations instead:
 *   1. `UAT_LANE=parallel` — every other spec, across `UAT_WORKERS` workers (globalSetup seeds).
 *   2. `UAT_LANE=serial`   — `@serial` specs on one worker, reusing that seed and those sessions.
 * Extra CLI arguments (a spec path, `--grep`, `--project`) are passed to both. The exit code is
 * non-zero when either lane fails.
 */
import { spawnSync } from "node:child_process";

const args = process.argv.slice(2);

function runLane(lane, extraEnv) {
  const result = spawnSync(
    "pnpm",
    // A filtered run (`pnpm e2e session.spec.ts`) often has nothing for one lane; that lane
    // passing empty is correct, not a failure.
    ["exec", "playwright", "test", "--config", "e2e/playwright.config.ts", "--pass-with-no-tests", ...args],
    { stdio: "inherit", shell: true, env: { ...process.env, UAT_LANE: lane, ...extraEnv } },
  );
  return result.status ?? 1;
}

const parallel = runLane("parallel", {});
const serial = runLane("serial", { UAT_REUSE_SEED: "1" });

process.exit(parallel !== 0 ? parallel : serial);
