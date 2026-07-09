import { describe, it, expect } from "vitest";
import { ReportService } from "./report-service";
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
    delete: rec("delete"),
  } as unknown as HttpClient;
  return { http, calls };
}

describe("ReportService contract (mirrors /verifications/{id}/report)", () => {
  it("fetches the customer report", async () => {
    const { http, calls } = mockHttp();
    await new ReportService(http).getReport("ver-1");
    expect(calls[0]).toMatchObject({ method: "get", url: "/verifications/ver-1/report" });
  });

  it("records the access-gate acknowledgement", async () => {
    const { http, calls } = mockHttp();
    await new ReportService(http).acknowledge("ver-1");
    expect(calls[0]).toMatchObject({ method: "post", url: "/verifications/ver-1/report/acknowledge" });
  });

  it("builds the proxied PDF download URL", () => {
    const { http } = mockHttp();
    expect(new ReportService(http).pdfUrl("ver-1")).toBe("/api/verifications/ver-1/report/pdf");
  });
});
