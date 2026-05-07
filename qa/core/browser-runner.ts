// ─────────────────────────────────────────────────────────────────────────────
// core/browser-runner.ts
// Manages Playwright browser lifecycle and runs browser-mode journeys.
// App readiness: tries window.__app_ready first, then appReadySelector,
// with precedence: domain contract > QAConfig > __app_ready signal.
// ─────────────────────────────────────────────────────────────────────────────

import { chromium, firefox, webkit } from "@playwright/test";
import type { Browser, BrowserContext, Page } from "@playwright/test";
import type { Domain, Journey, JourneyResult, QAConfig } from "./types.js";
import { FlowEngine } from "./flow-engine.js";
import { APIRunner } from "./api-runner.js";

type BrowserType = "chromium" | "firefox" | "webkit";

export class BrowserRunner {
  private browser: Browser | null = null;
  private config: QAConfig;
  private runId: string;

  constructor(config: QAConfig, runId: string) {
    this.config = config;
    this.runId = runId;
  }

  // ─── Lifecycle ────────────────────────────────────────────────────────────

  async launch(browserType: BrowserType = "chromium"): Promise<void> {
    const launcher = { chromium, firefox, webkit }[browserType];
    this.browser = await launcher.launch({
      headless: this.config.headless,
      timeout: this.config.timeout,
    });
  }

  async close(): Promise<void> {
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
    }
  }

  // ─── Journey execution ────────────────────────────────────────────────────

  async runJourney(
    journey: Journey,
    domain: Domain
  ): Promise<JourneyResult> {
    if (!this.browser) {
      throw new Error("BrowserRunner.launch() must be called before runJourney()");
    }

    const context = await this.createContext();
    const page = await context.newPage();

    // Resolve app-ready strategy for this domain
    const appReadySelector =
      domain.contract.appReadySelector ??
      this.config.appReadySelector;

    try {
      await this.waitForAppReady(page, appReadySelector);

      const engine = new FlowEngine(this.config, this.runId, domain.contract.name);
      // API runner available in browser journeys for hybrid steps
      const apiRunner = new APIRunner(this.config);

      return await engine.executeJourney(
        journey,
        domain.selectors,
        page,
        apiRunner
      );
    } finally {
      await context.close();
    }
  }

  // ─── Context ──────────────────────────────────────────────────────────────

  private async createContext(): Promise<BrowserContext> {
    if (!this.browser) throw new Error("Browser not launched");

    return this.browser.newContext({
      baseURL: this.config.baseUrl,
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: this.config.environment !== "ci",
      // Capture console errors for forensic logs
      recordVideo: undefined,
    });
  }

  // ─── App readiness ────────────────────────────────────────────────────────

  /**
   * Waits for the application to signal it is ready.
   *
   * Resolution order:
   *   1. window.__app_ready === true  (frontend sets this after hydration)
   *   2. appReadySelector visible     (CSS selector fallback from config/contract)
   *   3. networkidle                  (last resort — always attempted if above timeout)
   *
   * If neither signal fires within timeout, execution continues with a warning
   * rather than throwing, so individual step failures surface cleanly.
   */
  private async waitForAppReady(
    page: Page,
    appReadySelector?: string
  ): Promise<void> {
    const timeout = this.config.timeout;

    try {
      await Promise.race([
        // Strategy 1: JS signal
        page.waitForFunction(() => (window as unknown as Record<string, unknown>)["__app_ready"] === true, {
          timeout,
        }),

        // Strategy 2: CSS selector fallback (only if configured)
        ...(appReadySelector
          ? [
              page
                .waitForSelector(appReadySelector, {
                  state: "visible",
                  timeout,
                })
                .then(() => {
                  console.log(
                    `[browser-runner] App ready via selector: "${appReadySelector}"`
                  );
                }),
            ]
          : []),
      ]);
    } catch {
      // Neither signal fired — fall back to networkidle
      console.warn(
        `[browser-runner] window.__app_ready not detected` +
          (appReadySelector ? ` and selector "${appReadySelector}" not visible` : "") +
          `. Falling back to networkidle. ` +
          `Set window.__app_ready = true in your app or configure APP_READY_SELECTOR.`
      );
      try {
        await page.waitForLoadState("networkidle", { timeout });
      } catch {
        console.warn(
          `[browser-runner] networkidle fallback also timed out after ${timeout}ms. ` +
            `Proceeding — individual steps will fail if the app is not ready.`
        );
      }
    }
  }
}
