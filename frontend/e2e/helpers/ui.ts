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

/**
 * Sign out the way the user would on this layout, then wait for the login page. Desktop signs out
 * from the top-nav user menu; below `lg` that menu is hidden, and signing out lives in the drawer.
 */
export async function signOut(page: Page): Promise<void> {
  const userMenu = page.getByTestId("user-menu");
  const drawerToggle = page.getByTestId("sidebar-open");
  // Both entry points are always in the DOM — CSS hides one per breakpoint — so wait for whichever
  // is actually visible before choosing (an instant check can run before the shell paints).
  await expect(userMenu.or(drawerToggle).filter({ visible: true })).toBeVisible();
  if (await userMenu.isVisible()) {
    const signOutItem = page.getByTestId("user-menu-signout");
    // A click that lands before the dropdown is interactive only focuses the trigger. Retry the
    // open until the item shows, clicking only while the menu is closed so a slow render is never
    // toggled shut.
    await expect(async () => {
      if ((await userMenu.getAttribute("aria-expanded")) !== "true") {
        await userMenu.click();
      }
      await expect(signOutItem).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 15_000 });
    await signOutItem.click();
  } else {
    const signOutItem = page.getByTestId("sidebar-signout");
    // The drawer stays mounted and slides in, so its contents keep a box on the page and read as
    // "visible" even while parked off-screen — being *in the viewport* is what says it is open.
    // The toggle only ever opens (never closes), so retrying the click is safe: a click that lands
    // before hydration does nothing at all.
    await expect(async () => {
      await drawerToggle.click();
      await expect(signOutItem).toBeInViewport({ timeout: 2_000 });
    }).toPass({ timeout: 15_000 });
    await signOutItem.click();
  }
  await page.waitForURL((url) => url.pathname === ROUTES.AUTH.LOGIN);
}

/**
 * Follow a sidebar entry by its label, whichever layout is on screen.
 *
 * The shell renders one nav for the desktop rail and one inside the mobile drawer, so a bare
 * `getByRole("link")` matches twice and the mobile copy is parked off-screen until the drawer is
 * opened. Layout detection mirrors {@link signOut}: both entry points are always in the DOM and
 * CSS hides one per breakpoint.
 */
export async function openNavItem(page: Page, title: string): Promise<void> {
  const userMenu = page.getByTestId("user-menu");
  const drawerToggle = page.getByTestId("sidebar-open");
  await expect(userMenu.or(drawerToggle).filter({ visible: true })).toBeVisible();

  const item = page.getByRole("link", { name: title, exact: true }).filter({ visible: true });

  if (await drawerToggle.isVisible()) {
    // The drawer stays mounted and slides in, so its contents read as "visible" even while parked
    // off-screen — being *in the viewport* is what says it is open. The toggle only ever opens, so
    // retrying the click is safe: one that lands before hydration does nothing at all.
    await expect(async () => {
      await drawerToggle.click();
      await expect(item.first()).toBeInViewport({ timeout: 2_000 });
    }).toPass({ timeout: 15_000 });
  }

  await item.first().click();
}

/** Run *trigger*, capture the download it starts, and return the file's bytes (PDF/CSV). */
export async function downloadAndRead(page: Page, trigger: () => Promise<void>): Promise<Buffer> {
  const [download] = await Promise.all([page.waitForEvent("download"), trigger()]);
  const path = await download.path();
  return readFile(path);
}
