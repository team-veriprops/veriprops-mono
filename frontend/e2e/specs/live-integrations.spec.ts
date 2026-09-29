/**
 * UAT-LIVE — the third-party journeys, for real, on a deployed staging (docs/live-integration-smoke.md).
 *
 * `@live` never runs in CI or in `pnpm e2e`: it pays a sandbox gateway, calls Dojah and writes to
 * S3, and it only means something against a deployment running those integrations live. It runs
 * on demand — `UAT_BASE_URL=https://staging.veriprops.ng pnpm e2e:live` — as the release gate
 * beside `backend/scripts/live_smoke.py`, which covers the calls that need no browser.
 *
 * What only a browser on the deployment can show:
 * - a customer pays on the gateway's hosted page, comes back, and the webhook makes the case PAID —
 *   then failing the case refunds the charge, and the gateway accepts the refund;
 * - the report PDF renders on the deployed runtime, not just on a developer's machine;
 * - an applicant's selfie and ID photo go through Dojah's liveness check, land in private storage,
 *   and reach the reviewer side by side through short-lived links that actually load.
 *
 * Staging is shared with human QA, so nothing is reset: every case and account comes from
 * `/dev/scenario`, fresh per test.
 */
import path from "node:path";

import { Browser, Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { DATATABLE_TEST_IDS } from "@components/ui/table/testIds";

import { expect, test } from "../fixtures";
import { LIVE_ADMIN_EMAIL, LIVE_ADMIN_PASSWORD, LIVE_SELFIE } from "../helpers/env";
import { openLive, payOnHostedCheckout, signInLive } from "../helpers/live";
import { buildScenario, ScenarioStage } from "../helpers/scenario";

const ID_DOCUMENT_PHOTO = path.join("e2e", "fixtures", "evidence-photo.jpg");
const SURVEYOR_LICENCE = "SURCON/2026/4471";
const FAIL_REASON = "Live smoke: refunding the sandbox charge.";

/**
 * A value the live run needs, or a failure naming it. Never a skip: a skipped live test proves
 * nothing, and a release gate must not go green on one.
 */
function required(value: string | undefined, name: string, what: string): string {
  if (!value) throw new Error(`Set ${name}: ${what}.`);
  return value;
}

/** Staging's super admin. */
function liveAdmin(): { email: string; password: string } {
  return {
    email: required(LIVE_ADMIN_EMAIL, "UAT_LIVE_ADMIN_EMAIL", "staging's SUPER_ADMIN_EMAIL"),
    password: required(LIVE_ADMIN_PASSWORD, "UAT_LIVE_ADMIN_PASSWORD", "staging's SUPER_ADMIN_PASSWORD"),
  };
}

/** Run *act* as another person, in a browser context of their own that is closed afterwards. */
async function asAnotherPerson(
  browser: Browser,
  account: { email: string; password: string },
  act: (page: Page) => Promise<void>,
): Promise<void> {
  const context = await browser.newContext({ ignoreHTTPSErrors: true });
  try {
    const page = await context.newPage();
    await signInLive(page, account.email, account.password);
    await act(page);
  } finally {
    await context.close();
  }
}

test.describe("UAT-LIVE — third-party journeys on staging @live", () => {
  // Real gateways, real storage, real identity checks: minutes, not seconds. Each test stands
  // alone, so one integration being down does not hide the others.
  test.describe.configure({ timeout: 600_000 });

  test("UAT-LIVE-01 · a customer pays on the gateway's hosted page, and failing the case refunds it", async ({
    page,
    browser,
  }) => {
    const admin = liveAdmin();
    const scenario = await buildScenario(ScenarioStage.SUBMITTED);
    await signInLive(page, scenario.customer.email, scenario.customer.password);

    // ── Pay: out to the gateway with its sandbox card, and back ─────────────
    await openLive(page, ROUTES.PORTAL.VERIFICATION_PAY(scenario.verificationId), "verify-pay-initiate");
    await page.getByTestId("verify-pay-initiate").click();
    const gateway = await payOnHostedCheckout(page);
    test.info().annotations.push({ type: "gateway", description: gateway });

    // The gateway's webhook (verified against the charge) is what makes the case PAID; the pay
    // page waits for it and moves on by itself, or offers to check again.
    const confirmed = ROUTES.PORTAL.VERIFICATION_CONFIRMED(scenario.verificationId);
    await expect(async () => {
      if (new URL(page.url()).pathname === confirmed) return;
      const checkAgain = page.getByTestId("verify-pay-check-again");
      if (await checkAgain.isVisible()) await checkAgain.click();
      throw new Error("still waiting for the payment to be confirmed");
    }).toPass({ timeout: 180_000, intervals: [5_000] });

    // ── Refund: an admin fails the case, and the gateway accepts the refund ──
    await asAnotherPerson(browser, admin, async (adminPage) => {
      await openLive(adminPage, ROUTES.ADMIN.REPORT_REVIEW(scenario.verificationId), "fail-reason");
      await adminPage.getByTestId("fail-reason").fill(FAIL_REASON);
      await adminPage.getByTestId("fail-submit").click();
      // The refund is asked for inside the failing request, and the admin is told what the
      // gateway did: this sentence only when it took the refund (`failSummary`).
      await expect(adminPage.getByText("Verification failed & refunded", { exact: true })).toBeVisible();
    });
  });

  test("UAT-LIVE-02 · a released report downloads as a PDF rendered on the deployment", async ({ page }) => {
    const scenario = await buildScenario(ScenarioStage.RELEASED);
    await signInLive(page, scenario.customer.email, scenario.customer.password);

    await openLive(page, ROUTES.PORTAL.VERIFICATION_REPORT(scenario.verificationId), "report-download-pdf");
    const href = await page.getByTestId("report-download-pdf").getAttribute("href");
    expect(href).toBeTruthy();

    const response = await page.request.get(href!);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("application/pdf");
    const body = await response.body();
    expect(body.subarray(0, 5).toString()).toBe("%PDF-");
  });

  test("UAT-LIVE-03 · an applicant's selfie and passport photo reach the reviewer side by side", async ({
    page,
    browser,
  }) => {
    const admin = liveAdmin();
    const selfie = required(LIVE_SELFIE, "UAT_LIVE_SELFIE", "a JPEG of a real, live face (Dojah's liveness check)");
    const { customer } = await buildScenario(ScenarioStage.DRAFT);
    await signInLive(page, customer.email, customer.password);

    // ── Apply with a passport: liveness on the selfie, then a person decides ─
    await openLive(page, ROUTES.AGENT.APPLY, "agent-apply-role-field");
    await page.getByTestId("agent-apply-role-field").click();
    await page.getByTestId("agent-apply-role-surveyor").click();
    await page.getByTestId("agent-apply-continue").click();

    await expect(page.getByTestId("agent-apply-kyc")).toBeVisible();
    await page.getByTestId("agent-apply-kyc-method-govid").click();
    await page.getByTestId("agent-apply-idtype").click();
    await page.getByRole("option", { name: /passport/i }).click();
    await page.getByTestId("agent-apply-idnumber").fill("A00000000");
    await page.getByTestId("agent-apply-selfie-file").setInputFiles(selfie);
    await expect(page.getByTestId("agent-apply-selfie-preview")).toBeVisible();
    await page.getByTestId("agent-apply-id-document-file").setInputFiles(ID_DOCUMENT_PHOTO);
    await expect(page.getByTestId("agent-apply-id-document-preview")).toBeVisible();
    await page.getByTestId("agent-apply-continue").click();

    await expect(page.getByTestId("agent-apply-credentials")).toBeVisible();
    await page.getByTestId("agent-apply-licence-surveyor").fill(SURVEYOR_LICENCE);
    await page.getByTestId("agent-apply-continue").click();
    await expect(page.getByTestId("agent-apply-review")).toBeVisible();
    await page.getByTestId("agent-apply-truthfulness").click();
    await page.getByTestId("agent-apply-terms").click();
    await page.getByTestId("agent-apply-submit").click();
    await expect(page.getByTestId("agent-status-card")).toContainText("Pending review");

    // ── The reviewer: both photos, from private storage, side by side ───────
    await asAnotherPerson(browser, admin, async (adminPage) => {
      await openLive(adminPage, ROUTES.ADMIN.AGENT_APPLICATIONS, DATATABLE_TEST_IDS.SEARCH);
      await adminPage.getByTestId(DATATABLE_TEST_IDS.SEARCH).fill(customer.email);
      const row = adminPage.getByTestId(DATATABLE_TEST_IDS.ROW);
      await expect(row).toHaveCount(1);
      await row.click();

      const compare = adminPage.getByTestId("admin-kyc-compare");
      await expect(compare).toBeVisible();
      for (const photo of ["admin-kyc-selfie", "admin-kyc-document"]) {
        // A presigned link that is wrong, expired or refused leaves an image with no pixels.
        await expect
          .poll(() => adminPage.getByTestId(photo).evaluate((img) => (img as HTMLImageElement).naturalWidth))
          .toBeGreaterThan(0);
      }

      // The divider moves from the keyboard, enlarging the selfie side.
      const divider = adminPage.getByTestId("admin-kyc-compare-divider");
      const before = Number(await divider.getAttribute("aria-valuenow"));
      await divider.focus();
      await adminPage.keyboard.press("ArrowRight");
      await expect.poll(async () => Number(await divider.getAttribute("aria-valuenow"))).toBeGreaterThan(before);
    });
  });
});
