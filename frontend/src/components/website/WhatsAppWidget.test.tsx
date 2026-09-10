import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PublicConfig } from "@/types/models";
import { ROUTES } from "@lib/routes";

// Annotated, not inferred: `ROUTES` is `as const`, so `ROUTES.HOME` has the literal type
// `"/"` and every later reassignment to another route fails to typecheck.
let pathname: string = ROUTES.HOME;
let config: PublicConfig | null = null;

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@components/website/auth/libs/useAuthQueries", () => ({
  usePublicConfigQuery: () => ({ data: config }),
}));

import WhatsAppWidget from "./WhatsAppWidget";

const liveConfig: PublicConfig = {
  phoneVerificationEnabled: true,
  whatsappNumber: "2349167624347",
  whatsappDisplayNumber: "+234 916 762 4347",
  whatsappWidgetEnabled: true,
};

describe("WhatsAppWidget", () => {
  beforeEach(() => {
    pathname = ROUTES.HOME;
    config = liveConfig;
  });

  it("deep-links to the official number with the page's attribution code", () => {
    const html = renderToStaticMarkup(<WhatsAppWidget />);
    expect(html).toContain("https://wa.me/2349167624347");
    expect(html).toContain("ref%3A%20web-home");
  });

  it("carries the accessible name and opens safely in a new context", () => {
    const html = renderToStaticMarkup(<WhatsAppWidget />);
    expect(html).toContain('aria-label="Chat with Veriprops on WhatsApp"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain("noopener");
    expect(html).toContain("noreferrer");
  });

  it("re-codes the link per page so enquiries stay attributable", () => {
    pathname = ROUTES.SAMPLE_REPORT;
    expect(renderToStaticMarkup(<WhatsAppWidget />)).toContain("ref%3A%20web-report-sample");
  });

  it("disappears inside the payment flow", () => {
    // PRD 7.4.1 — no distraction at the highest-value moment.
    pathname = ROUTES.PORTAL.VERIFICATION_PAY("abc123");
    expect(renderToStaticMarkup(<WhatsAppWidget />)).toBe("");
  });

  it("stays visible on the rest of the authenticated surface", () => {
    pathname = ROUTES.PORTAL.DASHBOARD;
    expect(renderToStaticMarkup(<WhatsAppWidget />)).toContain("ref%3A%20web-portal");
  });

  it("honours the backend kill switch", () => {
    config = { ...liveConfig, whatsappWidgetEnabled: false };
    expect(renderToStaticMarkup(<WhatsAppWidget />)).toBe("");
  });

  it("renders nothing until the backend supplies a number", () => {
    // Never a hardcoded fallback number (PRD 7.1.2 anti-impersonation).
    config = null;
    expect(renderToStaticMarkup(<WhatsAppWidget />)).toBe("");
    config = { ...liveConfig, whatsappNumber: "" };
    expect(renderToStaticMarkup(<WhatsAppWidget />)).toBe("");
  });

  it("is fixed-position, so mounting it late shifts no layout", () => {
    // Zero CLS is an acceptance criterion, not an accident of styling.
    expect(renderToStaticMarkup(<WhatsAppWidget />)).toContain("fixed");
  });
});
