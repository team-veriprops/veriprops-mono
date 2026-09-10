/**
 * UAT-DEV — Dev/QA contracts (PRD §25, P0 meta).
 *
 * The suite's own trust anchors: if these fail, every other scenario's green is
 * meaningless. They assert the determinism foundation the strategy depends on — seeded
 * accounts and verifications exist, the deterministic OTP resolves, the automation window
 * hooks are live, and Mailpit is capturing.
 */
import { expect, test } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { anonymousApi } from "../helpers/api";
import { expectAutomationHooks, goto } from "../helpers/app";
import { TEST_OTP } from "../helpers/env";
import { clearMailbox, waitForEmail } from "../helpers/mailpit";
import { PERSONAS, storageStatePath } from "../helpers/personas";
import { readSeed } from "../helpers/seed";

test.describe("UAT-DEV — automation determinism contracts @P0", () => {
  test("UAT-DEV-01 · the run's seed produced the deterministic scenario", async () => {
    const seed = readSeed();

    expect(seed.customer.email).toBe("qa-customer@veriprops.io");
    expect(seed.erasable.email).toBe("qa-erasable@veriprops.io");
    expect(seed.admin.email).toBeTruthy();

    // Every PREMIUM role has a credentialed, approved agent — assignment can proceed
    // without extra setup for either tier.
    expect(Object.keys(seed.agents)).toEqual(
      expect.arrayContaining(["REGISTRY", "FIELD", "SURVEYOR", "LAWYER"]),
    );

    // The primary verification is the review/release entry point; the ops verification is
    // the destructive-scenario fixture. Both must survive a reset+seed.
    expect(seed.verification.status).toBe("UNDER_REVIEW");
    expect(seed.verification.vid).toMatch(/^VP-/);
    expect(Object.keys(seed.tasks).length).toBeGreaterThan(0);
    expect(seed.ops.vid).toMatch(/^VP-/);
  });

  test("UAT-DEV-02 · the automation window hooks are live", async ({ page }) => {
    await goto(page, ROUTES.HOME);
    // __app_ready__ + __TEST_MODE__ gate every deterministic wait the suite performs.
    await expectAutomationHooks(page);
  });

  test("UAT-DEV-03 · the deterministic OTP verifies a fresh email", async () => {
    const api = await anonymousApi();
    try {
      const email = `uat-otp-${Date.now()}@veriprops.io`;
      await api.post("/users/auth/otp/send", {
        channel: "EMAIL",
        email,
        fullname: "UAT Probe",
      });

      // OTP_MODE=deterministic ⇒ TEST_OTP is always accepted; the suite never reads an
      // inbox for a code. A failure here means the backend is in random-OTP mode.
      const result = await api.post<{ verified: boolean }>("/users/auth/otp/verify", {
        channel: "EMAIL",
        email,
        code: TEST_OTP,
      });
      expect(result.verified).toBe(true);
    } finally {
      await api.dispose();
    }
  });

  test("UAT-DEV-04 · Mailpit captures outbound email", async () => {
    await clearMailbox();

    const api = await anonymousApi();
    try {
      const email = `uat-mail-${Date.now()}@veriprops.io`;
      await api.post("/users/auth/otp/send", {
        channel: "EMAIL",
        email,
        fullname: "UAT Probe",
      });

      // Proves the email path end-to-end (backend → SMTP → Mailpit), which every
      // token-driven flow (invite, reset, share) depends on.
      const message = await waitForEmail(email);
      expect(message.To.map((to) => to.Address)).toContain(email);
    } finally {
      await api.dispose();
    }
  });

});

test.describe("UAT-DEV — captured sessions @P0", () => {
  test.use({ storageState: storageStatePath(PERSONAS.CUSTOMER) });

  test("UAT-DEV-06 · no seeded persona is trapped by the consent modal", async ({ page }) => {
    await goto(page, ROUTES.PORTAL.DASHBOARD);

    // The re-acceptance modal (§3.2) is deliberately non-dismissible, so a seeded account
    // missing consent rows would block every click behind it and make UI automation
    // impossible. seed() records them; this is the guard that it still does.
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("UAT-DEV-05 · the seeded customer's session was captured", async ({ page }) => {
    const seed = readSeed();
    await goto(page, ROUTES.PORTAL.DASHBOARD);

    // globalSetup logged this persona in; the saved storageState must land authenticated
    // on a protected route rather than bouncing to /auth/login.
    await page.waitForFunction(() => window.__auth_snapshot__?.isAuthenticated === true);
    const userId = await page.evaluate(() => window.__auth_snapshot__?.userId);
    // User ids travel in two string forms (36-char with dashes vs 32-char hex) depending
    // on the surface — compare on the dashless form (backend CLAUDE.md).
    expect(userId?.replaceAll("-", "")).toBe(seed.customer.id.replaceAll("-", ""));
  });
});
