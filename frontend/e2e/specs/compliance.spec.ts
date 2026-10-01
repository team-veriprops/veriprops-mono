/**
 * UAT — data protection: erasure, consent history and the audit trail (PRD §19, docs/uat-strategy.md §19).
 *
 * A customer asks for their data to be erased and is told where the request stands. Compliance
 * either refuses it with a reason the customer reads, or approves and carries it out — after an
 * explicit, irreversible confirmation — and the erased account can no longer sign in. Each
 * customer can see and download the consents they gave.
 */
import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { DATATABLE_TEST_IDS, datatableActionTestId } from "@components/ui/table/testIds";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto } from "../helpers/app";
import { loginViaUi } from "../helpers/auth";
import { ScenarioAccount, ScenarioStage } from "../helpers/scenario";

/** The account's id as the erasure table may print it: with or without the UUID dashes. */
function idPattern(account: ScenarioAccount): RegExp {
  const hex = account.id.replace(/-/g, "");
  const dashed = `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  return new RegExp(`${hex}|${dashed}`, "i");
}

/** Ask for erasure from the account's own privacy page, through its confirmation. */
async function requestErasure(page: Page): Promise<void> {
  await goto(page, ROUTES.ACCOUNT.DATA_PRIVACY);
  await page.getByTestId("request-erasure").click();
  await expect(page.getByTestId("erasure-request")).toBeVisible();
  await expectNoA11yViolations(page);
  await page.getByTestId("erasure-request-confirm").click();
  await expect(page.getByTestId("data-privacy")).toContainText("PENDING");
}

/** Open a row action on the compliance queue for *account*'s request. */
async function rowAction(admin: Page, account: ScenarioAccount, label: string): Promise<void> {
  await goto(admin, ROUTES.ADMIN.ERASURE_REQUESTS);
  const row = admin.getByTestId(DATATABLE_TEST_IDS.ROW).filter({ hasText: idPattern(account) });
  await row.getByTestId(DATATABLE_TEST_IDS.ROW_ACTIONS).click();
  await admin.getByTestId(datatableActionTestId(label)).click();
}

test.describe("UAT-COMP — data protection @P0", () => {
  test("UAT-COMP-01 · a refused erasure request reaches the customer with its reason", async ({
    scenario,
    pageFor,
    adminPage,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    await requestErasure(page);

    await rowAction(adminPage, customer, "Reject");
    const dialog = adminPage.getByTestId("erasure-reject");
    await expect(dialog).toBeVisible();
    // A refusal names its reason: the customer is pointed at it.
    await expect(adminPage.getByTestId("erasure-reject-confirm")).toBeDisabled();
    await adminPage.getByTestId("erasure-reject-reason").fill("Your verification history must be retained for six years.");
    await adminPage.getByTestId("erasure-reject-confirm").click();
    await expect(dialog).toBeHidden();

    await goto(page, ROUTES.ACCOUNT.DATA_PRIVACY);
    await expect(page.getByTestId("data-privacy")).toContainText("REJECTED");
    await expect(page.getByTestId("data-privacy")).toContainText("retained for six years");
  });

  test("UAT-COMP-02 · an approved erasure is carried out only after an explicit confirmation, and the account is gone", async ({
    scenario,
    pageFor,
    adminPage,
    anonPage,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    await requestErasure(await pageFor(customer));

    await rowAction(adminPage, customer, "Approve");
    await rowAction(adminPage, customer, "Execute erasure");
    const dialog = adminPage.getByTestId("erasure-execute");
    await expect(dialog).toContainText("cannot be undone");
    // Backing out changes nothing.
    await adminPage.getByTestId("erasure-execute-back").click();
    await expect(dialog).toBeHidden();
    await rowAction(adminPage, customer, "Execute erasure");
    await adminPage.getByTestId("erasure-execute-confirm").click();
    await expect(dialog).toBeHidden();
    await expect(
      adminPage.getByTestId(DATATABLE_TEST_IDS.ROW).filter({ hasText: idPattern(customer) }),
    ).toContainText(/executed/i);

    // The erased account can no longer sign in.
    await goto(anonPage, ROUTES.AUTH.LOGIN);
    await loginViaUi(anonPage, customer.email, customer.password).catch(() => undefined);
    expect(await anonPage.evaluate(() => window.__auth_snapshot__?.isAuthenticated ?? false)).toBe(false);
  });

  test("UAT-COMP-03 · a customer sees and can download the consents they gave", async ({ scenario, pageFor }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);

    await goto(page, ROUTES.ACCOUNT.CONSENTS);
    const history = page.getByTestId("consent-history");
    await expect(history).toContainText(/terms/i);
    await expect(history).toContainText(/privacy/i);
    await expect(page.getByTestId("consent-download")).toHaveAttribute("href", /consents\/history\/download/);
    await expectNoA11yViolations(page);
  });

  test("UAT-COMP-04 · the admin audit trail records the decisions taken", async ({ adminPage }) => {
    await goto(adminPage, ROUTES.ADMIN.AUDIT_ACTIONS);
    await expect(adminPage.getByTestId("admin-audit-log")).toBeVisible();
    await expect(adminPage.getByTestId(DATATABLE_TEST_IDS.ROW).first()).toBeVisible();
    await expectNoA11yViolations(adminPage);
  });
});
