import { describe, it, expect, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import { TransactionCurrency } from "@/types/models";
import { RefundRequest, RefundRequestStatus, RefundSource } from "@/types/closure";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: () => {}, replace: () => {} }),
  usePathname: () => "/admin/finance/refunds",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("sonner", () => ({ toast: { success: vi.fn(), warning: vi.fn(), error: vi.fn() } }));

const queryCalls: unknown[][] = [];
const result: { data: unknown; isLoading: boolean; isError: boolean; error: null } = {
  data: null, isLoading: false, isError: false, error: null,
};
const noopMutation = { mutateAsync: vi.fn(), mutate: vi.fn(), isPending: false };
vi.mock("./libs/useFinanceQueries", () => ({
  useRefundRequestsQuery: (...args: unknown[]) => {
    queryCalls.push(args);
    return result;
  },
  useApproveRefundMutation: () => noopMutation,
  useRejectRefundMutation: () => noopMutation,
}));
vi.mock("@hooks/useSyncedQueryState", () => ({
  useSyncedQueryState: () => [{ page: 0, status: RefundRequestStatus.PENDING }, () => {}],
}));

import RefundApprovals, { refundReasonLabel } from "./RefundApprovals";

const request: RefundRequest = {
  id: "req-1", verificationId: "v1", vid: "VP-2026-ABC", customerId: "c1",
  source: RefundSource.CASE_CLOSURE, status: RefundRequestStatus.PENDING, amountMinor: 1_200_000,
  currency: TransactionCurrency.NGN, reason: "CUSTOMER_WITHDREW", note: "Customer withdrew", dateCreated: "2026-09-30T10:00:00Z",
};

describe("RefundApprovals", () => {
  it("opens on the pending queue, read from the server", () => {
    result.data = { status: "success", code: "200", items: [request], meta: { page: 0, pageSize: 10, count: 1, total: 1, totalPages: 1 } };
    const html = renderToStaticMarkup(<RefundApprovals />);
    expect(queryCalls.at(-1)).toEqual([0, RefundRequestStatus.PENDING]);
    expect(html).toContain("VP-2026-ABC");
    expect(html).toContain('href="/admin/verifications/v1"');
  });
});

describe("refundReasonLabel", () => {
  it("names the close reason behind a closed case's refund", () => {
    expect(refundReasonLabel(request)).toBe("Case closed: customer withdrew");
  });

  it("names the source when there is no close reason", () => {
    expect(refundReasonLabel({ ...request, source: RefundSource.LATE_CHARGE, reason: "LATE_CHARGE" }))
      .toBe("Charge after the case closed");
  });
});
