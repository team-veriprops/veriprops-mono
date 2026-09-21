/**
 * UAT-WAH — WhatsApp handoff landings (PRD §26.4.2, §26.5, S3).
 *
 * A handoff link is a bearer capability that travels through a chat, where forwarding a
 * message is ordinary behaviour. So the scenarios below are written from both sides: the
 * customer who follows their own link must land on their case with its context intact,
 * and anyone holding a forwarded copy must get nothing — with no hint of why.
 */
import { expect, test } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { HandoffIntent } from "@/types/handoff";

import { anonymousApi } from "../helpers/api";
import { expectNoA11yViolations } from "../helpers/a11y";
import { goto } from "../helpers/app";
import { readSeed } from "../helpers/seed";

/** Mint a link the way the bot will once its flows land (backend dev contract).
 *
 * Anonymous on purpose: the dev endpoint needs no session, and neither does the landing
 * it produces a link for — that is the property under test. */
async function mintToken(intent: HandoffIntent): Promise<string> {
  const seed = readSeed();
  const client = await anonymousApi();
  // ApiClient unwraps the SuccessResponse envelope, so this is the payload itself.
  const minted = await client.post<{ token: string }>("/dev/whatsapp/handoff-token", {
    caseId: seed.verification.id,
    customerId: seed.customer.id,
    intent,
  });
  return minted.token;
}

test.describe("UAT-WAH — handoff landings @P0", () => {
  test("UAT-WAH-01 · a payment link lands the customer on their own case, in context", async ({
    page,
  }) => {
    const seed = readSeed();
    const token = await mintToken(HandoffIntent.PAY);

    await goto(page, ROUTES.WA.PAY(token));

    // §26.4.2: the page must say where the customer left off — silent context loss is a
    // spec violation, not a cosmetic gap.
    const context = page.locator("[data-testid=wa-handoff-context]");
    await expect(context).toBeVisible();
    await expect(context).toContainText("Picking up where you left off");
    await expect(context).toContainText(seed.verification.vid);

    // §26.1.1: the payment pledge is repeated at every payment handoff — this is exactly
    // where an impersonator's lookalike link would land.
    await expect(page.locator("[data-testid=wa-handoff-pledge]")).toContainText("veriprops.ng");

    // No login happened: the token authorized the action, not a session (§26.5).
    expect(await page.evaluate(() => window.__auth_snapshot__?.isAuthenticated ?? false)).toBe(
      false,
    );

    await expectNoA11yViolations(page);
  });

  test("UAT-WAH-02 · a forwarded link is dead once it has been opened", async ({ browser }) => {
    // The single most likely real-world exposure: the customer forwards the message.
    const token = await mintToken(HandoffIntent.PAY);

    const first = await browser.newContext();
    const firstPage = await first.newPage();
    await goto(firstPage, ROUTES.WA.PAY(token));
    await expect(firstPage.locator("[data-testid=wa-handoff-context]")).toBeVisible();

    // A second person, with the same link and no shared cookies.
    const second = await browser.newContext();
    const secondPage = await second.newPage();
    await goto(secondPage, ROUTES.WA.PAY(token));
    await expect(secondPage.locator("[data-testid=wa-handoff-expired]")).toBeVisible();
    await expect(secondPage.locator("[data-testid=wa-handoff-context]")).toHaveCount(0);

    await expectNoA11yViolations(secondPage);
    await first.close();
    await second.close();
  });

  test("UAT-WAH-03 · the customer can reload their own landing without losing it", async ({
    page,
  }) => {
    // Single-use must not mean single-pageview: a refresh or a back-navigation is normal
    // on a phone, and the grant (D51) is what keeps it working.
    const token = await mintToken(HandoffIntent.PAY);
    await goto(page, ROUTES.WA.PAY(token));
    await expect(page.locator("[data-testid=wa-handoff-context]")).toBeVisible();

    await page.reload();
    await expect(page.locator("[data-testid=wa-handoff-context]")).toBeVisible();
    await expect(page.locator("[data-testid=wa-handoff-expired]")).toHaveCount(0);
  });

  test("UAT-WAH-04 · an expired link offers a way back into the chat, not a dead end", async ({
    page,
  }) => {
    await goto(page, ROUTES.WA.PAY("clearly-not-a-real-token"));

    const expired = page.locator("[data-testid=wa-handoff-expired]");
    await expect(expired).toBeVisible();
    // The bot resends on request only (§26.4.2) — the page offers the ask, never an
    // automatic resend.
    await expect(page.locator("[data-testid=wa-handoff-new-link]")).toBeVisible();

    // Never explains *why*: expired, used, and forged must be indistinguishable.
    const text = (await expired.textContent())?.toLowerCase() ?? "";
    for (const leak of ["already used", "invalid", "not found", "expired token"]) {
      expect(text).not.toContain(leak);
    }

    await expectNoA11yViolations(page);
  });

  test("UAT-WAH-05 · a link presented at the wrong landing is refused", async ({ page }) => {
    // A report link opened at the payment landing is not a payment authorization (§26.5).
    const token = await mintToken(HandoffIntent.REPORT);
    await goto(page, ROUTES.WA.PAY(token));
    await expect(page.locator("[data-testid=wa-handoff-expired]")).toBeVisible();
  });

  test("UAT-WAH-06 · document and report links continue into the authenticated portal", async ({
    page,
  }) => {
    // D50: canonical evidence (§26.1.6) and the report link (Decision B) sit behind a real
    // login, so these landings acknowledge context and hand off rather than completing.
    const token = await mintToken(HandoffIntent.REPORT);
    await goto(page, ROUTES.WA.REPORT(token));

    await expect(page.locator("[data-testid=wa-handoff-context]")).toBeVisible();
    await expect(page.locator("[data-testid=wa-handoff-continue-link]")).toBeVisible();
    // Payment is the only action completed on a token alone.
    await expect(page.locator("[data-testid=wa-handoff-pay]")).toHaveCount(0);

    await expectNoA11yViolations(page);
  });
});
