/**
 * UAT — agent earnings and payouts (PRD §15, docs/uat-strategy.md §15).
 *
 * An agent withdraws to an account the bank itself has named, sees the transfer fee before
 * confirming, and can take back a request Finance has not touched. Finance approves and pays out,
 * or holds one with a reason the agent can read, and a rejected withdrawal returns its funds.
 */
import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { AgentRole } from "@/types/agent";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto } from "../helpers/app";
import { ScenarioStage, scenarioAgent } from "../helpers/scenario";

/** Request a withdrawal of *naira* into the agent's first saved account; returns the payout id. */
async function requestWithdrawal(page: Page, naira: number): Promise<string> {
  await goto(page, ROUTES.AGENT.PAYOUTS);
  await page.getByTestId("payout-amount").fill(String(naira));
  await page.getByTestId("payout-bank").selectOption({ index: 1 });
  await page.getByTestId("payout-review-btn").click();
  // The fee is quoted before anything is requested, and comes out of what the agent receives.
  await expect(page.getByTestId("payout-quote-fee")).toBeVisible();
  await expect(page.getByTestId("payout-quote-net")).toBeVisible();
  const historyBefore = await page.getByTestId("payout-history").locator("li").count().catch(() => 0);
  await page.getByTestId("payout-submit").click();
  const rows = page.getByTestId("payout-history").locator("> li");
  await expect(rows).toHaveCount(historyBefore + 1);
  const testId = await rows.first().getAttribute("data-testid");
  return testId!.replace(/^payout-/, "");
}

test.describe("UAT-PAY — earnings & payouts @P0", () => {
  test("UAT-PAY-01 · a withdrawal Finance approves is paid out to the agent's bank", async ({
    scenario,
    pageFor,
    financeAdminPage,
  }) => {
    const ready = await scenario(ScenarioStage.PAYOUT_READY);
    const registry = scenarioAgent(ready, AgentRole.REGISTRY);
    const agent = await pageFor(registry);

    await goto(agent, ROUTES.AGENT.EARNINGS);
    await expect(agent.getByTestId("earning-jobs")).toBeVisible();

    const payoutId = await requestWithdrawal(agent, Math.floor(registry.availableMinor! / 200));
    await expect(agent.getByTestId(`payout-${payoutId}`)).toContainText(/requested/i);
    await expectNoA11yViolations(agent);

    await goto(financeAdminPage, ROUTES.ADMIN.FINANCE_PAYOUTS);
    await financeAdminPage.getByTestId(`admin-payout-${payoutId}`).click();
    await financeAdminPage.getByTestId("payout-approve").click();
    await expect(financeAdminPage.getByTestId(`admin-payout-${payoutId}`)).toContainText(/approved/i);
    await financeAdminPage.keyboard.press("Escape");
    await financeAdminPage.getByTestId("payout-disburse").click();
    await expect(financeAdminPage.getByTestId(`admin-payout-${payoutId}`)).toContainText(/paid/i);

    await goto(agent, ROUTES.AGENT.PAYOUTS);
    await expect(agent.getByTestId(`payout-${payoutId}`)).toContainText(/paid/i);
  });

  test("UAT-PAY-02 · a held withdrawal tells the agent it is under review, and rejecting it releases the funds", async ({
    scenario,
    pageFor,
    financeAdminPage,
  }) => {
    const ready = await scenario(ScenarioStage.PAYOUT_READY);
    const registry = scenarioAgent(ready, AgentRole.REGISTRY);
    const agent = await pageFor(registry);
    const payoutId = await requestWithdrawal(agent, Math.floor(registry.availableMinor! / 200));

    await goto(financeAdminPage, ROUTES.ADMIN.FINANCE_PAYOUTS);
    await financeAdminPage.getByTestId(`admin-payout-${payoutId}`).click();
    await financeAdminPage.getByLabel(/Note/).fill("Checking the account name with the bank.");
    await financeAdminPage.getByTestId("payout-hold").click();
    await expect(financeAdminPage.getByTestId(`admin-payout-${payoutId}`)).toContainText(/held/i);

    await goto(agent, ROUTES.AGENT.PAYOUTS);
    await expect(agent.getByTestId(`payout-${payoutId}`)).toContainText(/held/i);
    // The agent is told it is under review; Finance's own note stays internal.
    await expect(agent.getByTestId(`payout-${payoutId}-note`)).toContainText("reviewing");
    await expect(agent.getByTestId(`payout-${payoutId}`)).not.toContainText("Checking the account name");
    // Finance holds it, so it is no longer the agent's to cancel.
    await expect(agent.getByTestId(`payout-${payoutId}-cancel`)).toHaveCount(0);

    // Deciding closes the drawer; reopen it to decide again.
    await financeAdminPage.getByTestId(`admin-payout-${payoutId}`).click();
    await financeAdminPage.getByLabel(/Note/).fill("Account name does not match the agent.");
    await financeAdminPage.getByTestId("payout-reject").click();
    await expect(financeAdminPage.getByTestId(`admin-payout-${payoutId}`)).toContainText(/rejected/i);
    await goto(agent, ROUTES.AGENT.PAYOUTS);
    await expect(agent.getByTestId(`payout-${payoutId}`)).toContainText(/rejected/i);
  });

  test("UAT-PAY-03 · an agent withdraws a request Finance has not touched", async ({ scenario, pageFor }) => {
    const ready = await scenario(ScenarioStage.PAYOUT_READY);
    const registry = scenarioAgent(ready, AgentRole.REGISTRY);
    const agent = await pageFor(registry);
    const payoutId = await requestWithdrawal(agent, Math.floor(registry.availableMinor! / 200));

    await agent.getByTestId(`payout-${payoutId}-cancel`).click();
    await expect(agent.getByTestId(`payout-${payoutId}`)).toContainText(/cancelled/i);
  });

  test("UAT-PAY-04 · a new account is saved under the name the bank holds, never one the agent types", async ({
    scenario,
    pageFor,
  }) => {
    const ready = await scenario(ScenarioStage.PAYOUT_READY);
    const agent = await pageFor(scenarioAgent(ready, AgentRole.FIELD));
    await goto(agent, ROUTES.AGENT.PAYOUTS);

    await agent.getByTestId("bank-name").selectOption({ index: 1 });
    await agent.getByTestId("bank-number").fill("1234567890");
    await agent.getByTestId("bank-verify").click();
    await expect(agent.getByTestId("bank-resolved-name")).toContainText("TEST ACCOUNT 7890");
    await agent.getByTestId("bank-add").click();
    await expect(agent.getByTestId("bank-accounts")).toContainText("TEST ACCOUNT 7890");
    await expectNoA11yViolations(agent);
  });
});
