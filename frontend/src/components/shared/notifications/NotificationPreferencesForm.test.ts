import { describe, it, expect } from "vitest";
import { getEventsForPersona, ALL_EVENTS } from "./NotificationPreferencesForm";

describe("getEventsForPersona", () => {
  it("returns all events when no persona is given", () => {
    expect(getEventsForPersona()).toEqual(ALL_EVENTS);
    expect(getEventsForPersona(undefined)).toEqual(ALL_EVENTS);
  });

  describe("customer persona", () => {
    const events = getEventsForPersona("customer");

    it("includes customer-specific events", () => {
      const keys = events.map((e) => e.key);
      expect(keys).toContain("STATUS_CHANGE");
      expect(keys).toContain("PAYMENT_CONFIRMED");
      expect(keys).toContain("AGENTS_ASSIGNED");
      expect(keys).toContain("REPORT_READY");
      expect(keys).toContain("RECHECK_DECISION");
      expect(keys).toContain("DISPUTE_RESOLVED");
    });

    it("includes NEW_MESSAGE (shared with agents)", () => {
      expect(events.map((e) => e.key)).toContain("NEW_MESSAGE");
    });

    it("excludes agent-only events", () => {
      const keys = events.map((e) => e.key);
      expect(keys).not.toContain("JOB_ALERT");
      expect(keys).not.toContain("REVISION_REQUEST");
      expect(keys).not.toContain("PAYOUT_APPROVED");
      expect(keys).not.toContain("PAYOUT_HELD");
    });

    it("excludes admin-only events", () => {
      const keys = events.map((e) => e.key);
      expect(keys).not.toContain("SLA_BREACH");
      expect(keys).not.toContain("DISPUTE_FILED");
    });
  });

  describe("agent persona", () => {
    const events = getEventsForPersona("agent");

    it("includes agent-specific events", () => {
      const keys = events.map((e) => e.key);
      expect(keys).toContain("JOB_ALERT");
      expect(keys).toContain("REVISION_REQUEST");
      expect(keys).toContain("PAYOUT_APPROVED");
      expect(keys).toContain("PAYOUT_HELD");
    });

    it("includes NEW_MESSAGE (shared with customers)", () => {
      expect(events.map((e) => e.key)).toContain("NEW_MESSAGE");
    });

    it("excludes customer-only events", () => {
      const keys = events.map((e) => e.key);
      expect(keys).not.toContain("STATUS_CHANGE");
      expect(keys).not.toContain("PAYMENT_CONFIRMED");
      expect(keys).not.toContain("AGENTS_ASSIGNED");
      expect(keys).not.toContain("REPORT_READY");
      expect(keys).not.toContain("RECHECK_DECISION");
      expect(keys).not.toContain("DISPUTE_RESOLVED");
    });

    it("excludes admin-only events", () => {
      const keys = events.map((e) => e.key);
      expect(keys).not.toContain("SLA_BREACH");
      expect(keys).not.toContain("DISPUTE_FILED");
    });
  });

  it("admin-only events (SLA_BREACH, DISPUTE_FILED) appear only in unfiltered list", () => {
    const all = getEventsForPersona();
    const adminKeys = ["SLA_BREACH", "DISPUTE_FILED"];
    for (const k of adminKeys) {
      expect(all.map((e) => e.key)).toContain(k);
    }
  });
});
