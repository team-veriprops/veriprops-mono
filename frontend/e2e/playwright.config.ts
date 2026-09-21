/**
 * Veriprops UAT suite — browser-driven acceptance (docs/uat-strategy.md).
 *
 * A green run across the engine matrix *is* the acceptance signal (§1), so the config
 * optimises for trustworthiness first, then speed: one reset+seed per run, parallel workers for
 * specs that own their data, a strictly one-at-a-time lane for specs that touch shared state,
 * and a full artifact trail on every failure so a stakeholder can inspect a red without
 * re-running it.
 *
 * Run: `pnpm e2e` (e2e/run-lanes.mjs) — see §9 for the stack the suite expects to be running.
 */
import { defineConfig, devices, Project } from "@playwright/test";

import { BASE_URL } from "./helpers/env";

/**
 * The §7 engine matrix: Chromium, WebKit and Firefox, each desktop and mobile.
 * `UAT_ENGINES` narrows it for a fast local loop (`UAT_ENGINES=chromium-desktop`).
 */
const ENGINES = [
  { name: "chromium-desktop", use: { ...devices["Desktop Chrome"] } },
  { name: "chromium-mobile", use: { ...devices["Pixel 7"] } },
  { name: "firefox-desktop", use: { ...devices["Desktop Firefox"] } },
  /* Firefox has no touch/`isMobile` emulation in Playwright, so its mobile profile is a
   * phone-sized viewport only — enough to accept the responsive layout on Gecko. */
  {
    name: "firefox-mobile",
    use: { ...devices["Desktop Firefox"], viewport: { width: 412, height: 915 } },
  },
  { name: "webkit-desktop", use: { ...devices["Desktop Safari"] } },
  { name: "webkit-mobile", use: { ...devices["iPhone 14"] } },
];

/**
 * Risk tags pick the engines (§7): `@P0` runs everywhere; `@P1`/`@P2` run on one desktop and one
 * mobile engine, which covers both layouts and both rendering families at a fraction of the cost.
 */
const FULL_MATRIX_ENGINES = new Set(["chromium-desktop", "webkit-mobile"]);
const P0 = "@P0";

/**
 * `@serial` marks specs that touch state other specs can see (the Mailpit inbox, the seeded
 * personas' data). `UAT_LANE` selects which lane this invocation runs — `run-lanes.mjs` runs the
 * parallel lane and then the serial lane on one worker, so a serial spec never races another
 * spec and still runs when the parallel lane has failures. Without `UAT_LANE` (e.g. `--list`)
 * both lanes are listed.
 */
const SERIAL = "@serial";
type Lane = "parallel" | "serial";
const lane = process.env.UAT_LANE as Lane | undefined;

const requestedEngines = process.env.UAT_ENGINES?.split(",").map((name) => name.trim());
const engines = requestedEngines?.length
  ? ENGINES.filter((engine) => requestedEngines.includes(engine.name))
  : ENGINES;

/** A regex matching titles carrying every tag in *tags*. */
const allTags = (...tags: string[]) => new RegExp(tags.map((tag) => `(?=.*${tag})`).join(""));

const parallelProjects: Project[] = engines.map((engine) => ({
  name: engine.name,
  use: engine.use,
  grep: FULL_MATRIX_ENGINES.has(engine.name) ? undefined : allTags(P0),
  grepInvert: new RegExp(SERIAL),
}));

const serialProjects: Project[] = engines.map((engine) => ({
  name: `${engine.name}-serial`,
  use: engine.use,
  grep: FULL_MATRIX_ENGINES.has(engine.name) ? allTags(SERIAL) : allTags(SERIAL, P0),
}));

const DEFAULT_WORKERS = process.env.CI ? 2 : 4;

export default defineConfig({
  testDir: "./specs",
  globalSetup: "./global-setup.ts",

  /* Parallel-lane specs own their data (scenario fixtures), so tests within a file may run
   * concurrently too. The serial lane runs on a single worker. */
  fullyParallel: lane !== "serial",
  workers: lane === "serial" ? 1 : Number(process.env.UAT_WORKERS ?? DEFAULT_WORKERS),

  /* A retry absorbs engine-specific timing flake without hiding a real failure: the HTML
   * report still flags the test as flaky. */
  retries: process.env.CI ? 2 : 1,
  forbidOnly: !!process.env.CI,

  timeout: 90_000,
  expect: { timeout: 15_000 },

  reporter: process.env.CI
    ? [
        ["github"],
        ["junit", { outputFile: `test-results/junit-${lane ?? "all"}.xml` }],
        ["html", { outputFolder: `playwright-report/${lane ?? "all"}`, open: "never" }],
      ]
    : [
        ["list"],
        ["html", { outputFolder: `playwright-report/${lane ?? "all"}`, open: "never" }],
      ],
  outputDir: `test-results/${lane ?? "all"}`,

  use: {
    baseURL: BASE_URL,
    /* The local HTTPS server uses a self-signed certificate (see BASE_URL in helpers/env.ts
     * for why TLS is required at all). */
    ignoreHTTPSErrors: true,
    /* Full artifact trail on failure (§8a) — trace, screenshot and video, retained where a
     * stakeholder can open them without re-running the suite. */
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },

  projects:
    lane === "parallel"
      ? parallelProjects
      : lane === "serial"
        ? serialProjects
        : [...parallelProjects, ...serialProjects],
});
