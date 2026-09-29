/**
 * Helpers for the `@live` lane: a real browser on a deployed staging, through the real
 * third-party pages (docs/live-integration-smoke.md).
 *
 * Staging is not an automation environment, so the window hooks the rest of the suite waits
 * on (`__app_ready__`, `__auth_snapshot__`) do not exist there. Readiness here is the one
 * signal a production build still gives: React has hydrated the element about to be used
 * (`waitForHydration`). And staging's OTPs are random, so every account comes from
 * `/dev/scenario` (verified, with the QA password), never from a signup.
 */
import { Frame, Locator, Page, expect } from "@playwright/test";

import { ROUTES } from "@lib/routes";
import { PaymentMethod } from "@/types/models";

import { waitForHydration } from "./app";
import { BASE_URL } from "./env";

const APP_ORIGIN = new URL(BASE_URL).origin;

/** Open *path* and wait until *testId* is hydrated. */
export async function openLive(page: Page, path: string, testId: string): Promise<void> {
  await page.goto(path, { waitUntil: "domcontentloaded" });
  await waitForHydration(page, testId);
}

/** Sign in through the login form and wait to be taken off the auth pages. */
export async function signInLive(page: Page, email: string, password: string): Promise<void> {
  await openLive(page, ROUTES.AUTH.LOGIN, "login-email");
  await page.getByTestId("login-email").fill(email);
  await page.getByTestId("login-password").fill(password);
  await page.getByTestId("login-submit").click();
  await page.waitForURL((url) => url.origin === APP_ORIGIN && !url.pathname.startsWith(ROUTES.AUTH.GATE), {
    waitUntil: "domcontentloaded",
    timeout: 30_000,
  });
}

// ─── Hosted checkouts ─────────────────────────────────────────────────────────────
//
// The gateways' pages are theirs: fields are found by what a person reads (label, placeholder,
// accessible name), in the page or any frame, never by their markup. Each step after the card
// form is optional — which ones a test card triggers (PIN, OTP) is the gateway's decision.

/** A gateway's documented sandbox card, and the answers its challenges expect. */
export interface TestCard {
  number: string;
  expiry: string;
  cvv: string;
  pin?: string;
  otp?: string;
}

/** Flutterwave's documented Mastercard: PIN, then OTP. */
export const FLUTTERWAVE_TEST_CARD: TestCard = {
  number: "5531886652142950", expiry: "09/32", cvv: "564", pin: "3310", otp: "12345",
};

/** Paystack's documented "no validation" Visa; any future expiry. */
export const PAYSTACK_TEST_CARD: TestCard = {
  number: "4084084084084081", expiry: "12/30", cvv: "408", otp: "123456",
};

/** The gateways with a hosted checkout, and each one's sandbox card. */
type HostedGateway = PaymentMethod.FLUTTERWAVE | PaymentMethod.PAYSTACK;

const CARD_FOR: Record<HostedGateway, TestCard> = {
  [PaymentMethod.FLUTTERWAVE]: FLUTTERWAVE_TEST_CARD,
  [PaymentMethod.PAYSTACK]: PAYSTACK_TEST_CARD,
};

/** Which gateway's page this is, from its host (`checkout.flutterwave.com`, `checkout.paystack.com`). */
export function gatewayOf(url: string): HostedGateway | null {
  const host = new URL(url).hostname;
  return (Object.keys(CARD_FOR) as HostedGateway[]).find((gateway) => host.includes(gateway)) ?? null;
}

const FIELD = {
  cardNumber: /card\s*number|0000 0000/i,
  expiry: /expir|valid|mm\s*\/\s*yy/i,
  cvv: /cvv|cvc|security code/i,
  pin: /\bpin\b/i,
  otp: /otp|one[- ]time|token|verification code/i,
};
const PAY_BUTTON = /^pay\b/i;
const CONFIRM_BUTTON = /continue|authori[sz]e|submit|proceed|verify|confirm/i;

