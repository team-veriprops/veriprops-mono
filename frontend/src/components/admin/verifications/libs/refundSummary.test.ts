import { describe, it, expect } from "vitest";

import { refundSummary } from "./refundSummary";

describe("refundSummary", () => {
  it("says refunded only when the gateway took the refund", () => {
    expect(refundSummary("Verification failed", { refundedMinor: 1_500_000, failedPaymentIds: [], heldPaymentIds: [] }))
      .toEqual({ ok: true, message: "Verification failed & refunded" });
  });

  it("says so when a gateway refused the refund, and where it waits", () => {
    const summary = refundSummary("Verification cancelled", { refundedMinor: 0, failedPaymentIds: ["p1"], heldPaymentIds: [] });
    expect(summary.ok).toBe(false);
    expect(summary.message).toMatch(/^Verification cancelled, but the gateway refused the refund/);
    expect(summary.message).toMatch(/Finance/);
  });

  it("says a refund was held back for a chargeback, which returns the money instead", () => {
    const summary = refundSummary("Verification failed", { refundedMinor: 0, failedPaymentIds: [], heldPaymentIds: ["p1"] });
    expect(summary.ok).toBe(false);
    expect(summary.message).toMatch(/chargeback/);
  });

  it("claims no refund when there was nothing to refund", () => {
    expect(refundSummary("Verification cancelled", null)).toEqual({ ok: true, message: "Verification cancelled" });
  });
});
