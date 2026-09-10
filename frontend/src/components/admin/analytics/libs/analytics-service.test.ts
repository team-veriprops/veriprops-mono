import { describe, it, expect } from "vitest";
import { AnalyticsService } from "./analytics-service";
import { HttpClient } from "@lib/FetchHttpClient";

function mockHttp() {
  const calls: { method: string; url: string }[] = [];
  const rec = (method: string) => (url: string) => {
    calls.push({ method, url });
    return Promise.resolve({ status: "success", code: "200", data: {} });
  };
  const http = { get: rec("get"), post: rec("post"), put: rec("put"), patch: rec("patch"), delete: rec("delete") } as unknown as HttpClient;
  return { http, calls };
}

describe("AnalyticsService contract (mirrors app/domain/analytics/controller.py)", () => {
  it("hits the five analytics endpoints", async () => {
    const { http, calls } = mockHttp();
    const svc = new AnalyticsService(http);
    await svc.getFunnel();
    await svc.getTimeByTier();
    await svc.getRevenue();
    await svc.getRegional();
    await svc.getAgentTrends();
    expect(calls.map((c) => c.url)).toEqual([
      "/admin/analytics/funnel",
      "/admin/analytics/time-by-tier",
      "/admin/analytics/revenue",
      "/admin/analytics/regional",
      "/admin/analytics/agent-trends",
    ]);
    expect(calls.every((c) => c.method === "get")).toBe(true);
  });
});

describe("WhatsApp channel analytics (§26.10, WA-43)", () => {
  it("reads the channel panel, letting the backend pick the window by default", async () => {
    // No `?days=` — the backend owns the default so the window is the same everywhere it
    // is quoted, rather than the frontend guessing one.
    const { http, calls } = mockHttp();
    await new AnalyticsService(http).getWhatsAppChannel();
    expect(calls).toEqual([{ method: "get", url: "/admin/analytics/whatsapp" }]);
  });

  it("passes an explicit window through", async () => {
    const { http, calls } = mockHttp();
    await new AnalyticsService(http).getWhatsAppChannel(7);
    expect(calls[0].url).toBe("/admin/analytics/whatsapp?days=7");
  });

  it("syncs the Meta quality rating over POST", async () => {
    const { http, calls } = mockHttp();
    await new AnalyticsService(http).syncWhatsAppQuality();
    expect(calls).toEqual([
      { method: "post", url: "/admin/analytics/whatsapp/quality/sync" },
    ]);
  });
});
