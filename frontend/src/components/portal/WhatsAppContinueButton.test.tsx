import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

/**
 * The web→chat half of continuation (§26.4.3, D58).
 *
 * Two properties matter. The link must **pre-fill the case reference**, because the bot
 * matches a `VP-…` on the customer's literal words — without it the customer has to go and
 * find a reference before the chat can help them, which is the friction the button exists
 * to remove. And it must render **nothing** without a configured number: the official
 * number is the §26.1.2 anti-impersonation anchor, so a hardcoded fallback would be worse
 * than no button at all.
 */

const config: { whatsappNumber?: string } = {};

vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  usePublicConfigQuery: () => ({ data: config }),
}));
vi.mock("next/navigation", () => ({
  usePathname: () => "/portal/verifications/abc",
}));

const { default: WhatsAppContinueButton } = await import("./WhatsAppContinueButton");

describe("WhatsAppContinueButton", () => {
  it("pre-fills the case reference so the chat lands on the right case", () => {
    config.whatsappNumber = "2349167624347";

    const html = renderToStaticMarkup(<WhatsAppContinueButton vid="VP-2026-0001" />);

    expect(html).toContain("wa.me/2349167624347");
    expect(html).toContain(encodeURIComponent("Continue VP-2026-0001"));
  });

  it("carries the page code so the §26.10 attribution still works", () => {
    config.whatsappNumber = "2349167624347";

    const html = renderToStaticMarkup(<WhatsAppContinueButton vid="VP-2026-0001" />);

    expect(html).toContain(encodeURIComponent("[ref: web-portal]"));
  });

  it("renders nothing when no number is configured", () => {
    config.whatsappNumber = undefined;

    expect(renderToStaticMarkup(<WhatsAppContinueButton vid="VP-2026-0001" />)).toBe("");
  });

  it("renders nothing without a case reference to quote", () => {
    config.whatsappNumber = "2349167624347";

    expect(renderToStaticMarkup(<WhatsAppContinueButton vid="" />)).toBe("");
  });

  it("opens in a new tab without leaking the referrer", () => {
    config.whatsappNumber = "2349167624347";

    const html = renderToStaticMarkup(<WhatsAppContinueButton vid="VP-2026-0001" />);

    expect(html).toContain('rel="noopener noreferrer"');
  });
});
