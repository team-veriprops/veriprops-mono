/**
 * UAT-CHAT — Unified chat and the surface-neutral assistant (PRD §16, §26.6-§26.10, D89-D93).
 *
 * WhatsApp and the web portal share one `conversations`/`chat_messages` store (Decision K),
 * and one assistant engine answers on both (D93). This suite drives the seams that make that
 * true from the browser, on top of the backend unit tests and the live drive-through:
 *
 * - the web assistant's two-phase turn (deterministic steps answered inline, a model-needing
 *   turn deferred behind a typing indicator, PRD §16.7);
 * - a linked customer's WhatsApp thread surfacing at `/portal/chat`, and going read-only
 *   (not gone) once the number is unlinked (§26.8, §26.4.4);
 * - D92 read receipts: "Seen by support" once an admin opens a thread, and delivery ticks
 *   progressing through the same `WhatsAppStatusService` a signed Meta webhook reaches;
 * - the admin Conversations inbox listing web support and WhatsApp side by side, filterable
 *   (§16.5, D91);
 * - D57's sticky hand-off, generalised in D93 to any thread the assistant can answer.
 *
 * Every test builds its own customer (`scenario`) and, where it touches WhatsApp, its own
 * random number, so the suite is safe in the default parallel lane.
 */
import { randomUUID } from "node:crypto";

import { Page } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { expect, test } from "../fixtures";
import { expectNoA11yViolations } from "../helpers/a11y";
import { api } from "../helpers/api";
import { goto, waitForHydration, waitReady } from "../helpers/app";
import { TEST_OTP } from "../helpers/env";
import { ScenarioAccount, ScenarioStage } from "../helpers/scenario";

/**
 * A short, unique token safe to drop into a message body. Not `Date.now()`: the send-time
 * fraud scanner (§4.7) holds any run of 9+ digits as a possible phone number, and a raw
 * millisecond timestamp is exactly that — a message built from one is held for admin
 * review instead of delivering, and never appears where these tests look for it.
 */
function uniqueToken(): string {
  return randomUUID().slice(0, 8);
}

/** A fresh Nigerian mobile number, unique per test so parallel workers never collide. */
function freshNigerianNumber(): { national: string; e164: string } {
  const national = `80${Math.floor(Math.random() * 1e8)
    .toString()
    .padStart(8, "0")}`;
  return { national, e164: `+234${national}` };
}

/** Link *national* to the signed-in customer's account (§26.4.4). OTP_MODE=deterministic in
 * test, so the code sent is always `TEST_OTP` — the automation-determinism contract. */
async function linkWhatsAppNumber(page: Page, national: string): Promise<void> {
  await goto(page, ROUTES.ACCOUNT.WHATSAPP);
  await page.getByTestId("wa-link-phone").fill(national);
  await page.getByTestId("wa-link-send").click();
  await page.getByTestId("wa-link-code").fill(TEST_OTP);
  await page.getByTestId("wa-link-confirm").click();
  await expect(page.getByTestId("wa-link-linked")).toBeVisible();
}

/** Link *e164* to *account* through the endpoints the linking screen calls — for tests whose
 * subject is what a linked number leads to, not the screen itself (UAT-CHAT-02/03 drive that). */
async function linkWhatsAppNumberViaApi(account: ScenarioAccount, e164: string): Promise<void> {
  const client = await api(account.email, account.password);
  try {
    await client.post("/channel/whatsapp/link/me/start", { phoneE164: e164 });
    await client.post("/channel/whatsapp/link/me/confirm", { phoneE164: e164, code: TEST_OTP });
  } finally {
    await client.dispose();
  }
}

/** Open *account*'s web support thread and post *body* to it, as the support page does. */
async function sendWebSupportMessageViaApi(account: ScenarioAccount, body: string): Promise<void> {
  const client = await api(account.email, account.password);
  try {
    await client.get("/support/chat");
    await client.post("/support/chat/messages", { body });
  } finally {
    await client.dispose();
  }
}

