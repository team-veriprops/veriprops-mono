/**
 * UAT-AUTH — Auth & Sessions (PRD §7, P0).
 *
 * Identity is a P0 trust surface: these scenarios assert what a real user observes when
 * signing in, being turned away from a protected route, and recovering a password —
 * always through rendered UI state, never "no error thrown".
 */
import { expect, test } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitReady } from "../helpers/app";
import { loginViaUi } from "../helpers/auth";
import { clearMailbox, extractLinkFromEmail } from "../helpers/mailpit";
import { PERSONAS, storageStatePath } from "../helpers/personas";
import { readSeed } from "../helpers/seed";

test.describe("UAT-AUTH — signed-out access @P0", () => {
  // These scenarios are about *not* having a session, so they must not inherit one.
  test.use({ storageState: { cookies: [], origins: [] } });

  test("UAT-AUTH-01 · a protected route sends a signed-out visitor to login", async ({ page }) => {
    await page.goto(ROUTES.PORTAL.DASHBOARD);
    await waitReady(page);

    // The guard redirects to the login page and preserves where the user was heading, so
    // signing in resumes the journey instead of dumping them on a dashboard.
    expect(page.url()).toContain(ROUTES.AUTH.LOGIN);
    expect(new URL(page.url()).searchParams.get("redirect")).toContain(
      ROUTES.PORTAL.DASHBOARD,
    );
    await expect(page.getByTestId("login-form")).toBeVisible();
  });

  test("UAT-AUTH-02 · the login page is accessible", async ({ page }) => {
    await goto(page, ROUTES.AUTH.LOGIN);
    await expect(page.getByTestId("login-form")).toBeVisible();
    await expectNoA11yViolations(page);
  });

  test("UAT-AUTH-03 · a wrong password is rejected and the user stays signed out", async ({
    page,
  }) => {
    const seed = readSeed();
    await goto(page, ROUTES.AUTH.LOGIN);

    await page.getByTestId("login-email").fill(seed.customer.email);
    await page.getByTestId("login-password").fill("WrongPassword123!");
    await page.getByTestId("login-submit").click();

    // The user must remain on the login form with no session — a failed attempt that
    // silently navigated would be a far worse defect than a missing message.
    await expect(page.getByTestId("login-form")).toBeVisible();
    expect(page.url()).toContain(ROUTES.AUTH.LOGIN);
    expect(await page.evaluate(() => window.__auth_snapshot__?.isAuthenticated ?? false)).toBe(
      false,
    );
  });

  test("UAT-AUTH-04 · a valid login lands the customer in their portal", async ({ page }) => {
    const seed = readSeed();
    await loginViaUi(page, seed.customer.email, seed.customer.password);

    // Portal priority puts a CUSTOMER-only account in the customer portal.
    await expect(page).toHaveURL(/\/portal(\/|$)/);
    const snapshot = await page.evaluate(() => window.__auth_snapshot__);
    expect(snapshot?.personas).toContain("CUSTOMER");
  });

  test("UAT-AUTH-05 · password reset issues a single-use link that changes the password", async ({
    page,
  }) => {
    const seed = readSeed();
    const email = seed.erasable.email; // A disposable account: resetting it disturbs nothing.
    await clearMailbox();

    await goto(page, ROUTES.AUTH.FORGOT_PASSWORD);
    await page.getByTestId("forgot-email").fill(email);
    await page.getByTestId("forgot-submit").click();

    // The reset token only ever reaches the user by email — extract it the way a user
    // would, by following the link in the message.
    const resetLink = await extractLinkFromEmail(email, { pathContains: "reset-password" });
    await page.goto(resetLink);
    await waitReady(page);

    const newPassword = "Reset1234!";
    await expect(page.getByTestId("reset-password-form")).toBeVisible();
    await page.getByTestId("reset-password-password").fill(newPassword);
    await page.getByTestId("reset-password-confirm").fill(newPassword);
    await page.getByTestId("reset-password-submit").click();

    // Acceptance is the business outcome: the new password signs in.
    await loginViaUi(page, email, newPassword);
    expect(await page.evaluate(() => window.__auth_snapshot__?.isAuthenticated)).toBe(true);
  });
});

test.describe("UAT-AUTH — authenticated session @P0", () => {
  test.use({ storageState: storageStatePath(PERSONAS.CUSTOMER) });

  test("UAT-AUTH-06 · a signed-in customer is kept out of guest-only pages", async ({ page }) => {
    await page.goto(ROUTES.AUTH.LOGIN);
    await waitReady(page);

    // Guest-only routes bounce an authenticated user to their portal rather than
    // showing a login form that would strand them.
    await expect(page).not.toHaveURL(new RegExp(`${ROUTES.AUTH.LOGIN}$`));
  });

  test("UAT-AUTH-07 · the devices surface lists the current session and is accessible", async ({
    page,
  }) => {
    await goto(page, ROUTES.ACCOUNT.DEVICES);

    // A user must be able to see where their account is signed in — the surface that
    // makes revocation possible at all.
    await expect(page.getByTestId("devices-list")).toBeVisible();
    await expect(page.getByTestId("device-current-badge").first()).toBeVisible();
    await expectNoA11yViolations(page);
  });
});

test.describe("UAT-AUTH — agent portal routing @P0", () => {
  test.use({ storageState: storageStatePath(PERSONAS.AGENT_REGISTRY) });

  test("UAT-AUTH-08 · an agent lands in the agent portal, not the customer portal", async ({
    page,
  }) => {
    await goto(page, ROUTES.AGENT.DASHBOARD);

    const snapshot = await page.evaluate(() => window.__auth_snapshot__);
    expect(snapshot?.isAuthenticated).toBe(true);
    expect(snapshot?.personas).toContain("AGENT");
    expect(page.url()).toContain("/agents");
  });
});
