/**
 * UAT-AUTH — Auth & Sessions (PRD §7, P0).
 *
 * Identity is a P0 trust surface: these scenarios assert what a real user observes when
 * signing in, being turned away from a protected route, and recovering a password —
 * always through rendered UI state, never "no error thrown".
 */

import type { Route } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { SERVER_ERROR_MESSAGE } from "@lib/errors";
import { UserPersona } from "@components/website/auth/models";
import { RATE_LIMIT_LOCKOUT_AT } from "@components/website/auth/schemas";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { api } from "../helpers/api";
import { goto, waitForHydration, waitForPage, waitReady } from "../helpers/app";
import { loginViaUi } from "../helpers/auth";
import { clearMailbox, extractLinkFromEmail } from "../helpers/mailpit";
import { PERSONAS, storageStatePath } from "../helpers/personas";
import { ScenarioStage } from "../helpers/scenario";
import { readSeed } from "../helpers/seed";

import { acceptConsentsAndSubmit, enterOtp, fillAccountStep, fillResidenceStep, fillVerifyStep, newAccount, openOtpDialog } from "../helpers/signup";
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

    await waitForHydration(page, "login-email");
    await page.getByTestId("login-email").fill(seed.customer.email);
    await page.getByTestId("login-password").fill("WrongPassword123!");
    await page.getByTestId("login-submit").click();

    // The user must remain on the login form with no session — a failed attempt that
    // silently navigated would be a far worse defect than a missing message.
    await expect(page.getByTestId("login-form")).toBeVisible();
    // The rejection is explained in the backend's own words — a signed-out form has no
    // session, so the session-refresh machinery must never replace that message.
    await expect(page.getByTestId("login-error")).toHaveText(/invalid username or password/i);
    expect(page.url()).toContain(ROUTES.AUTH.LOGIN);
    expect(await page.evaluate(() => window.__auth_snapshot__?.isAuthenticated ?? false)).toBe(
      false,
    );
  });

  test("UAT-AUTH-15 · a server failure during sign-in never shows internals or locks the user out", async ({
    page,
  }) => {
    // What a database outage used to put on this form, verbatim. The mock stands in for the
    // outage so the spec needs no broken backend; the backend's own half (it no longer sends
    // this text at all) is pinned by its unit tests.
    const raw = "Exception during DB session usage: [WinError 1225] The remote computer refused the network connection";
    const reference = "7F3K92QA";
    const outage = async (route: Route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({
        status: 500,
        contentType: "application/json",
        headers: { "X-Request-ID": reference },
        body: JSON.stringify({ error: { code: "INTERNAL_ERROR", message: raw, reference } }),
      });
    };
    const seed = readSeed();
    await page.route("**/api/users/auth/sessions", outage);
    await goto(page, ROUTES.AUTH.LOGIN);

    await waitForHydration(page, "login-email");
    await page.getByTestId("login-email").fill(seed.customer.email);
    await page.getByTestId("login-password").fill(seed.customer.password);

    // As many tries as would lock the form if they were wrong passwords.
    for (let attempt = 0; attempt < RATE_LIMIT_LOCKOUT_AT; attempt++) {
      const failed = page.waitForResponse((r) => r.url().endsWith("/api/users/auth/sessions") && r.status() === 500);
      await page.getByTestId("login-submit").click();
      await failed;

      const error = page.getByTestId("login-error");
      // Our fault, said plainly, with the reference support can look up — never the server's text,
      // and never "your password is wrong".
      await expect(error).toContainText(SERVER_ERROR_MESSAGE);
      await expect(error).toContainText(reference);
      await expect(error).not.toContainText("WinError");
      await expect(error).not.toContainText(/incorrect/i);
      await expect(page.getByTestId("login-submit")).toBeEnabled();
    }

    // Once the backend recovers, the same credentials still work: the outage cost no attempts.
    await page.unroute("**/api/users/auth/sessions", outage);
    await page.getByTestId("login-submit").click();
    await waitForPage(page, (url) => !url.pathname.startsWith(ROUTES.AUTH.GATE), { timeout: 30_000 });
  });

  test("UAT-AUTH-04 · a valid login lands the customer in their portal", async ({ page }) => {
    const seed = readSeed();
    await loginViaUi(page, seed.customer.email, seed.customer.password);

    // Portal priority puts a CUSTOMER-only account in the customer portal.
    await expect(page).toHaveURL(/\/portal(\/|$)/);
    const snapshot = await page.evaluate(() => window.__auth_snapshot__);
    expect(snapshot?.personas).toContain(UserPersona.CUSTOMER);
  });
});

