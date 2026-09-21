/**
 * UAT-GP — the golden-path lifecycle backbone (docs/uat-strategy.md §4).
 *
 * One ordered cross-persona journey driven entirely through the browser — the spine every
 * other area hangs off, and the producer of shared state (a real paid verification) that
 * branch specs consume.
 *
 * Currently implemented: **leg 1**, the customer's own journey — submit a STANDARD
 * verification through the wizard, pay via the deterministic stub, and land on the
 * confirmation with a VID and SLA date. Legs 2-6 (admin assignment → agent execution →
 * review/release → report → dispute) are still backlog; each will extend this file so the
 * journey stays one ordered narrative rather than fragmenting.
 */
import { expect, test } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { VerificationTier } from "@/types/verification";

import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitReady } from "../helpers/app";
import { loginViaUi } from "../helpers/auth";
import { TEST_OTP } from "../helpers/env";
import { PERSONAS, storageStatePath } from "../helpers/personas";
import { buildScenario, ScenarioStage } from "../helpers/scenario";
import { stubPay } from "../helpers/ui";

// The seeded customer resumes any unpaid draft, so parallel runs of this journey would share one.
test.describe("UAT-GP — golden path, leg 1: submission & payment @P0 @serial", () => {
  test.use({ storageState: storageStatePath(PERSONAS.CUSTOMER) });

  test("UAT-GP-01 · a customer submits and pays for a STANDARD verification", async ({ page }) => {
    await goto(page, ROUTES.PORTAL.VERIFICATIONS_NEW);

    // ── Step 1: Property ────────────────────────────────────────────────────
    // The draft is created lazily on first change, so typing is what starts the
    // verification — nothing exists server-side until the customer commits something.
    await expect(page.getByTestId("verify-new-property")).toBeVisible();
    await page.getByTestId("verify-new-type-land").click();
    await page.getByTestId("verify-new-address").fill("Plot 15 Admiralty Way, Lekki Phase 1");
    await page.getByTestId("verify-new-landmark").fill("Opposite the roundabout");
    await page.getByTestId("verify-new-state").fill("Lagos");
    await expectNoA11yViolations(page);
    await page.getByTestId("verify-new-continue").click();

    // ── Step 2: Tier & pricing ──────────────────────────────────────────────
    await expect(page.getByTestId("verify-new-tier")).toBeVisible();
    await page.getByTestId("verify-new-tier-standard").click();
    // The customer must see a real price before committing — the quote comes from the
    // backend, never computed client-side.
    await expect(page.getByTestId("verify-new-price-ngn")).toBeVisible();
    await page.getByTestId("verify-new-continue").click();

    // ── Step 3: Consent ─────────────────────────────────────────────────────
    await expect(page.getByTestId("verify-new-consent")).toBeVisible();
    await page.getByTestId("verify-new-consent-accept").click();
    await page.getByTestId("verify-new-continue").click();

    // ── Step 4: Payment ─────────────────────────────────────────────────────
    // Submitting routes to the pay page for the newly created verification.
    await page.waitForURL(/\/portal\/verifications\/[^/]+\/pay/, { timeout: 30_000 });
    await waitReady(page);
    await expect(page.getByTestId("verify-pay")).toBeVisible();
    await expectNoA11yViolations(page);

    // The seeded customer verified their phone long ago, so the pay-step phone gate (PRD
    // §10.5) must not stand in their way. UAT-GP-02 covers the customer who hasn't.
    await expect(page.getByTestId("verify-pay-initiate")).toBeVisible();
    await expect(page.getByTestId("verify-pay-phone-gate")).toHaveCount(0);

    await stubPay(page);

    // ── Outcome: the business-observable result ─────────────────────────────
    const confirmation = page.getByTestId("verify-confirmed");
    await expect(confirmation).toBeVisible();
    // A VID the customer can quote to support, and a completion date they can hold us to.
    await expect(confirmation).toContainText(/VP-/);
    await expect(confirmation).toContainText(/Estimated completion/i);
    await expect(page.getByTestId("verify-confirmed-track")).toBeVisible();
    await expectNoA11yViolations(page);
  });
});

test.describe("UAT-GP — golden path, leg 1: first-payment phone gate @P0", () => {
  // A fresh scenario customer, logged in through the UI — never the seeded persona.
  test.use({ storageState: { cookies: [], origins: [] } });

  test("UAT-GP-02 · a customer with an unverified phone corrects their number and verifies it before paying", async ({
    page,
  }) => {
    const scenario = await buildScenario(ScenarioStage.SUBMITTED, VerificationTier.STANDARD, {
      customerPhoneVerified: false,
    });
    await loginViaUi(page, scenario.customer.email, scenario.customer.password);
    await goto(page, ROUTES.PORTAL.VERIFICATION_PAY(scenario.verificationId));
    await waitReady(page);

    // ── The gate: the number on file is shown, and payment is not offered yet (PRD §10.5) ──
    const gate = page.getByTestId("verify-pay-phone-gate");
    await expect(gate).toBeVisible();
    await expect(page.getByTestId("verify-pay-initiate")).toHaveCount(0);
    const phoneInput = page.getByTestId("verify-pay-phone-input");
    await expect(phoneInput).not.toHaveValue("");
    await expectNoA11yViolations(page);

    // ── Correct the number, receive a code, verify it ───────────────────────
    const correctedNumber = `81${Math.floor(Math.random() * 1e8).toString().padStart(8, "0")}`;
    await phoneInput.fill(correctedNumber);
    await page.getByTestId("verify-pay-send-otp").click();
    await expect(page.getByTestId("verify-pay-otp")).toBeVisible();
    // The number is locked while its code is pending; "Change number" unlocks it.
    await expect(phoneInput).toBeDisabled();
    await expect(page.getByTestId("verify-pay-change-phone")).toBeVisible();
    await expectNoA11yViolations(page);
    await page.getByTestId("verify-pay-otp").fill(TEST_OTP);
    await page.getByTestId("verify-pay-verify-otp").click();

    // ── Outcome: the gate lifts and the customer pays ───────────────────────
    await expect(gate).toBeHidden();
    await stubPay(page);
    await expect(page.getByTestId("verify-confirmed")).toContainText(scenario.vid);
    await expectNoA11yViolations(page);
  });
});
