/**
 * Browser-side readiness and auth-state helpers built on the app's automation window
 * hooks (`frontend/src/lib/automation.ts`, docs/uat-strategy.md §2).
 *
 * These hooks only exist when the frontend runs with
 * `NEXT_PUBLIC_ENVIRONMENT ∈ {dev_personal, development, test}` — the suite's §9 run
 * contract. `waitReady` is how specs wait deterministically: never a fixed timeout.
 */
import { Page, expect } from "@playwright/test";

/** Auth state the app publishes for automation after a session query resolves. */
export interface AuthSnapshot {
  isAuthenticated: boolean;
  userId: string | null;
  personas: string[];
}

/**
 * Block until the React tree has mounted and `ClientWrapperProvider` has flipped
 * `__app_ready__`. Use after every navigation instead of `waitForTimeout`.
 */
export async function waitReady(page: Page): Promise<void> {
  await page.waitForFunction(() => window.__app_ready__ === true);
}

/**
 * Block until React has hydrated the element behind *testId*.
 *
 * `waitReady` only says the root provider has mounted. A form below a `Suspense` boundary can
 * still be server-rendered HTML with no handlers: text typed into it is either never seen by
 * the form library or wiped when hydration resets the input to its default (observed on WebKit,
 * where the email box came back empty and the sign-in never submitted). React marks a hydrated
 * DOM node with a `__reactProps$…` key, which is a deterministic signal — no fixed sleep.
 */
export async function waitForHydration(page: Page, testId: string): Promise<void> {
  await page.waitForFunction((id) => {
    const el = document.querySelector(`[data-testid="${id}"]`);
    return !!el && Object.keys(el).some((key) => key.startsWith("__reactProps"));
  }, testId);
}

/**
 * Navigate to *path* on the app origin and wait for the ready gate.
 *
 * Waits for `domcontentloaded`, not `load`: the app's readiness signal is `__app_ready__`, and
 * `load` additionally waits on every image and font — so third-party asset latency would fail a
 * spec that never asserts on those assets.
 */
export async function goto(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await waitReady(page);
}

/**
 * Wait for a navigation the page itself made — a redirect after sign-in, a form that moves on —
 * to land on *url*, then for the ready gate. The counterpart of `goto` for navigations a spec
 * didn't start, and for the same reason: `waitForURL` defaults to `load`, which also waits for
 * every image and font, so a slow asset failed specs that never look at one (SESS-04).
 */
export async function waitForPage(
  page: Page,
  url: Parameters<Page["waitForURL"]>[0],
  options: { timeout?: number } = {},
): Promise<void> {
  await page.waitForURL(url, { waitUntil: "domcontentloaded", ...options });
  await waitReady(page);
}

/**
 * The app's current auth snapshot, once the session query has published one.
 * Returns `null` when the hook has not been written yet (no session query ran).
 */
export async function authSnapshot(page: Page): Promise<AuthSnapshot | null> {
  return page.evaluate(() => window.__auth_snapshot__ ?? null);
}

/** Assert the page is authenticated, optionally as a specific user id. */
export async function expectAuthenticated(page: Page, userId?: string): Promise<void> {
  await page.waitForFunction(() => window.__auth_snapshot__?.isAuthenticated === true);
  if (userId) {
    const snapshot = await authSnapshot(page);
    expect(snapshot?.userId).toBe(userId);
  }
}

/** Assert the automation hooks are live — the suite's own trust anchor (§6.20). */
export async function expectAutomationHooks(page: Page): Promise<void> {
  await waitReady(page);
  expect(await page.evaluate(() => window.__TEST_MODE__)).toBe(true);
}
