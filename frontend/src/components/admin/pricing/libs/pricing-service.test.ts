import { describe, it, expect } from "vitest";
import { PricingService } from "./pricing-service";
import { HttpClient } from "@lib/FetchHttpClient";
import { VerificationTier } from "@/types/verification";

function mockHttp() {
  const calls: { method: string; url: string; body?: unknown }[] = [];
  const rec = (method: string) => (url: string, body?: unknown) => {
    calls.push({ method, url, body });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = { get: (u: string) => rec("get")(u), post: rec("post"), put: rec("put"), patch: rec("patch"), delete: rec("delete") } as unknown as HttpClient;
  return { http, calls };
}

describe("PricingService contract (mirrors app/domain/verification/pricing_config/controller.py)", () => {
  it("gets pricing", async () => {
    const { http, calls } = mockHttp();
    await new PricingService(http).getPricing();
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/pricing" });
  });

  it("sets a tier price", async () => {
    const { http, calls } = mockHttp();
    await new PricingService(http).setTierPrice(VerificationTier.BASIC, 6_000_000);
    expect(calls[0]).toMatchObject({ method: "put", url: "/admin/pricing/tiers/BASIC", body: { priceNgnMinor: 6_000_000 } });
  });

  it("sets line items", async () => {
    const { http, calls } = mockHttp();
    await new PricingService(http).setLineItems(VerificationTier.STANDARD, [{ label: "Fee", amountMinor: 100 }]);
    expect(calls[0]).toMatchObject({ method: "put", url: "/admin/pricing/tiers/STANDARD/line-items" });
  });
});
