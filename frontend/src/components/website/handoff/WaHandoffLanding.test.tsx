import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { HandoffIntent } from "@/types/handoff";
import { VerificationStatus, VerificationTier } from "@/types/verification";
import { TransactionCurrency } from "@/types/models";

// `vi.hoisted` because the component builds its service at module scope, so the mock
// factory runs before ordinary consts would exist.
const { redeemSpy, initiatePaymentSpy } = vi.hoisted(() => ({
  redeemSpy: vi.fn(),
  initiatePaymentSpy: vi.fn(),
}));

vi.mock("./libs/handoff-service", () => ({
  HandoffService: class {
    redeem = redeemSpy;
    initiatePayment = initiatePaymentSpy;
    release = vi.fn();
  },
}));
vi.mock("@/containers", () => ({ httpClient: {} }));
vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  usePublicConfigQuery: () => ({ data: { whatsappNumber: "2349167624347" } }),
}));

import WaHandoffLanding, {
  ExpiredLink,
  OriginBanner,
  PaySection,
  PaymentPledge,
} from "./WaHandoffLanding";
import { NO_WHATSAPP_CONSENT } from "@/types/whatsappConsent";
import { ROUTES } from "@lib/routes";

const context = {
  intent: HandoffIntent.PAY,
  caseId: "case-1",
  vid: "VP-1042",
  tier: VerificationTier.STANDARD,
  status: VerificationStatus.PAYMENT_PENDING,
  amountDueMinor: 5_000_000,
  currency: TransactionCurrency.NGN,
  expiresAt: "2026-09-01T00:15:00Z",
};

describe("WaHandoffLanding", () => {
  beforeEach(() => {
    redeemSpy.mockReset();
    initiatePaymentSpy.mockReset();
  });

  it("acknowledges the customer's context while the link is still resolving", () => {
    // §26.4.2: silent context loss is a spec violation — the page never shows a bare
    // spinner with no explanation of what it is doing.
    redeemSpy.mockReturnValue(new Promise(() => {}));
    const html = renderToStaticMarkup(
      <WaHandoffLanding intent={HandoffIntent.PAY} token="tok" />,
    );
    expect(html).toContain("Picking up where you left off");
  });

  it("renders on the server without redeeming, so a link preview cannot burn it", () => {
    // WhatsApp fetches a URL to build its preview card. Redemption is single-use, so it
    // must only happen from a real browser session (in an effect), never during render.
    redeemSpy.mockReturnValue(new Promise(() => {}));
    renderToStaticMarkup(<WaHandoffLanding intent={HandoffIntent.PAY} token="tok" />);
    expect(redeemSpy).not.toHaveBeenCalled();
  });
});

describe("WaHandoffLanding · states", () => {
  // Effects don't run under renderToStaticMarkup, so the resolved states are exercised
  // through the presentational pieces the container selects between.
  it("names the case and the action once context resolves", () => {
    const html = renderToStaticMarkup(<OriginBanner context={context} />);
    expect(html).toContain("VP-1042");
    expect(html).toContain("payment");
  });

  it("repeats the payment pledge at the moment of highest exposure", () => {
    // §26.1.1: the pledge is stated at every payment handoff, not only in chat — this is
    // exactly when an impersonator's lookalike link would land.
    const html = renderToStaticMarkup(<PaymentPledge />);
    expect(html).toContain("veriprops.ng");
    expect(html).toContain("check the address bar");
  });

  it("offers one tap back into the chat when a link is spent", () => {
    // Expiry is normal, not exceptional — links last 15 minutes and work once.
    const html = renderToStaticMarkup(<ExpiredLink number="2349167624347" />);
    expect(html).toContain("expired");
    expect(html).toContain("https://wa.me/2349167624347");
  });

  const paySection = (phoneVerificationRequired: boolean) =>
    renderToStaticMarkup(
      <PaySection
        context={{ ...context, phoneVerificationRequired }}
        payment={null}
        paying={false}
        onPay={() => {}}
        consent={NO_WHATSAPP_CONSENT}
        onConsentChange={() => {}}
      />,
    );

  it("offers payment on the landing once the customer's phone is verified", () => {
    const html = paySection(false);
    expect(html).toContain('data-testid="wa-handoff-pay"');
    expect(html).not.toContain('data-testid="wa-handoff-continue"');
  });

  it("hands an unverified phone into the portal pay page instead of a payment that would fail", () => {
    // §10.5: the phone gate needs a login, so "Pay now" here could only fail — and a
    // failure on this page reads as an expired link.
    const html = paySection(true);
    expect(html).not.toContain('data-testid="wa-handoff-pay"');
    expect(html).toContain(`href="${ROUTES.PORTAL.VERIFICATION_PAY("case-1")}"`);
    expect(html).toContain("Verify your phone to pay");
  });

  it("never explains why a link failed", () => {
    // Expired, already used, and forged are one state: a person who was forwarded the
    // message must not be able to tell them apart.
    const html = renderToStaticMarkup(<ExpiredLink number="2349167624347" />);
    for (const leak of ["already used", "invalid", "not found", "forged"]) {
      expect(html.toLowerCase()).not.toContain(leak);
    }
  });
});