// Clears the shared Mailpit inbox and changes a seeded account's password, so it runs alone.
test.describe("UAT-AUTH — password recovery @P0 @serial", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("UAT-AUTH-05 · password reset issues a single-use link that changes the password", async ({
    page,
  }) => {
    const seed = readSeed();
    const email = seed.erasable.email; // A disposable account: resetting it disturbs nothing.
    await clearMailbox();

    await goto(page, ROUTES.AUTH.FORGOT_PASSWORD);
    await waitForHydration(page, "forgot-email");
    await page.getByTestId("forgot-email").fill(email);
    await page.getByTestId("forgot-submit").click();

    // The reset token only ever reaches the user by email — extract it the way a user
    // would, by following the link in the message.
    const resetLink = await extractLinkFromEmail(email, { pathContains: "reset-password" });
    await page.goto(resetLink);
    await waitReady(page);

    const newPassword = "Reset1234!";
    await expect(page.getByTestId("reset-password-form")).toBeVisible();
    await waitForHydration(page, "reset-password-password");
    await page.getByTestId("reset-password-password").fill(newPassword);
    await page.getByTestId("reset-password-confirm").fill(newPassword);
    await page.getByTestId("reset-password-submit").click();
    // The form moves on to login only once the backend has accepted the new password;
    // signing in any earlier races the reset request itself.
    await waitForPage(page, /\/auth\/login\?reset=ok/);

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
    expect(snapshot?.personas).toContain(UserPersona.AGENT);
    expect(page.url()).toContain("/agents");
  });
});

/**
 * The signup funnel (PRD §2, §3.2) — Account → Verify → Residence → Consent, the four steps a
 * new user must clear before the product will let them submit a property.
 *
 * Each test signs up a brand-new account (unique email and phone), so they own their data and
 * run in parallel without disturbing the seeded personas.
 *
 * This stack runs `PHONE_VERIFICATION_ENABLED=false` (PRD §10.5), so the Verify step asks for a
 * single OTP — email — and collects the phone number to be verified later, at the pay step.
 */

test.describe("UAT-AUTH — signup funnel @P0", () => {
  // Signing up is a signed-out journey, so it must not inherit a session.
  test.use({ storageState: { cookies: [], origins: [] } });
  // The funnel waits on a real email being delivered inside the OTP request (see
  // `openOtpDialog`), so these are slow by design rather than by accident.
  test.slow();

  test("UAT-AUTH-09 · a new customer completes the four-step signup and lands on their first verification", async ({
    page,
  }) => {
    const account = newAccount();
    await goto(page, ROUTES.AUTH.SIGNUP);

    await fillAccountStep(page, account);
    await fillVerifyStep(page, account);
    await fillResidenceStep(page);
    await acceptConsentsAndSubmit(page);

    // A brand-new customer owns no verification yet, so the journey continues into the wizard
    // rather than stranding them on an empty dashboard.
    // `domcontentloaded` rather than the default `load`, for the same reason `goto` uses it:
    // `load` additionally waits on every image and font, which this assertion does not care
    // about and which is what makes an otherwise-passing wait time out under parallel load.
    await waitForPage(page, (url) => url.pathname === ROUTES.PORTAL.VERIFICATIONS_NEW, { timeout: 30_000 });

    const snapshot = await page.evaluate(() => window.__auth_snapshot__);
    expect(snapshot?.isAuthenticated).toBe(true);
    expect(snapshot?.personas).toContain(UserPersona.CUSTOMER);
  });

  test("UAT-AUTH-10 · a half-finished signup resumes where the user left off", async ({ page }) => {
    const account = newAccount();
    await goto(page, ROUTES.AUTH.SIGNUP);
    await fillAccountStep(page, account);
    await expect(page.getByTestId("verify-form")).toBeVisible();

    // Losing the tab mid-wizard must not cost the user what they already typed.
    await goto(page, ROUTES.AUTH.SIGNUP);

    await expect(page.getByTestId("signup-resumed")).toBeVisible();
    await expect(page.getByTestId("verify-form")).toBeVisible();
    await expect(page.getByTestId("verify-email-input")).toHaveValue(account.email);
  });
});

