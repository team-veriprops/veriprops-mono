import { describe, it, expect } from "vitest";

import { AgentRole } from "@/types/agent";
import { TaskState } from "@/types/adminVerification";
import { CloseReason, ClosureQuote } from "@/types/closure";
import { VerificationStatus } from "@/types/verification";

import { TransactionCurrency } from "@/types/models";

import { CLOSE_REASONS, closeOutcomeMessage, closureConfirmation, majorToMinor } from "./closure";

const quote = (over: Partial<ClosureQuote> = {}): ClosureQuote => ({
  reason: CloseReason.CUSTOMER_WITHDREW,
  currency: TransactionCurrency.NGN,
  refundableMinor: 1_500_000,
  refundMinor: 1_200_000,
  resultingStatus: VerificationStatus.CANCELLED,
  requiresApproval: true,
  agents: [
    { taskId: "t1", role: AgentRole.FIELD, agentId: "a1", state: TaskState.SUBMITTED, paid: true },
    { taskId: "t2", role: AgentRole.REGISTRY, agentId: "a2", state: TaskState.IN_PROGRESS, paid: false },
  ],
  ...over,
});

describe("CLOSE_REASONS", () => {
  it("names every reason the backend accepts", () => {
    expect(CLOSE_REASONS.map((r) => r.value).sort()).toEqual(Object.values(CloseReason).sort());
  });
});

describe("closureConfirmation", () => {
  it("states the refund, that Finance approves it, the hold, and what happens to each agent", () => {
    const copy = closureConfirmation(quote());
    expect(copy.description).toContain("₦12,000");
    expect(copy.description).toMatch(/Finance/);
    expect(copy.description).toMatch(/on hold/);
    expect(copy.description).toMatch(/1 agent .* paid/);
    expect(copy.description).toMatch(/1 unfinished task .* cancelled/);
    expect(copy.description).toMatch(/cannot be undone/);
    expect(copy.confirmLabel).toContain("₦12,000");
  });

  it("says plainly when nothing is refunded and the case ends now", () => {
    const copy = closureConfirmation(quote({ refundMinor: 0, requiresApproval: false, reason: CloseReason.FRAUD }));
    expect(copy.description).toMatch(/Nothing is refunded/);
    expect(copy.description).toMatch(/ends now as cancelled/i);
    expect(copy.confirmLabel).toBe("Close case now");
  });

  it("names a failed ending when we cannot deliver", () => {
    const copy = closureConfirmation(quote({ reason: CloseReason.CANNOT_DELIVER, resultingStatus: VerificationStatus.FAILED }));
    expect(copy.description).toMatch(/failed/i);
  });
});

describe("closeOutcomeMessage", () => {
  it("tells the admin the refund is waiting for Finance", () => {
    expect(closeOutcomeMessage({ status: VerificationStatus.PAID, onHold: true, refundMinor: 1_200_000, currency: TransactionCurrency.NGN }))
      .toMatch(/on hold.*₦12,000.*Finance/);
  });

  it("tells the admin the case closed with nothing refunded", () => {
    expect(closeOutcomeMessage({ status: VerificationStatus.CANCELLED, onHold: false, refundMinor: 0, currency: TransactionCurrency.NGN }))
      .toMatch(/closed.*Nothing was refunded/);
  });
});

describe("majorToMinor", () => {
  it.each([
    ["5000", 500_000],
    ["5,000.50", 500_050],
    ["0", 0],
  ])("reads %s as %i kobo", (text, minor) => {
    expect(majorToMinor(text)).toBe(minor);
  });

  it.each(["", "abc", "-1", "1.234"])("refuses %s", (text) => {
    expect(majorToMinor(text)).toBeUndefined();
  });
});
