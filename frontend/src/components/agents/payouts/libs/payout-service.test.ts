import { describe, it, expect } from "vitest";
import { PayoutService } from "./payout-service";
import { HttpClient } from "@lib/FetchHttpClient";

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

describe("PayoutService contract (mirrors app/domain/payout/controller.py)", () => {
  it("lists payouts with pagination params", async () => {
    const { http, calls } = mockHttp();
    await new PayoutService(http).listPayouts(2, 5);
    expect(calls[0].url).toContain("/agents/payouts");
    expect(calls[0].url).toContain("page=2");
    expect(calls[0].url).toContain("page_size=5");
  });

  it("requests a withdrawal", async () => {
    const { http, calls } = mockHttp();
    await new PayoutService(http).requestPayout({ amountMinor: 50000, bankAccountId: "b-1" });
    expect(calls[0]).toMatchObject({ method: "post", url: "/agents/payouts" });
    expect(calls[0].body).toMatchObject({ amountMinor: 50000 });
  });

  it("cancels a payout", async () => {
    const { http, calls } = mockHttp();
    await new PayoutService(http).cancelPayout("p-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/agents/payouts/p-1/cancel" });
  });

  it("manages bank accounts", async () => {
    const { http, calls } = mockHttp();
    const svc = new PayoutService(http);
    await svc.listBankAccounts();
    await svc.addBankAccount({ bankName: "GT", accountNumber: "1", accountName: "A" });
    await svc.removeBankAccount("b-1");
    expect(calls[0]).toMatchObject({ method: "get", url: "/agents/payouts/bank-accounts" });
    expect(calls[1]).toMatchObject({ method: "post", url: "/agents/payouts/bank-accounts" });
    expect(calls[2]).toMatchObject({ method: "delete", url: "/agents/payouts/bank-accounts/b-1" });
  });
});
