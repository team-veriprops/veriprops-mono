import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { TransactionCurrency } from "@/types/models";
import {
  AdminPayment,
  PaymentCheckoutKind,
  PaymentMethodKind,
  PaymentPurpose,
  PaymentStatus,
} from "@/types/verification";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  usePathname: () => "/admin/finance/payments",
  useSearchParams: () => new URLSearchParams(),
}));

const queryCalls: unknown[][] = [];
const result: { data: unknown; isLoading: boolean; isError: boolean; error: null } = {
  data: null, isLoading: false, isError: false, error: null,
};
vi.mock("./libs/useFinanceQueries", () => ({
  useAdminPaymentsQuery: (...args: unknown[]) => {
    queryCalls.push(args);
    return result;
  },
}));
vi.mock("@hooks/useSyncedQueryState", () => ({
  useSyncedQueryState: () => [{ page: 2, query: "VP-7", status: PaymentStatus.REFUNDED }, () => {}],
}));

import AdminPayments, { paymentAftermath } from "./AdminPayments";

const payment: AdminPayment = {
  id: "p1",
  verificationId: "v1",
  vid: "VP-2026-ABC",
  customerId: "c1",
  txRef: "VP-2026-ABC-x1",
  method: PaymentMethodKind.CARD,
  purpose: PaymentPurpose.INITIAL,
  status: PaymentStatus.REFUNDED,
  amountMinor: 1_500_000,
  currency: TransactionCurrency.NGN,
  checkoutKind: PaymentCheckoutKind.HOSTED,
  provider: "flutterwave",
  refundedAmountMinor: 1_500_000,
  dateCreated: "2026-09-29T10:00:00Z",
};

describe("AdminPayments", () => {
  it("asks the server for the page, search and status in the URL — never filters rows itself", () => {
    result.data = { status: "success", code: "200", items: [payment], meta: { page: 2, pageSize: 10, count: 1, total: 21, totalPages: 3 } };
    renderToStaticMarkup(<AdminPayments />);
    expect(queryCalls.at(-1)).toEqual([2, { query: "VP-7", status: PaymentStatus.REFUNDED }]);
  });

  it("lists each charge with its case, linked to the admin verification", () => {
    const html = renderToStaticMarkup(<AdminPayments />);
    expect(html).toContain("VP-2026-ABC-x1");
    expect(html).toContain('href="/admin/verifications/v1"');
    expect(html).toContain("Flutterwave");
  });
});

describe("paymentAftermath", () => {
  it("names a chargeback before a refund, because the issuer is returning that money", () => {
    expect(paymentAftermath({ ...payment, chargebackStatus: "FLAGGED" })).toBe("Chargeback: Flagged");
  });

  it("states a refund's amount", () => {
    expect(paymentAftermath(payment)).toMatch(/^Refunded /);
  });

  it("names an approved refund the gateway refused, which Finance retries", () => {
    expect(paymentAftermath({ ...payment, refundedAmountMinor: null, refundDueMinor: 1_500_000 })).toMatch(/^Refund owed: .* retry from Finance$/);
  });

  it("is a dash for a charge that simply settled", () => {
    expect(paymentAftermath({ ...payment, refundedAmountMinor: null })).toBe("—");
  });
});
