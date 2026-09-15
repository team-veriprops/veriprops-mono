/**
 * UI primitives shared across specs, anchored on the app's stable test ids so a spec reads as the
 * user journey rather than as selectors.
 */
import { readFile } from "node:fs/promises";

import { Locator, Page, expect } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { DATATABLE_TEST_IDS, datatableActionTestId } from "@components/ui/table/testIds";

import { waitReady } from "./app";

/** The DataTable row for the record with *rowId*. */
export function tableRow(page: Page, rowId: string): Locator {
  return page.locator(`[data-testid="${DATATABLE_TEST_IDS.ROW}"][data-row-id="${rowId}"]`);
}

/** Open *rowId*'s actions menu and choose the action labelled *label*. */
export async function rowAction(page: Page, rowId: string, label: string): Promise<void> {
  await tableRow(page, rowId).getByTestId(DATATABLE_TEST_IDS.ROW_ACTIONS).click();
  await page.getByTestId(datatableActionTestId(label)).click();
}

/** The open DetailDrawer (there is at most one at a time). */
export function drawer(page: Page): Locator {
  return page.getByTestId("detail-drawer");
}

/** Close the open DetailDrawer through its own close control. */
export async function closeDrawer(page: Page): Promise<void> {
  await drawer(page).getByTestId("detail-drawer-close").click();
  await expect(drawer(page)).toHaveCount(0);
}

/** A 403 navigates the whole page to the access-denied screen (frontend CLAUDE.md). */
export async function expectForbidden(page: Page): Promise<void> {
  await page.waitForURL((url) => url.pathname === ROUTES.FORBIDDEN);
}

/**
 * Pay on the verification pay step through the deterministic stub gateway and land on the
 * confirmation. The real gateway is out of scope (PRD §G); the checkout hand-off is still
 * asserted.
 */
export async function stubPay(page: Page): Promise<void> {
  await page.getByTestId("verify-pay-initiate").click();
  await expect(page.getByTestId("verify-pay-checkout")).toBeVisible();
  await page.getByTestId("verify-pay-confirm").click();
  await page.waitForURL(/\/portal\/verifications\/[^/]+\/confirmed/, { timeout: 30_000 });
  await waitReady(page);
}

/** Run *trigger*, capture the download it starts, and return the file's bytes (PDF/CSV). */
export async function downloadAndRead(page: Page, trigger: () => Promise<void>): Promise<Buffer> {
  const [download] = await Promise.all([page.waitForEvent("download"), trigger()]);
  const path = await download.path();
  return readFile(path);
}
