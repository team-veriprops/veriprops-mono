import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { WhatsAppChannelAnalytics as ChannelAnalytics } from "@/types/analytics";

const { query, syncSpy } = vi.hoisted(() => ({
  query: { current: { data: null as unknown, isLoading: false, isError: false } },
  syncSpy: vi.fn(),
}));

vi.mock("./libs/useAnalyticsQueries", () => ({
  useWhatsAppChannelAnalyticsQuery: () => query.current,
  useSyncWhatsAppQualityMutation: () => ({ mutate: syncSpy, isPending: false }),
}));

import WhatsAppChannelAnalytics from "./WhatsAppChannelAnalytics";

function analytics(over: Partial<ChannelAnalytics> = {}): ChannelAnalytics {
  return {
    windowDays: 30,
    intakeCompleted: 0,
    paymentCompleted: 0,
    seamConversionRate: 0,
    enquiries: 0,
    enquiriesByPageCode: [],
    intakeStarted: 0,
    enquiryToIntakeRate: 0,
    escalations: 0,
    escalationRate: 0,
    escalationsByReason: [],
    linkedNumbers: 0,
    utilityOptIns: 0,
    marketingOptIns: 0,
    utilityOptInRate: 0,
    marketingOptInRate: 0,
    voiceNotes: 0,
    ...over,
  };
}

function render(data: ChannelAnalytics, overrides = {}) {
  query.current = { data, isLoading: false, isError: false, ...overrides };
  return renderToStaticMarkup(<WhatsAppChannelAnalytics />);
}

describe("WhatsAppChannelAnalytics (§7.10, WA-43)", () => {
  it("names the window every figure covers", () => {
    // Four of the seven metrics are rates, and a rate whose period is not stated invites
    // the reader to assume it is all-time.
    const html = render(analytics({ windowDays: 7 }));
    expect(html).toContain("Trailing 7 days");
  });

  it("shows the counts behind the seam conversion rate", () => {
    // §7.10's headline. 60% over three intakes and 60% over three hundred call for
    // opposite decisions, so the percentage alone is not a usable figure.
    const html = render(
      analytics({ intakeCompleted: 10, paymentCompleted: 6, seamConversionRate: 0.6 }),
    );
    expect(html).toContain("60%");
    expect(html).toContain("6 paid of 10 completed intakes");
  });

  it("breaks enquiries down by the widget page code they arrived through", () => {
    const html = render(
      analytics({
        enquiries: 5,
        enquiriesByPageCode: [
          { label: "web-pricing", count: 3 },
          { label: "direct", count: 2 },
        ],
      }),
    );
    // The hyphenated code survives humanization, which is what an admin needs: page
    // codes are identifiers to match against `lib/whatsapp.ts`, not status labels.
    expect(html).toContain("Web-pricing");
    expect(html).toContain("Direct");
  });

  it("names why conversations reached a person", () => {
    // The half of §7.10's escalation metric that says what to build next.
    const html = render(
      analytics({
        escalations: 4,
        escalationRate: 0.4,
        escalationsByReason: [{ label: "GUARDRAIL_TOPIC", count: 4 }],
      }),
    );
    expect(html).toContain("Guardrail Topic");
    expect(html).toContain("40% of enquiries");
  });

  it("states the opt-in denominator rather than only the percentage", () => {
    // D84 — the rate is over numbers the channel can actually reach, and an admin has to
    // be able to see that is what it means.
    const html = render(
      analytics({ linkedNumbers: 8, utilityOptIns: 6, utilityOptInRate: 0.75 }),
    );
    expect(html).toContain("75%");
    expect(html).toContain("6 of 8 opted in");
  });

  it("does not present a never-synced quality rating as healthy", () => {
    // §7.11 treats the rating as a launch gate, so the absence of Meta's verdict must not
    // read as a clean bill of health.
    const html = render(analytics({ numberHealth: undefined }));
    expect(html).toContain("Never synced");
    expect(html).toContain("Not yet read from Meta");
  });

  it("warns when the rating on screen could not be refreshed", () => {
    const html = render(
      analytics({
        numberHealth: {
          qualityRating: "GREEN",
          syncedAt: "2026-08-01T00:00:00Z",
          syncError: "timeout",
        },
      }),
    );
    expect(html).toContain("Last sync failed");
  });

  it("offers a re-check control for the quality rating", () => {
    const html = render(analytics());
    expect(html).toContain('data-testid="whatsapp-quality-sync"');
  });
});
