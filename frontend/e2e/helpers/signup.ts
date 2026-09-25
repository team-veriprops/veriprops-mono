/**
 * The signup funnel, driven the way a new user meets it (PRD §2, §3.2) — Account → Verify →
 * Residence → Consent.
 *
 * `auth.spec.ts` asserts the funnel itself; other specs need an account that only this journey can
 * produce — an agent applicant, for instance, gets the AGENT persona by signing up with
 * `?intent=agent`, and `proxy.ts` will not let anyone else near `/agents/*`. Both drive the same
 * steps, so the steps live here rather than in either spec.
 *
 * This stack runs `PHONE_VERIFICATION_ENABLED=false` (PRD §10.5), so the Verify step asks for a
 * single OTP — email — and collects the phone number to be verified later, at the pay step.
 */
import { randomUUID } from "node:crypto";

import { Page, expect } from "@playwright/test";

import { ROUTES } from "@lib/routes";

import { goto, waitForHydration } from "./app";
import { TEST_OTP } from "./env";

/** A brand-new account's details, unique per test so parallel workers never collide. */
export interface NewAccount {
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  password: string;
}

export function newAccount(): NewAccount {
  return {
    firstName: "Ada",
    lastName: "Signup",
    email: `qa-signup-${randomUUID().slice(0, 8)}@veriprops.io`,
    // Digits only, 7–15 of them (`phoneFields` in schemas.ts), and unique: no two signups may
    // submit the same number.
    phone: `80${Math.floor(Math.random() * 1e9)
      .toString()
      .padStart(9, "0")}`,
    password: "Signup1234!",
  };
}

/** Step 1 — account basics. */
export async function fillAccountStep(page: Page, account: NewAccount): Promise<void> {
  await expect(page.getByTestId("signup-basics-form")).toBeVisible();
  await waitForHydration(page, "signup-first-name");
  await page.getByTestId("signup-first-name").fill(account.firstName);
  await page.getByTestId("signup-last-name").fill(account.lastName);
  await page.getByTestId("signup-email").fill(account.email);
  await page.getByTestId("signup-password").fill(account.password);
  await page.getByTestId("signup-basics-submit").click();
}

/** Ask for a code on *field* and wait until the dialog is ready to be typed into. */
export async function openOtpDialog(page: Page, field: "email" | "phone"): Promise<void> {
  const send = page.getByTestId(`verify-${field}-send`);
  const modal = page.getByTestId("verify-otp-modal");
  const sendError = page.getByTestId(`verify-${field}-error`);
  const sending = send.getByText("Sending code…");

  // WebKit occasionally drops a click on this button just after the step swaps in: nothing is
  // sent and the button never enters its sending state — observed in CI and locally, with the
  // click passing every actionability check. A user simply taps again; a test would otherwise
  // wait out the whole budget below. So a click is repeated only while it has provably had no
  // effect. Any effect at all — the button sending, an error, the dialog — ends the retrying and
  // is left to decide the outcome, so a send that fails or hangs still fails this helper.
  await expect(async () => {
    const registered = (await modal.isVisible()) || (await sendError.isVisible()) || (await sending.isVisible());
    if (!registered) await send.click();
    await expect(modal.or(sendError).or(sending).first()).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 20_000 });

  // The endpoint itself is quick (~0.15s measured), but this whole step is generously budgeted
  // because the browser gets starved when several workers share one machine, and that is where
  // this wait has actually failed. The form's own error is watched alongside, so a refused send
  // is reported in the app's words rather than as a bare "element not found" on the dialog.
  // One wait on either outcome — not a race of two waits, whose loser would linger to its own
  // timeout long after the step had moved on.
  await modal
    .or(sendError)
    .first()
    .waitFor({ state: "visible", timeout: 90_000 })
    .catch(() => {
      throw new Error(`The ${field} code dialog never opened, and no error was shown.`);
    });
  const opened = await modal.isVisible();

  if (!opened) {
    throw new Error(`Sending the ${field} code failed: ${(await sendError.innerText()).trim()}`);
  }
  // The dialog clears itself and focuses its first box when it opens. Waiting for that focus is
  // what proves the reset has already run, so the digits typed next survive it.
  await expect(page.getByTestId("verify-otp-digit-0")).toBeFocused();
  // The boxes then fade in on a stagger. Anything that lands mid-animation sees a
  // half-transparent input — which an a11y scan scores as a contrast failure against the
  // backdrop — so wait for the last one to finish arriving.
  await expect(page.getByTestId(`verify-otp-digit-${TEST_OTP.length - 1}`)).toHaveCSS("opacity", "1");
}

