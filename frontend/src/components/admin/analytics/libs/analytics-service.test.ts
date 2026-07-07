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
