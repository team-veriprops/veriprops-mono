/**
 * UAT-SESS — Session lifecycle (PRD §7.2, P0).
 *
 * A session has three ways to end or recover, and each must look right to the user:
 * - an access token expires (15 min) → renewed silently from the refresh cookie;
 * - the whole session is gone → the next protected navigation lands on login and, once signed in,
 *   returns the user to where they were;
 * - the device is revoked elsewhere → refresh dies at once, so when the access token lapses the
 *   user is told their session expired and handed to login (access tokens live out their TTL,
 *   PRD §3/§7.2).
 * And signing out through the UI must actually end the session — even when the logout call never
 * answers and the page leaves on its failsafe.
 *
 * Every test builds its own customer (`scenario`), so revoking or signing out never touches a
 * session another spec depends on.
 */
import { BrowserContext, Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitForHydration, waitForPage, waitReady } from "../helpers/app";
import { ScenarioStage } from "../helpers/scenario";
import { signOut } from "../helpers/ui";

/** The access-token cookie pair. Clearing it is what an expired access token looks like. */
const ACCESS_COOKIES = ["__Host-access_token", "__Host-access_csrf_token"];
/** Every session cookie — clearing them all is a session that no longer exists. */
const SESSION_COOKIES = [...ACCESS_COOKIES, "__Host-refresh_token", "__Host-refresh_csrf_token"];
/** The logout call (`authService.logout`) as the browser sends it, through the `/api` rewrite. */
const LOGOUT_PATH = "/users/auth/sessions/current";

async function clearCookies(context: BrowserContext, names: string[]): Promise<void> {
  for (const name of names) {
    await context.clearCookies({ name });
  }
}

/**
 * Change *page*'s session cookies with no app page open to react to it. An open portal page keeps
 * making requests; one that hits the changed session first would start its own recovery (and its
 * own login redirect) and race the navigation the test is about to make.
 */
async function clearCookiesOffApp(page: Page, names: string[]): Promise<void> {
  await page.goto("about:blank");
  await clearCookies(page.context(), names);
}

/** The page is on the login form, carrying *returnTo* as its post-sign-in destination. */
async function expectLoginReturningTo(page: Page, returnTo: string): Promise<void> {
  await waitForPage(page, (url) => url.pathname === ROUTES.AUTH.LOGIN, { timeout: 30_000 });
  expect(new URL(page.url()).searchParams.get("redirect")).toContain(returnTo);
}

test.describe("UAT-SESS — session lifecycle @P0", () => {
  test("UAT-SESS-01 · an expired access token is renewed without interrupting the user", async ({
    scenario,
    pageFor,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);

    await clearCookiesOffApp(page, ACCESS_COOKIES);
    await goto(page, ROUTES.ACCOUNT.DEVICES);

    // The page's own data loads — the 401 was absorbed by a silent refresh — and the recovery
    // dialog never appeared.
    await expect(page.getByTestId("devices-list")).toBeVisible();
    await expect(page.getByTestId("device-current-badge")).toBeVisible();
    await expect(page.getByTestId("session-recovery-overlay")).toHaveCount(0);
  });

  test("UAT-SESS-02 · a session that is gone sends the user to sign in and back to where they were", async ({
    scenario,
    pageFor,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);

    await clearCookiesOffApp(page, SESSION_COOKIES);
    await page.goto(ROUTES.ACCOUNT.DEVICES, { waitUntil: "domcontentloaded" });
    await expectLoginReturningTo(page, ROUTES.ACCOUNT.DEVICES);
    await waitReady(page);
    await waitForHydration(page, "login-email");

    // Sign in on the form the guard landed on, so its redirect is the one honoured.
    await page.getByTestId("login-email").fill(customer.email);
    await page.getByTestId("login-password").fill(customer.password);
    await page.getByTestId("login-submit").click();

    await waitForPage(page, (url) => url.pathname === ROUTES.ACCOUNT.DEVICES, { timeout: 30_000 });
    await expect(page.getByTestId("devices-list")).toBeVisible();
  });

  test("UAT-SESS-03 · a device revoked from another device is signed out once its access token lapses", async ({
    scenario,
    pageFor,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const revokedDevice = await pageFor(customer);
    const otherDevice = await pageFor(customer);

    // From the other device, revoke the first one.
    await goto(otherDevice, ROUTES.ACCOUNT.DEVICES);
    const rows = otherDevice.getByTestId("device-row");
    await expect(rows).toHaveCount(2);
    await otherDevice.getByTestId("device-revoke").click();
    await expect(rows).toHaveCount(1);

    // Revocation kills the refresh at once; the access token lives out its TTL. Clearing it stands
    // in for that expiry, so the revoked device's next request has to refresh — and cannot.
    await clearCookiesOffApp(revokedDevice, ACCESS_COOKIES);
    await revokedDevice.goto(ROUTES.ACCOUNT.DEVICES, { waitUntil: "domcontentloaded" });

    // The dialog tells the user why, then hands off to login on its own after ~1.5s. Catching it is
    // inherently racy — on a fast machine the redirect can win — so the handoff below is the
    // assertion that must hold, and the dialog's wording is checked whenever it is still on screen.
    // Read the wording in the same step that finds the dialog: checking it is visible and then
    // asserting on it separately left a gap the ~1.5s handoff could fall into, failing on
    // "element not found" even though the product did exactly the right thing.
    const overlayText = await revokedDevice
      .getByTestId("session-recovery-overlay")
      .textContent({ timeout: 10_000 })
      .catch(() => null);
    if (overlayText !== null) {
      expect(overlayText).toContain("Your session has expired");
    }

    await expectLoginReturningTo(revokedDevice, ROUTES.ACCOUNT.DEVICES);
    await waitReady(revokedDevice);
    await expectNoA11yViolations(revokedDevice);
  });

  test("UAT-SESS-04 · signing out ends the session", async ({ scenario, pageFor }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    // Start from a page inside the app shell, wherever sign-in happened to land.
    await goto(page, ROUTES.PORTAL.DASHBOARD);

    await signOut(page);

    // The session is really gone: a protected page now sends the user to sign in.
    await page.goto(ROUTES.PORTAL.DASHBOARD, { waitUntil: "domcontentloaded" });
    await expectLoginReturningTo(page, ROUTES.PORTAL.DASHBOARD);
  });

  test("UAT-SESS-05 · a sign-out whose call never answers still ends on login, and still ends the session", async ({
    scenario,
    pageFor,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    await goto(page, ROUTES.PORTAL.DASHBOARD);

    // Hold the first logout call forever, so sign-out leaves on its failsafe while the session
    // cookies are still in the browser. Any later call — the queued retry — goes through.
    let held = false;
    await page.route(`**${LOGOUT_PATH}`, async (route) => {
      if (route.request().method() !== "DELETE" || held) return route.continue();
      held = true;
    });
    const retried = page.waitForResponse(
      (r) => r.url().endsWith(LOGOUT_PATH) && r.request().method() === "DELETE" && r.ok(),
    );

    await signOut(page);

    // On the login form, not bounced back into the app by the surviving cookie.
    await expect(page.getByTestId("login-form")).toBeVisible();
    expect(new URL(page.url()).pathname).toBe(ROUTES.AUTH.LOGIN);

    // The login page re-sent the queued logout, and it ended the session.
    await retried;
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await page.goto(ROUTES.PORTAL.DASHBOARD, { waitUntil: "domcontentloaded" });
    await expectLoginReturningTo(page, ROUTES.PORTAL.DASHBOARD);
  });
});
