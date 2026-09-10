/**
 * Veriprops UAT suite — browser-driven acceptance (docs/uat-strategy.md).
 *
 * A green run across the engine matrix *is* the acceptance signal (§1), so the config
 * optimises for trustworthiness over speed: one reset+seed per run, single worker for
 * shared-state areas, and a full artifact trail on every failure so a stakeholder can
 * inspect a red without re-running it.
 *
 * Run: `pnpm e2e` — see §9 for the stack the suite expects to be running.
 */
import { defineConfig, devices } from "@playwright/test";

import { BASE_URL } from "./helpers/env";

/**
 * The §7 engine matrix: Chromium, WebKit and Firefox, each desktop and mobile.
 * `UAT_ENGINES` narrows it for a fast local loop (`UAT_ENGINES=chromium-desktop`);
 * the standing decision for an acceptance run is the full matrix.
 */
const ENGINE_PROJECTS = [
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

const requestedEngines = process.env.UAT_ENGINES?.split(",").map((name) => name.trim());
const projects = requestedEngines?.length
  ? ENGINE_PROJECTS.filter((project) => requestedEngines.includes(project.name))
  : ENGINE_PROJECTS;

export default defineConfig({
  testDir: "./specs",
  globalSetup: "./global-setup.ts",

  /*
   * Shared seeded scenario ⇒ specs must not race each other for the same rows. Specs are
   * independently bootstrappable (§3 step 3), so this is a correctness-cheap performance
   * choice, not a dependency chain.
   */
  fullyParallel: false,
  workers: 1,

  /* A retry absorbs engine-specific timing flake without hiding a real failure: the HTML
   * report still flags the test as flaky. */
  retries: process.env.CI ? 2 : 1,
  forbidOnly: !!process.env.CI,

  timeout: 90_000,
  expect: { timeout: 15_000 },

  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  outputDir: "test-results",

  use: {
    baseURL: BASE_URL,
    /* The local HTTPS dev server uses a self-signed certificate (see BASE_URL in
     * helpers/env.ts for why TLS is required at all). */
    ignoreHTTPSErrors: true,
    /* Full artifact trail on failure (§8a) — trace, screenshot and video, retained where a
     * stakeholder can open them without re-running the suite. */
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 20_000,
    navigationTimeout: 30_000,
  },

  projects,
});
