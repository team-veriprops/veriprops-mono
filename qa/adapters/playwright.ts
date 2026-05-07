// ─────────────────────────────────────────────────────────────────────────────
// adapters/playwright.ts
// Playwright browser factory and context helpers.
// Mirrors the appReadySelector fallback logic from browser-runner.ts
// for use in standalone adapter-level operations.
// ─────────────────────────────────────────────────────────────────────────────

import { chromium, firefox, webkit } from "@playwright/test";
import type { Browser, BrowserContext, BrowserContextOptions, Page } from "@playwright/test";
import type { QAConfig } from "../core/types.js";

export type SupportedBrowser = "chromium" | "firefox" | "webkit";

// ─── Browser factory ──────────────────────────────────────────────────────────

export async function launch(
  config: QAConfig,
  browserType: SupportedBrowser = "chromium"
): Promise<Browser> {
  const launcher = { chromium, firefox, webkit }[browserType];
  return launcher.launch({
    headless: config.headless,
    timeout: config.timeout,
  });
}

// ─── Context factory ──────────────────────────────────────────────────────────

export function defaultContextOptions(config: QAConfig): BrowserContextOptions {
  return {
    baseURL: config.baseUrl,
    viewport: { width: 1280, height: 800 },
    ignoreHTTPSErrors: config.environment !== "ci",
    locale: "en-US",
    timezoneId: "UTC",
  };
}

export async function createContext(
  browser: Browser,
  config: QAConfig,
  overrides?: Partial<BrowserContextOptions>
): Promise<BrowserContext> {
  return browser.newContext({
    ...defaultContextOptions(config),
    ...overrides,
  });
}

// ─── App readiness ────────────────────────────────────────────────────────────

/**
 * Waits for the application to be ready on a given page.
 *
 * Resolution order:
 *   1. window.__app_ready === true
 *   2. appReadySelector visible (from domain contract or QAConfig)
 *   3. networkidle fallback
 *
 * @param page             - Playwright page instance
 * @param config           - QA config (contains global appReadySelector)
 * @param domainSelector   - Optional per-domain selector override from contract
 */
export async function waitForAppReady(
  page: Page,
  config: QAConfig,
  domainSelector?: string
): Promise<void> {
  const timeout = config.timeout;
  const selector = domainSelector ?? config.appReadySelector;

  try {
    await Promise.race([
      page.waitForFunction(
        () => (window as unknown as Record<string, unknown>)["__app_ready"] === true,
        { timeout }
      ),
      ...(selector
        ? [
            page
              .waitForSelector(selector, { state: "visible", timeout })
              .then(() => {
                console.log(`[playwright] App ready via selector: "${selector}"`);
              }),
          ]
        : []),
    ]);
  } catch {
    console.warn(
      `[playwright] App ready signal not detected` +
        (selector ? ` (selector: "${selector}")` : "") +
        `. Falling back to networkidle.`
    );
    try {
      await page.waitForLoadState("networkidle", { timeout });
    } catch {
      console.warn(
        `[playwright] networkidle timed out after ${timeout}ms. Proceeding anyway.`
      );
    }
  }
}

// ─── OAuth / SSO helpers ──────────────────────────────────────────────────────

/**
 * Waits for an OAuth redirect to complete and land on an expected URL pattern.
 * Use in journeys that include a third-party auth step.
 */
export async function waitForOAuthComplete(
  page: Page,
  expectedUrlPattern: string | RegExp,
  timeoutMs?: number
): Promise<void> {
  const timeout = timeoutMs ?? 30000;
  await page.waitForURL(expectedUrlPattern, { timeout });
}

/**
 * Extracts cookies from the current browser context as a plain object.
 * Useful for transferring auth state between browser and API-mode steps.
 */
export async function extractCookies(
  context: BrowserContext
): Promise<Record<string, string>> {
  const cookies = await context.cookies();
  return Object.fromEntries(cookies.map((c) => [c.name, c.value]));
}

/**
 * Injects cookies into a browser context.
 * Used to restore a session from a previously authenticated API runner.
 */
export async function injectCookies(
  context: BrowserContext,
  cookies: Record<string, string>,
  domain: string
): Promise<void> {
  const cookieList = Object.entries(cookies).map(([name, value]) => ({
    name,
    value,
    domain,
    path: "/",
  }));
  await context.addCookies(cookieList);
}
