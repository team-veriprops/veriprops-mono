/**
 * UAT — living with a case: tracking, notifications, held messages, the report PDF and admin notes
 * (PRD §9, §10, §11, §12, §6.3; docs/uat-strategy.md §9–§12, §6).
 *
 * The customer can follow their case and its activity, reaches the report only once it is
 * released, and downloads it as a PDF. Notifications can be read and cleared. A chat message
 * carrying a phone number is held — its sender told so without accusation — until an admin
 * approves it. An admin's note lands on the case.
 */
import { ROUTES } from "@lib/routes";
import { DATATABLE_TEST_IDS } from "@components/ui/table/testIds";
import { AdminMessagesTab } from "@components/chat/libs/adminMessagesTab";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto } from "../helpers/app";
import { ScenarioStage } from "../helpers/scenario";

test.describe("UAT-CASE — living with a case @P1", () => {
  test("UAT-CASE-01 · a case in progress can be followed, and its report appears only once released", async ({
    scenario,
    pageFor,
  }) => {
    const working = await scenario(ScenarioStage.IN_PROGRESS);
    const customer = await pageFor(working.customer);

    await goto(customer, ROUTES.PORTAL.VERIFICATION_TRACKING(working.verificationId));
    await expect(customer.getByTestId("verify-tracking")).toBeVisible();
    await expect(customer.getByTestId("tracking-view-report")).toHaveCount(0);
    await expectNoA11yViolations(customer);

    await customer.getByTestId("view-activity").click();
    await expect(customer.getByTestId("verification-activity")).toBeVisible();

    const released = await scenario(ScenarioStage.RELEASED);
    const owner = await pageFor(released.customer);
    await goto(owner, ROUTES.PORTAL.VERIFICATION_TRACKING(released.verificationId));
    await owner.getByTestId("tracking-view-report").click();
    await expect(owner.getByTestId("verify-report")).toBeVisible();
  });

  test("UAT-CASE-02 · the released report downloads as a PDF", async ({ scenario, pageFor }) => {
    const released = await scenario(ScenarioStage.RELEASED);
    const owner = await pageFor(released.customer);
    await goto(owner, ROUTES.PORTAL.VERIFICATION_REPORT(released.verificationId));

    const href = await owner.getByTestId("report-download-pdf").getAttribute("href");
    const pdf = await owner.request.get(href!);
    expect(pdf.status()).toBe(200);
    expect(pdf.headers()["content-type"]).toContain("application/pdf");
    expect((await pdf.body()).subarray(0, 5).toString()).toBe("%PDF-");
  });

  test("UAT-CASE-03 · notifications can be read and cleared", async ({ scenario, pageFor }) => {
    const released = await scenario(ScenarioStage.RELEASED);
    const owner = await pageFor(released.customer);

    await goto(owner, ROUTES.PORTAL.NOTIFICATIONS);
    const unread = owner.locator('[data-testid="notification"][data-read="false"]');
    await expect(unread.first()).toBeVisible();
    await expectNoA11yViolations(owner);
    await owner.getByTestId("notifications-mark-all").click();
    await expect(unread).toHaveCount(0);
  });

  test("UAT-CASE-04 · a message with a phone number is held, its sender told so, until an admin approves it", async ({
    scenario,
    pageFor,
    opsAdminPage,
  }) => {
    const working = await scenario(ScenarioStage.IN_PROGRESS);
    const customer = await pageFor(working.customer);
    const marker = `call me on 0803${Math.floor(1_000_000 + Math.random() * 8_999_999)}`;

    await goto(customer, ROUTES.PORTAL.VERIFICATION_MESSAGES(working.verificationId));
    await customer.getByTestId("chat-composer").fill(marker);
    await customer.getByTestId("chat-send").click();
    // Told it is being checked — not accused, and not silently swallowed.
    await expect(customer.getByText(marker)).toBeVisible();
    await expect(customer.getByText(/check/i).first()).toBeVisible();

    await goto(opsAdminPage, ROUTES.ADMIN.MESSAGES_TAB(AdminMessagesTab.REVIEW));
    const held = opsAdminPage.getByTestId("held-message").filter({ hasText: marker });
    await expect(held).toBeVisible();
    await expectNoA11yViolations(opsAdminPage);
    await held.getByTestId("held-message-approve").click();
    await expect(held).toHaveCount(0);
  });

  test("UAT-CASE-05 · an admin finds a case by its VID and leaves a note on it", async ({ scenario, opsAdminPage }) => {
    const working = await scenario(ScenarioStage.IN_PROGRESS);

    await goto(opsAdminPage, ROUTES.ADMIN.VERIFICATIONS);
    await opsAdminPage.getByTestId(DATATABLE_TEST_IDS.SEARCH).fill(working.vid);
    const row = opsAdminPage.getByTestId(DATATABLE_TEST_IDS.ROW);
    await expect(row).toHaveCount(1);
    await row.click();
    await expect(opsAdminPage.getByTestId("admin-verification-detail")).toBeVisible();

    const note = `Called the customer about site access (${working.vid}).`;
    await opsAdminPage.getByTestId("note-body").fill(note);
    await opsAdminPage.getByTestId("note-submit").click();
    await expect(opsAdminPage.getByText(note)).toBeVisible();
  });
});
