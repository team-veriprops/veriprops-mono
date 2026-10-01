import { describe, it, expect } from "vitest";
import { AdminPayoutService } from "./admin-payout-service";
import { CommissionRuleService } from "./commission-rule-service";
import { AdminPaymentService } from "./admin-payment-service";
import { RefundRequestService } from "./refund-request-service";
import { RefundRequestStatus } from "@/types/closure";
import { HttpClient } from "@lib/FetchHttpClient";
import { AgentRole } from "@/types/agent";
import { PaymentStatus } from "@/types/verification";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = {
    get: (url: string) => rec("get")(url),
    post: rec("post"),
    put: rec("put"),
    patch: rec("patch"),
    delete: (url: string) => rec("delete")(url),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("AdminPayoutService contract (mirrors app/domain/payout/controller.py finance routes)", () => {
  it("lists payouts filtered by status", async () => {
    const { http, calls } = mockHttp();
    await new AdminPayoutService(http).listPayouts(0, 10, "REQUESTED");
    expect(calls[0].url).toContain("/admin/payouts");
    expect(calls[0].url).toContain("status=REQUESTED");
  });

  it("posts finance decisions", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminPayoutService(http);
    await svc.approve("p-1");
    await svc.hold("p-1", { note: "verify" });
    await svc.reject("p-1", { note: "no" });
    await svc.adjust("p-1", { adjustmentMinor: -100 });
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/payouts/p-1/approve" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/payouts/p-1/hold" });
    expect(calls[2]).toMatchObject({ method: "post", url: "/admin/payouts/p-1/reject" });
    expect(calls[3]).toMatchObject({ method: "post", url: "/admin/payouts/p-1/adjust" });
  });

  it("retries a failed transfer", async () => {
    const { http, calls } = mockHttp();
    await new AdminPayoutService(http).retry("p-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/admin/payouts/p-1/retry" });
  });

  it("reads the disbursement queue and runs a batch", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminPayoutService(http);
    await svc.disbursementQueue();
    await svc.disburse();
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/payouts/disbursement-queue" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/payouts/disburse" });
  });
});

describe("CommissionRuleService contract (mirrors app/domain/commission_rule/controller.py)", () => {
  it("lists rules", async () => {
    const { http, calls } = mockHttp();
    await new CommissionRuleService(http).listRules();
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/commission-rules" });
  });

  it("sets a role's fixed commission — no tier in the path", async () => {
    const { http, calls } = mockHttp();
    await new CommissionRuleService(http).setRule(AgentRole.REGISTRY, { amountNgnKobo: 2_000_000 });
    expect(calls[0]).toMatchObject({ method: "put", url: "/admin/commission-rules/REGISTRY" });
    expect(calls[0].body).toMatchObject({ amountNgnKobo: 2_000_000 });
  });
});

describe("AdminPaymentService contract (mirrors admin_payment_router in app/domain/payment/controller.py)", () => {
  it("lists refunds a gateway refused, paged, and retries one", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminPaymentService(http);
    await svc.listRefundRetries(2, 20);
    await svc.retryRefund("pay-1");
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/payments/refund-retries?page=2&page_size=20" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/admin/payments/pay-1/refund" });
  });

  it("lists every payment, paged, forwarding the search and the status filter to the server", async () => {
    const { http, calls } = mockHttp();
    const svc = new AdminPaymentService(http);
    await svc.list(1, 10, { query: "VP 7&x", status: PaymentStatus.REFUNDED });
    await svc.list(0, 10);
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/payments?page=1&page_size=10&query=VP+7%26x&status=REFUNDED" });
    expect(calls[1]).toMatchObject({ method: "get", url: "/admin/payments?page=0&page_size=10" });
  });
});

describe("RefundRequestService contract (mirrors refund_request_router in app/domain/payment/refund_request/controller.py)", () => {
  it("pages the queue by status, and approves or rejects one request", async () => {
    const { http, calls } = mockHttp();
    const svc = new RefundRequestService(http);
    await svc.list(0, 10, RefundRequestStatus.PENDING);
    await svc.list(1, 10);
    await svc.approve("req-1", "checked");
    await svc.reject("req-1", "customer continued");
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/refund-requests?page=0&page_size=10&status=PENDING" });
    expect(calls[1]).toMatchObject({ method: "get", url: "/admin/refund-requests?page=1&page_size=10" });
    expect(calls[2]).toMatchObject({ method: "post", url: "/admin/refund-requests/req-1/approve", body: { note: "checked" } });
    expect(calls[3]).toMatchObject({ method: "post", url: "/admin/refund-requests/req-1/reject", body: { note: "customer continued" } });
  });
});
