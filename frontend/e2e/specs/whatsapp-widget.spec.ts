/**
 * UAT-WA — WhatsApp channel front door (PRD §7.4.1, §7.10, S1).
 *
 * The widget is the channel's only customer-visible surface until the bot lands, and its
 * two acceptance properties are opposites: it must be reachable from everywhere, and it
 * must be absent from the payment flow. Both are asserted here against the real rendered
 * page, with the attribution code checked on the live href so the §7.10
 * "WhatsApp-attributed enquiries" metric cannot silently lose its input.
 */
import { expect, test } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { expectNoA11yViolations } from "../helpers/a11y";
import { goto } from "../helpers/app";
import { PERSONAS, storageStatePath } from "../helpers/personas";
import { readSeed } from "../helpers/seed";

const WIDGET = "[data-testid=whatsapp-widget]";

test.describe("UAT-WA — website WhatsApp widget @P1", () => {
  test("UAT-WA-01 · a visitor can reach Veriprops on WhatsApp from the landing page", async ({
    page,
  }) => {
    await goto(page, ROUTES.HOME);

    const widget = page.locator(WIDGET);
    await expect(widget).toBeVisible();
    await expect(widget).toHaveAccessibleName("Chat with Veriprops on WhatsApp");

    // The deep link carries the official number and this page's attribution code.
    const href = await widget.getAttribute("href");
    expect(href).toContain("https://wa.me/2349167624347");
    expect(decodeURIComponent(href ?? "")).toContain("[ref: web-home]");

    // Opens WhatsApp in its own context, never navigating the site away.
    await expect(widget).toHaveAttribute("target", "_blank");
    await expect(widget).toHaveAttribute("rel", /noopener/);

    await expectNoA11yViolations(page);
  });

  test("UAT-WA-02 · the code changes with the page, so enquiries stay attributable", async ({
    page,
  }) => {
    await goto(page, ROUTES.SAMPLE_REPORT);
    const href = await page.locator(WIDGET).getAttribute("href");
    expect(decodeURIComponent(href ?? "")).toContain("[ref: web-report-sample]");
    await expectNoA11yViolations(page);
  });
});

test.describe("UAT-WA — payment-flow suppression @P1", () => {
  test.use({ storageState: storageStatePath(PERSONAS.CUSTOMER) });

  test("UAT-WA-03 · the widget is absent on the payment step but present around it", async ({
    page,
  }) => {
    const seed = readSeed();

    // Present on the customer's own dashboard …
    await goto(page, ROUTES.PORTAL.DASHBOARD);
    await expect(page.locator(WIDGET)).toBeVisible();

    // … and gone once the customer is actually paying (PRD §7.4.1).
    await goto(page, ROUTES.PORTAL.VERIFICATION_PAY(seed.verification.id));
    await expect(page.locator(WIDGET)).toHaveCount(0);

    await expectNoA11yViolations(page);
  });
});
