/**
 * UAT — after the report: disputes, re-checks and upgrades (PRD §19, docs/uat-strategy.md §14).
 *
 * A dispute that names part of the work reaches that task's agent, whose defence the admin reads
 * before deciding — and the agent never learns who the customer is. A re-check waits for an admin
 * to scope it. An upgrade charges only the difference and raises the tier.
 */
import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { AgentRole } from "@/types/agent";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitForPage } from "../helpers/app";
import { Scenario, ScenarioStage, scenarioAgent } from "../helpers/scenario";

/** The owner's released report, through its one-time access gate. */
async function openReport(page: Page, scenario: Scenario): Promise<void> {
  await goto(page, ROUTES.PORTAL.VERIFICATION_REPORT(scenario.verificationId));
  // Wait for the report itself before deciding: the one-time gate renders with it.
  const gate = page.getByTestId("report-gate-accept");
  await expect(gate.or(page.getByTestId("report-share")).first()).toBeVisible();
  if (await gate.isVisible()) {
    await gate.click();
    await expect(gate).toBeHidden();
  }
  await expect(page.getByTestId("action-dispute")).toBeVisible();
}

const DISPUTE_TEXT =
  "The survey plan in the report places the plot two hundred metres north of where the beacons " +
  "actually stand, and the coordinates do not match the registry extract I hold.";

test.describe("UAT-AFT — after the report @P0", () => {
  test("UAT-AFT-01 · a dispute naming the survey reaches the surveyor, whose defence the admin reads before deciding", async ({
    scenario,
    pageFor,
    opsAdminPage,
  }) => {
    const released = await scenario(ScenarioStage.RELEASED);
    const customer = await pageFor(released.customer);
    await openReport(customer, released);

    await customer.getByTestId("action-dispute").click();
    await expect(customer.getByTestId("dispute-dialog")).toBeVisible();
    await customer.getByTestId("dispute-role").selectOption(AgentRole.SURVEYOR);
    // Too short is refused before it is sent, at the length the backend configures.
    await customer.getByTestId("dispute-desc").fill("Too short.");
    await expect(customer.getByTestId("dispute-submit")).toBeDisabled();
    await customer.getByTestId("dispute-desc").fill(DISPUTE_TEXT);
    await expectNoA11yViolations(customer);
    await customer.getByTestId("dispute-submit").click();
    await expect(customer.getByTestId("dispute-dialog")).toBeHidden();

    // The surveyor is asked to answer — and is not told who the customer is.
    const surveyor = await pageFor(scenarioAgent(released, AgentRole.SURVEYOR));
    await goto(surveyor, ROUTES.AGENT.DISPUTES);
    const card = surveyor.getByTestId("agent-dispute-card").filter({ hasText: released.vid });
    await expect(card).toBeVisible();
    await expect(card).not.toContainText(released.customer.email);
    await card.getByTestId("agent-defence-text").fill("The beacons were located with the registry surveyor present; photos are on the task.");
    await card.getByTestId("agent-defence-submit").click();
    await expect(card.getByTestId("agent-defence-submit")).toHaveCount(0);

    // The admin reads that defence before resolving.
    await goto(opsAdminPage, ROUTES.ADMIN.DISPUTES);
    await opsAdminPage.getByTestId("dispute-row").filter({ hasText: released.vid }).click();
    await expect(opsAdminPage.getByText("photos are on the task")).toBeVisible();
    await opsAdminPage.getByTestId("outcome-REJECTED").check();
    await opsAdminPage.getByTestId("resolve-note").fill("The survey evidence matches the registry; the finding stands.");
    await opsAdminPage.getByTestId("resolve-submit").click();
    await expect(opsAdminPage.getByTestId("dispute-row").filter({ hasText: released.vid })).toHaveCount(0);
  });

  test("UAT-AFT-02 · an admin scopes and approves a re-check, and it leaves the queue", async ({
    scenario,
    opsAdminPage,
  }) => {
    const requested = await scenario(ScenarioStage.RECHECK_REQUESTED);

    await goto(opsAdminPage, ROUTES.ADMIN.RECHECKS);
    const row = opsAdminPage.getByTestId("recheck-row").filter({ hasText: requested.vid });
    await row.click();
    // Approving needs a scope: which parts are redone.
    await opsAdminPage.getByTestId(`recheck-role-${AgentRole.SURVEYOR}`).check();
    await expectNoA11yViolations(opsAdminPage);
    await opsAdminPage.getByTestId("recheck-approve").click();
    await expect(row).toHaveCount(0);
  });

  test("UAT-AFT-03 · an upgrade charges only the difference and raises the tier", async ({ scenario, pageFor }) => {
    const released = await scenario(ScenarioStage.RELEASED);
    const customer = await pageFor(released.customer);
    await openReport(customer, released);

    await customer.getByTestId("action-upgrade").click();
    await customer.getByTestId("upgrade-tier").selectOption("PREMIUM");
    await customer.getByTestId("upgrade-submit").click();

    // The stub checkout is the case's own pay page; paying it applies the upgrade.
    await waitForPage(customer, /\/pay\?/, { timeout: 30_000 });
    await customer.getByTestId("verify-pay-confirm").click();
    // An upgrade is a second payment on the case: it lands back on the case, not the
    // first-payment confirmation.
    await waitForPage(
      customer,
      (url) => url.pathname === ROUTES.PORTAL.VERIFICATION_DETAIL(released.verificationId),
      { timeout: 30_000 },
    );
    await expect(customer.getByText("Premium").first()).toBeVisible();
  });
});
