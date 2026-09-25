/**
 * UAT-STATUS — Dead ends (404, 403).
 *
 * Both pages are what a user meets when something already went wrong, so the only outcome that
 * matters is whether they can get out: a visible, working way forward, aimed at a surface this
 * particular user is allowed to open. The 403 is reached by every permission failure in the app
 * (`FetchHttpClient` redirects there), not just an admin's.
 */

import { AgentRole } from "@/types/agent";
import { ROUTES } from "@lib/routes";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto, waitForPage } from "../helpers/app";

const DEAD_URL = "/this-page-does-not-exist";

test.describe("UAT-STATUS — not found @P1", () => {
  // A dead link is most often followed by someone with no session at all.
  test.use({ storageState: { cookies: [], origins: [] } });

  test("UAT-STATUS-01 · a dead URL offers a way home that works", async ({ page }) => {
    await goto(page, DEAD_URL);

    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();

    // The way out must be a real control, not a label the theme failed to paint: clicking it
    // has to land on the home page.
    await page.getByRole("link", { name: "Go back home" }).click();
    await waitForPage(page, (url) => url.pathname === ROUTES.HOME);
  });

  test("UAT-STATUS-02 · the not-found page is accessible", async ({ page }) => {
    await goto(page, DEAD_URL);
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
    await expectNoA11yViolations(page);
  });
});

test.describe("UAT-STATUS — forbidden @P1", () => {
  test("UAT-STATUS-03 · a signed-out visitor is offered home, never a dashboard", async ({
    anonPage,
  }) => {
    await goto(anonPage, ROUTES.FORBIDDEN);

    await expect(anonPage.getByRole("heading", { name: /isn’t open to your account/ })).toBeVisible();
    await expect(anonPage.getByRole("link", { name: "Back to home" })).toBeVisible();
    // Offering a dashboard to someone with no session sends them to a login round-trip.
    await expect(anonPage.getByRole("link", { name: "Go to your dashboard" })).toHaveCount(0);
    await expectNoA11yViolations(anonPage);
  });

  // The page is shared by every persona, so a hardcoded destination is wrong for most of them.
  for (const [persona, dashboard] of [
    ["customer", ROUTES.PORTAL.DASHBOARD],
    ["agent", ROUTES.AGENT.DASHBOARD],
    ["admin", ROUTES.ADMIN.DASHBOARD],
  ] as const) {
    test(`UAT-STATUS-04 · ${persona}: sent to their own dashboard`, async ({
      customerPage,
      adminPage,
      agentPage,
    }) => {
      const page =
        persona === "customer" ? customerPage : persona === "admin" ? adminPage : await agentPage(AgentRole.FIELD);

      await goto(page, ROUTES.FORBIDDEN);

      const dashboardLink = page.getByRole("link", { name: "Go to your dashboard" });
      await expect(dashboardLink).toBeVisible();
      await dashboardLink.click();
      await waitForPage(page, (url) => url.pathname.startsWith(dashboard));
    });
  }
});
