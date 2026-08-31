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

/** Navigate to *path* on the app origin and wait for the ready gate. */
export async function goto(page: Page, path: string): Promise<void> {
  await page.goto(path);
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
