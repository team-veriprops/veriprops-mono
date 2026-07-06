import { describe, it, expect } from "vitest";
import { AdminPayoutService } from "./admin-payout-service";
import { CommissionRuleService } from "./commission-rule-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { AgentRole } from "@/types/agent";
import { VerificationTier } from "@/types/verification";

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
});

describe("CommissionRuleService contract (mirrors app/domain/commission_rule/controller.py)", () => {
  it("lists rules", async () => {
    const { http, calls } = mockHttp();
    await new CommissionRuleService(http).listRules();
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/commission-rules" });
  });

  it("sets a rule by tier and role", async () => {
    const { http, calls } = mockHttp();
    await new CommissionRuleService(http).setRule(VerificationTier.BASIC, AgentRole.REGISTRY, { rateBps: 4000 });
    expect(calls[0]).toMatchObject({ method: "put", url: "/admin/commission-rules/BASIC/REGISTRY" });
    expect(calls[0].body).toMatchObject({ rateBps: 4000 });
  });
});
