/**
 * UAT — public lookup and report sharing (PRD §13, docs/uat-strategy.md §13 + UAT-LEAK-01).
 *
 * A released report is private until its owner shares it. Every path out — the public VID
 * lookup, a summary link, a named recipient — shows exactly the allow-listed summary or (after a
 * disclaimer) the report to the person it was meant for, and stops the moment it is turned off or
 * revoked. Nothing the owner did not choose to share reaches a stranger: not their name, their
 * email, the property's street address, or the numeric trust score.
 */
import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto } from "../helpers/app";
import { Scenario, ScenarioStage } from "../helpers/scenario";

/** What a scenario's case carries that a stranger must never see. */
const PRIVATE_DETAILS = ["12 Scenario Close", "Beside the estate gate", "Scenario"];

/** Open the owner's report, through its one-time gate, and then the sharing controls. */
async function openSharing(page: Page, scenario: Scenario): Promise<Page> {
  await goto(page, ROUTES.PORTAL.VERIFICATION_REPORT(scenario.verificationId));
  // Wait for the report itself before deciding: the one-time gate renders with it.
  const gate = page.getByTestId("report-gate-accept");
  await expect(gate.or(page.getByTestId("report-share")).first()).toBeVisible();
  if (await gate.isVisible()) {
    await gate.click();
    await expect(gate).toBeHidden();
  }
  await page.getByTestId("report-share").click();
  await expect(page.getByTestId("report-share-modal")).toBeVisible();
  return page;
}

/** The token at the end of the newest share link the modal lists. */
async function newestShareToken(page: Page): Promise<string> {
  const link = page.getByTestId("report-share-modal").getByText(/\/shared\//).last();
  await expect(link).toBeVisible();
  const url = (await link.innerText()).trim();
  return url.slice(url.lastIndexOf("/") + 1);
}

/** A stranger's page must carry none of the owner's private details. */
async function expectNoPrivateDetails(page: Page, scenario: Scenario): Promise<void> {
  const text = await page.locator("main").innerText();
  for (const detail of [...PRIVATE_DETAILS, scenario.customer.email]) {
    expect(text, `a public page showed "${detail}"`).not.toContain(detail);
  }
  // The trust *band* is public; the number behind it is not.
  expect(text).not.toMatch(/trust score\s*\d/i);
}

test.describe("UAT-PUB — public lookup & sharing @P0", () => {
  test("UAT-PUB-01 · a released report stays private until its owner turns the public lookup on, and off again", async ({
    scenario,
    pageFor,
    anonPage,
  }) => {
    const released = await scenario(ScenarioStage.RELEASED);

    // Private by default: the lookup says nothing about whether the case exists.
    await goto(anonPage, ROUTES.PUBLIC.VERIFY(released.vid));
    await expect(anonPage.getByTestId("public-state-notice")).toBeVisible();
    await expect(anonPage.getByTestId("public-summary")).toHaveCount(0);

    const owner = await openSharing(await pageFor(released.customer), released);
    const toggle = owner.getByTestId("share-public-toggle");
    await expect(toggle).toHaveText("Turn on");
    await toggle.click();
    await expect(toggle).toHaveText("Turn off");

    await goto(anonPage, ROUTES.PUBLIC.VERIFY(released.vid));
    const summary = anonPage.getByTestId("public-summary");
    await expect(summary).toBeVisible();
    await expect(summary).toContainText(released.vid);
    await expect(summary).toContainText("Verified");
    await expectNoPrivateDetails(anonPage, released);
    await expectNoA11yViolations(anonPage);

    // The owner can take it back.
    await toggle.click();
    await expect(toggle).toHaveText("Turn on");
    await goto(anonPage, ROUTES.PUBLIC.VERIFY(released.vid));
    await expect(anonPage.getByTestId("public-state-notice")).toBeVisible();
  });

  test("UAT-PUB-02 · a summary link shows the summary to anyone holding it, until it is revoked", async ({
    scenario,
    pageFor,
    anonPage,
  }) => {
    const released = await scenario(ScenarioStage.RELEASED);
    const owner = await openSharing(await pageFor(released.customer), released);

    await owner.getByTestId("share-create-link").click();
    const token = await newestShareToken(owner);

    await goto(anonPage, ROUTES.PUBLIC.SHARED(token));
    await expect(anonPage.getByTestId("public-summary")).toContainText(released.vid);
    await expectNoPrivateDetails(anonPage, released);

    await owner.getByTestId("share-revoke").last().click();
    await expect(owner.getByTestId("share-revoke")).toHaveCount(0);
    await goto(anonPage, ROUTES.PUBLIC.SHARED(token));
    await expect(anonPage.getByTestId("public-state-notice")).toContainText("no longer available");
  });

  test("UAT-PUB-03 · a named recipient sees the full report only after acknowledging the disclaimer", async ({
    scenario,
    pageFor,
    anonPage,
  }) => {
    const released = await scenario(ScenarioStage.RELEASED);
    const owner = await openSharing(await pageFor(released.customer), released);

    await owner.getByTestId("share-named-email").fill("lawyer@example.com");
    await owner.getByTestId("share-named-send").click();
    const token = await newestShareToken(owner);

    await goto(anonPage, ROUTES.PUBLIC.SHARED(token));
    await expect(anonPage.getByTestId("shared-disclaimer")).toBeVisible();
    await expect(anonPage.getByTestId("shared-full-report")).toHaveCount(0);
    await expectNoA11yViolations(anonPage);

    await anonPage.getByTestId("shared-ack").click();
    await expect(anonPage.getByTestId("shared-full-report")).toBeVisible();
  });

  test("UAT-PUB-04 · an unknown VID and a made-up link fail the same way a private case does", async ({
    anonPage,
  }) => {
    // No oracle: a stranger cannot tell "doesn't exist" from "exists but private".
    await goto(anonPage, ROUTES.PUBLIC.VERIFY("VP-2026-NOPE00"));
    await expect(anonPage.getByTestId("public-state-notice")).toBeVisible();
    await goto(anonPage, ROUTES.PUBLIC.SHARED("not-a-real-token"));
    await expect(anonPage.getByTestId("public-state-notice")).toContainText("no longer available");
  });
});
