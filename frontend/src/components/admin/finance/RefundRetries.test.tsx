import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Page, TransactionCurrency } from "@/types/models";
import {
  Payment,
  PaymentCheckoutKind,
  PaymentMethodKind,
  PaymentPurpose,
  PaymentStatus,
} from "@/types/verification";

const query: { data: Page<Payment> | undefined; isError: boolean } = { data: undefined, isError: false };

vi.mock("./libs/useFinanceQueries", () => ({
  useRefundRetriesQuery: () => query,
  useRetryRefundMutation: () => ({ mutate: vi.fn(), isPending: false }),
}));

import RefundRetries from "./RefundRetries";

function page(items: Payment[]): Page<Payment> {
  return {
    items,
    meta: { page: 0, pageSize: 10, count: items.length, total: items.length, totalPages: 1 },
  } as Page<Payment>;
}

const refused: Payment = {
  id: "pay-1",
  verificationId: "ver-1",
  txRef: "VP-2026-ABC123-x1y2",
  method: PaymentMethodKind.CARD,
  purpose: PaymentPurpose.INITIAL,
  status: PaymentStatus.SUCCEEDED,
  amountMinor: 12_000_000,
  currency: TransactionCurrency.NGN,
  chargeCurrency: TransactionCurrency.USD,
  chargeAmountMinor: 8_000,
  checkoutKind: PaymentCheckoutKind.HOSTED,
  dateCreated: "2026-09-27T12:00:00Z",
};

describe("RefundRetries", () => {
  it("lists each refused refund with what the customer paid and a retry control", () => {
    query.data = page([refused]);
    query.isError = false;
    const html = renderToStaticMarkup(<RefundRetries />);
    expect(html).toContain("Refunds to retry");
    expect(html).toContain("VP-2026-ABC123-x1y2");
    expect(html).toContain('data-testid="refund-retry-pay-1-submit"');
    // The charge currency the customer actually paid in, not the contractual NGN.
    expect(html).toContain("80");
    expect(html).not.toContain("120,000");
  });

  it("says nothing is waiting when the list is empty", () => {
    query.data = page([]);
    query.isError = false;
    expect(renderToStaticMarkup(<RefundRetries />)).toContain('data-testid="refund-retries-empty"');
  });

  it("renders nothing for an admin the backend refuses the list to", () => {
    query.data = undefined;
    query.isError = true;
    expect(renderToStaticMarkup(<RefundRetries />)).toBe("");
  });
});
