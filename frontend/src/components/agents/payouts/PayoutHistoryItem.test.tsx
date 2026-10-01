import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { TransactionCurrency } from "@/types/models";
import { Payout, PayoutAction, PayoutStatus } from "@/types/payout";
import { PayoutHistoryItem } from "./PayoutHistoryItem";

function payout(over: Partial<Payout> = {}): Payout {
  return {
    id: "p-1", agentId: "a-1", amountMinor: 5_000_000, feeMinor: 2_500, netMinor: 4_997_500,
    currency: TransactionCurrency.NGN, status: PayoutStatus.REQUESTED, bankName: "Guaranty Trust Bank",
    accountNumber: "0123456789", accountName: "ADA OBI", adjustmentMinor: 0,
    dateCreated: "2026-09-28T09:00:00Z", allowedActions: [PayoutAction.CANCEL], ...over,
  };
}

const render = (p: Payout) => renderToStaticMarkup(<ul><PayoutHistoryItem payout={p} onCancel={() => {}} /></ul>);

describe("PayoutHistoryItem", () => {
  it("leads with what reaches the bank and shows the fee taken from it", () => {
    const html = render(payout());
    expect(html).toContain("49,975");
    expect(html).toContain("50,000");
    expect(html).toContain("25");
  });

  it("offers cancel only when the backend allows it", () => {
    expect(render(payout())).toContain('data-testid="payout-p-1-cancel"');
    expect(render(payout({ status: PayoutStatus.APPROVED, allowedActions: [] })))
      .not.toContain('data-testid="payout-p-1-cancel"');
  });

  it("tells the agent a failed transfer is with finance, not lost", () => {
    const html = render(payout({ status: PayoutStatus.FAILED, allowedActions: [] }));
    expect(html).toContain('data-testid="payout-p-1-note"');
    expect(html).toContain("finance team");
  });
});
