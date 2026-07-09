import { describe, it, expect } from "vitest";
import { EarningsService } from "./earnings-service";
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

describe("EarningsService contract (mirrors app/domain/earnings/controller.py)", () => {
  it("gets the earnings summary", async () => {
    const { http, calls } = mockHttp();
    await new EarningsService(http).getSummary();
    expect(calls[0]).toMatchObject({ method: "get", url: "/agents/earnings" });
  });

  it("lists paged earning jobs with snake_case params", async () => {
    const { http, calls } = mockHttp();
    await new EarningsService(http).listJobs(1, 20);
    expect(calls[0].method).toBe("get");
    expect(calls[0].url).toContain("/agents/earnings/jobs");
    expect(calls[0].url).toContain("page=1");
    expect(calls[0].url).toContain("page_size=20");
  });
});