test.describe("UAT-AUTH — signup variants @P1", () => {
  test.use({ storageState: { cookies: [], origins: [] } });
  // Same reason as the funnel above: each of these drives the OTP round-trip.
  test.slow();

  test("UAT-AUTH-11 · signing up through a referral link costs the invitee nothing", async ({
    page,
  }) => {
    // A real code from a real referrer: an invented one would prove nothing, because an unknown
    // code is deliberately ignored rather than rejected (§17.1).
    const seed = readSeed();
    const client = await api(seed.customer.email, seed.customer.password);
    const { code } = await client.get<{ code: string }>("/referrals/me");
    await client.dispose();
    expect(code).toBeTruthy();

    const account = newAccount();
    await goto(page, `${ROUTES.AUTH.SIGNUP}?ref=${code}`);
    await fillAccountStep(page, account);
    await fillVerifyStep(page, account);
    await fillResidenceStep(page);
    await acceptConsentsAndSubmit(page);

    // The referrer's reward only exists once this invitee's first payment clears the chargeback
    // window, so the credit itself belongs to the referral spec. What matters here is that
    // arriving through a referral link changes nothing about the invitee's own signup.
    await waitForPage(page, (url) => url.pathname === ROUTES.PORTAL.VERIFICATIONS_NEW, { timeout: 30_000 });
  });

  test("UAT-AUTH-12 · signing up with agent intent lands in the agent portal", async ({ page }) => {
    const account = newAccount();
    await goto(page, `${ROUTES.AUTH.SIGNUP}?intent=agent`);

    // The page tells an applicant this is only half the journey — the application follows.
    await expect(page.getByText("Step 1 of 2 — agent path")).toBeVisible();

    await fillAccountStep(page, account);
    await fillVerifyStep(page, account);
    await fillResidenceStep(page);
    await acceptConsentsAndSubmit(page);

    await waitForPage(page, (url) => url.pathname.startsWith(ROUTES.AGENT.GATE), { timeout: 30_000 });

    const snapshot = await page.evaluate(() => window.__auth_snapshot__);
    expect(snapshot?.personas).toContain(UserPersona.AGENT);
  });

  test("UAT-AUTH-13 · every step of the signup funnel is accessible", async ({ page }) => {
    const account = newAccount();
    await goto(page, ROUTES.AUTH.SIGNUP);
    await expectNoA11yViolations(page);

    await fillAccountStep(page, account);
    await expect(page.getByTestId("verify-form")).toBeVisible();
    await expectNoA11yViolations(page);

    // The OTP dialog is the funnel's only modal — scan it while it is open.
    await openOtpDialog(page, "email");
    await expectNoA11yViolations(page);
    await enterOtp(page);
    await expect(page.getByTestId("verify-email-verified")).toBeVisible();

    await page.getByTestId("verify-phone-input").fill(account.phone);
    await page.getByTestId("verify-submit").click();

    await expect(page.getByTestId("signup-residence-form")).toBeVisible();
    await expectNoA11yViolations(page);
    await fillResidenceStep(page);

    await expect(page.getByTestId("signup-consent-form")).toBeVisible();
    await expectNoA11yViolations(page);
  });
});

test.describe("UAT-AUTH — set a password @P1", () => {
  // Builds its own scenario and signs in twice, so it is slow by design rather than by accident.
  test.slow();

  test("UAT-AUTH-14 · setting a password makes it the one that signs the user in", async ({
    scenario,
    pageFor,
    anonPage,
  }) => {
    // A scenario's own customer, so changing their password disturbs no other spec.
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);

    await goto(page, ROUTES.AUTH.SET_PASSWORD);
    await expect(page.getByTestId("set-password-form")).toBeVisible();

    const chosen = "Chosen1234!";
    await waitForHydration(page, "set-password-input");
    await page.getByTestId("set-password-input").fill(chosen);
    await page.getByTestId("set-password-confirm-input").fill(chosen);
    await page.getByTestId("set-password-submit").click();

    await waitForPage(
      page,
      (url) =>
        url.pathname === ROUTES.ACCOUNT.SECURITY && url.searchParams.get("password") === "ok",
      { timeout: 30_000 },
    );

    // Acceptance is the business outcome: the chosen password is the one that now signs in.
    await loginViaUi(anonPage, customer.email, chosen);
    expect(await anonPage.evaluate(() => window.__auth_snapshot__?.isAuthenticated)).toBe(true);
  });
});