/**
 * Filter + search the admin Conversations tab down to the one row containing *hasText*,
 * and return it. The search box is debounced (300ms), so the list briefly reflects the
 * filter alone before the typed text narrows it further — asserting on plain row count
 * right after `fill` can pass against that transient, unrelated set. Filtering the
 * locator by the identifying text (an email or a number, never the customer's name alone —
 * every scenario customer is named "Ada Scenario") makes Playwright's own retry absorb the
 * debounce instead of racing it.
 *
 * The search is a controlled input, so the inbox has to be hydrated before it is typed into:
 * text that lands first is discarded when React takes over, the list stays unfiltered, and the
 * row — off its first page — reads as missing. A filter click that lands first does nothing.
 */
async function findAdminRow(
  admin: Page,
  filterId: "support" | "whatsapp" | "cases" | "all",
  search: string,
  hasText: string,
) {
  await waitForHydration(admin, "admin-conversations-search");
  const filter = admin.getByTestId(`admin-conversations-filter-${filterId}`);
  if ((await filter.getAttribute("aria-pressed")) !== "true") await filter.click();
  await admin.getByTestId("admin-conversations-search").fill(search);
  const row = admin.getByTestId("admin-conversation-row").filter({ hasText });
  await expect(row).toHaveCount(1, { timeout: 10_000 });
  return row;
}

/** Find, by *national*, the one WhatsApp row the admin Conversations tab shows, and open
 * it. Assumes the tab is already on screen. */
async function openWhatsAppThread(admin: Page, national: string) {
  const row = await findAdminRow(admin, "whatsapp", national, national);
  await row.click();
  return row;
}

