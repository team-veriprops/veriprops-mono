import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { ChannelMode, type NotificationPreference } from "@/types/notification";

const query: { data: NotificationPreference[]; isLoading: boolean; isError: boolean; error: unknown } = {
  data: [], isLoading: false, isError: false, error: null,
};
vi.mock("./libs/useNotificationQueries", () => ({
  useNotificationPreferencesQuery: () => query,
  useSetPreferenceMutation: () => ({ mutate: vi.fn() }),
}));

import NotificationPreferences from "./NotificationPreferences";

const pref = (over: Partial<NotificationPreference>): NotificationPreference => ({
  eventType: "PAYMENT_CONFIRMED", label: "Payment confirmed", description: "When your payment is received.",
  emailMode: ChannelMode.OPTIONAL, smsMode: ChannelMode.OPTIONAL, emailEnabled: true, smsEnabled: false,
  ...over,
});

describe("NotificationPreferences", () => {
  it("renders exactly the events and copy the backend sends", () => {
    query.data = [pref({}), pref({ eventType: "NEW_JOB", label: "New jobs", description: "When a task is available for you." })];
    const html = renderToStaticMarkup(<NotificationPreferences />);
    expect(html).toContain("Payment confirmed");
    expect(html).toContain("New jobs");
    expect(html.match(/type="checkbox"/g)).toHaveLength(4);
  });

  it("offers a toggle only for an optional channel, a lock for a required one, and nothing for an unused one", () => {
    query.data = [pref({ label: "Report ready", emailMode: ChannelMode.REQUIRED, smsMode: ChannelMode.OPTIONAL })];
    let html = renderToStaticMarkup(<NotificationPreferences />);
    expect(html.match(/type="checkbox"/g)).toHaveLength(1);
    expect(html).toContain('aria-label="Report ready email: always sent"');

    query.data = [pref({ label: "Status updates", smsMode: ChannelMode.UNUSED })];
    html = renderToStaticMarkup(<NotificationPreferences />);
    expect(html.match(/type="checkbox"/g)).toHaveLength(1);
    expect(html).toContain('aria-label="Status updates SMS: not used"');
  });

  it("says so when there is nothing to change", () => {
    query.data = [];
    expect(renderToStaticMarkup(<NotificationPreferences />)).toMatch(/no email or SMS notifications to change/);
  });
});