function fieldIn(frame: Frame, name: RegExp): Locator {
  return frame
    .getByLabel(name)
    .or(frame.getByPlaceholder(name))
    .or(frame.getByRole("textbox", { name }))
    .filter({ visible: true })
    .first();
}

/** The first visible field matching *name* in the page or any of its frames, or null. */
async function findField(page: Page, name: RegExp): Promise<Locator | null> {
  for (const frame of page.frames()) {
    const field = fieldIn(frame, name);
    if (await field.count()) return field;
  }
  return null;
}

async function findButton(page: Page, name: RegExp): Promise<Locator | null> {
  for (const frame of page.frames()) {
    const button = frame.getByRole("button", { name }).filter({ visible: true }).first();
    if (await button.count()) return button;
  }
  return null;
}

async function fillRequired(page: Page, name: RegExp, value: string): Promise<void> {
  await expect(async () => {
    const field = await findField(page, name);
    if (!field) throw new Error(`the checkout shows no field matching ${name}`);
    // Typed, not filled: card fields format as they go (spaces, the expiry slash). Cleared first,
    // so a retry after a half-typed attempt does not append to it.
    await field.click();
    await field.clear();
    await field.pressSequentially(value, { delay: 30 });
  }).toPass({ timeout: 30_000 });
}

async function clickRequired(page: Page, name: RegExp): Promise<void> {
  await expect(async () => {
    const button = await findButton(page, name);
    if (!button) throw new Error(`the checkout shows no button matching ${name}`);
    await button.click();
  }).toPass({ timeout: 30_000 });
}

/** Answer a challenge (PIN, OTP) if the gateway asks within *withinMs*; true when it did.
 * Single-digit boxes auto-advance, so the answer is typed from the first one. */
async function answerIfAsked(page: Page, name: RegExp, answer: string | undefined, withinMs: number): Promise<boolean> {
  if (!answer) return false;
  const deadline = Date.now() + withinMs;
  while (Date.now() < deadline) {
    if (new URL(page.url()).origin === APP_ORIGIN) return false; // already sent back
    const field = await findField(page, name);
    if (field) {
      await field.click();
      await page.keyboard.type(answer, { delay: 50 });
      const confirm = await findButton(page, CONFIRM_BUTTON);
      if (confirm) await confirm.click();
      return true;
    }
    await page.waitForTimeout(500);
  }
  return false;
}

/**
 * Pay on the gateway's hosted page with its sandbox card, then wait to be sent back to the app.
 * The gateway is read off the page's host, so the spec follows whichever one staging's
 * `ACTIVE_PAYMENT_METHOD` chose.
 */
export async function payOnHostedCheckout(page: Page): Promise<HostedGateway> {
  await page.waitForURL((url) => url.origin !== APP_ORIGIN, { waitUntil: "domcontentloaded", timeout: 60_000 });
  const gateway = gatewayOf(page.url());
  if (!gateway) throw new Error(`the checkout opened on an unknown host: ${page.url()}`);
  const card = CARD_FOR[gateway];

  // Paystack can open on a channel list; Flutterwave opens on the card form. Either one renders
  // after the page loads, so wait for the card number or the channel that leads to it.
  await expect(async () => {
    if (await findField(page, FIELD.cardNumber)) return;
    const cardChannel = await findButton(page, /pay with card|^card$/i);
    if (!cardChannel) throw new Error("the checkout shows neither a card form nor a card channel");
    await cardChannel.click();
    throw new Error("opened the card channel; waiting for its form");
  }).toPass({ timeout: 30_000 });

  await fillRequired(page, FIELD.cardNumber, card.number);
  await fillRequired(page, FIELD.expiry, card.expiry.replace("/", ""));
  await fillRequired(page, FIELD.cvv, card.cvv);
  await clickRequired(page, PAY_BUTTON);

  await answerIfAsked(page, FIELD.pin, card.pin, 20_000);
  await answerIfAsked(page, FIELD.otp, card.otp, 30_000);

  await page.waitForURL((url) => url.origin === APP_ORIGIN, { waitUntil: "domcontentloaded", timeout: 120_000 });
  return gateway;
}
