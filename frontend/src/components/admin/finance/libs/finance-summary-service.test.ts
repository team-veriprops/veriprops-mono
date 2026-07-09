import { describe, it, expect } from "vitest";
import { FinanceSummaryService } from "./finance-summary-service";
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

describe("FinanceSummaryService contract (mirrors app/domain/finance/controller.py)", () => {
  it("gets the finance summary", async () => {
    const { http, calls } = mockHttp();
    await new FinanceSummaryService(http).getSummary();
    expect(calls[0]).toMatchObject({ method: "get", url: "/admin/finance/summary" });
  });
});
