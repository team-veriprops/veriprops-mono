/**
 * UAT-AUTH — Auth & Sessions (PRD §7, P0).
 *
 * Identity is a P0 trust surface: these scenarios assert what a real user observes when
 * signing in, being turned away from a protected route, and recovering a password —
 * always through rendered UI state, never "no error thrown".
 */
import { randomUUID } from "node:crypto";

import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { UserPersona } from "@components/website/auth/models";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { api } from "../helpers/api";
import { goto, waitReady } from "../helpers/app";
import { loginViaUi } from "../helpers/auth";
import { TEST_OTP } from "../helpers/env";
import { clearMailbox, extractLinkFromEmail } from "../helpers/mailpit";
import { PERSONAS, storageStatePath } from "../helpers/personas";
import { ScenarioStage } from "../helpers/scenario";
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
    // The rejection is explained in the backend's own words — a signed-out form has no
    // session, so the session-refresh machinery must never replace that message.
    await expect(page.getByTestId("login-error")).toHaveText(/invalid username or password/i);
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
    // The form moves on to login only once the backend has accepted the new password;
    // signing in any earlier races the reset request itself.
    await page.waitForURL(/\/auth\/login\?reset=ok/);

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

/** A brand-new account's details, unique per test so parallel workers never collide. */
interface NewAccount {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  password: string;
}

function newAccount(): NewAccount {
  return {
    firstName: "Ada",
    lastName: "Signup",
    email: `qa-signup-${randomUUID().slice(0, 8)}@veriprops.io`,
    // Digits only, 7–15 of them (`phoneFields` in schemas.ts), and unique: no two signups may
    // submit the same number.
    phone: `80${Math.floor(Math.random() * 1e9)
      .toString()
      .padStart(9, "0")}`,
    password: "Signup1234!",
  };
}

/** Step 1 — account basics. */
async function fillAccountStep(page: Page, account: NewAccount): Promise<void> {
  await expect(page.getByTestId("signup-basics-form")).toBeVisible();
  await page.getByTestId("signup-first-name").fill(account.firstName);
  await page.getByTestId("signup-last-name").fill(account.lastName);
  await page.getByTestId("signup-email").fill(account.email);
  await page.getByTestId("signup-password").fill(account.password);
  await page.getByTestId("signup-basics-submit").click();
}

/** Ask for a code on *field* and wait until the dialog is ready to be typed into. */
async function openOtpDialog(page: Page, field: "email" | "phone"): Promise<void> {
  await page.getByTestId(`verify-${field}-send`).click();

  const modal = page.getByTestId("verify-otp-modal");
  const sendError = page.getByTestId(`verify-${field}-error`);
  // The endpoint itself is quick (~0.15s measured), but this whole step is generously budgeted
  // because the browser gets starved when several workers share one machine, and that is where
  // this wait has actually failed. The form's own error is watched alongside, so a refused send
  // is reported in the app's words rather than as a bare "element not found" on the dialog.
  const opened = await Promise.race([
    modal.waitFor({ state: "visible", timeout: 90_000 }).then(() => true),
    sendError.waitFor({ state: "visible", timeout: 90_000 }).then(() => false),
  ]).catch(() => {
    throw new Error(`The ${field} code dialog never opened, and no error was shown.`);
  });

  if (!opened) {
    throw new Error(`Sending the ${field} code failed: ${(await sendError.innerText()).trim()}`);
  }
  // The dialog clears itself and focuses its first box when it opens. Waiting for that focus is
  // what proves the reset has already run, so the digits typed next survive it.
  await expect(page.getByTestId("verify-otp-digit-0")).toBeFocused();
  // The boxes then fade in on a stagger. Anything that lands mid-animation sees a
  // half-transparent input — which an a11y scan scores as a contrast failure against the
  // backdrop — so wait for the last one to finish arriving.
  await expect(page.getByTestId(`verify-otp-digit-${TEST_OTP.length - 1}`)).toHaveCSS(
    "opacity",
    "1",
  );
}

/** Type the deterministic code into the open dialog and confirm it. */
async function enterOtp(page: Page): Promise<void> {
  // One digit per box: the boxes reject anything longer, which is what real keystrokes look like.
  for (const [index, digit] of [...TEST_OTP].entries()) {
    await page.getByTestId(`verify-otp-digit-${index}`).fill(digit);
  }
  await page.getByTestId("verify-otp-confirm").click();
}

async function verifyWithOtp(page: Page, field: "email" | "phone"): Promise<void> {
  await openOtpDialog(page, field);
  await enterOtp(page);
  await expect(page.getByTestId("verify-otp-modal")).toBeHidden();
  await expect(page.getByTestId(`verify-${field}-verified`)).toBeVisible();
}

/** Step 2 — prove the email, then give the phone number. */
async function fillVerifyStep(page: Page, account: NewAccount): Promise<void> {
  await expect(page.getByTestId("verify-form")).toBeVisible();
  await verifyWithOtp(page, "email");
  await page.getByTestId("verify-phone-input").fill(account.phone);
  await page.getByTestId("verify-submit").click();
}

/** Step 3 — residence. The country is what drives currency and timezone. */
async function fillResidenceStep(page: Page): Promise<void> {
  await expect(page.getByTestId("signup-residence-form")).toBeVisible();
  await page.getByTestId("signup-country").selectOption("NG");
  // Choosing Nigeria picks the Naira for the user instead of making them do it.
  await expect(page.getByTestId("signup-currency-NGN")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("signup-residence-submit").click();
}

/** Step 4 — accept both documents and create the account. */
async function acceptConsentsAndSubmit(page: Page): Promise<void> {
  await expect(page.getByTestId("signup-consent-form")).toBeVisible();
  await page.getByTestId("signup-consent-terms").click();
  await page.getByTestId("signup-consent-privacy").click();
  await page.getByTestId("signup-consent-submit").click();
}

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
    await page.waitForURL((url) => url.pathname === ROUTES.PORTAL.VERIFICATIONS_NEW, {
      timeout: 30_000,
    });
    await waitReady(page);

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
    await page.waitForURL((url) => url.pathname === ROUTES.PORTAL.VERIFICATIONS_NEW, {
      timeout: 30_000,
    });
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

    await page.waitForURL((url) => url.pathname.startsWith(ROUTES.AGENT.GATE), { timeout: 30_000 });
    await waitReady(page);

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
    await page.getByTestId("set-password-input").fill(chosen);
    await page.getByTestId("set-password-confirm-input").fill(chosen);
    await page.getByTestId("set-password-submit").click();

    await page.waitForURL(
      (url) =>
        url.pathname === ROUTES.ACCOUNT.SECURITY && url.searchParams.get("password") === "ok",
      { timeout: 30_000 },
    );

    // Acceptance is the business outcome: the chosen password is the one that now signs in.
    await loginViaUi(anonPage, customer.email, chosen);
    expect(await anonPage.evaluate(() => window.__auth_snapshot__?.isAuthenticated)).toBe(true);
  });
});
