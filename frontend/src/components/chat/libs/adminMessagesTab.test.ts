import { describe, expect, it } from "vitest";
import { AdminMessagesTab, parseAdminMessagesTab } from "./adminMessagesTab";

describe("parseAdminMessagesTab", () => {
  it("opens the tab a link names", () => {
    expect(parseAdminMessagesTab("conversations")).toBe(AdminMessagesTab.CONVERSATIONS);
    expect(parseAdminMessagesTab("review")).toBe(AdminMessagesTab.REVIEW);
  });

  it("falls back to the review queue for anything else", () => {
    // The retired `whatsapp` tab still appears in old notification links.
    expect(parseAdminMessagesTab("whatsapp")).toBe(AdminMessagesTab.REVIEW);
    expect(parseAdminMessagesTab(null)).toBe(AdminMessagesTab.REVIEW);
  });
});
