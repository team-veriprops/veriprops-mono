import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { TransactionCurrency } from "@/types/models";
import { AdminPayout, PayoutAction, PayoutStatus } from "@/types/payout";

vi.mock("./libs/useFinanceQueries", () => ({
  usePayoutDecisionMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

import PayoutDecisionPanel from "./PayoutDecisionPanel";

function payout(over: Partial<AdminPayout> = {}): AdminPayout {
  return {
    id: "p-1", agentId: "a-1", amountMinor: 5_000_000, feeMinor: 2_500, netMinor: 4_997_500,
    currency: TransactionCurrency.NGN, status: PayoutStatus.REQUESTED, bankName: "Guaranty Trust Bank",
    accountNumber: "0123456789", accountName: "ADA OBI", adjustmentMinor: 0, dateCreated: "2026-09-28T09:00:00Z",
    allowedActions: [PayoutAction.APPROVE, PayoutAction.HOLD, PayoutAction.ADJUST, PayoutAction.REJECT],
    transferAttempts: 0, ...over,
  };
}

const render = (p: AdminPayout) => renderToStaticMarkup(<PayoutDecisionPanel payout={p} onDone={() => {}} />);

describe("PayoutDecisionPanel", () => {
  it("offers exactly the moves the backend allows", () => {
    const html = render(payout());
    for (const id of ["approve", "hold", "adjust", "reject"]) expect(html).toContain(`data-testid="payout-${id}"`);
    expect(html).not.toContain('data-testid="payout-retry"');
  });

  it("lets finance retry or reject a failed transfer, and shows why it failed", () => {
    const html = render(payout({
      status: PayoutStatus.FAILED, allowedActions: [PayoutAction.RETRY, PayoutAction.ADJUST, PayoutAction.REJECT],
      transferReference: "vp-po-abc-1", transferAttempts: 1, failureReason: "Insufficient balance",
    }));
    expect(html).toContain('data-testid="payout-retry"');
    expect(html).not.toContain('data-testid="payout-approve"');
    expect(html).toContain("Insufficient balance");
    expect(html).toContain("vp-po-abc-1");
  });

  it("offers nothing while the transfer is with the bank", () => {
    const html = render(payout({ status: PayoutStatus.PROCESSING, allowedActions: [], transferReference: "vp-po-abc-1" }));
    expect(html).toContain('data-testid="payout-no-actions"');
    expect(html).not.toContain("<button");
  });

  it("breaks the amount down into request, fee and what reaches the bank", () => {
    const html = render(payout());
    expect(html).toContain("49,975");
    expect(html).toContain('data-testid="payout-breakdown"');
  });
});
