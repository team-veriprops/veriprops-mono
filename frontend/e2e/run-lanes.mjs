/**
 * `pnpm e2e` entry point: the parallel lane, then the `@serial` lane — always both.
 *
 * Specs that touch shared state (`@serial`) must never run beside the rest, and must still run
 * when the parallel lane has failures. Playwright project dependencies can order the lanes but
 * skip the dependants on any failure, so the lanes are two invocations instead:
 *   1. `UAT_LANE=parallel` — every other spec, across `UAT_WORKERS` workers (globalSetup seeds).
 *   2. `UAT_LANE=serial`   — `@serial` specs on one worker, reusing that seed and those sessions.
 * Extra CLI arguments (a spec path, `--grep`, `--project`) are passed to both. A `--project` filter
 * names an engine (`chromium-desktop`); the serial lane's projects are that engine's `-serial`
 * twin, so the filter is renamed for it. The exit code is non-zero when either lane fails.
 *
 * `--live` runs the `@live` lane instead, and only it: the specs that drive the real third
 * parties on a deployed staging (`UAT_BASE_URL`, docs/live-integration-smoke.md).
 */
import { spawnSync } from "node:child_process";

const LIVE_FLAG = "--live";
const live = process.argv.includes(LIVE_FLAG);
const args = process.argv.slice(2).filter((arg) => arg !== LIVE_FLAG);

const SERIAL_SUFFIX = "-serial";

/** `--project=chromium-desktop` / `--project chromium-desktop` → the same engine's serial project. */
function serialLaneArgs(laneArgs) {
  const toSerial = (name) => (name.endsWith(SERIAL_SUFFIX) ? name : `${name}${SERIAL_SUFFIX}`);
  return laneArgs.map((arg, i) => {
    if (arg.startsWith("--project=")) return `--project=${toSerial(arg.slice("--project=".length))}`;
    if (laneArgs[i - 1] === "--project") return toSerial(arg);
    return arg;
  });
}

function runLane(lane, laneArgs, extraEnv) {
  // A filtered run (`pnpm e2e session.spec.ts`) often has nothing for one lane; that lane passing
  // empty is correct, not a failure. The live lane is the exception: it is a release gate, and
  // one that found nothing to run proved nothing.
  const emptyPasses = lane === "live" ? [] : ["--pass-with-no-tests"];
  const result = spawnSync(
    "pnpm",
    ["exec", "playwright", "test", "--config", "e2e/playwright.config.ts", ...emptyPasses, ...laneArgs],
    { stdio: "inherit", shell: true, env: { ...process.env, UAT_LANE: lane, ...extraEnv } },
  );
  return result.status ?? 1;
}

if (live) process.exit(runLane("live", args, {}));

const parallel = runLane("parallel", args, {});
const serial = runLane("serial", serialLaneArgs(args), { UAT_REUSE_SEED: "1" });

process.exit(parallel !== 0 ? parallel : serial);
