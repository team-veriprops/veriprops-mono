import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { FinanceSummary } from "@/types/finance";

const result: { data: FinanceSummary | null; isLoading: boolean; isError: boolean } = {
  data: null,
  isLoading: false,
  isError: false,
};

vi.mock("./libs/useFinanceSummaryQuery", () => ({
  useFinanceSummaryQuery: () => result,
}));

import AdminFinance from "./AdminFinance";

describe("AdminFinance", () => {
  it("renders the hero revenue, a pending-payout attention chip, and humanized status bars", () => {
    result.data = {
      revenueMinor: 241290000,
      paymentsByStatus: { PAID: 120, PAYMENT_PENDING: 8 },
      commissionsByStatus: { CLEARED: 88 },
      payoutsByStatus: { PAID: 40, REQUESTED: 3 },
      pendingPayouts: 3,
    };
    const html = renderToStaticMarkup(<AdminFinance />);
    expect(html).toContain("Collected revenue");
    expect(html).toContain("3 payouts pending");
    // Status keys are humanized via StatusPill — never rendered raw.
    expect(html).toContain("Payment Pending");
    expect(html).toContain("Paid");
    expect(html).not.toContain("PAYMENT_PENDING");
    expect(html).not.toContain(">PAID<");
  });
});
