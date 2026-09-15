/**
 * UI login — the one place the suite types credentials into the login form.
 *
 * `globalSetup` uses it to mint each persona's `storageState`; specs that assert login
 * behaviour itself (lockout, redirects, OAuth) drive the form directly instead.
 */
import { Page, expect } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { goto, waitReady } from "./app";

/**
 * Sign *page* in as *email* through the real login form and wait until the sign-in has fully
 * settled, so the caller can immediately persist `storageState` or navigate on.
 *
 * "Settled" is more than an authenticated snapshot: after a successful sign-in the login form
 * redirects into the user's portal. A caller that navigates before that redirect lands races it —
 * Firefox cancels the caller's navigation (`NS_BINDING_ABORTED`) — so this also waits for the page
 * to leave the auth surface and for the destination to report ready.
 */
export async function loginViaUi(page: Page, email: string, password: string): Promise<void> {
  await goto(page, ROUTES.AUTH.LOGIN);

  await page.getByTestId("login-email").fill(email);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();

  await page.waitForFunction(() => window.__auth_snapshot__?.isAuthenticated === true, {
    timeout: 30_000,
  });
  expect(await page.evaluate(() => window.__auth_snapshot__?.userId)).toBeTruthy();

  await page.waitForURL((url) => !url.pathname.startsWith(ROUTES.AUTH.GATE), { timeout: 30_000 });
  await waitReady(page);
}

/**
 * Sign out through the same endpoint the app calls, from inside the page so the session
 * cookies and their double-submit CSRF twin travel together, then clear the client-side
 * mirror the way the app's own logout does.
 */
export async function logout(page: Page): Promise<void> {
  await page.evaluate(async () => {
    const csrf = document.cookie
      .split("; ")
      .find((entry) => entry.startsWith("__Host-access_csrf_token="))
      ?.split("=")[1];
    await fetch("/api/users/auth/sessions/current", {
      method: "DELETE",
      headers: csrf ? { "X-CSRF-Token": csrf } : {},
    });
    window.localStorage.removeItem("veriprops-auth");
  });
}
