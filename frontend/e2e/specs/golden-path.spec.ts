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

import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitReady } from "../helpers/app";
import { TEST_OTP } from "../helpers/env";
import { PERSONAS, storageStatePath } from "../helpers/personas";

test.describe("UAT-GP — golden path, leg 1: submission & payment @P0", () => {
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

    // A customer whose phone is unverified must clear the phone gate before paying
    // (PRD §10.5). The seeded customer is already verified, so this is conditional.
    const phoneGate = page.getByTestId("verify-pay-phone-gate");
    if (await phoneGate.isVisible().catch(() => false)) {
      await page.getByTestId("verify-pay-send-otp").click();
      await page.getByTestId("verify-pay-otp").fill(TEST_OTP);
      await page.getByTestId("verify-pay-verify-otp").click();
    }

    await page.getByTestId("verify-pay-initiate").click();
    // The stub gateway stands in for Paystack/Flutterwave — the checkout hand-off is
    // asserted, the real gateway is out of scope (PRD §G).
    await expect(page.getByTestId("verify-pay-checkout")).toBeVisible();
    await page.getByTestId("verify-pay-confirm").click();

    // ── Outcome: the business-observable result ─────────────────────────────
    await page.waitForURL(/\/portal\/verifications\/[^/]+\/confirmed/, { timeout: 30_000 });
    await waitReady(page);

    const confirmation = page.getByTestId("verify-confirmed");
    await expect(confirmation).toBeVisible();
    // A VID the customer can quote to support, and a completion date they can hold us to.
    await expect(confirmation).toContainText(/VP-/);
    await expect(confirmation).toContainText(/Estimated completion/i);
    await expect(page.getByTestId("verify-confirmed-track")).toBeVisible();
    await expectNoA11yViolations(page);
  });
});