/** Type the deterministic code into the open dialog and confirm it. */
export async function enterOtp(page: Page): Promise<void> {
  // One digit per box: the boxes reject anything longer, which is what real keystrokes look like.
  for (const [index, digit] of [...TEST_OTP].entries()) {
    await page.getByTestId(`verify-otp-digit-${index}`).fill(digit);
  }
  await page.getByTestId("verify-otp-confirm").click();
}

export async function verifyWithOtp(page: Page, field: "email" | "phone"): Promise<void> {
  await openOtpDialog(page, field);
  await enterOtp(page);
  // Confirming is a round trip, and several signups share one machine whenever the parallel lane
  // is full — the dialog sits in "Verifying…" until it answers. Budgeted like the send above,
  // rather than left on the 15s default that is sized for an ordinary re-render.
  await expect(page.getByTestId("verify-otp-modal")).toBeHidden({ timeout: 60_000 });
  await expect(page.getByTestId(`verify-${field}-verified`)).toBeVisible({ timeout: 30_000 });
}

/** Step 2 — prove the email, then give the phone number. */
export async function fillVerifyStep(page: Page, account: NewAccount): Promise<void> {
  await expect(page.getByTestId("verify-form")).toBeVisible();
  await verifyWithOtp(page, "email");
  await page.getByTestId("verify-phone-input").fill(account.phone);
  // Asserted apart from the click: a button still disabled (the number not accepted) then reads
  // as that, not as a click that timed out — which is what an engine starved of CPU looks like.
  const submit = page.getByTestId("verify-submit");
  await expect(submit).toBeEnabled();
  await submit.click();
}

/** Step 3 — residence. The country is what drives currency and timezone. */
export async function fillResidenceStep(page: Page): Promise<void> {
  await expect(page.getByTestId("signup-residence-form")).toBeVisible();
  await page.getByTestId("signup-country").selectOption("NG");
  // Choosing Nigeria picks the Naira for the user instead of making them do it.
  await expect(page.getByTestId("signup-currency-NGN")).toHaveAttribute("aria-pressed", "true");
  await page.getByTestId("signup-residence-submit").click();
}

/** Step 4 — accept both documents and create the account. */
export async function acceptConsentsAndSubmit(page: Page): Promise<void> {
  await expect(page.getByTestId("signup-consent-form")).toBeVisible();
  await page.getByTestId("signup-consent-terms").click();
  await page.getByTestId("signup-consent-privacy").click();
  await page.getByTestId("signup-consent-submit").click();
}

/**
 * Sign a brand-new account up through all four steps and hand back its details. `intent` is
 * carried into the funnel exactly as a CTA would carry it, because it decides both what the
 * applicant is told and which persona they come out with.
 *
 * Where the account lands afterwards depends on that intent, so the caller waits for its own
 * destination rather than this helper assuming one.
 */
export async function signUpViaUi(
  page: Page,
  options: { intent?: string } = {},
): Promise<NewAccount> {
  const account = newAccount();
  await goto(page, options.intent ? `${ROUTES.AUTH.SIGNUP}?intent=${options.intent}` : ROUTES.AUTH.SIGNUP);
  await fillAccountStep(page, account);
  await fillVerifyStep(page, account);
  await fillResidenceStep(page);
  await acceptConsentsAndSubmit(page);
  return account;
}
