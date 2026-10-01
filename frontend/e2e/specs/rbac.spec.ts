/**
 * UAT — roles and access (PRD §4, §6a, docs/uat-strategy.md §4).
 *
 * Each admin sub-role reaches its own work and is turned away from the rest; a customer can never
 * open another customer's case, however they come by its id; and an admin invitation can be taken
 * up only by the account it was issued to.
 */
import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { expect, test } from "../fixtures";
import { goto, waitForPage } from "../helpers/app";
import { ScenarioStage } from "../helpers/scenario";

/** Open *path* and expect the access-denied page, whichever way the refusal arrives. */
async function expectTurnedAway(page: Page, path: string): Promise<void> {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await waitForPage(page, (url) => url.pathname === ROUTES.FORBIDDEN, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: /isn.t open to your account/i })).toBeVisible();
}

test.describe("UAT-RBAC — roles and access @P0", () => {
  test("UAT-RBAC-01 · Finance reaches payouts and is turned away from compliance", async ({ financeAdminPage }) => {
    await goto(financeAdminPage, ROUTES.ADMIN.FINANCE_PAYOUTS);
    await expect(financeAdminPage.getByTestId("admin-payouts").or(financeAdminPage.getByText(/no payouts/i)).first()).toBeVisible();
    await expectTurnedAway(financeAdminPage, ROUTES.ADMIN.ERASURE_REQUESTS);
  });

  test("UAT-RBAC-02 · Operations reaches verifications and is turned away from finance", async ({ opsAdminPage }) => {
    await goto(opsAdminPage, ROUTES.ADMIN.VERIFICATIONS);
    await expect(opsAdminPage.getByRole("heading").first()).toBeVisible();
    await expectTurnedAway(opsAdminPage, ROUTES.ADMIN.FINANCE_PAYOUTS);
  });

  test("UAT-RBAC-03 · a customer cannot open another customer's case by its id", async ({ scenario, pageFor }) => {
    const theirs = await scenario(ScenarioStage.RELEASED);
    const mine = await scenario(ScenarioStage.DRAFT);
    const intruder = await pageFor(mine.customer);

    for (const path of [
      ROUTES.PORTAL.VERIFICATION_DETAIL(theirs.verificationId),
      ROUTES.PORTAL.VERIFICATION_REPORT(theirs.verificationId),
    ]) {
      // The case API refuses with 403 and the client lands on the access-denied page. Waiting for
      // that page is what makes the checks below meaningful, and keeps the late redirect from
      // aborting the next navigation.
      await expectTurnedAway(intruder, path);
      await expect(intruder.locator("body")).not.toContainText(theirs.vid);
      await expect(intruder.locator("body")).not.toContainText("12 Scenario Close");
    }
  });

  test("UAT-RBAC-04 · an admin invitation is taken up only by the account it was issued to", async ({
    scenario,
    pageFor,
    adminPage,
  }) => {
    const invited = (await scenario(ScenarioStage.DRAFT)).customer;
    const stranger = (await scenario(ScenarioStage.DRAFT)).customer;

    await goto(adminPage, ROUTES.ADMIN.TEAM);
    await adminPage.getByTestId("admin-invite-toggle").click();
    await adminPage.getByTestId("admin-invite-first-name").fill("Ada");
    await adminPage.getByTestId("admin-invite-last-name").fill("Finance");
    await adminPage.getByTestId("admin-invite-email").fill(invited.email);
    await adminPage.getByTestId("admin-invite-role").click();
    await adminPage.getByRole("option", { name: /finance/i }).click();
    await adminPage.getByTestId("admin-invite-submit").click();

    // The Super Admin is handed the link to pass on (no invitation email yet — PRD §G).
    const link = (await adminPage.getByTestId("admin-invite-link").innerText()).match(/https?:\/\/\S+/)![0];
    const path = new URL(link).pathname;

    // Someone else signed in cannot use the link.
    const wrong = await pageFor(stranger);
    await goto(wrong, path);
    await wrong.getByTestId("admin-invite-accept-btn").click();
    await waitForPage(wrong, (url) => url.pathname === ROUTES.FORBIDDEN, { timeout: 30_000 });

    // The invited account accepts and lands in the admin area.
    const right = await pageFor(invited);
    await goto(right, path);
    await right.getByTestId("admin-invite-accept-btn").click();
    await waitForPage(right, (url) => url.pathname.startsWith("/admin"), { timeout: 30_000 });
  });
});