test.describe("UAT-CHAT — unified chat & the surface-neutral assistant @P1", () => {
  test("UAT-CHAT-01 · the web assistant answers the welcome inline, then a typing indicator covers the deferred turn", async ({
    scenario,
    pageFor,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);

    await goto(page, ROUTES.PORTAL.SUPPORT);
    await page.getByTestId("chat-composer").fill("Hi");
    await page.getByTestId("chat-send").click();

    // §26.6.1 — the welcome, the disclosure and the menu answer the first turn on their own,
    // inline in the send response: no typing indicator for a deterministic step.
    await expect(page.getByText("Welcome to")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("What would you like to do?")).toBeVisible();
    await expect(page.getByTestId("chat-assistant-typing")).toHaveCount(0);

    // Free text that matches no menu number, keyword or case reference: the deterministic
    // gauntlet can't answer it, so it defers to the intent model (D93).
    await page.getByTestId("chat-composer").fill("banana kayak firmament seventeen");
    await page.getByTestId("chat-send").click();

    // Catching the indicator mid-flight is inherently racy on a fast stack — the turn can
    // resolve before the next poll — so its visibility is best-effort; the reply landing is
    // the assertion that must hold (the same pattern session.spec.ts uses for the recovery
    // overlay).
    const typing = page.getByTestId("chat-assistant-typing");
    const sawTyping = await typing
      .waitFor({ state: "visible", timeout: 3_000 })
      .then(() => true)
      .catch(() => false);
    if (sawTyping) {
      await expect(typing).toHaveCount(0, { timeout: 15_000 });
    }
    await expect(page.getByText("Sorry, I didn't quite get that.")).toBeVisible({
      timeout: 15_000,
    });

    await expectNoA11yViolations(page);
  });

  test("UAT-CHAT-02 · linking a WhatsApp number surfaces its thread at /portal/chat, already answered by the assistant", async ({
    scenario,
    pageFor,
    wa,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    const { national, e164 } = freshNigerianNumber();

    await linkWhatsAppNumber(page, national);
    // WhatsApp always runs both turn phases in the one webhook call, so the assistant's
    // welcome is already in the thread by the time the customer looks.
    await wa.inbound({ fromPhone: e164, text: "Hi" });

    await goto(page, ROUTES.PORTAL.CHAT);
    const row = page.getByRole("link", { name: /WhatsApp chat/ });
    await expect(row).toBeVisible({ timeout: 10_000 });
    await row.click();

    await page.waitForURL((url) => url.pathname.startsWith(`${ROUTES.PORTAL.CHAT}/`));
    await expect(page.getByText("Hi", { exact: true })).toBeVisible();
    await expect(page.getByText("What would you like to do?")).toBeVisible();
    await expect(page.getByTitle("Received on WhatsApp").first()).toBeVisible();

    await expectNoA11yViolations(page);
  });

  test("UAT-CHAT-03 · unlinking a WhatsApp number leaves its thread read-only, not gone", async ({
    scenario,
    pageFor,
    wa,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    const { national, e164 } = freshNigerianNumber();

    await linkWhatsAppNumber(page, national);
    await wa.inbound({ fromPhone: e164, text: "Hi" });

    await goto(page, ROUTES.PORTAL.CHAT);
    await page.getByRole("link", { name: /WhatsApp chat/ }).click();
    await expect(page.getByTestId("chat-composer")).toBeVisible();

    await goto(page, ROUTES.ACCOUNT.WHATSAPP);
    await page.getByTestId("wa-unlink").click();
    await page.getByTestId("wa-unlink-confirm").click();
    // Back on the empty-state form: the number really is gone from the account.
    await expect(page.getByTestId("wa-link-send")).toBeVisible();

    await goto(page, ROUTES.PORTAL.CHAT);
    await page.getByRole("link", { name: /WhatsApp chat/ }).click();
    const readOnly = page.getByTestId("chat-read-only");
    await expect(readOnly).toBeVisible();
    await expect(readOnly).toContainText("no longer linked");
    await expect(page.getByTestId("chat-composer")).toHaveCount(0);

    await expectNoA11yViolations(page);
  });

  test("UAT-CHAT-04 · a customer's message shows 'Seen' once an admin opens the thread", async ({
    scenario,
    pageFor,
    adminPage,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    const text = `Hi, a billing question ${uniqueToken()}`;

    await goto(page, ROUTES.PORTAL.SUPPORT);
    await page.getByTestId("chat-composer").fill(text);
    await page.getByTestId("chat-send").click();
    await expect(page.getByText(text)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByTestId("chat-seen-by-support")).toHaveCount(0);

    await goto(adminPage, ROUTES.ADMIN.MESSAGES_TAB("conversations"));
    const row = await findAdminRow(adminPage, "support", customer.email, customer.email);
    await row.click();
    // Opening the thread is what marks it read (§16, D92's receipts-off fallback for a
    // customer's own inbound applies the same way to an admin opening the console).
    await expect(adminPage.getByText(text)).toBeVisible();

    await page.reload({ waitUntil: "domcontentloaded" });
    await waitReady(page);
    await expect(page.getByTestId("chat-seen-by-support")).toBeVisible({ timeout: 10_000 });

    await expectNoA11yViolations(page);
  });

  test("UAT-CHAT-05 · WhatsApp delivery ticks progress through the status dev door", async ({
    scenario,
    pageFor,
    adminPage,
    wa,
  }) => {
    const { customer } = await scenario(ScenarioStage.DRAFT);
    const page = await pageFor(customer);
    const { national, e164 } = freshNigerianNumber();
    const reply = `Thanks for reaching out — ${uniqueToken()}`;

    await linkWhatsAppNumber(page, national);
    await wa.inbound({ fromPhone: e164, text: "Hi" });

    await goto(adminPage, ROUTES.ADMIN.MESSAGES_TAB("conversations"));
    await openWhatsAppThread(adminPage, national);
    await adminPage.getByTestId("chat-composer").fill(reply);
    await adminPage.getByTestId("chat-send").click();

    const bubble = adminPage.getByText(reply, { exact: true });
    const ticks = bubble.locator("..").getByTestId("chat-channel-status");
    await expect(ticks).toHaveAttribute("data-status", "SENT", { timeout: 10_000 });

    // The stub records the recipient as Meta's wa_id (digits, no "+").
    const outbox = await wa.outbox<{
      messages: { wamid: string; to: string; text?: string }[];
    }>(e164.replace("+", ""));
    const sent = outbox.messages.find((m) => m.text === reply);
    if (!sent) throw new Error("The admin's reply never reached the stub outbox");

    await wa.status(sent.wamid, "delivered");
    await goto(adminPage, ROUTES.ADMIN.MESSAGES_TAB("conversations"));
    await openWhatsAppThread(adminPage, national);
    await expect(ticks).toHaveAttribute("data-status", "DELIVERED", { timeout: 10_000 });

    await wa.status(sent.wamid, "read");
    await goto(adminPage, ROUTES.ADMIN.MESSAGES_TAB("conversations"));
    await openWhatsAppThread(adminPage, national);
    await expect(ticks).toHaveAttribute("data-status", "READ", { timeout: 10_000 });
  });

  test("UAT-CHAT-06 · the admin Conversations tab lists web support and WhatsApp threads, filterable", async ({
    scenario,
    adminPage,
    wa,
  }) => {
    // The two threads are set up over the API: the support composer and the linking screen
    // are UAT-CHAT-01/02's subjects, and driving them here (two sign-ins, the link flow) spent
    // most of this test's budget before the inbox — what it is about — was even opened.
    const { customer: webCustomer } = await scenario(ScenarioStage.DRAFT);
    await sendWebSupportMessageViaApi(webCustomer, `Hi, a web support question ${uniqueToken()}`);

    const { customer: waCustomer } = await scenario(ScenarioStage.DRAFT);
    const { national, e164 } = freshNigerianNumber();
    await linkWhatsAppNumberViaApi(waCustomer, e164);
    await wa.inbound({ fromPhone: e164, text: "Hi from WhatsApp" });

    await goto(adminPage, ROUTES.ADMIN.MESSAGES_TAB("conversations"));

    // The web thread shows under "Web support" and carries no WhatsApp badge.
    const webRow = await findAdminRow(adminPage, "support", webCustomer.email, webCustomer.email);
    await expect(webRow.getByTitle("Received on WhatsApp")).toHaveCount(0);

    // The same web customer never shows under the WhatsApp facet …
    await adminPage.getByTestId("admin-conversations-filter-whatsapp").click();
    await adminPage.getByTestId("admin-conversations-search").fill(webCustomer.email);
    await expect(adminPage.getByTestId("admin-conversation-row")).toHaveCount(0, {
      timeout: 10_000,
    });

    // … while the WhatsApp customer's own number does, badge and all.
    const waRow = await findAdminRow(adminPage, "whatsapp", national, national);
    await expect(waRow.getByTitle("Received on WhatsApp")).toBeVisible();

    await expectNoA11yViolations(adminPage);
  });

  test("UAT-CHAT-07 · an admin reply takes a case thread off the assistant, and hand-back gives it back", async ({
    scenario,
    adminPage,
  }) => {
    const { verificationId } = await scenario(ScenarioStage.DRAFT);

    await goto(adminPage, ROUTES.ADMIN.VERIFICATION_MESSAGES(verificationId));
    await expect(adminPage.getByTestId("wa-bot-mode-label")).toHaveText(
      "The assistant is answering",
    );
    await expect(adminPage.getByTestId("wa-bot-hand-back")).toHaveCount(0);

    await adminPage.getByTestId("chat-composer").fill("Thanks — I'm looking into this now.");
    await adminPage.getByTestId("chat-send").click();

    // D57, generalised in D93: a person replying takes the thread off the assistant.
    await expect(adminPage.getByTestId("wa-bot-mode-label")).toHaveText(
      "You're handling this thread",
    );
    const handBack = adminPage.getByTestId("wa-bot-hand-back");
    await expect(handBack).toBeVisible();
    await handBack.click();

    await expect(adminPage.getByTestId("wa-bot-mode-label")).toHaveText(
      "The assistant is answering",
    );
    await expect(adminPage.getByTestId("wa-bot-hand-back")).toHaveCount(0);

    await expectNoA11yViolations(adminPage);
  });
});
