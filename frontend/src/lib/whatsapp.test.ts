import { describe, it, expect } from "vitest";
import { ROUTES } from "./routes";
import { WHATSAPP_PREFILL_GREETING, isPaymentFlowPath, pageCodeFor, waMeUrl } from "./whatsapp";

describe("pageCodeFor", () => {
  it("names the landing page explicitly", () => {
    expect(pageCodeFor("/")).toBe("web-home");
  });

  it("uses the PRD's own code for the sample report", () => {
    expect(pageCodeFor(ROUTES.SAMPLE_REPORT)).toBe("web-report-sample");
  });

  it("distinguishes intake from the rest of the portal", () => {
    // Enquiry -> intake-started is a tracked funnel step (PRD 7.10).
    expect(pageCodeFor(ROUTES.PORTAL.VERIFICATIONS_NEW)).toBe("web-intake");
    expect(pageCodeFor(ROUTES.PORTAL.DASHBOARD)).toBe("web-portal");
  });

  it("derives a code from the first segment for pages without an explicit entry", () => {
    // New pages stay attributable without editing the table.
    expect(pageCodeFor(ROUTES.ABOUT)).toBe("web-about");
    expect(pageCodeFor(ROUTES.LEGAL.PRIVACY)).toBe("web-legal");
    expect(pageCodeFor(ROUTES.PUBLIC.VERIFY("VP-1042"))).toBe("web-verify");
    expect(pageCodeFor(ROUTES.AGENT.DASHBOARD)).toBe("web-agents");
  });

  it("ignores query strings, hashes, and trailing slashes", () => {
    expect(pageCodeFor("/about/")).toBe("web-about");
    expect(pageCodeFor("/about?utm_source=x")).toBe("web-about");
    expect(pageCodeFor("/about#team")).toBe("web-about");
    expect(pageCodeFor("")).toBe("web-home");
  });

  it("never emits characters that would break the ref token", () => {
    // The code round-trips through WhatsApp message text and back out of the bot's
    // parser, so keep it to lowercase, digits, and dashes.
    const codes = [
      pageCodeFor("/Odd_Segment/x"),
      pageCodeFor("/%20spaces%20"),
      pageCodeFor("/UPPER"),
    ];
    for (const code of codes) expect(code).toMatch(/^web-[a-z0-9-]+$/);
  });
});

describe("waMeUrl", () => {
  it("builds a wa.me deep link carrying the page code", () => {
    const url = new URL(waMeUrl("2349167624347", "web-home"));
    expect(url.origin + url.pathname).toBe("https://wa.me/2349167624347");
    expect(url.searchParams.get("text")).toBe(`${WHATSAPP_PREFILL_GREETING} [ref: web-home]`);
  });

  it("percent-encodes the prefill so the brackets survive the hop", () => {
    expect(waMeUrl("2349167624347", "web-home")).toContain("%5Bref%3A%20web-home%5D");
  });

  it("yields an empty string without a number, so callers render nothing", () => {
    // /config/public is the only source of the number; before it resolves there is
    // no link to render (PRD 7.1.2 - never a hardcoded fallback number).
    expect(waMeUrl("", "web-home")).toBe("");
  });
});

describe("isPaymentFlowPath", () => {
  it("suppresses the widget inside the portal payment step", () => {
    // PRD 7.4.1: no distraction at the highest-value moment.
    expect(isPaymentFlowPath(ROUTES.PORTAL.VERIFICATION_PAY("abc123"))).toBe(true);
  });

  it("suppresses the widget on the WhatsApp payment handoff landing", () => {
    expect(isPaymentFlowPath(ROUTES.WA.PAY("token123"))).toBe(true);
  });

  it("leaves the rest of the verification surface alone", () => {
    expect(isPaymentFlowPath(ROUTES.PORTAL.VERIFICATION_DETAIL("abc123"))).toBe(false);
    expect(isPaymentFlowPath(ROUTES.PORTAL.VERIFICATION_CONFIRMED("abc123"))).toBe(false);
    expect(isPaymentFlowPath(ROUTES.HOME)).toBe(false);
    expect(isPaymentFlowPath(ROUTES.WA.REPORT("token123"))).toBe(false);
  });
});
